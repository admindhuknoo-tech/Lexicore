"""LexiCore Full-document Legal AI Reasoning Layer (Python).

Uses Gemini REST directly via Python stdlib when GEMINI_API_KEY is configured.
No extra Python package is required. If AI is unavailable or a call fails, callers
should retain the deterministic Deep Case Analysis fallback.
"""
from __future__ import annotations
import json, os, re, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Iterable

class FullDocumentFailure(RuntimeError):
    def __init__(self, message: str, diagnostics: Dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

from version import LEXICORE_VERSION
from services.case_domain_classifier import FEW_SHOT_BOUNDARY
from urllib import request as urlrequest, error as urlerror

def provider_config() -> Dict[str, str]:
    """Resolve provider/model at call time, not import time.

    This prevents stale .env/test state and makes runtime diagnostics truthful.
    """
    provider = os.environ.get('LEXICORE_AI_PROVIDER', 'local').strip().lower() or 'local'
    model_env = os.environ.get('LEXICORE_AI_MODEL', '').strip()
    if provider == 'gemini':
        model = model_env or 'gemini-3.6-flash'
    else:
        provider = 'local' if provider not in ('gemini',) else provider
        model = 'local-deterministic'
    return {'provider': provider, 'model': model}

# Compatibility aliases only. Core execution resolves provider_config() dynamically.
PROVIDER = provider_config()['provider']
MODEL = provider_config()['model']
CHUNK_SIZE = max(4000, int(os.environ.get('LEXICORE_AI_CHUNK_SIZE', '10000')))
CHUNK_OVERLAP = max(0, min(2000, int(os.environ.get('LEXICORE_AI_CHUNK_OVERLAP', '700'))))
MAX_CHUNKS = max(1, min(40, int(os.environ.get('LEXICORE_AI_MAX_CHUNKS', '24'))))
CONCURRENCY = max(1, min(4, int(os.environ.get('LEXICORE_AI_CONCURRENCY', '2'))))
TIMEOUT = max(8, min(90, int(os.environ.get('LEXICORE_AI_TIMEOUT_SECONDS', '35'))))
AI_RETRIES = max(0, min(3, int(os.environ.get('LEXICORE_AI_RETRIES', '2'))))
MAX_INPUT_TOKENS_PER_CHUNK = max(1200, min(12000, int(os.environ.get('LEXICORE_AI_MAX_INPUT_TOKENS_PER_CHUNK', '3600'))))
SYNTHESIS_TOKEN_BUDGET = max(4000, min(60000, int(os.environ.get('LEXICORE_AI_SYNTHESIS_TOKEN_BUDGET', '22000'))))


class GeminiHTTPError(RuntimeError):
    def __init__(self, status_code: int, detail: str = '', retry_after: str | None = None):
        self.status_code = int(status_code or 0)
        self.detail = (detail or '').strip()[:1200]
        self.retry_after = retry_after
        super().__init__(f'Gemini HTTP {self.status_code}: {self.detail}')


_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0
MIN_REQUEST_INTERVAL = max(0.0, min(5.0, float(os.environ.get('LEXICORE_AI_MIN_REQUEST_INTERVAL', '0.75'))))

def _pace_request():
    global _LAST_REQUEST_AT
    if MIN_REQUEST_INTERVAL <= 0:
        return
    with _REQUEST_LOCK:
        now = time.time()
        wait = MIN_REQUEST_INTERVAL - (now - _LAST_REQUEST_AT)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_AT = time.time()

def _http_reason(code: int) -> str:
    if code == 400: return 'HTTP_400_BAD_REQUEST'
    if code in (401,403): return f'HTTP_{code}_AUTH_OR_PERMISSION'
    if code == 408: return 'HTTP_408_TIMEOUT'
    if code == 429: return 'HTTP_429_RATE_LIMIT'
    if 500 <= code <= 599: return f'HTTP_{code}_UPSTREAM'
    return f'HTTP_{code}'


def configuration_diagnostics() -> Dict[str, Any]:
    """Return explicit, fail-safe AI configuration state without making a network call.

    LexiCore is allowed to run in deterministic-local mode, but an operator who
    explicitly selects Gemini must be told immediately when the remote setup is
    incomplete instead of discovering it through a later HTTP 500.
    """
    cfg = provider_config()
    key = (os.environ.get('GEMINI_API_KEY') or '').strip()
    error = None
    if cfg['provider'] == 'gemini' and not key:
        error = 'MISSING_GEMINI_API_KEY'
    elif cfg['provider'] == 'gemini' and cfg['model'] == 'local-deterministic':
        error = 'INVALID_GEMINI_MODEL'
    return {
        'configuration_valid': error is None,
        'configuration_error': error,
        'remote_ai_requested': cfg['provider'] == 'gemini',
        'remote_ai_available': cfg['provider'] == 'gemini' and error is None,
        'fallback_active': cfg['provider'] != 'gemini' or error is not None,
        'fallback_reason': error or ('LOCAL_PROVIDER_SELECTED' if cfg['provider'] != 'gemini' else None),
    }


def is_available() -> bool:
    return bool(configuration_diagnostics()['remote_ai_available'])


def status() -> Dict[str, Any]:
    cfg = provider_config()
    diag = configuration_diagnostics()
    return {
        'available': is_available(),
        **diag,
        'provider': cfg['provider'],
        'model': cfg['model'],
        'reasoning_mode': 'FULL_DOCUMENT_MULTI_PASS_HYBRID',
        'chunk_size': CHUNK_SIZE,
        'chunk_overlap': CHUNK_OVERLAP,
        'max_chunks': MAX_CHUNKS,
        'max_input_tokens_per_chunk': MAX_INPUT_TOKENS_PER_CHUNK,
        'synthesis_token_budget': SYNTHESIS_TOKEN_BUDGET,
        'concurrency': CONCURRENCY,
        'timeout_seconds': TIMEOUT,
        'retries': AI_RETRIES,
        'min_request_interval': MIN_REQUEST_INTERVAL,
        'transport': 'LOCAL' if cfg['provider'] == 'local' else 'REST_X_GOOG_API_KEY',
        'fallback': 'DEEP_CASE_ANALYSIS_V2',
    }


def _estimate_tokens(text: str) -> int:
    """Conservative dependency-free token estimate for Indonesian legal text/OCR.

    It is intentionally an estimate, not a tokenizer contract.  We combine a
    character bound with lexical/punctuation density and use the larger value so
    OCR-heavy statutes, tables and citation-dense pleadings are budgeted safely.
    """
    text = text or ''
    if not text:
        return 0
    lexical = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, int(max(len(text) / 3.4, len(lexical) * 1.18)))


