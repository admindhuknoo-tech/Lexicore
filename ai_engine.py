"""LexiCore Full-document Legal AI Reasoning Layer (Python).

Uses Gemini REST directly via Python stdlib when GEMINI_API_KEY is configured.
No extra Python package is required. If AI is unavailable or a call fails, callers
should retain the deterministic Deep Case Analysis fallback.
"""
from __future__ import annotations
import json, os, re, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

class FullDocumentFailure(RuntimeError):
    def __init__(self, message: str, diagnostics: Dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}

from version import LEXICORE_VERSION
from urllib import request as urlrequest, error as urlerror

PROVIDER = os.environ.get('LEXICORE_AI_PROVIDER', 'gemini').strip().lower()
MODEL = os.environ.get('LEXICORE_AI_MODEL', 'gemini-2.5-flash').strip()
CHUNK_SIZE = max(4000, int(os.environ.get('LEXICORE_AI_CHUNK_SIZE', '10000')))
CHUNK_OVERLAP = max(0, min(2000, int(os.environ.get('LEXICORE_AI_CHUNK_OVERLAP', '700'))))
MAX_CHUNKS = max(1, min(40, int(os.environ.get('LEXICORE_AI_MAX_CHUNKS', '24'))))
CONCURRENCY = max(1, min(4, int(os.environ.get('LEXICORE_AI_CONCURRENCY', '2'))))
TIMEOUT = max(8, min(90, int(os.environ.get('LEXICORE_AI_TIMEOUT_SECONDS', '35'))))
AI_RETRIES = max(0, min(3, int(os.environ.get('LEXICORE_AI_RETRIES', '2'))))


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


def is_available() -> bool:
    return PROVIDER == 'gemini' and bool(os.environ.get('GEMINI_API_KEY'))


def status() -> Dict[str, Any]:
    return {
        'available': is_available(),
        'provider': PROVIDER,
        'model': MODEL,
        'reasoning_mode': 'FULL_DOCUMENT_MULTI_PASS_HYBRID',
        'chunk_size': CHUNK_SIZE,
        'chunk_overlap': CHUNK_OVERLAP,
        'max_chunks': MAX_CHUNKS,
        'concurrency': CONCURRENCY,
        'timeout_seconds': TIMEOUT,
        'retries': AI_RETRIES,
        'min_request_interval': MIN_REQUEST_INTERVAL,
        'transport': 'REST_X_GOOG_API_KEY',
        'fallback': 'DEEP_CASE_ANALYSIS_V2',
    }


def _chunks(text: str) -> List[str]:
    text = (text or '').strip()
    if not text:
        return []
    # Prefer paragraph boundaries while keeping deterministic character limits.
    paras = [p.strip() for p in re.split(r'\n\s*\n+', text) if p.strip()]
    chunks, cur = [], ''
    for p in paras:
        candidate = (cur + '\n\n' + p).strip() if cur else p
        if len(candidate) <= CHUNK_SIZE:
            cur = candidate
            continue
        if cur:
            chunks.append(cur)
            tail = cur[-CHUNK_OVERLAP:] if CHUNK_OVERLAP else ''
            cur = (tail + '\n\n' + p).strip()
        else:
            start = 0
            while start < len(p):
                end = min(len(p), start + CHUNK_SIZE)
                chunks.append(p[start:end])
                if end >= len(p): break
                start = max(end - CHUNK_OVERLAP, start + 1)
            cur = ''
        if len(chunks) >= MAX_CHUNKS:
            break
    if cur and len(chunks) < MAX_CHUNKS:
        chunks.append(cur)
    return chunks[:MAX_CHUNKS]


def _gemini_request(prompt: str, *, structured: bool = True) -> Dict[str, Any]:
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise RuntimeError('GEMINI_API_KEY belum dikonfigurasi')
    endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'
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
        'chunk_size': CHUNK_SIZE,
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


def _synthesis_prompt(title: str, text_len: int, evidence_maps: List[Dict[str, Any]], fallback: Dict[str, Any], official: Any) -> str:
    evidence_json = json.dumps(evidence_maps, ensure_ascii=False)
    fallback_compact = {k: fallback.get(k) for k in ('facts','incriminating_facts','mitigating_facts','legal_issues','element_matrix','evidentiary_gaps','recommendations','provision_refs','regulatory_matches','norm_conflicts')}
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
 "legal_analysis":"analisis terstruktur dan mendalam",
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
        'provider': PROVIDER, 'model': MODEL, 'segment_trace': trace,
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