def _legal_segments(text: str) -> List[str]:
    """Split at legal/document boundaries before applying hard token limits."""
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return []
    # Form-feed preserves PDF page boundaries when extraction provides them.
    pages = [p for p in re.split(r'\f+', text) if p.strip()]
    segments: List[str] = []
    heading = re.compile(
        r'(?im)(?=^[ \t]*(?:BAB\s+[IVXLCDM0-9]+\b|BAGIAN\s+(?:KE[- ]?[A-Z0-9]+|[IVXLCDM0-9]+)\b|'
        r'PASAL\s+\d+[A-Z]?\b|DALAM\s+(?:EKSEPSI|POKOK\s+PERKARA|REKONVENSI|KONVENSI)\b|'
        r'PETITUM\b|PERTANYAAN\s*:|JAWABAN\s*:|KESIMPULAN\b))'
    )
    for page in pages:
        parts = [p.strip() for p in heading.split(page) if p.strip()]
        if len(parts) == 1:
            parts = [p.strip() for p in re.split(r'\n\s*\n+', page) if p.strip()]
        segments.extend(parts)
    return segments


def _hard_split_token_budget(text: str) -> List[str]:
    """Fallback split that respects both configured chars and estimated tokens."""
    out: List[str] = []
    text = (text or '').strip()
    while text:
        # Start from the configured character ceiling, then shrink until token-safe.
        cut = min(len(text), CHUNK_SIZE)
        candidate = text[:cut]
        while cut > 800 and _estimate_tokens(candidate) > MAX_INPUT_TOKENS_PER_CHUNK:
            cut = max(800, int(cut * 0.82))
            candidate = text[:cut]
        if cut < len(text):
            # Prefer a sentence/newline boundary near the tail of the safe slice.
            boundary = max(candidate.rfind('\n'), candidate.rfind('. '), candidate.rfind('; '))
            if boundary >= int(cut * 0.60):
                cut = boundary + 1
                candidate = text[:cut]
        out.append(candidate.strip())
        if cut >= len(text):
            break
        overlap = min(CHUNK_OVERLAP, max(0, cut // 8))
        text = text[max(1, cut - overlap):].lstrip()
    return [x for x in out if x]


def _chunks(text: str) -> List[str]:
    text = (text or '').strip()
    if not text:
        return []
    chunks: List[str] = []
    cur = ''
    for segment in _legal_segments(text):
        candidate = (cur + '\n\n' + segment).strip() if cur else segment
        if len(candidate) <= CHUNK_SIZE and _estimate_tokens(candidate) <= MAX_INPUT_TOKENS_PER_CHUNK:
            cur = candidate
            continue
        if cur:
            chunks.append(cur)
            if len(chunks) >= MAX_CHUNKS:
                break
            cur = ''
        if len(segment) > CHUNK_SIZE or _estimate_tokens(segment) > MAX_INPUT_TOKENS_PER_CHUNK:
            for piece in _hard_split_token_budget(segment):
                chunks.append(piece)
                if len(chunks) >= MAX_CHUNKS:
                    break
        else:
            cur = segment
        if len(chunks) >= MAX_CHUNKS:
            break
    if cur and len(chunks) < MAX_CHUNKS:
        chunks.append(cur)
    return chunks[:MAX_CHUNKS]


def _gemini_request(prompt: str, *, structured: bool = True) -> Dict[str, Any]:
    key = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if not key:
        raise RuntimeError('AI_CONFIGURATION_ERROR:MISSING_GEMINI_API_KEY')
    cfg = provider_config()
    if cfg['provider'] != 'gemini':
        raise RuntimeError('Remote AI provider tidak aktif; gunakan mode local atau konfigurasi Gemini')
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent"
    generation = {'temperature': 0.15, 'maxOutputTokens': 8192}
    if structured:
        generation['responseMimeType'] = 'application/json'
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': generation
    }
    _pace_request()
    req = urlrequest.Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers={
        'Content-Type': 'application/json',
        'x-goog-api-key': key,
        'User-Agent': f'LexiCore/{LEXICORE_VERSION}'
    }, method='POST')
    try:
        with urlrequest.urlopen(req, timeout=TIMEOUT) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'ignore')[:1200]
        retry_after = exc.headers.get('Retry-After') if getattr(exc, 'headers', None) else None
        raise GeminiHTTPError(exc.code, detail, retry_after) from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f'Gemini network error: {exc.reason}') from exc

    candidates = body.get('candidates') or []
    if not candidates:
        feedback = body.get('promptFeedback') or {}
        raise RuntimeError('Gemini tidak mengembalikan kandidat jawaban' + (f': {feedback}' if feedback else ''))
    cand = candidates[0] or {}
    parts = (((cand.get('content') or {}).get('parts')) or [])
    raw = ''.join(str(p.get('text') or '') for p in parts).strip()
    if not raw:
        finish = cand.get('finishReason') or 'UNKNOWN'
        raise RuntimeError(f'Gemini mengembalikan respons kosong (finishReason={finish})')
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I|re.S).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        first, last = raw.find('{'), raw.rfind('}')
        if first >= 0 and last > first:
            return json.loads(raw[first:last+1])
        raise


def _gemini_json(prompt: str) -> Dict[str, Any]:
    try:
        return _gemini_request(prompt, structured=True)
    except GeminiHTTPError as exc:
        # Some API gateways/key policies reject optional structured-output config.
        # A single plain generateContent retry preserves the JSON-only prompt and
        # avoids falsely dropping the whole document for a transport/config quirk.
        if exc.status_code == 400:
            return _gemini_request(prompt, structured=False)
        raise



def chunk_diagnostics(text: str) -> Dict[str, Any]:
    chunks = _chunks(text)
    return {
        'characters': len(text or ''),
        'segments_total': len(chunks),
        'segment_lengths': [len(c) for c in chunks[:8]],
        'segment_token_estimates': [_estimate_tokens(c) for c in chunks[:8]],
        'chunk_size': CHUNK_SIZE,
        'max_input_tokens_per_chunk': MAX_INPUT_TOKENS_PER_CHUNK,
        'synthesis_token_budget': SYNTHESIS_TOKEN_BUDGET,
        'chunk_overlap': CHUNK_OVERLAP,
        'max_chunks': MAX_CHUNKS,
    }


def _gemini_json_retry(prompt: str) -> Dict[str, Any]:
    last = None
    for attempt in range(AI_RETRIES + 1):
        try:
            return _gemini_json(prompt)
        except GeminiHTTPError as exc:
            last = exc
            retryable = exc.status_code in (408, 409, 429, 500, 502, 503, 504)
            if not retryable or attempt >= AI_RETRIES:
                break
            delay = 1.2 * (2 ** attempt)
            try:
                if exc.retry_after:
                    delay = max(delay, float(exc.retry_after))
            except Exception:
                pass
            time.sleep(min(delay, 12.0))
        except Exception as exc:
            last = exc
            if attempt >= AI_RETRIES:
                break
            time.sleep(0.7 * (attempt + 1))
    raise last


def _evidence_prompt(chunk: str, index: int, total: int, title: str) -> str:
    return f'''Anda adalah Evidence Extraction Engine LexiCore untuk praktik hukum Indonesia.
Dokumen: {title}. Bagian {index}/{total}.

ATURAN KERAS:
- Bedakan pertanyaan/dugaan pemeriksa dari fakta dan jawaban pihak yang diperiksa.
- Jangan mengubah allegation menjadi fact.
- Kutipan harus singkat dan berasal dari bagian dokumen ini.
- Catat admission, denial, keterbatasan pengetahuan, aktor, dokumen/bukti, norma yang disebut, dan gap.
- Jangan menyimpulkan bersalah/tidak bersalah.

TEKS BAGIAN:
{chunk}

Kembalikan JSON murni:
{{
 "facts":[{{"statement":"...","evidence":"kutipan singkat","type":"DOCUMENT_FACT|PROCEDURAL_FACT"}}],
 "admissions":[{{"statement":"...","evidence":"..."}}],
 "denials_or_limits":[{{"statement":"...","evidence":"..."}}],
 "allegations":[{{"statement":"...","evidence":"..."}}],
 "actors":[{{"name":"...","role":"..."}}],
 "documents":["..."],
 "legal_refs":["..."],
 "procedural_points":["..."],
 "unresolved_questions":["..."],
 "source_items":[{{"label":"SOURCE FACT|ADMISSION|DENIAL_LIMIT|ALLEGATION|DOCUMENT|LEGAL_REFERENCE|PROCEDURAL_POINT","statement":"...","evidence":"kutipan singkat","segment":str(index)}}]
}}'''


def _truncate_value(value: Any, limit: int = 520) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit-1].rstrip() + '…'
    if isinstance(value, dict):
        return {k: _truncate_value(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_value(v, limit) for v in value]
    return value


def _compact_evidence_maps(evidence_maps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate and budget map-reduce evidence before the synthesis request."""
    fields = ('facts','admissions','denials_or_limits','allegations','actors','documents','legal_refs',
              'procedural_points','unresolved_questions','source_items')
    seen = set()
    compact: List[Dict[str, Any]] = []
    for item in evidence_maps or []:
        row: Dict[str, Any] = {'_segment': item.get('_segment')}
        for field in fields:
            values = item.get(field) or []
            kept = []
            for value in values[:8]:
                norm = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict,list)) else str(value)
                key = (field, re.sub(r'\s+', ' ', norm).strip().lower())
                if not key[1] or key in seen:
                    continue
                seen.add(key)
                kept.append(_truncate_value(value))
            if kept:
                row[field] = kept
        if len(row) > 1:
            compact.append(row)

    # Enforce a synthesis input ceiling by trimming low-priority tail records,
    # never by silently allowing an oversized request.
    low_priority = ('unresolved_questions','actors','documents','procedural_points','allegations')
    def token_count() -> int:
        return _estimate_tokens(json.dumps(compact, ensure_ascii=False))
    guard = 0
    while compact and token_count() > SYNTHESIS_TOKEN_BUDGET and guard < 500:
        changed = False
        for field in low_priority:
            for row in reversed(compact):
                vals = row.get(field)
                if vals:
                    vals.pop()
                    if not vals:
                        row.pop(field, None)
                    changed = True
                    break
            if changed:
                break
        if not changed:
            # Preserve at least the earliest source-grounded material, but cap the
            # number of segment maps when all low-priority material is exhausted.
            if len(compact) > 1:
                compact.pop()
                changed = True
        if not changed:
            break
        guard += 1
    return compact


def _synthesis_prompt(title: str, text_len: int, evidence_maps: List[Dict[str, Any]], fallback: Dict[str, Any], official: Any) -> str:
    compact_maps = _compact_evidence_maps(evidence_maps)
    evidence_json = json.dumps(compact_maps, ensure_ascii=False)
    fallback_compact = {k: fallback.get(k) for k in ('case_posture','domain_classification','domain_contract','facts','incriminating_facts','mitigating_facts','legal_issues','element_matrix','evidentiary_gaps','recommendations','provision_refs','regulatory_matches','norm_conflicts')}
    return f'''Anda adalah Senior Legal Reasoning Engine LexiCore untuk lawyer Indonesia.
Sintesis seluruh peta bukti dari dokumen "{title}" ({text_len} karakter) menjadi analisis yuridis berimbang dan source-grounded.

PRINSIP WAJIB:
1. Pelanggaran SOP tidak otomatis tindak pidana.
2. Kredit macet/plafon tidak otomatis kerugian negara; uji actual loss dan pemulihan/agunan jika relevan.
3. Tanda tangan/otoritas akhir tidak otomatis membuktikan pengetahuan atas seluruh fakta teknis.
4. Pertanyaan pemeriksa atau tuduhan bukan fakta kecuali didukung jawaban/dokumen.
5. Pisahkan act, authority, mens rea, benefit/purpose, actual loss, causation, personal responsibility, intervening acts, tempus delicti, evidentiary gaps.
6. Untuk norma hukum, jangan klaim status berlaku final hanya dari pengetahuan model. Tandai perlu verifikasi sumber resmi.
7. Berikan teori penuntut/lawan dan teori pembelaan secara fair.
8. Jangan menampilkan chain-of-thought internal. Berikan alasan hukum ringkas dan dapat diaudit.
9. Regulatory corpus lokal adalah retrieval aid, bukan sumber final; jangan menaikkan LOCAL_CORPUS_MATCH menjadi VERIFIED tanpa sumber resmi.
10. Norm conflict output adalah issue spotting. Uji lex superior, lex specialis, lex posterior, tempus, dan kewenangan pembentuk secara terpisah sebelum rekomendasi final.
11. CASE POSTURE dan DOMAIN CLASSIFICATION dari deterministic engine adalah KONTRAK YURIDIS IMMUTABLE. AI boleh memperkaya alasan tetapi DILARANG mengubah primary domain hanya karena menemukan istilah transaksi/perjanjian.
12. Jika BPR/Bank/Fasilitas Kredit/Keuangan Negara-Daerah muncul, lakukan Tipikor priority screen terlebih dahulu. Perjanjian kredit pada perkara penyidikan dugaan fraud/penyimpangan internal BPR adalah hubungan pendukung, bukan otomatis wanprestasi sebagai primary domain.
13. Jangan mengeluarkan rekomendasi, bukti yang dibutuhkan, atau regulasi dari domain yang tidak berada pada PRIMARY/SECONDARY contract kecuali diberi label SUPPORTING dan dijelaskan relevansi materialnya.
14. Gunakan tiga level eksplisit: FACT (didukung sumber), INFERENCE (analisis dari fakta), LEGAL CONCLUSION (hanya jika norma, identitas instrumen, status berlaku, tempus, case nexus dan unsur yang relevan cukup terverifikasi).
15. No evidence → no specific allegation. No nexus → no domain-specific conclusion. No tempus → no definitive applicable-law conclusion. No verified provision → no definitive legal conclusion.
16. Jangan melakukan silent correction atas nomor/tahun undang-undang yang tampak salah. Tampilkan sebagai POTENTIAL_TYPO_OR_OCR dan minta verifikasi terhadap dokumen asli/sumber resmi.
17. Pada eksepsi, bedakan kompetensi/forum dari merits. Dalil bahwa peristiwa lebih tepat dikualifikasikan sebagai tindak pidana lain tidak otomatis berarti pengadilan yang memeriksa dakwaan tidak berwenang.
18. Bedakan error in persona (salah identitas subjek) dari tidak terbuktinya atribusi perbuatan atau adanya pihak lain yang lebih bertanggung jawab.
19. Field "legal_analysis" WAJIB berupa prosa naratif biasa tanpa heading -- DILARANG menulis heading/judul bagian sendiri atau penomoran romawi/angka/abjad sendiri (dilarang menulis "I.", "II.", "1.", "A." dsb sebagai judul bagian) -- sistem LexiCore sudah menomori bagian secara otomatis di lapisan render, dan penomoran ganda dari teks Anda akan tampil bertumpuk/rusak. Tulis sebagai paragraf mengalir yang secara eksplisit menyebut nama pihak, tanggal, jumlah uang, dan objek konkret dari fakta yang sudah diekstraksi di atas (bukan kerangka doktrinal generik yang bisa berlaku untuk kasus apa pun) -- setiap kalimat kesimpulan harus bisa ditelusuri balik ke satu fakta atau pasal spesifik dalam data yang diberikan, bukan pernyataan umum seperti "harus diuji lebih lanjut" tanpa merujuk fakta mana yang dimaksud.
20. Sebelum menulis "legal_analysis", klasifikasikan dalam pikiran Anda setiap potongan informasi ke salah satu dari 3 kategori: (A) FAKTA TEKSTUAL -- tertulis eksplisit di sumber; (B) DALIL/KLAIM SEPIHAK -- baru pengakuan/tuduhan satu pihak, belum tentu benar; (C) ANOMALI -- kontradiksi antar-pernyataan atau antara tindakan aktor dengan klaimnya. Jangan pernah menaikkan (B) menjadi (A) hanya karena konsisten dengan teori kasus Anda. Sebutkan ANOMALI secara eksplisit di narasi ("A." vs "B" bertentangan karena ...) bila ditemukan -- ini justru memperkuat, bukan melemahkan, kredibilitas analisis.
21. KUTIPAN WAJIB: setiap kali "legal_analysis" menyimpulkan adanya hak, kewajiban, pelanggaran, unsur delik, atau risiko konkret, sertakan tag kutipan singkat dalam kurung siku persis dari sumber: [FAKTA: "kutipan singkat kata demi kata dari narasi/dokumen sumber"]. Jika tidak ada kalimat sumber yang mendukung klaim tersebut, jangan menuliskannya sebagai kesimpulan pasti -- tulis [KLAIM KOSONG: alasan singkat kenapa belum ada dasar tekstual] dan turunkan klaim itu ke tingkat hipotesis/pertanyaan yang perlu diverifikasi, bukan kesimpulan. Tag ini WAJIB berbentuk frasa pendek dalam kurung siku, BUKAN heading/judul baris baru (lihat aturan 19).

FEW-SHOT BATAS DEMARKASI DOMAIN:
{FEW_SHOT_BOUNDARY}

EVIDENCE MAPS:
{evidence_json}

DETERMINISTIC FALLBACK SIGNALS:
{json.dumps(fallback_compact, ensure_ascii=False)}

OFFICIAL SOURCE VERIFICATION SNAPSHOT (hanya signal, bukan pengganti membaca bunyi norma):
{json.dumps(official or {}, ensure_ascii=False)[:12000]}

JSON murni dengan skema:
{{
 "facts":["..."],
 "incriminating_facts":["..."],
 "mitigating_facts":["..."],
 "legal_issues":["..."],
 "applicable_law":[{{"domain":"...","source":"...","status":"PERLU VERIFIKASI SUMBER RESMI","confidence":"HIGH|MEDIUM|LOW"}}],
 "legal_analysis":"prosa naratif (bukan heading/penomoran sendiri) yang secara eksplisit merujuk nama pihak, tanggal, jumlah, dan objek konkret dari fakta di atas, dengan tag [FAKTA: "kutipan"] atau [KLAIM KOSONG: alasan] pada tiap kesimpulan hak/kewajiban/pelanggaran/risiko",
 "element_matrix":[{{"element":"...","prosecution_support":"...","defense_focus":"...","status":"SUPPORTED|DISPUTED|NOT_ESTABLISHED|NEEDS_EVIDENCE"}}],
 "mens_rea_analysis":"...",
 "actual_loss_analysis":"...",
 "causation_analysis":"...",
 "personal_responsibility_analysis":"...",
 "temporal_law_analysis":"...",
 "arguments_for":["..."],
 "arguments_against":["..."],
 "evidence_needed":["..."],
 "evidentiary_gaps":["..."],
 "risks":["..."],
 "recommendations":["..."],
 "decision_summary":{{
   "already_established":["..."],
   "not_yet_established":["..."],
   "must_be_verified":["..."]
 }},
 "action_plan":[{{"priority":"P1|P2|P3","issue":"...","current_status":"...","action":"...","why_it_matters":"...","source_segments":[1]}}],
 "hypotheses":{{
   "primary":{{"name":"...","summary":"...","strength":"HIGH|MEDIUM|LOW","reasoning":["alasan ringkas..."]}},
   "secondary":{{"name":"...","summary":"...","strength":"HIGH|MEDIUM|LOW","reasoning":["..."]}},
   "opposition":{{"name":"...","summary":"...","strength":"HIGH|MEDIUM|LOW","reasoning":["..."]}}
 }}
}}'''


def _validate_evidence_payload(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, 'SCHEMA_NOT_OBJECT'
    expected = ('facts','admissions','denials_or_limits','allegations','actors','documents','legal_refs','procedural_points','unresolved_questions','source_items')
    if not any(k in data for k in expected):
        return False, 'SCHEMA_NO_EXPECTED_FIELDS'
    if all(not data.get(k) for k in expected):
        return False, 'EMPTY_EVIDENCE_PAYLOAD'
    return True, 'ACCEPTED'


_LEADING_NUMBERED_HEADING = re.compile(r'^\s*(?:[IVXLCDM]{1,6}|[0-9]{1,3}|[A-Z])[.)]\s+')

_SELF_NUMBERED_NARRATIVE_FIELDS = ('legal_analysis', 'mens_rea_analysis', 'actual_loss_analysis',
                                    'causation_analysis', 'personal_responsibility_analysis',
                                    'temporal_law_analysis')


def _strip_self_numbered_headings(text: str) -> str:
    """Defensive text sanitizer, applied at the source.

    LexiCore's export layer (PDF/DOCX working paper) adds its OWN Roman-numeral
    section numbering around every narrative field it renders. If the model
    additionally invents its own top-level numbered heading inside a free-text
    field (e.g. starting a paragraph with "I. CORE LEGAL THESIS" despite the
    prompt instructing it not to), that self-assigned number visually stacks
    with whichever numbering the exporter adds on top of it downstream (e.g.
    "II. I. CORE LEGAL THESIS"). Rather than guessing which of several export
    code paths is active for a given run, this strips only a LEADING
    numbered-heading-style prefix from short heading-shaped lines, at the
    moment the AI response is received -- so every downstream renderer is
    protected uniformly. It never removes body content, only a numbering
    prefix -- substantive prose (including a numbered clause inline within a
    normal sentence) is left untouched.
    """
    if not isinstance(text, str) or not text.strip():
        return text
    cleaned_lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        # Only touch short, heading-shaped lines (a numbered label on its own
        # line), never a numbered item inside a normal sentence/paragraph.
        if stripped and len(stripped) < 120 and _LEADING_NUMBERED_HEADING.match(stripped):
            line = _LEADING_NUMBERED_HEADING.sub('', line, count=1)
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


def _strip_self_numbered_headings_in_synthesis(synthesis: Dict[str, Any]) -> Dict[str, Any]:
    """Apply _strip_self_numbered_headings to every known free-text narrative
    field of a synthesis payload. Never touches structured list/dict fields."""
    for key in _SELF_NUMBERED_NARRATIVE_FIELDS:
        val = synthesis.get(key)
        if isinstance(val, str) and val.strip():
            synthesis[key] = _strip_self_numbered_headings(val)
    return synthesis


def _validate_synthesis_payload(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, 'SYNTHESIS_NOT_OBJECT'
    anchors = ('legal_analysis','legal_issues','facts','evidentiary_gaps','action_plan','decision_summary')
    if not any(data.get(k) for k in anchors):
        return False, 'SYNTHESIS_EMPTY_OR_SCHEMA_MISMATCH'
    return True, 'ACCEPTED'


def analyze_full_document(text: str, title: str, fallback: Dict[str, Any], official: Any = None) -> Dict[str, Any] | None:
    if not is_available():
        return None
    chunks = _chunks(text)
    if not chunks:
        return None
    evidence_maps: List[Dict[str, Any] | None] = [None] * len(chunks)
    trace = [{
        'segment': i + 1, 'characters': len(chunk), 'state': 'PLANNED', 'attempts': 0,
        'reason': None,
    } for i, chunk in enumerate(chunks)]
    failures = []
    started = time.time()

    def run(i: int, chunk: str):
        trace[i]['state'] = 'SENT'
        trace[i]['attempts'] = AI_RETRIES + 1
        try:
            data = _gemini_json_retry(_evidence_prompt(chunk, i+1, len(chunks), title))
            trace[i]['state'] = 'RESPONSE_RECEIVED'
            ok, reason = _validate_evidence_payload(data)
            if not ok:
                trace[i]['state'] = 'REJECTED'
                trace[i]['reason'] = reason
                raise RuntimeError(reason)
            trace[i]['state'] = 'ACCEPTED'
            return i, data
        except json.JSONDecodeError as exc:
            trace[i]['state'] = 'REJECTED'; trace[i]['reason'] = 'INVALID_JSON'
            raise RuntimeError(f'INVALID_JSON: {exc}') from exc
        except Exception as exc:
            if trace[i]['state'] not in ('REJECTED', 'ACCEPTED'):
                trace[i]['state'] = 'REJECTED'
                msg = str(exc)
                if isinstance(exc, GeminiHTTPError):
                    reason = _http_reason(exc.status_code)
                    trace[i]['http_status'] = exc.status_code
                    trace[i]['detail'] = exc.detail[:240]
                elif re.search(r'gemini\s+http\s+(\d{3})', msg, flags=re.I):
                    # Preserve auditable HTTP diagnostics even when a lower layer or
                    # test double wraps GeminiHTTPError into a plain RuntimeError.
                    status = int(re.search(r'gemini\s+http\s+(\d{3})', msg, flags=re.I).group(1))
                    reason = _http_reason(status)
                    trace[i]['http_status'] = status
                    trace[i]['detail'] = msg[:240]
                elif 'timed out' in msg.lower() or 'timeout' in msg.lower():
                    reason = 'TIMEOUT'
                elif 'kandidat' in msg.lower():
                    reason = 'EMPTY_CANDIDATE'
                elif 'network error' in msg.lower():
                    reason = 'NETWORK_ERROR'
                else:
                    reason = 'REQUEST_OR_PARSE_ERROR'
                trace[i]['reason'] = reason
            raise

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futs = [pool.submit(run, i, c) for i,c in enumerate(chunks)]
        for fut in as_completed(futs):
            try:
                i, data = fut.result(); data['_segment'] = i+1; evidence_maps[i] = data
            except Exception as exc:
                failures.append(str(exc)[:300])

    successful = [x for x in evidence_maps if x]
    diagnostics = {
        'characters': len(text), 'segments_total': len(chunks), 'segments_read': len(successful),
        'provider': provider_config()['provider'], 'model': provider_config()['model'], 'segment_trace': trace,
        'failures': failures[:10], 'elapsed_seconds': round(time.time()-started, 2),
    }
    if not successful:
        diagnostics['status'] = 'ALL_SEGMENTS_REJECTED'
        raise FullDocumentFailure('Full-Document AI: seluruh segmen gagal atau ditolak', diagnostics)

    try:
        synthesis = _gemini_json_retry(_synthesis_prompt(title, len(text), successful, fallback, official))
        ok, reason = _validate_synthesis_payload(synthesis)
        if not ok:
            raise RuntimeError(reason)
        synthesis = _strip_self_numbered_headings_in_synthesis(synthesis)
    except Exception as exc:
        diagnostics['status'] = 'SYNTHESIS_REJECTED'
        diagnostics['synthesis_reason'] = str(exc)[:300]
        raise FullDocumentFailure('Full-Document AI: sintesis gagal atau ditolak', diagnostics) from exc

    diagnostics['status'] = 'COMPLETE' if len(successful)==len(chunks) else 'PARTIAL'
    diagnostics['elapsed_seconds'] = round(time.time()-started,2)
    synthesis['ai_evidence_map'] = successful
    synthesis['document_reading'] = diagnostics
    synthesis['analytical_method'] = 'EVIDENCE_TO_ACTION_REGULATORY_NORM_V1_3_1_1'
    return synthesis


def run_grounded_json_prompt(prompt: str) -> Dict[str, Any] | None:
    """Additive, single-purpose entrypoint: one grounded structured (JSON)
    completion from the configured provider, without the Full-Document
    multi-pass chunking/synthesis machinery `analyze_full_document` uses.

    Fail-closed by design: returns None (never raises) when AI is
    unavailable or the call fails for any reason. Callers MUST treat None
    as "not available" and degrade to a clearly-labeled placeholder rather
    than fabricate content. Does not change the behavior of any existing
    function in this module — it only reuses the already-private HTTP
    call/retry helper.
    """
    if not is_available():
        return None
    try:
        return _gemini_json_retry(prompt)
    except Exception:
        return None
