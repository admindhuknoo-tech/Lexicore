from typing import Iterable, List, Tuple
import re

from identity_profile import get_identity_profile

from services.case_consistency_guard import regulation_merits_reportable


# Reader-facing terminology mapping is intentionally kept inside exporters/common.py.
# tools/release_audit.py freezes exporters/ to the canonical four live modules only.
_READER_PHRASE_REPLACEMENTS = (
    (re.compile(r"chain cannot support a final conclusion while a required gate or element remains unresolved", re.I),
     "Rantai analisis belum dapat mendukung kesimpulan akhir karena masih terdapat unsur atau tahap verifikasi yang belum terpenuhi"),
    (re.compile(r"\bNot established\b", re.I), "Belum terbukti"),
    (re.compile(r"\bGAP\s*/\s*non[- ]merits\b", re.I), "kekosongan verifikasi pada isu prosedural"),
    (re.compile(r"\bnon[- ]merits\b", re.I), "prosedural"),
    (re.compile(r"\bcounter[- ]evidence\b", re.I), "bantahan atau bukti lawan"),
    (re.compile(r"\belement test\b", re.I), "uji unsur"),
    (re.compile(r"\bimpact\b", re.I), "dampak atau kerugian nyata"),
    (re.compile(r"\bact\s+yang\s+did(alilkan|uga)\b", re.I), "perbuatan yang didalilkan"),
    (re.compile(r"\bmerits\b", re.I), "pokok perkara"),
)

class LexiCoreCivilPresentationSanitizer:
    """Unified Presentation Sanitizer v1.2.3 (presentation-only).

    This adapter never mutates the canonical reasoning ledger.  It only
    projects a reader-facing civil pleading label and cleans strings in the
    final export model.
    """

    @staticmethod
    def resolve_civil_posture_label(raw_text: str) -> str:
        text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
        low = text.lower()
        if not text:
            return ""

        # Strong-evidence patterns: require pleading role/context, not a bare
        # mention that may merely quote the opponent's filing.
        if (re.search(r"\bdupl(?:i|ie)k\s+(?:terhadap|atas)\s+repl(?:i|ie)k\b", low) or
            (re.search(r"\bmengajukan\s+dupl(?:i|ie)k\b", low) and
             re.search(r"\b(?:para\s+)?tergugat\b", low))):
            return "Duplik Perdata / Pihak Tergugat"
        if (re.search(r"\brepl(?:i|ie)k\s+(?:terhadap|atas)\s+jawaban\b", low) or
            (re.search(r"\bmengajukan\s+repl(?:i|ie)k\b", low) and
             re.search(r"\bpenggugat\b", low))):
            return "Replik Perdata / Pihak Penggugat"
        if (re.search(r"\b(?:surat\s+)?gugatan\b", low) and
            re.search(r"\b(?:pdt\.?g|penggugat)\b", low)):
            return "Surat Gugatan / Pihak Penggugat"
        if (re.search(r"\bjawaban(?:\s+atas)?\s+gugatan\b", low) and
            re.search(r"\b(?:para\s+)?tergugat\b", low)):
            return "Jawaban Gugatan / Pihak Tergugat"
        return ""

    @staticmethod
    def clean_text(value: str, *, is_civil: bool = False) -> str:
        text = str(value or "")
        if is_civil:
            civil_patterns = (
                (r"\bsurat\s+dakwaan\b", "surat gugatan"),
                (r"\bteks\s+dakwaan\b", "posita gugatan"),
                (r"\btuduhan\s+dakwaan\b", "dalil gugatan"),
                (r"\bdidakwakan\b", "digugat atau disengketakan"),
                (r"\bpengadilan\s+tipikor\b", "Pengadilan Negeri"),
                (r"keberatan\s+formil\s+terhadap\s+dakwaan\s+atau\s+forum",
                 "keberatan formil terhadap gugatan, jawaban, atau forum"),
                (r"norma\s+yang\s+dirujuk\s+dalam\s+dakwaan",
                 "norma hukum yang dirujuk dalam posita gugatan"),
                (r"bagian\s+dakwaan\s+yang\s+secara\s+spesifik\s+dipersoalkan",
                 "bagian posita atau jawaban lawan yang secara spesifik dipersoalkan"),
                (r"masing-masing\s+dengan\s+teks\s+dakwaan",
                 "masing-masing dengan posita atau jawaban lawan"),
            )
            for pattern, replacement in civil_patterns:
                text = re.sub(pattern, replacement, text, flags=re.I)

        universal_patterns = (
            (r"\bNot established\b", "Belum terbukti"),
            (r"\bcounter[- ]evidence\b", "bantahan atau bukti lawan"),
            (r"\bLEGAL_VERIFICATION_REQUIRED\b", "DIPERLUKAN VERIFIKASI HUKUM POSITIF"),
            (r"\bFACT_ASSERTION/PRIMARY_EVIDENCE\b", "pernyataan faktual atau bukti primer"),
            (r"\bPositive-Allow SAL\b", "penyaringan kelayakan semantik"),
            (r"\bactive-clash admission SAL\b", "penyaringan semantik"),
            (r"\bcurrent issue\b", "isu hukum aktif"),
            # Legacy repair: content generated before this fix (or produced by any
            # other path) may still contain the doubled phrase baked in literally.
            # Collapse it to the single correct form regardless of source.
            (r"\bisu hukum aktif yang lolos isu aktif yang lolos penyaringan semantik\b",
             "isu hukum aktif yang lolos penyaringan semantik"),
            (r"\bGAP\s*/\s*non[- ]merits\b", "kekosongan verifikasi pada isu prosedural"),
            (r"\bDocument Audit\b", "Audit Dokumen"),
            (r"\bProcedural/Merits\b", "Prosedural / Pokok Perkara"),
            (r"\bRegulation/Tempus\b", "Dasar Hukum / Waktu Berlaku"),
            (r"\bDEFENSE_COUNSEL\b", "Penasihat Hukum"),
            (r"\bPROSECUTOR\b", "Jaksa Penuntut Umum"),
            (r"\bElement Test\b", "Pengujian Unsur Hukum"),
            (r"\bcase\s+keterkaitan\b", "Keterkaitan Materi Perkara"),
            (r"\bcandidate\s+result\b", "hasil kandidat hukum"),
            (r"\bLocal\s+Deterministic\b", "mode deterministik lokal"),
            (r"\bEvidence-to-Action\b", "analisis bukti ke tindakan"),
            (r"\bretrieval\s+sumber\s+hukum\b", "penelusuran sumber hukum"),
            (r"\bactual\s+loss\b", "kerugian nyata"),
            (r"\bintervening\s+acts\b", "tindakan atau faktor perantara"),
            (r"\boutstanding\s+principal\b", "sisa pokok kewajiban"),
            (r"\bcausal\s+chain\b", "Rantai Hubungan Kausalitas"),
            # Phrase-level replacements only; do not globally replace ordinary
            # words such as 'applicable', 'exposure', or 'recovery' inside
            # quoted/source text.
            (r"\bdinyatakan\s+applicable\b", "dinyatakan dapat diterapkan"),
            (r"\bApplicable\s+law\b", "Hukum yang berlaku"),
            (r"\bexposure\s*,\s*recovery\s+dan\s+kausalitas\b", "risiko hukum, pemulihan kerugian/aset, dan kausalitas"),
            (r"\bexposure\s+dan\s+recovery\b", "risiko hukum dan pemulihan kerugian/aset"),
            (r"\bexposure\s*,\s*recovery\b", "risiko hukum dan pemulihan kerugian/aset"),
            (r"\bHubungan\s+sebab/akibat\s+atau\s+impact\b", "Hubungan sebab-akibat atau dampak"),
            (r"asal-usul data SAL", "asal-usul data analisis"),
            (r"chain cannot support a final conclusion while a required gate or element remains unresolved",
             "Rantai analisis belum dapat mendukung kesimpulan akhir karena masih terdapat unsur atau tahap verifikasi yang belum terpenuhi"),
            (r"norma yang berlaku,\s*act,\s*bukti",
             "norma yang berlaku, perbuatan yang didalilkan, bukti"),
            (r"\bact yang didalilkan\b", "perbuatan yang didalilkan"),
        )
        for pattern, replacement in universal_patterns:
            text = re.sub(pattern, replacement, text, flags=re.I)

        # v1.2.7 final-render vocabulary lock.  These substitutions target exact
        # diagnostic/English phrases observed in exported reports; they do not
        # alter canonical values or raw source artifacts.
        final_render_patterns = (
            (r"\bUNKNOWN_DATE\b", "Belum ditentukan"),
            (r"\bintervening\s+act\b", "tindakan atau faktor perantara"),
            (r"\bimpact\b", "dampak"),
            (r"\boutstanding\s+principal\b", "sisa pokok kewajiban"),
            (r"\boutstanding\b", "saldo kewajiban yang masih terutang"),
            (r"\bseluruh\s+gate\b", "seluruh tahap verifikasi"),
            (r"\blevel\s+provisional\b", "tingkat sementara"),
            (r"\bUnsur\s+keterkaitan:\s*existing_\d+\b",
             "Unsur keterkaitan: terdapat sumber terkait yang masih perlu diverifikasi"),
            (r"keterkaitan\s+semantik\s+CREDIT\s*,\s*FIDUCIARY\s*,\s*LOSS",
             "keterkaitan topik kredit, fidusia, dan kerugian"),
            (r"keterkaitan\s+semantik\s+CREDIT\s*,\s*RESPONSIBILITY",
             "keterkaitan topik kredit dan tanggung jawab"),
            (r"keterkaitan\s+semantik\s+CREDIT", "keterkaitan topik kredit"),
            (r"keterkaitan\s+semantik\s+LOSS", "keterkaitan topik kerugian"),
        )
        for pattern, replacement in final_render_patterns:
            text = re.sub(pattern, replacement, text, flags=re.I)

        # v1.2.9 reader-quality normalization.  These are bounded phrases
        # observed at the real render boundary, not generic semantic rewrites.
        natural_language_patterns = (
            (r"kerugian\s+nyata\s*\(\s*kerugian\s+nyata\s*\)",
             "kerugian nyata"),
            (r"kontribusi\s+pihak\s+lain\s*/\s*(?:tindakan\s+atau\s+faktor\s+perantara|faktor\s+atau\s+tindakan\s+intervensi\s+pihak\s+lain)",
             "kontribusi atau tindakan pihak lain yang memengaruhi hubungan kausal"),
            (r"rantai\s+keputusan-akibat\s*/\s*(?:tindakan\s+atau\s+faktor\s+perantara|faktor\s+atau\s+tindakan\s+intervensi\s+pihak\s+lain)",
             "rantai keputusan-akibat serta faktor atau tindakan perantara"),
            (r"\brecovery\b", "pemulihan kerugian/aset"),
            (r"berdasarkan\s+record\s+yang\s+tersedia",
             "berdasarkan data yang tersedia"),
            (r"melalui\s+tempus\s+engine",
             "melalui mekanisme verifikasi waktu berlaku"),
            (r"tidak\s+di-hard-code\s+sebagai\s+dasar\s+final",
             "tidak ditetapkan secara tetap sebagai dasar final"),
            (r"sumber\s+non-pleading",
             "sumber di luar dokumen argumentasi para pihak"),
        )
        for pattern, replacement in natural_language_patterns:
            text = re.sub(pattern, replacement, text, flags=re.I)

        # v1.3.0 final micro-normalization guard. These replacements are
        # deliberately literal and case-sensitive so only the observed
        # reader-facing phrases/labels are changed at the render boundary.
        final_micro_normalization = (
            ("missing link", "keterputusan uraian"),
            ("Missing Link", "keterputusan uraian"),
            ("merits", "pokok perkara"),
            ("Merits", "pokok perkara"),
            ("Personal responsibility", "Pertanggungjawaban individual"),
            ("personal responsibility", "Pertanggungjawaban individual"),
            ("Provision Citation:", "Tautan Sumber Resmi:"),
            ("Source:", "Sumber:"),
            ("Domain:", "Ranah hukum:"),
            ("[CRITICAL]", "[KRITIS]"),
            ("Status review:", "Status penelaahan:"),
            ("Review ini", "Penelaahan ini"),
            ("Ringkasan Review Hukum", "Ringkasan Penelaahan Hukum"),
            ("diverifikasi lawyer", "diverifikasi profesional hukum"),
            ("wajib diverifikasi lawyer", "wajib diverifikasi profesional hukum"),
            ("Versi tampilan: ADV-VIEW-1.1", "Mode tampilan: Pemisahan posisi para pihak"),
            ("Versi kontrak:", "Versi struktur analisis:"),
            ("Status struktur:", "Kelengkapan struktur analisis:"),
            ("Status semantik:", "Status verifikasi analisis:"),
            ("Urutan wajib:", "Urutan analisis:"),
            ("tanggal cut-off", "tanggal batas perhitungan"),
            ("mode mode deterministik lokal", "mode deterministik lokal"),
            ("Mode Mode Deterministik Lokal", "Mode Deterministik Lokal"),
            # v1.3.0 reader-facing macro polish retained at the final string boundary.
            # Branding is rendered from a literal outside this sanitizer, so the
            # Evidence-to-Action masthead remains untouched.
            ("CASE ANALYSIS", "ANALISIS PERKARA"),
            ("Case Analysis", "Analisis Perkara"),
            ("menjawab gap ini", "menjawab kekosongan pembuktian ini"),
            ("menutup gap ini", "menutup kekosongan pembuktian ini"),
            ("Keterkaitan Materi Perkara", "keterkaitan materi perkara"),
            ("adanya fee", "adanya imbalan/komisi"),
            ("bukti fee", "bukti imbalan/komisi"),
            ("aliran dana fee", "aliran dana imbalan/komisi"),
            ("adanya kickback", "adanya pembayaran balik tidak sah"),
            ("bukti kickback", "bukti pembayaran balik tidak sah"),
            ("aliran dana kickback", "aliran dana pembayaran balik tidak sah"),
        )
        for old, new in final_micro_normalization:
            text = text.replace(old, new)

        # v1.3.5 reader-facing OCR typography repair.  This list is deliberately
        # bounded to joined/obviously malformed word forms observed in the final
        # benchmark.  It changes only exported strings; the canonical/raw source
        # ledger remains untouched for audit and evidentiary traceability.
        joined_word_repairs = (
            (r"\bhariini\b", "hari ini"),
            (r"\btanggalDua\b", "tanggal Dua"),
            (r"\bPenyidikKejaksaan\b", "Penyidik Kejaksaan"),
            (r"\bBlitarNomor\b", "Blitar Nomor"),
            (r"\bDirekturUtama\b", "Direktur Utama"),
            (r"\bKredityang\b", "Kredit yang"),
            (r"\bdiberikankepada\b", "diberikan kepada"),
            (r"\bmemilikiusaha\b", "memiliki usaha"),
            (r"\bkreditmaksimal\b", "kredit maksimal"),
            (r"\bsetiapbulannnya\b", "setiap bulannya"),
            (r"\bpersetujuankreditadalah\b", "persetujuan kredit adalah"),
            (r"\bKreditkepada\b", "Kredit kepada"),
            (r"\btelahditambahdan\b", "telah ditambah dan"),
            (r"\btelahditambah\b", "telah ditambah"),
            (r"\btentangPerubahan\b", "tentang Perubahan"),
            (r"\bpersyaratanadministratifyang\b", "persyaratan administratif yang"),
            (r"\bfotokopidata\b", "fotokopi data"),
            (r"\bditindakianjuti\b", "ditindaklanjuti"),
            (r"\btindaklanjutsurvey\b", "tindak lanjut survei"),
            (r"\bSelanjutnyadilakukanoleh\b", "Selanjutnya dilakukan oleh"),
            (r"\bdata-datayang\b", "data-data yang"),
            (r"\bkreditoleh\b", "kredit oleh"),
            (r"\bkreditterdiridani\b", "kredit terdiri dari"),
            (r"\bSelanjutnyadata\b", "Selanjutnya data"),
            (r"\btersebutdisajikandan\b", "tersebut disajikan dan"),
            (r"\bterdiridani\b", "terdiri dari"),
            (r"\bterkaitijinusaha\b", "terkait izin usaha"),
            (r"\bBlitarsaya\b", "Blitar saya"),
            (r"\bijinusahanya\b", "izin usahanya"),
            (r"\bintermediasiadalah\b", "intermediasi adalah"),
            (r"\bkerjatelahterlaksana\b", "kerja telah terlaksana"),
            (r"\bunitkerjaatau\b", "unit kerja atau"),
            (r"\bdireksiyang\b", "direksi yang"),
            (r"\bDiperlihatkankepada\b", "Diperlihatkan kepada"),
            (r"\btanggal(?=\d{1,2}\b)", "tanggal "),
            (r"\bditandatanganioleh\b", "ditandatangani oleh"),
            (r"\bBlitardan\b", "Blitar dan"),
            (r"\bdebiturwajib\b", "debitur wajib"),
            (r"\btidakboleh\b", "tidak boleh"),
            (r"\bPraj[aA]ada\b", "Praja ada"),
            (r"\bsendirimenjadi\b", "sendiri menjadi"),
        )
        for pattern, replacement in joined_word_repairs:
            text = re.sub(pattern, replacement, text, flags=re.I)

        # Punctuation spacing cleanup after joined-word repair.  Keep this
        # intentionally narrow so citations, article numbers, and URLs are not
        # rewritten.
        text = re.sub(r",(?=[A-Za-zÀ-ÿ])", ", ", text)
        text = re.sub(r";(?=[A-Za-zÀ-ÿ])", "; ", text)

        # Reader-facing audit reference: preserve traceability without exposing
        # the internal SAL ledger identifier/hash.
        text = re.sub(
            r"ID audit\s+SAL_CONTRACT_LEDGER_(\d{4})_[A-F0-9]+",
            lambda m: f"Referensi Audit: {m.group(1)}",
            text,
            flags=re.I,
        )
        return text

    _ACTION_KEYS = {
        "actions",
        "recommended_actions",
        "recommended_action",
        "rencana_tindakan",
        "tindakan",
    }

    @staticmethod
    def _action_fingerprint(action) -> str:
        """Fingerprint the text that is actually rendered for an action node.

        Canonical action dictionaries can carry different provenance/issue metadata
        while rendering the same ``action`` text.  Deduplicating the whole dict
        therefore misses visual duplicates.  Prefer the reader-visible action field
        and fall back to a stable structural fingerprint only when no display text
        exists.  This remains presentation-only and never mutates the source node.
        """
        if isinstance(action, str):
            return " ".join(action.split()).casefold()
        if isinstance(action, dict):
            for key in ("action", "recommendation", "instruction"):
                value=action.get(key)
                if isinstance(value, str) and value.strip():
                    return " ".join(value.split()).casefold()
            # ``issue`` is rendered only as a fallback by the canonical-chain export.
            value=action.get("issue")
            if isinstance(value, str) and value.strip():
                return "issue:" + " ".join(value.split()).casefold()
            parts=[]
            for key in sorted(action):
                value=action.get(key)
                if isinstance(value, (str, int, float, bool)) or value is None:
                    parts.append((str(key), " ".join(str(value or "").split()).casefold()))
                else:
                    parts.append((str(key), repr(value)))
            return repr(parts)
        return repr(action)

    @classmethod
    def deduplicate_actions(cls, actions):
        """Remove duplicate action nodes only; never deduplicate generic lists."""
        if not isinstance(actions, list):
            return actions
        seen=set()
        out=[]
        for action in actions:
            fp=cls._action_fingerprint(action)
            if fp in seen:
                continue
            seen.add(fp)
            out.append(action)
        return out

    @classmethod
    def sanitize_object(cls, obj, *, is_civil: bool = False):
        if isinstance(obj, dict):
            cleaned={}
            for k,v in obj.items():
                value=cls.sanitize_object(v, is_civil=is_civil)
                if str(k) in cls._ACTION_KEYS and isinstance(value, list):
                    value=cls.deduplicate_actions(value)
                cleaned[k]=value
            return cleaned
        if isinstance(obj, list):
            return [cls.sanitize_object(v, is_civil=is_civil) for v in obj]
        if isinstance(obj, tuple):
            return tuple(cls.sanitize_object(v, is_civil=is_civil) for v in obj)
        if isinstance(obj, str):
            return cls.clean_text(obj, is_civil=is_civil)
        return obj


class LexiCoreLowLevelRenderGovernor:
    """Low-level presentation boundary for PDF/DOCX renderers.

    The governor is deliberately presentation-only: it receives already-built
    export strings and may only sanitize their visual representation or skip an
    immediately duplicated rendered action line. It never mutates the canonical
    analysis payload.
    """

    _ACTION_SECTION_HEADINGS = frozenset({
        "RANTAI PENALARAN HUKUM KANONIK",
        "CANONICAL LEGAL REASONING CHAIN",
        "RENCANA TINDAKAN",
        "ACTION PLAN",
    })

    _ACTION_MARKERS = (
        "TINDAKAN:",
        "ACTION:",
        "Dapatkan dan uji bukti primer",
    )

    # Exact final-render substitutions. Specific phrases precede shorter ones.
    _UNIVERSAL_EXACT_REPLACEMENTS = (
        ("case keterkaitan", "Keterkaitan Materi Perkara"),
        ("candidate result", "Hasil Kandidat Hukum"),
        ("UNKNOWN_DATE", "Tanggal Belum Terverifikasi"),
        ("actual loss", "kerugian nyata"),
        ("intervening acts", "faktor atau tindakan intervensi pihak lain"),
        ("intervening act", "faktor atau tindakan intervensi pihak lain"),
        ("outstanding principal", "sisa pokok kewajiban"),
        ("LEGAL_VERIFICATION_REQUIRED", "DIPERLUKAN VERIFIKASI HUKUM POSITIF"),
        ("existing_4", "elemen keterkaitan aktif"),
        ("CREDIT", "Konteks Kredit"),
        ("FIDUCIARY", "Fidusia/Agunan"),
        ("LOSS", "Potensi Kerugian"),
        ("RESPONSIBILITY", "Tanggung Jawab Individual"),
        ("impact", "dampak nyata"),
    )

    _CIVIL_EXACT_REPLACEMENTS = (
        ("keberatan formil terhadap dakwaan atau forum",
         "keberatan formil terhadap gugatan, jawaban, atau forum"),
        ("norma yang dirujuk dalam dakwaan",
         "norma hukum yang dirujuk dalam posita gugatan"),
        ("SURAT DAKWAAN", "SURAT GUGATAN"),
        ("surat dakwaan", "surat gugatan"),
        ("teks dakwaan", "posita gugatan"),
        ("didakwakan", "digugat atau disengketakan"),
        ("Pengadilan Tipikor", "Pengadilan Negeri"),
    )

    def __init__(self, *, is_civil: bool = False):
        self.is_civil = bool(is_civil)
        self._inside_action_section = False
        self._last_rendered_action = None

    @staticmethod
    def _normalize_for_compare(value: str) -> str:
        return " ".join(str(value or "").split()).casefold()

    @classmethod
    def _is_action_line(cls, text: str) -> bool:
        value = str(text or "").strip()
        return any(marker in value for marker in cls._ACTION_MARKERS)

    def enter_section(self, heading: str) -> None:
        normalized = " ".join(str(heading or "").split()).upper()
        self._inside_action_section = normalized in self._ACTION_SECTION_HEADINGS
        self._last_rendered_action = None

    _BRAND_LITERALS = {
        "Evidence-to-Action Legal Working Paper",
    }

    def sanitize(self, value) -> str:
        # Brand identity is immutable reader-facing copy and must never be
        # translated by generic terminology cleanup.
        original = str(value if value is not None else "")
        if original in self._BRAND_LITERALS or original.startswith("Evidence-to-Action Case Analysis | "):
            return original

        # Exact boundary substitutions run first so previously-established
        # presentation mappings cannot consume the diagnostic token before this
        # governor applies the final production wording. The established sanitizer
        # then performs the broader safe phrase cleanup.
        text = original

        if self.is_civil:
            for old, new in self._CIVIL_EXACT_REPLACEMENTS:
                text = text.replace(old, new)

        for old, new in self._UNIVERSAL_EXACT_REPLACEMENTS:
            text = text.replace(old, new)

        return LexiCoreCivilPresentationSanitizer.clean_text(
            text, is_civil=self.is_civil
        )

    def intercept(self, value):
        """Return renderable text or ``None`` for an immediate duplicate action."""
        text = self.sanitize(value)

        if not self._inside_action_section:
            self._last_rendered_action = None
            return text

        if not self._is_action_line(text):
            self._last_rendered_action = None
            return text

        fingerprint = self._normalize_for_compare(text)
        if fingerprint == self._last_rendered_action:
            return None

        self._last_rendered_action = fingerprint
        return text


def _presentation_source_corpus(x) -> str:
    """Build a bounded presentation-only corpus for posture projection."""
    if not isinstance(x, dict):
        return ""
    chunks=[]
    for key in ("source_text", "raw_text", "document_text", "extracted_text", "text"):
        value=x.get(key)
        if isinstance(value, str) and value.strip():
            chunks.append(value[:12000])
    for ledger_key in ("material_source_ledger", "source_ledger", "sal_contract_ledger"):
        ledger=x.get(ledger_key) or []
        if isinstance(ledger, list):
            for item in ledger[:16]:
                if isinstance(item, dict):
                    value=item.get("statement") or item.get("text_payload") or item.get("text")
                    if value:
                        chunks.append(str(value)[:1800])
    return "\n".join(chunks)[:24000]


def clean_section_13_chain(chain_text: str) -> str:
    """Presentation-only cleanup for section 13; canonical payload is unchanged."""
    out = str(chain_text or "")
    for pattern, replacement in _READER_PHRASE_REPLACEMENTS:
        out = pattern.sub(replacement, out)
    out = re.sub(r"rantai\s+unsur\s+['\"]{2}", "rantai unsur yang belum terbentuk", out, flags=re.I)
    return out

def sanitize_section_14_text(value: str) -> str:
    """Hide internal role/domain variable names from reader-facing action-plan prose."""
    out = str(value or "")
    m_domain = re.search(r"ranah_hukum\s*=\s*([A-Z_]+)", out, re.I)
    m_role = re.search(r"posisi_pengguna\s*=\s*([A-Z_]+)", out, re.I)
    if m_domain:
        raw = m_domain.group(1).upper()
        label = {"PERDATA": "Perdata", "PIDANA": "Pidana", "TUN": "Tata Usaha Negara"}.get(raw, raw.replace("_", " ").title())
        out = re.sub(r"ranah_hukum\s*=\s*[A-Z_]+", f"kategori perkara: {label}", out, flags=re.I)
    if m_role:
        raw = m_role.group(1).upper()
        label = {
            "TIDAK_TERIDENTIFIKASI": "kedudukan pengguna belum teridentifikasi",
            "BELUM_TERIDENTIFIKASI": "kedudukan pengguna belum teridentifikasi",
        }.get(raw, raw.replace("_", " ").title())
        out = re.sub(r"posisi_pengguna\s*=\s*[A-Z_]+", label, out, flags=re.I)
    out = re.sub(r"\bplaybook\b", "panduan prosedural", out, flags=re.I)
    return out
"""Shared professional Case Analysis export model/formatting helpers."""

def _export_scalar(value):
    """Human-readable scalar for case export; never exposes Python repr noise."""
    if value is None:
        return '-'
    if isinstance(value, bool):
        return 'Ya' if value else 'Tidak'
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip() or '-'


_EXPORT_LABELS_ID = {
    "already established": "Sudah Teridentifikasi",
    "must be verified": "Wajib Diverifikasi",
    "not yet established": "Belum Terbukti / Belum Terverifikasi",
    "classification": "Klasifikasi", "general norm": "Norma Umum", "special norm": "Norma Khusus",
    "newer norm": "Norma Lebih Baru", "older norm": "Norma Lebih Lama", "legal reasoning": "Analisis Hukum",
    "recommendation for counsel": "Rekomendasi Counsel", "verification status": "Status Verifikasi",
    "current status": "Status Saat Ini", "why it matters": "Relevansi", "coverage note": "Catatan Cakupan"
}

def _export_label_id(key):
    raw=str(key or '').replace('_',' ').strip()
    return _EXPORT_LABELS_ID.get(raw.lower(), raw.title())



# Reader-facing projection only. Internal contract/status codes remain unchanged
# in the canonical payload and persistence layer.
_READER_STATUS_ID = {
    'PASS': 'Lolos',
    'HOLD': 'Ditahan untuk verifikasi',
    'READY': 'Siap ditampilkan',
    'MISSING': 'Belum tersedia',
    'NOT_INSTANTIATED': 'Belum dapat dibentuk',
    'BLOCKED_LAW_VERIFICATION': 'Ditahan — dasar hukum belum terverifikasi',
    'BLOCKED_ROUTE_CONTRACT': 'Ditahan — jalur data belum memenuhi kontrak',
    'NEXUS_NOT_ESTABLISHED': 'Hubungan sebab-akibat belum terbukti',
    'NOT_ASSESSED': 'Belum dinilai',
    'GAP': 'Masih terdapat kekosongan pembuktian',
    'LINKED': 'Tindakan telah ditautkan',
    'MERITS': 'Pokok perkara',
    'PROCEDURAL': 'Prosedural',
    'COUNTER_ARGUMENT_ONLY': 'Hanya berupa dalil bantahan',
    'LEAD_ONLY': 'Petunjuk awal saja',
    'LIMITED': 'Terbatas',
    'REJECTED': 'Ditolak dari jalur pembuktian',
    'REJECTED_UNPROVEN': 'Ditolak — belum terbukti',
    'REJECTED_SUBJECT_MATTER_UNPROVEN': 'Ditolak — relevansi materi belum terbukti',
    'CANDIDATE': 'Kandidat — wajib diverifikasi',
    'WORKING_DRAFT_ONLY': 'Draf kerja — belum untuk dasar tindakan',
    'BAD_FAITH_NOT_ESTABLISHED_FROM_CURRENT_LEDGER': 'Niat buruk belum dapat dibuktikan dari sumber yang tersedia',
    'ACTUAL_IMPACT_NOT_ESTABLISHED_FROM_CURRENT_LEDGER': 'Dampak/kerugian nyata belum dapat dibuktikan dari sumber yang tersedia',
    'INTENT_EVIDENCE_PRESENT_NEEDS_TEST': 'Ada sumber terkait niat, tetapi masih harus diuji',
    'IMPACT_EVIDENCE_PRESENT_NEEDS_NEXUS_TEST': 'Ada sumber terkait dampak, tetapi hubungan sebab-akibat masih harus diuji',
    'ASSESS_AFTER_ELEMENT_AND_IMPACT_VERIFICATION': 'Dinilai setelah unsur dan dampak terverifikasi',
}

_READER_SEMANTIC_ID = {
    'FACT_ASSERTION': 'Pernyataan fakta yang belum terverifikasi',
    'DOCUMENT_REFERENCE': 'Referensi dokumen',
    'PARTY_ARGUMENT': 'Dalil pihak',
    'COUNTER_ARGUMENT': 'Dalil bantahan',
    'QUESTION': 'Pertanyaan pemeriksaan',
    'FUTURE_ACTION': 'Rencana tindakan',
    'EVIDENCE_CLAIM': 'Klaim mengenai bukti',
    'PRIMARY_EVIDENCE': 'Bukti primer',
    'LAW_CITATION': 'Rujukan hukum',
    'LEGAL_OPINION': 'Pendapat hukum',
    'METADATA': 'Informasi administratif / asal sumber',
}

def _reader_status(value):
    raw=str(value or '-').strip()
    return _READER_STATUS_ID.get(raw, raw.replace('_',' ').capitalize())

def _reader_semantic(value):
    raw=str(value or '-').strip()
    return _READER_SEMANTIC_ID.get(raw, raw.replace('_',' ').capitalize())

def _reader_strategy(value):
    raw=str(value or '-').strip()
    mapping={
        'MITIGATE_INTENT_ONLY_IF_PRIMARY_EVIDENCE_REMAINS_ABSENT': 'Batasi analisis mengenai niat apabila bukti primer tetap belum tersedia',
        'CHALLENGE_OR_LIMIT_CAUSAL_NEXUS': 'Uji dan batasi hubungan sebab-akibat yang belum terbukti',
        'SEEK_PROPORTIONATE_OUTCOME_IF_ONLY_LIMITED_VIOLATION_ESTABLISHED': 'Ajukan hasil yang proporsional apabila hanya pelanggaran terbatas yang terbukti',
    }
    return mapping.get(raw, raw.replace('_',' ').capitalize())

def _translate_status_id(value):
    m={
        'LOCAL CORPUS ARTICLE - OFFICIAL SOURCE VERIFICATION REQUIRED':'KORPUS LOKAL — WAJIB VERIFIKASI KE SUMBER RESMI',
        'LOCAL CORPUS RECORD - OFFICIAL SOURCE VERIFICATION REQUIRED':'KORPUS LOKAL — WAJIB VERIFIKASI KE SUMBER RESMI',
        'LOCAL_METADATA - OFFICIAL SOURCE VERIFICATION REQUIRED':'METADATA LOKAL — WAJIB VERIFIKASI KE SUMBER RESMI',
        'LOCAL_METADATA - OFFICIAL COURT SOURCE VERIFICATION REQUIRED':'METADATA LOKAL — WAJIB VERIFIKASI KE SUMBER PUTUSAN RESMI',
        'PROFESSIONAL VERIFICATION: PENDING':'VERIFIKASI PROFESIONAL: PENDING',
        'POTENTIAL_CONFLICT':'POTENSI KONFLIK','CONFIRMED_CONFLICT':'KONFLIK TERKONFIRMASI',
        'RELATIONSHIP_ONLY':'HANYA RELASI NORMA','PROMULGATED':'DIUNDANGKAN','EFFECTIVE':'MULAI BERLAKU'
    }
    return m.get(str(value), str(value))


_REVIEW_TYPE_ID={
    'TEMPUS_GAP':'Celah tempus / waktu perbuatan',
    'NUMBER_DATE_INCONSISTENCY':'Ketidaksesuaian nomor dan tanggal',
    'ENTITY_NAME_VARIANT':'Variasi identitas pihak',
    'FORUM_VS_MERITS':'Kompetensi/forum vs pokok perkara',
    'ERROR_IN_PERSONA_VS_ATTRIBUTION':'Error in persona vs atribusi perbuatan',
    'FIDUCIARY_NON_DISPOSITIVE':'Fidusia/agunan tidak menentukan hasil secara otomatis',
    'LEGAL_CITATION_ANOMALY':'Anomali rujukan hukum',
    'POTENTIAL_TEXT_TYPO':'Potensi salah ketik/OCR',
    'SOURCE_NOISE_HIGH':'Kandungan sumber nonmaterial tinggi',
    'EVIDENTIARY_GAP':'Celah pembuktian',
    'NO_VERIFIED_APPLICABLE_LAW':'Belum ada hukum berlaku yang terverifikasi',
    'DOCUMENT_STRUCTURE':'Struktur dokumen',
}
_EVIDENCE_CLASS_ID={
    'ACTUAL_EVIDENTIARY_ITEM':'Dokumen/bukti primer yang teridentifikasi',
    'EVIDENCE_ASSERTION':'Klaim mengenai keberadaan bukti/dokumen',
    'CASE_FACT':'Fakta perkara dari sumber non-pleading',
    'PLEADED_FACT':'Fakta yang didalilkan dalam dokumen',
    'ALLEGED_ROLE':'Peran/jabatan yang didalilkan',
    'LEGAL_ARGUMENT':'Argumentasi hukum',
    'HEADING_OR_SECTION':'Judul/bagian dokumen',
    'PLEADING_ASSERTION':'Dalil/pleading',
    'SOURCE_FACT':'Pernyataan sumber',
}

def _human_review_type(v):
    return _REVIEW_TYPE_ID.get(str(v or '').upper(), str(v or 'Temuan').replace('_',' ').title())

def _human_evidence_class(v):
    return _EVIDENCE_CLASS_ID.get(str(v or '').upper(), str(v or '-').replace('_',' ').title())

def _regulatory_export_lines(ri):
    if not isinstance(ri,dict): return []
    lines=[]
    articles=ri.get('articles') or []
    if articles:
        lines.append('Pasal Relevan:')
        for a in articles:
            if not isinstance(a,dict): continue
            citation=a.get('qualified_citation') or a.get('citation') or ((a.get('regulation') or '')+' - '+(a.get('article') or '')).strip(' -')
            if citation: lines.append('- '+str(citation))
            if a.get('text'): lines.append('  Uraian norma: '+str(a.get('text')))
            if a.get('topic'): lines.append('  Topik: '+str(a.get('topic')))
            if a.get('verification_status'): lines.append('  Status verifikasi: '+_translate_status_id(a.get('verification_status')))
    regulations=ri.get('regulations') or []
    if regulations:
        lines.append('Regulasi:')
        for r in regulations:
            if not isinstance(r,dict): continue
            title=r.get('title') or r.get('tentang') or r.get('number') or r.get('qualified_citation') or '-'
            number=r.get('number') or r.get('nomor')
            head=str(title)
            if number and str(number) not in head: head=f'{number} — {head}'
            lines.append('- '+head)
            details=[]
            if r.get('status'): details.append('Status: '+str(r.get('status')))
            if r.get('effective_date'): details.append('Berlaku: '+str(r.get('effective_date')))
            if r.get('authority_source'): details.append('Sumber otoritatif: '+str(r.get('authority_source')))
            if r.get('hierarchy_rank') not in (None,''): details.append('Tingkat hierarki: '+str(r.get('hierarchy_rank')))
            if details: lines.append('  '+' | '.join(details))
            if r.get('official_url'): lines.append('  Sumber resmi: '+str(r.get('official_url')))
            if r.get('verification_status'): lines.append('  Status verifikasi: '+_translate_status_id(r.get('verification_status')))
    relationships=ri.get('relationships') or []
    if relationships:
        lines.append('Relasi Hukum:')
        for rel in relationships:
            if not isinstance(rel,dict): continue
            src=rel.get('source_citation') or rel.get('source') or '-'
            typ=_translate_status_id(rel.get('relation_type') or rel.get('type') or 'TERKAIT_DENGAN')
            tgt=rel.get('target_citation') or rel.get('target') or '-'
            lines.append(f'- {src} → {typ} → {tgt}')
            if rel.get('basis'): lines.append('  Dasar relasi: '+str(rel.get('basis')))
            if rel.get('verification_status'): lines.append('  Status verifikasi: '+_translate_status_id(rel.get('verification_status')))
    timeline=ri.get('timeline') or []
    if timeline:
        lines.append('Linimasa Hukum:')
        for ev in timeline:
            if not isinstance(ev,dict): continue
            date=ev.get('date') or '-'; event=_translate_status_id(ev.get('event') or '-')
            citation=ev.get('qualified_citation') or ev.get('regulation') or ev.get('number') or '-'
            status=ev.get('status')
            line=f'- {date} — {event} — {citation}'
            if status: line += f' [{status}]'
            lines.append(line)
    return lines

def _norm_conflict_export_lines(nc):
    if not isinstance(nc,dict): return _export_item_lines(nc)
    lines=[]
    for i,c in enumerate(nc.get('conflicts_detected') or [],1):
        if not isinstance(c,dict): lines.append('- '+_export_scalar(c)); continue
        principle=c.get('rule_principle') or c.get('type') or 'Analisis Konflik Norma'
        lines.append(f'Potensi Konflik {i} — {principle}:')
        for key in ('classification','general_norm','special_norm','newer_norm','older_norm','legal_reasoning','recommendation_for_counsel','verification_status'):
            if c.get(key) not in (None,'',[],{}):
                val=_translate_status_id(c.get(key)) if key in ('classification','verification_status') else _export_scalar(c.get(key))
                lines.append(f'  {_export_label_id(key)}: {val}')
    if nc.get('coverage_note'):
        lines.append('Catatan Cakupan:')
        lines.append('  '+str(nc.get('coverage_note')))
    return lines

def _export_item_lines(value, prefix=''):
    """Flatten structured analysis into readable lines while preserving labels."""
    lines=[]
    if value is None:
        return lines
    if isinstance(value, str):
        if value.strip(): lines.append(prefix + value.strip())
        return lines
    if isinstance(value, (int, float, bool)):
        lines.append(prefix + _export_scalar(value)); return lines
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                # Prefer common legal-analysis keys before generic flattening.
                lead=(item.get('statement') or item.get('element') or item.get('issue') or item.get('title') or
                      item.get('action') or item.get('recommendation') or item.get('qualified_citation') or item.get('citation'))
                label=item.get('label') or item.get('status') or item.get('priority') or item.get('type')
                if lead:
                    head=(f'[{label}] ' if label else '') + _export_scalar(lead)
                    details=[]
                    for k,v in item.items():
                        if k in ('statement','element','issue','title','action','recommendation','qualified_citation','citation','label','status','priority','type') or v in (None,'',[],{}):
                            continue
                        if isinstance(v,(str,int,float,bool)):
                            details.append(f'{k.replace("_"," ").title()}: {_export_scalar(v)}')
                    lines.append(prefix + head + ((' | ' + ' | '.join(details)) if details else ''))
                else:
                    parts=[]
                    for k,v in item.items():
                        if v in (None,'',[],{}): continue
                        if isinstance(v,(str,int,float,bool)):
                            parts.append(f'{k.replace("_"," ").title()}: {_export_scalar(v)}')
                    if parts: lines.append(prefix + ' | '.join(parts))
            else:
                lines.extend(_export_item_lines(item,prefix))
        return lines
    if isinstance(value, dict):
        for k,v in value.items():
            if v in (None,'',[],{}): continue
            key=k.replace('_',' ').title()
            if isinstance(v,(str,int,float,bool)):
                lines.append(prefix + f'{key}: {_export_scalar(v)}')
            else:
                nested=_export_item_lines(v, prefix='')
                if nested:
                    lines.append(prefix + key + ':')
                    lines.extend(prefix + '  ' + n for n in nested)
        return lines
    return [prefix + str(value)]


def _regulation_allowed_for_case_domains(row, snapshot):
    domains={str(d.get('id')) for d in (snapshot.get('domains') or []) if isinstance(d,dict)}
    if not domains:
        return True
    reg=(row or {}).get('regulation') or {}
    hay=' '.join(str(reg.get(k) or '') for k in ('nomor','tentang','qualified_citation')).lower()
    hay += ' ' + ' '.join(str(a.get('pasal') or a.get('topic') or '') for a in ((row or {}).get('matched_articles') or []) if isinstance(a,dict)).lower()
    vocab={
        'financial_services':('bank','bpr','pojk','seojk','kredit','ojk'),
        'corruption':('tipikor','korupsi','pasal 603','penyalahgunaan kewenangan'),
        'criminal':('kuhp','kuhap','pidana','praperadilan','tersangka'),
        'civil_contract':('kuhperdata','burgerlijk','hukum perdata','perikatan','wanprestasi'),
        'corporate':('perseroan','uu no. 40 tahun 2007','direksi','komisaris'),
        'land_property':('uupa','agraria','pertanahan','sertipikat','sertifikat','bpn'),
        'religious_court':('peradilan agama','pengadilan agama','pasal 49'),
        'civil_procedure':('hir','rbg','rv','acara perdata','obscuur','plurium'),
        'regional_government':('bumd','perumda','pemerintah daerah'),
        'constitutional':('uud 1945','konstitusi'),
        'employment':('ketenagakerjaan','phk','pkwt','pesangon'),
    }
    allowed=tuple(v for d in domains for v in vocab.get(d,()))
    return not allowed or any(v in hay for v in allowed)



def _tempus_anchor_for_regulation(reg, snapshot):
    """Choose the legally relevant time anchor by regulation function.

    Substantive/sectoral norms are screened against the material event date;
    procedural norms are screened against the documented procedural/filing date.
    This avoids excluding a criminal-procedure statute merely because the
    underlying transaction happened years earlier.
    """
    reg=reg or {}; snapshot=snapshot or {}
    hay=(' '.join([str(reg.get('nomor') or ''),str(reg.get('tentang') or ''),' '.join(reg.get('domain_tags') or [])])).lower()
    procedural=any(k in hay for k in ('kuhap','acara pidana','hukum acara','peradilan umum','peradilan agama','ptun','kekuasaan kehakiman'))
    if procedural and snapshot.get('procedural_date_candidate'):
        return str(snapshot.get('procedural_date_candidate')), 'PROCEDURAL_DATE'
    if snapshot.get('event_date_candidate'):
        return str(snapshot.get('event_date_candidate')), 'MATERIAL_EVENT_DATE'
    if snapshot.get('event_year_candidate'):
        return str(snapshot.get('event_year_candidate')), 'YEAR_SCREENING_CANDIDATE'
    return None,'UNKNOWN'


def _tempus_status(reg, snapshot):
    anchor,anchor_type=_tempus_anchor_for_regulation(reg,snapshot)
    eff=str((reg or {}).get('effective_date') or (reg or {}).get('berlaku') or '')
    if not anchor or not eff: return 'UNVERIFIED',anchor_type
    criminal_substantive=any(k in (' '.join([str((reg or {}).get('nomor') or ''),str((reg or {}).get('tentang') or ''),' '.join((reg or {}).get('domain_tags') or [])])).lower() for k in ('kuhp','pidana materiil','pemberantasan tindak pidana korupsi','tipikor'))
    if len(anchor)>=10:
        if eff > anchor:
            return ('POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS' if criminal_substantive else 'POST_TEMPUS_EXCLUDED'),anchor_type
        return 'POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE',anchor_type
    if anchor[:4].isdigit() and eff[:4].isdigit():
        ey,ay=int(eff[:4]),int(anchor[:4])
        if ey>ay: return ('POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS' if criminal_substantive else 'POST_TEMPUS_EXCLUDED'),anchor_type
        if ey==ay: return 'TEMPUS_REQUIRES_EXACT_DATE',anchor_type
        return 'POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE',anchor_type
    return 'UNVERIFIED',anchor_type



def _human_release_status(value):
    mapping={
        'PENDING':'Menunggu verifikasi profesional',
        'HOLD_FOR_VERIFICATION':'Tahan kesimpulan — verifikasi diperlukan',
        'REVISE_BEFORE_RELIANCE':'Perlu revisi sebelum dijadikan dasar tindakan',
        'PROVISIONAL_REVIEW_COMPLETE':'Review sementara selesai',
        'TEMPUS_REQUIRES_EXACT_DATE':'Tanggal perbuatan harus dipastikan',
        'POTENTIALLY_APPLICABLE - VERIFY OFFICIAL SOURCE':'Berpotensi relevan — verifikasi sumber resmi',
        'POST_TEMPUS_REQUIRES_TRANSITIONAL_ANALYSIS':'Terbit setelah peristiwa — perlu analisis ketentuan peralihan',
        'POST_TEMPUS_EXCLUDED':'Terbit setelah peristiwa — tidak dipakai sebagai dasar materiil',
        'UNVERIFIED':'Belum diverifikasi',
        'PROCEDURAL_DATE':'Tanggal proses/prosedural',
        'MATERIAL_EVENT_DATE':'Tanggal peristiwa material',
        'YEAR_SCREENING_CANDIDATE':'Tahun indikatif — bukan tempus final',
        'UNKNOWN':'Belum ditentukan',
        'CASE_NEXUS_VERIFIED':'Relevansi terhadap perkara terverifikasi',
        'CASE_NEXUS_UNCERTAIN':'Relevansi terhadap perkara belum pasti',
        'NO_CASE_NEXUS':'Tidak relevan terhadap perkara',
        'VERIFIED_APPLICABLE':'Terverifikasi relevan dan berlaku',
        'VERIFIED_NOT_RELEVANT':'Terverifikasi tidak relevan',
        'IN_FORCE':'Berlaku',
        'AMENDED_IN_FORCE':'Berlaku dengan perubahan',
        'REVOKED':'Dicabut/tidak berlaku',
        'STATUS_UNCERTAIN':'Status hukum belum pasti',
        'TEMPUS_VERIFIED':'Waktu berlaku terverifikasi',
        'TEMPUS_UNVERIFIED':'Waktu berlaku belum terverifikasi',
        'PROVISION_VERIFIED':'Pasal terverifikasi pada teks resmi',
        'PROVISION_PARTIALLY_VERIFIED':'Sebagian pasal terverifikasi',
        'PROVISION_UNVERIFIED':'Pasal belum terverifikasi',
        'REQUIRES_VERIFICATION':'Perlu verifikasi',
        'PROVISIONALLY_SUPPORTED':'Dukungan sementara — tetap perlu verifikasi',
        'EVIDENCE_NEXUS_FOUND_LAW_UNVERIFIED':'Bukti terkait ditemukan — dasar hukum belum terverifikasi',
        'SEMANTIC_NEXUS_ONLY':'Keterkaitan topik ditemukan — daya bukti belum cukup',
        'PARTIAL_OFFICIAL_SOURCE_ACCESS':'Akses ke sumber resmi tersedia sebagian',
        'FULL_OFFICIAL_SOURCE_ACCESS':'Akses ke sumber resmi tersedia',
        'COMPLETE':'Pembacaan selesai',
        'DOCX_TEXT':'Teks dokumen DOCX',
        'PDF_TEXT':'Teks dokumen PDF',
        'HIGH':'Tinggi','MEDIUM':'Sedang','LOW':'Rendah','NONE':'Belum memadai',
        'REBUILD_OBJECTION_AROUND_FORMAL_DEFECTS':'Bangun ulang eksepsi berfokus pada cacat formil/prosedural',
        'ISSUE_EVIDENCE_LAW_RECOMMENDATION':'Isu → bukti → hukum → rekomendasi',
        'EKSEPSI_OR_OBJECTION':'Eksepsi / nota keberatan',
        'CIVIL_PLEADING':'Dokumen gugatan/perdata',
        'CRIMINAL_PLEADING':'Dokumen perkara pidana',
        'CONTRACT':'Kontrak/perjanjian',
        'LEGAL_DOCUMENT':'Dokumen hukum',
    }
    return mapping.get(str(value),str(value or '-'))


def _privacy_compact_source_context(x, max_chars=1050):
    """Return lawyer-facing context without contact/identity boilerplate.

    The raw source remains in the internal source ledger.  This projection is
    intentionally conservative: it removes obvious personal identifiers and
    prefers material/procedural context over letterhead/representation metadata.
    """
    source=re.sub(r'\s+',' ',str((x or {}).get('source_text') or '')).strip()
    if not source:
        return ''
    # Remove email, phone, NIK/KTP-like identifiers, and common advocate/contact boilerplate.
    source=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[email disembunyikan]',source)
    source=re.sub(r'(?i)\b(?:hp|telp|tlp|telepon)\.?\s*[:.]?\s*[+()\d][\d\s().-]{6,}\b','[kontak disembunyikan]',source)
    source=re.sub(r'(?i)\b(?:NIK|KTP\s*No\.?|No\.?\s*KTP)\s*[:.]?\s*\d{8,18}\b','[identitas disembunyikan]',source)
    source=re.sub(r'\b\d{16}\b','[identitas disembunyikan]',source)
    # Prefer substantive entry points if present.
    lows=source.lower()
    starts=[]
    for phrase in ('kasus posisi','dakwaan jaksa','terdakwa diajukan','dalam dakwaan','eksepsi kewenangan'):
        i=lows.find(phrase)
        if i>=0: starts.append(i)
    if starts:
        source=source[min(starts):]
    # Remove obvious representation-address clauses when they survive extraction.
    source=re.sub(r'(?i)para advokat[^.]{0,420}beralamat[^.]{0,420}\.?','',source)
    source=re.sub(r'(?i)kesemuanya beralamat kantor[^.]{0,420}\.?','',source)
    source=re.sub(r'\s+',' ',source).strip()
    return source[:max_chars].rstrip(' ,;:-')




def _resolved_document_header_label(x):
    """Presentation-only document identity label from SSoT with bounded civil fallback."""
    review=(x or {}).get('professional_review') or {}
    st=review.get('document_structure') or {}
    identity=(st.get('resolved_document_identity') or (x or {}).get('adversarial_document_identity') or {})
    posture=identity.get('document_posture') or st.get('display_document_type') or st.get('document_type') or '-'
    role=identity.get('speaker_role')
    generic=str(posture or '').strip().lower() in {'-', 'dokumen hukum', 'unknown', 'tidak teridentifikasi'} or 'kepemilikan suara belum terverifikasi' in str(posture or '').lower()
    if generic:
        civil_label=LexiCoreCivilPresentationSanitizer.resolve_civil_posture_label(_presentation_source_corpus(x))
        if civil_label:
            return civil_label
    suffix={
        'PROSECUTOR':' [Kubu Penuntutan]',
        'DEFENSE_COUNSEL':' [Kubu Pertahanan]',
        'INTERROGATOR_AND_SUSPECT':' [Dokumen Pemeriksaan Resmi]',
    }.get(role,'')
    return _human_release_status(str(posture))+suffix

def _reader_case_domain(x):
    dc=(x or {}).get('domain_classification') or (x or {}).get('domain_contract') or {}
    ranah=str(dc.get('ranah_hukum') or '').upper()
    if ranah:
        return ranah
    label=_resolved_document_header_label(x).lower()
    if any(k in label for k in ('replik','duplik','gugatan','jawaban perdata','jawaban gugatan')):
        return 'PERDATA'
    return ''


def _reader_strategy_projection(x, value):
    try:
        from extractors.pleading_cleaner import sanitize_strategy
        return sanitize_strategy(value, domain=_reader_case_domain(x))
    except Exception:
        return value




def _unique_preserve_order(values, limit=8):
    out=[]
    seen=set()
    for value in values:
        text=re.sub(r'\s+',' ',str(value or '')).strip(' ;,.-')
        if not text:
            continue
        key=text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out)>=limit:
            break
    return out


def _reader_case_context_projection(x):
    """Build a bounded, source-grounded case-context projection for the exporter.

    Presentation only: this helper does not classify admissibility, determine guilt,
    upgrade applicable law, or create a charging conclusion.  It surfaces what is
    expressly present in the uploaded source and states when indictment/sentencing
    material is not part of that source.
    """
    src=re.sub(r'\s+',' ',str((x or {}).get('source_text') or '')).strip()
    if not src:
        return []

    label=_resolved_document_header_label(x)
    label_low=str(label or '').lower()
    src_low=src.lower()
    lines=['Status dokumen/proses: '+str(label)]

    # A short factual orientation, selected only from source sentences/fragments.
    # Boilerplate/letterhead is deliberately de-prioritised.
    fragments=re.split(r'(?<=[.;!?])\s+|(?<=:)\s+(?=[A-Z])', src)
    material=[]
    material_keys=(
        'perjanjian kredit','pemberian kredit','kredit','debitur','tersangka','terdakwa',
        'direktur','kerugian','jaminan','fidusia','pencairan','persetujuan','perbuatan',
        'wanprestasi','pembayaran','agunan','kontrak','perjanjian','gugatan','sengketa'
    )
    boilerplate_keys=('demi keadilan','berita acara pemeriksaan tersangka','nama :','nip.','pangkat :','jabatan : jaksa')
    for frag in fragments:
        t=re.sub(r'\s+',' ',frag).strip(' -_;')
        lo=t.lower()
        if len(t)<45 or len(t)>520:
            continue
        if any(k in lo for k in boilerplate_keys):
            continue
        score=sum(1 for k in material_keys if k in lo)
        if score:
            material.append((score,t))
    material.sort(key=lambda item:(-item[0], len(item[1])))
    selected=_unique_preserve_order([t for _,t in material], limit=3)
    if selected:
        lines.append('Duduk perkara ringkas dari sumber: '+' '.join(selected)[:1450])
    else:
        compact=_privacy_compact_source_context(x, max_chars=900)
        if compact:
            lines.append('Duduk perkara ringkas dari sumber: '+compact)

    # Surface article and instrument identities exactly as source mentions them.
    pasal_matches=re.findall(r'(?i)\bPasal\s+\d+[A-Za-z]?(?:\s+ayat\s*\(\s*\d+\s*\))?(?:\s+huruf\s+[a-z])?', src)
    pasals=_unique_preserve_order(pasal_matches, limit=10)
    if pasals:
        lines.append('Pasal yang disebut dalam sumber: '+', '.join(pasals))

    instrument_patterns=[
        r'(?i)\bUndang[- ]Undang(?:\s+Republik\s+Indonesia)?\s+Nomor\s+\d+\s+Tahun\s+\d{4}(?:\s+tentang\s+[^.;]{3,140})?',
        r'(?i)\bUU\s+(?:RI\s+)?(?:No\.?|Nomor)\s*\d+\s+Tahun\s+\d{4}(?:\s+tentang\s+[^.;]{3,140})?',
    ]
    instruments=[]
    for pattern in instrument_patterns:
        instruments.extend(re.findall(pattern, src))
    instruments=_unique_preserve_order(instruments, limit=8)
    if instruments:
        lines.append('Undang-undang/instrumen yang disebut dalam sumber: '+'; '.join(instruments))

    # Do not convert an investigation record into an indictment or sentencing demand.
    is_bap=('berita acara pemeriksaan' in label_low or 'interogasi' in label_low or
            'berita acara pemeriksaan tersangka' in src_low)
    has_indictment=bool(re.search(r'(?i)\bsurat\s+dakwaan\b|\bdakwaan\s+jaksa\b', src))
    has_demand=bool(re.search(r'(?i)\bsurat\s+tuntutan\b|\bmenuntut\s+agar\b|\btuntutan\s+pidana\b', src))

    if is_bap:
        lines.append('Status dakwaan/tuntutan: sumber yang dianalisis adalah BAP/pemeriksaan tersangka. Surat dakwaan dan tuntutan pidana tidak boleh dianggap tersedia hanya dari dokumen ini.')
    elif has_indictment:
        lines.append('Status dakwaan: uraian/surat dakwaan terdeteksi dalam sumber dan harus dibaca sesuai teks sumber; status verifikasi tetap mengikuti hasil analisis LexiCore.')
    else:
        lines.append('Status dakwaan: tidak teridentifikasi secara eksplisit dalam sumber yang dianalisis.')
    if not has_demand:
        lines.append('Tuntutan atau lama pidana yang diminta penuntut: tidak teridentifikasi secara eksplisit dalam sumber ini.')
    else:
        lines.append('Tuntutan pidana: terdeteksi dalam sumber; nilai/lamanya harus dibaca dan diverifikasi langsung terhadap bagian tuntutan sumber.')

    return lines

def _executive_legal_review_lines(x):
    """Build lawyer-facing top-level review from Professional Review findings."""
    review=(x or {}).get('professional_review') or {}
    findings=review.get('findings') or []
    sr=review.get('strategic_recommendation') or {}
    lines=[]
    if review:
        lines.append('Status: '+_human_release_status(review.get('review_status') or '-'))
        st=(review.get('document_structure') or {})
        lines.append('Dokumen: '+_resolved_document_header_label(x))
    if findings:
        lines.append('Matriks temuan utama: [Aspek] | [Posisi/teks dokumen] | [Temuan] | [Rekomendasi]')
        for f in findings[:8]:
            aspect=_human_review_type(f.get('type') or 'Temuan')
            src=re.sub(r'\s+',' ',str(f.get('source_text') or '')).strip()[:240] or '-'
            finding=re.sub(r'\s+',' ',str(f.get('finding') or '')).strip()
            rec=re.sub(r'\s+',' ',str(f.get('recommendation') or '')).strip()
            sev=_human_release_status(f.get('severity') or '-')
            lines.append(f"{aspect} [{sev}] | {src} | {finding} | {rec}")
    priorities=(_reader_strategy_projection(x, sr.get('priorities') or []) or [])[:5]
    if priorities:
        lines.append('Arah strategi yang direkomendasikan:')
        lines += ['- '+str(v) for v in priorities]
    return lines


def _adaptive_reasoning_export_sections(x):
    """Project R34/R34.1 adaptive reasoning objects into lawyer-facing export sections.

    This is projection-only. It must never promote a mapping into a legal finding,
    modify readiness, or alter verification/tempus/applicability state.
    """
    sections=[]
    issue_tests=x.get('issue_element_tests') or []
    element_matrix=x.get('element_matrix') or []
    mappings=x.get('evidence_to_element_mapping') or []
    summary=x.get('element_test_summary') or {}
    causation=x.get('causation_analysis') or {}
    risks=x.get('risk_assessment') or []
    mitigation=x.get('mitigation_strategy') or {}
    pleading=x.get('pleading_strategy') or {}

    if issue_tests or element_matrix:
        lines=[]
        if summary:
            lines.append(
                f"Element mapping: {summary.get('assessed',0)}/{summary.get('total',len(element_matrix))} "
                f"elemen memiliki mapping sumber ({summary.get('percentage',0)}%). "
                "Mapping sumber bukan kesimpulan bahwa unsur hukum terpenuhi."
            )
        if issue_tests:
            for idx,issue in enumerate(issue_tests[:10],1):
                lines.append(f"ISSUE {idx}: {issue.get('issue','-')}")
                lines.append(
                    f"  Status mapping: {issue.get('status','NOT_ESTABLISHED')} | "
                    f"Kesimpulan hukum: {issue.get('legal_conclusion','VERIFICATION_REQUIRED')}"
                )
                for elem in (issue.get('elements') or [])[:8]:
                    conf=round(float(elem.get('mapping_confidence') or 0)*100)
                    lines.append(
                        f"  ELEMENT: {elem.get('description','-')} | Status: {elem.get('status','NOT_ESTABLISHED')} | "
                        f"Mapping confidence: {conf}%"
                    )
                    support=elem.get('supporting_evidence') or []
                    counter=elem.get('counter_evidence') or []
                    if support:
                        for ev in support[:3]:
                            lines.append(f"    SUPPORT #{ev.get('source_index','-')}: {str(ev.get('statement') or '-')[:420]}")
                    else:
                        lines.append('    SUPPORT: Belum ada sumber yang dipetakan.')
                    if counter:
                        for ev in counter[:3]:
                            lines.append(f"    COUNTER #{ev.get('source_index','-')}: {str(ev.get('statement') or '-')[:420]}")
                    else:
                        lines.append('    COUNTER: Belum ada sumber kontra yang dipetakan.')
        else:
            for elem in element_matrix[:20]:
                lines.append(
                    f"ELEMENT: {elem.get('element') or elem.get('description') or '-'} | "
                    f"Status: {elem.get('status','NOT_ESTABLISHED')}"
                )
        lines.append('Catatan: seluruh status bersifat fail-closed dan memerlukan verifikasi profesional terhadap bukti primer dan norma resmi.')
        sections.append(('Element-by-Element Analysis',lines))

    if mappings:
        lines=['TABEL: [Elemen] | [Peran Bukti] | [Sumber] | [Pernyataan] | [Skor Mapping]']
        for row in mappings[:40]:
            lines.append(
                f"{row.get('element','-')} | {row.get('role','-')} | Source #{row.get('source_index','-')} | "
                f"{str(row.get('statement') or '-')[:430]} | {row.get('score','-')}"
            )
        lines.append('Evidence-to-element mapping menunjukkan keterkaitan sumber secara topikal; bukan penetapan kebenaran atau pemenuhan unsur.')
        sections.append(('Evidence-to-Element Matrix / Counter-Evidence',lines))

    if causation:
        lines=[f"Status hubungan sebab-akibat/dampak: {_reader_status(causation.get('status','NOT_ASSESSED'))}"]
        if causation.get('reason'):
            lines.append('Dasar: '+str(causation.get('reason')))
        if causation.get('element_id'):
            lines.append('Unsur keterkaitan: '+str(causation.get('element_id')))
        for ev in (causation.get('supporting_evidence') or [])[:4]:
            lines.append(f"- Bukti pendukung #{ev.get('source_index','-')}: {str(ev.get('statement') or '-')[:430]}")
        for ev in (causation.get('counter_evidence') or [])[:4]:
            lines.append(f"- Sumber bantahan #{ev.get('source_index','-')}: {str(ev.get('statement') or '-')[:430]}")
        lines.append('Kesimpulan kausal/impact tidak dinaikkan melampaui bukti primer, autentikasi, dan nexus normatif yang telah diverifikasi.')
        sections.append(('Hubungan Kausal dan Dampak',lines))

    if risks or mitigation:
        lines=[]
        if risks:
            lines.append('Klasifikasi risiko per isu:')
            for r in risks[:10]:
                conf=round(float(r.get('mapping_confidence') or 0)*100)
                lines.append(
                    f"- {_reader_status(r.get('classification','UNASSESSED'))} | {r.get('issue','-')} | "
                    f"Kekuatan pemetaan sumber: {conf}% | {r.get('basis','')}"
                )
        if mitigation:
            lines.append('Strategi mitigasi:')
            lines.append(
                f"- Niat/keadaan batin: {_reader_status(mitigation.get('intent','-'))} | Dampak: {_reader_status(mitigation.get('impact','-'))} | "
                f"Proporsionalitas: {_reader_status(mitigation.get('proportionality','-'))}"
            )
            for c in (mitigation.get('corrective_action') or [])[:8]:
                lines.append(f"- Tindakan korektif #{c.get('source_index','-')}: {str(c.get('statement') or '-')[:430]}")
        lines.append('Penilaian risiko dan mitigasi merupakan strategi kerja berbasis pemetaan sumber dan tetap memerlukan verifikasi profesional.')
        sections.append(('Risiko dan Mitigasi',lines))

    if pleading.get('strategy_sequence'):
        lines=[
            'Status kesiapan dokumen: '+_reader_status(pleading.get('output_readiness') or 'WORKING_DRAFT_ONLY'),
            'Urutan strategi yang direkomendasikan:'
        ]
        lines += [f"- {_reader_strategy(v)}" for v in (pleading.get('strategy_sequence') or [])[:12]]
        if pleading.get('note'):
            lines.append('Catatan: '+str(pleading.get('note')))
        lines.append('Strategi ini tidak mengubah status fakta, tempus, keberlakuan hukum terhadap perkara, atau hasil verifikasi hukum positif.')
        sections.append(('Strategi Penyusunan Dokumen',lines))

    # SAL remains an internal audit/control layer and is intentionally omitted
    # from reader-facing PDF/DOCX exports.

    adv=x.get('adversarial_viewpoint_splitter') or {}
    if adv:
        lines=[
            'Versi tampilan: '+str(adv.get('contract_version') or 'ADV-VIEW-1.1'),
            'Kebijakan tampilan: Hanya membaca hasil analisis terverifikasi; tidak melakukan klasifikasi ulang',
            'Status tampilan: '+_reader_status(adv.get('status') or '-'),
        ]
        for title,key in [('POSISI JPU / PENUNTUTAN','prosecution'),('POSISI PH / PEMBELAAN','defense'),('SUMBER NETRAL / KEPEMILIKAN SUMBER BELUM TERVERIFIKASI','neutral')]:
            rows=adv.get(key) or []
            lines.append(title+': '+str(len(rows))+' pernyataan')
            for row in rows[:12]:
                lines.append('  ID audit '+str(row.get('statement_id') or '-')+' | '+_reader_status(row.get('admissibility_state') or '-')+' | '+_reader_semantic(row.get('semantic_type') or '-')+' | '+str(row.get('trace_label') or '-'))
                lines.append('    '+str(row.get('text') or '-')[:520])
                lines.append('    Tujuan analisis: '+str(row.get('target_node') or '-')+' | Jalur yang diizinkan: '+(', '.join(row.get('allowed_consumers') or []) or 'Tidak ada'))
        lines.append('Pernyataan tanpa izin jalur tidak ditampilkan: '+str(adv.get('blocked_without_route_token') or 0))
        lines.append('Catatan: bagian ini hanya menampilkan kepemilikan sumber dan asal-usul data analisis; tidak mengubah jenis pernyataan, status penerimaan, jalur analisis, atau kesimpulan hukum.')
        sections.append(('Pemisahan Posisi Para Pihak', lines))

    # Contract Migration V2: export the same canonical 11-stage object that is
    # persisted by the API. Do not reconstruct a parallel chain in the exporter.
    full_chain=x.get('legal_reasoning_chain') or {}
    contract=x.get('reasoning_contract') or {}
    if full_chain.get('chains'):
        lines=[
            'Versi kontrak: '+str(contract.get('contract_version') or full_chain.get('contract_version') or '2.0'),
            'Status struktur: '+_reader_status(contract.get('status') or full_chain.get('goal_status') or '-'),
            'Status semantik: '+_reader_status(contract.get('semantic_status') or '-'),
            'Urutan wajib: Isu -> Hukum yang Berlaku -> Unsur Hukum -> Perbuatan yang Didalilkan -> Bukti -> Bukti/Bantahan Lawan -> Uji Unsur -> Kausalitas -> Risiko -> Klasifikasi Prosedural/Pokok Perkara -> Tindakan yang Direkomendasikan',
        ]
        if contract.get('hard_semantic_violations'):
            lines.append('Hard semantic violations: '+str(len(contract.get('hard_semantic_violations') or [])))
            for v in (contract.get('hard_semantic_violations') or [])[:8]:
                lines.append('  VIOLATION: '+str(v.get('chain_id') or '-')+' | '+str(v.get('status') or v.get('kind') or '-'))
        for row in (full_chain.get('chains') or [])[:24]:
            if not isinstance(row,dict):
                continue
            lines.append(f"RANTAI {row.get('chain_id','-')} | Status: {_reader_status(row.get('status','-'))}")
            lines.append('  ISU: '+str((row.get('issue') or {}).get('value') or '-'))
            law=row.get('applicable_law') or {}; selected=law.get('selected') or {}
            law_text=law.get('rule') or (selected.get('source') if isinstance(selected,dict) else '') or '-'
            lines.append(f"  HUKUM YANG BERLAKU: {law_text} | Status verifikasi: {_reader_status(law.get('status','MISSING'))}")
            elem=row.get('legal_elements') or {}; lines.append(f"  UNSUR HUKUM: {elem.get('element','-')} | Status sumber: {_reader_status(elem.get('source_status','-'))}")
            act=row.get('alleged_act') or {}; lines.append(f"  PERBUATAN YANG DIDALILKAN: {act.get('value') or '-'} | {_reader_status(act.get('status','MISSING'))}")
            ev=row.get('evidence') or {}; evs=ev.get('items') or []
            lines.append(f"  BUKTI: {_reader_status(ev.get('status','MISSING'))} | {len(evs)} sumber terpetakan")
            for item in evs[:3]:
                lines.append(f"    PENDUKUNG #{item.get('source_index','-')}: {str(item.get('statement') or '-')[:360]}")
            counter=row.get('counter_evidence') or {}; cis=counter.get('items') or []
            lines.append(f"  BUKTI/BANTAHAN LAWAN: {_reader_status(counter.get('status','MISSING'))}")
            for item in cis[:3]:
                if isinstance(item,dict):
                    lines.append(f"    BANTAHAN #{item.get('source_index','-')}: {str(item.get('statement') or '-')[:360]}")
                else:
                    lines.append('    BANTAHAN: '+str(item)[:360])
            test=row.get('element_test') or {}; lines.append(f"  UJI UNSUR: {_reader_status(test.get('status','-'))} | Status: {_reader_status(test.get('gate','HOLD'))} | {test.get('reason','')}")
            cau=row.get('causation') or {}; lines.append(f"  KAUSALITAS: {_reader_status(cau.get('status','GAP'))} | {cau.get('value') or '-'}")
            risk=row.get('risk') or {}; lines.append(f"  RISIKO: {risk.get('level','-')} | {risk.get('value') or '-'}")
            cls=row.get('procedural_merits_classification') or {}; lines.append(f"  KLASIFIKASI PROSEDURAL/POKOK PERKARA: {_reader_status(cls.get('value','-'))}")
            actions=(row.get('recommended_action') or {}).get('actions') or []
            actions=LexiCoreCivilPresentationSanitizer.deduplicate_actions(actions)
            lines.append(f"  TINDAKAN YANG DIREKOMENDASIKAN: {_reader_status((row.get('recommended_action') or {}).get('status','MISSING'))}")
            for action in actions[:2]:
                lines.append('    TINDAKAN: '+str(action.get('action') or action.get('issue') or '-')[:420])
        lines.append('Rantai ini merupakan struktur keterlacakan. Kesimpulan materiil tetap ditahan apabila hukum, bukti, bantahan, atau kausalitas belum lolos verifikasi.')
        lines=[clean_section_13_chain(v) for v in lines]
        sections.append(('Rantai Penalaran Hukum Kanonik',lines))

    return sections

def _case_export_sections(x):
    """Single canonical export model for PDF and DOCX case-analysis results."""
    dr=x.get('document_reading') or {}
    provenance=x.get('analysis_provenance') or {}
    method=provenance.get('mode') or x.get('analytical_method') or 'CASE_ANALYSIS'
    provider=provenance.get('provider') or dr.get('provider') or '-'
    model=provenance.get('model') or dr.get('model') or '-'
    ingestion=x.get('document_ingestion') or {}
    if ingestion.get('manual_review_required'):
        _read_status='PARTIAL_SOURCE_COVERAGE - MANUAL_REVIEW_REQUIRED'
    else:
        _read_status=_human_release_status(dr.get('status','UNKNOWN'))
    meta=[
        ('Judul', x.get('title') or 'Case Analysis'),
        ('Metode analisis', 'Analisis lokal deterministik' if str(method).upper() in {'LOCAL_DETERMINISTIC','DETERMINISTIC_FALLBACK'} else _human_release_status(method)),
        ('Input', 'Dokumen' if str(x.get('input_type') or '').lower()=='document' else (x.get('input_type') or '-')),
        ('Dokumen', x.get('filename') or '-'),
        ('Pembacaan', f"{_read_status} - {dr.get('segments_read',0)}/{dr.get('segments_total',0)} bagian analitis - {dr.get('characters',0)} karakter"),
    ]
    if ingestion.get('mode'):
        meta.append(('Pembacaan dokumen', f"{_human_release_status(ingestion.get('mode'))} - teks asli {ingestion.get('pages_native',0)} hlm - OCR {ingestion.get('pages_ocr',0)} hlm - belum terbaca {ingestion.get('pages_failed',0)} hlm"))
        if ingestion.get('pages_ocr'):
            portability='PORTABLE' if ingestion.get('portable') else 'LOCAL FALLBACK'
            meta.append(('OCR', f"{ingestion.get('engine','embedded_rapidocr')} / {ingestion.get('language','-')} - {ingestion.get('characters_ocr',0)} karakter OCR - {portability}"))
            if ingestion.get('average_confidence') is not None:
                meta.append(('OCR Confidence', f"{float(ingestion.get('average_confidence'))*100:.1f}% rata-rata"))
        if ingestion.get('manual_review_required'):
            coverage=ingestion.get('coverage_ratio')
            coverage_txt=(f'{float(coverage)*100:.1f}%' if coverage is not None else '-')
            meta.append(('OCR Review', f"MANUAL_REVIEW_REQUIRED - coverage {coverage_txt}; teks parsial yang berhasil dibaca tetap dipertahankan untuk audit, tetapi tidak boleh dianggap pembacaan dokumen lengkap."))
        warnings=[str(x) for x in (ingestion.get('warnings') or []) if str(x).strip()]
        if warnings:
            meta.append(('OCR Diagnostics', ' | '.join(warnings[:3])[:520]))
    if dr.get('failure_stage'):
        reasons=[]
        for item in dr.get('segment_trace') or []:
            if isinstance(item,dict) and item.get('reason'):
                reasons.append(str(item.get('reason')))
        reasons=list(dict.fromkeys(reasons))[:4]
        trace=f"{dr.get('failure_stage')}"
        if reasons: trace += ' | ' + ', '.join(reasons)
        meta.append(('AI Pipeline', trace))
        failures=dr.get('failures') or []
        if failures:
            detail=str(failures[0]).replace('\n',' ').strip()[:280]
            if detail:
                meta.append(('AI Failure Detail', detail))
    meta.append(('Verifikasi profesional', _human_release_status(x.get('professional_verification') or 'PENDING')))
    sections=[]

    # v1.3.5 reader hierarchy: the factual/source context is the opening Roman
    # section. The strategic legal review is intentionally delayed until after
    # Evidence Map so the reader sees source -> readiness -> evidence -> review.
    executive_review=_executive_legal_review_lines(x)
    _executive_review_inserted=False

    source_context=_privacy_compact_source_context(x)
    context_lines=[]
    if x.get('title'):
        context_lines.append('Perkara: '+str(x.get('title')))
    if x.get('filename'):
        context_lines.append('Dokumen: '+str(x.get('filename')))
    context_lines.extend(_reader_case_context_projection(x))
    if source_context:
        context_lines.append('Konteks sumber material (belum merupakan fakta terbukti): '+source_context)
    if context_lines:
        sections.append(('Konteks Perkara / Sumber', context_lines))
    # v1.3.4: the former "Working Paper Terperinci" heading was only a wrapper
    # sentence for the analytical sub-sections. It is intentionally omitted from
    # reader-facing numbering; the substantive Audit Dokumen Terperinci remains.

    wp=x.get('case_working_paper') or {}
    if wp:
        pct=wp.get('working_paper_percentage') or {}
        pct_lines=[f"Case Readiness / Analysis Completeness: {pct.get('percentage',0)}%", f"Confidence data/analisis: {pct.get('confidence','LOW')}"]
        if pct.get('variables_increasing'):
            pct_lines.append('Variabel penambah nilai:')
            for v in pct.get('variables_increasing')[:8]:
                pct_lines.append(f"- {v.get('impact',0):+} poin | {v.get('variable','-')} | {v.get('basis','-')}")
        if pct.get('variables_decreasing'):
            pct_lines.append('Variabel pengurang nilai:')
            for v in pct.get('variables_decreasing')[:8]:
                pct_lines.append(f"- {v.get('impact',0):+} poin | {v.get('variable','-')} | {v.get('basis','-')}")
        pct_lines.append(pct.get('disclaimer') or 'Estimasi analitis kertas kerja; bukan prediksi putusan.')
        sections.append(('Case Readiness / Analysis Completeness', pct_lines))

        em=wp.get('evidence_map') or {}; basis=em.get('legal_basis') or {}
        ev_lines=[f"Dasar pemetaan: {basis.get('citation','-')}", basis.get('note') or '']
        ev_lines.append('TABEL: [Sumber/Bukti Potensial] | [Proposisi Faktual yang Perlu Diuji] | [Status Pembuktian] | [Uji Lanjut]')
        for r in (em.get('rows') or [])[:28]:
            ev_lines.append(f"[{r.get('evidence_tool','-')}] | {r.get('fact_proved','-')} | {r.get('formal_strength','-')} | {r.get('opponent_evidence_weakness','-')}")
        sections.append(('Evidence Map / Pemetaan Bukti', ev_lines))

        # Move the former first-page Ringkasan Analisis Hukum to immediately
        # after Pemetaan Bukti. This is a presentation-order change only.
        if executive_review:
            sections.append(('Executive Legal Review', executive_review))
            _executive_review_inserted=True

        lc=wp.get('legal_construction') or {}
        legal_lines=['Jalinan utama: '+str(lc.get('synthesis') or x.get('legal_analysis') or '-')]
        for c in (lc.get('chains') or [])[:8]:
            score=c.get('evidence_nexus_score') or 0
            prob=c.get('probative_score') or 0
            nexus=(f" | Keterkaitan topik: {round(float(score)*100)}% — {c.get('evidence_nexus_reason','-')}" if score else '')
            probative=(f" | Bobot pembuktian: {_human_release_status(c.get('probative_level') or 'NONE')} ({round(float(prob)*100)}%) — {c.get('probative_reason','-')}" if prob or c.get('probative_reason') else '')
            legal_lines.append(f"ISU: {c.get('issue','-')} | FAKTA/DALIL: {c.get('material_fact','-')} | SUMBER: {_human_evidence_class(c.get('supporting_evidence','-'))} — {c.get('evidence_reference','-')}{nexus}{probative} | ATURAN: {c.get('legal_rule','-')} | ANALISIS: {c.get('causal_logic','-')} | STATUS: {_human_release_status(c.get('construction_status','-'))}")
        sections.append(('Analisis Hukum / Legal Construction', legal_lines))

        # R34.2 — project adaptive reasoning into dedicated export sections.
        # This is report-only and does not alter the reasoning or verification state.
        sections.extend(_adaptive_reasoning_export_sections(x))

        action_lines=[]
        for a in (wp.get('action_plan') or [])[:14]:
            action_lines.append(sanitize_section_14_text(f"Langkah {a.get('step','-')} | {a.get('time_window','-')} | {a.get('priority','P2')} | {a.get('action','-')} | Tujuan: {a.get('objective','-')} | Kondisi: {a.get('condition','-')}"))
        sections.append(('Action Plan / Rencana Tindakan', action_lines or ['Belum ada action plan taktis terstruktur.']))
    else:
        readiness=x.get('case_readiness') or {}
        if readiness:
            comp=readiness.get('components') or {}
            rlines=[f"Overall readiness: {readiness.get('overall_percentage',0)}%",
                    f"Evidence Map: {(comp.get('evidence_map') or {}).get('percentage',0)}%",
                    f"Analisis Hukum: {(comp.get('legal_analysis') or {}).get('percentage',0)}%",
                    f"Action Plan: {(comp.get('action_plan') or {}).get('percentage',0)}%",
                    readiness.get('disclaimer') or 'Bukan prediksi hasil perkara.']
            sections.append(('Case Readiness Review', rlines))
    # Fallback for payloads without a working-paper Evidence Map: preserve the
    # review rather than dropping it, placing it after the available opening
    # context/readiness material.
    if executive_review and not _executive_review_inserted:
        sections.append(('Executive Legal Review', executive_review))

    review=x.get('professional_review') or {}
    if review:
        review_lines=[
            f"Status review: {_human_release_status(review.get('review_status','-'))}",
            f"Tipe dokumen: {_resolved_document_header_label(x)}",
        ]
        st=review.get('document_structure') or {}
        if st.get('completeness') is not None:
            review_lines.append(f"Kelengkapan struktur terdeteksi: {st.get('completeness')}%")
        if review.get('strengths'):
            review_lines.append('Kekuatan yang teridentifikasi:')
            review_lines += ['- '+str(v) for v in review.get('strengths')[:8]]
        if review.get('findings'):
            review_lines.append('Temuan kritis dan kelemahan:')
            for f in review.get('findings')[:18]:
                line=f"- [{_human_release_status(f.get('severity','-'))}] {_human_review_type(f.get('type'))}: {f.get('finding','-')}"
                if f.get('source_text'): line += f" | Teks sumber: {f.get('source_text')}"
                if f.get('candidate'):
                    cand=str(f.get('candidate'))
                    if cand.lower().startswith('kandidat:'): cand=cand.split(':',1)[1].strip()
                    line += f" | Kandidat: {cand}"
                if f.get('recommendation'): line += f" | Rekomendasi: {f.get('recommendation')}"
                review_lines.append(line)
        if review.get('recommendations'):
            review_lines.append('Rekomendasi prioritas:')
            for r in review.get('recommendations')[:14]:
                review_lines.append(f"- {r.get('priority','P2')} | {r.get('action','-')} | Dasar: {r.get('basis','-')}")
        sr=review.get('strategic_recommendation') or {}
        if sr:
            review_lines.append('Rekomendasi strategis penyusunan:')
            if sr.get('approach'): review_lines.append('Pendekatan: '+_human_release_status(sr.get('approach')))
            review_lines += ['- '+str(v) for v in (_reader_strategy_projection(x, sr.get('priorities') or []) or [])[:10]]
            if sr.get('recommended_outline'):
                review_lines.append('Struktur yang direkomendasikan:')
                review_lines += [f"{i}. {v}" for i,v in enumerate((_reader_strategy_projection(x, sr.get('recommended_outline') or []) or [])[:12],1)]
        review_lines.append(review.get('disclaimer') or '')
        sections.append(('Audit Dokumen Terperinci', review_lines))

    summary_lines=_export_item_lines(x.get('executive_summary') or x.get('decision_summary') or x.get('legal_analysis') or '-')
    if executive_review:
        summary_lines=summary_lines[:2]
        summary_lines.append('Detail temuan dan rekomendasi tersedia pada Ringkasan Review Hukum dan Audit Dokumen Terperinci.')
    sections.append(('Ringkasan Eksekutif', summary_lines))

    ledger=x.get('material_source_ledger') or []
    source_lines=[]

    def _sal_trace_label(item):
        semantic=str(item.get('sal_semantic_type') or '').upper().strip()
        speaker=str(item.get('sal_speaker_role') or '').upper().strip()
        epistemic=str(item.get('sal_epistemic_status') or '').upper().strip()
        if speaker == 'PROSECUTOR' and ('ALLEGATION' in epistemic or semantic == 'PARTY_ARGUMENT'):
            return 'Dalil Penuntutan / PROSECUTOR'
        if speaker == 'DEFENSE_COUNSEL' and ('REBUTTAL' in epistemic or semantic in {'PARTY_ARGUMENT','COUNTER_ARGUMENT'}):
            return 'Dalil Pembelaan / DEFENSE_COUNSEL'
        mapping={
            'FUTURE_ACTION':'Rencana Tindakan / Pra-Litigasi',
            'DOCUMENT_REFERENCE':'Referensi Dokumen / Lead Only',
            'EVIDENCE_CLAIM':'Klaim Bukti / Lead Only',
            'PARTY_ARGUMENT':'Dalil / Proposisi Pihak',
            'COUNTER_ARGUMENT':'Bantahan / Proposisi Pihak',
            'PRIMARY_EVIDENCE':'Bukti Primer',
            'FACT_ASSERTION':'Pernyataan Fakta / Belum Terverifikasi',
            'LAW_CITATION':'Rujukan Hukum',
            'LEGAL_OPINION':'Pendapat Hukum',
            'QUESTION':'Konteks Pertanyaan',
            'METADATA':'Metadata',
        }
        if semantic in mapping:
            return mapping[semantic]
        # Compatibility-only fallback for pre-SAL records. This fallback is
        # display-only and cannot upgrade admissibility or routing.
        return _human_evidence_class(item.get('display_classification') or item.get('source_classification') or item.get('label') or 'SOURCE FACT')
    for item in ledger:
        if not isinstance(item,dict): continue
        label=_sal_trace_label(item)
        statement=item.get('statement') or '-'
        segment=item.get('segment')
        evidence=item.get('evidence')
        line=f'[{label}] {statement}' + (f' (Segmen {segment})' if segment else '')
        if evidence: line += f' | Dasar dokumen: {evidence}'
        source_lines.append(line)
    sections.append(('Jejak Sumber Material', source_lines or ['Tidak ada sumber material yang layak ditampilkan.']))

    # Evidence Map deliberately summarizes mapping and gaps; it does not repeat the raw document.
    counts={}; segs={}
    for item in ledger:
        if not isinstance(item,dict): continue
        label=str(item.get('label') or 'SOURCE FACT'); counts[label]=counts.get(label,0)+1
        seg=str(item.get('segment') or 'Tanpa segmen'); segs[seg]=segs.get(seg,0)+1
    evidence_lines=[f'{k}: {v} item' for k,v in sorted(counts.items())]
    groups=x.get('evidence_groups') or []
    if groups:
        evidence_lines.append('EVIDENCE GROUPS:')
        for g in groups[:12]:
            evidence_lines.append(f"{g.get('label') or g.get('id')}: {g.get('item_count',0)} item")
            for fact in (g.get('material_facts') or [])[:6]:
                evidence_lines.append('  - '+str(fact))
    else:
        evidence_lines += [f'Segmen {k}: {v} item evidence' for k,v in list(segs.items())[:40]]
    gaps=x.get('evidentiary_gaps') or x.get('evidence_needed') or []
    if gaps:
        evidence_lines.append('EVIDENTIARY GAPS:')
        evidence_lines += ['- '+line for line in _export_item_lines(gaps)]
    if not wp:
        sections.append(('Evidence Map', evidence_lines or ['Belum ada evidence map terstruktur.']))

    legal=[]
    if x.get('legal_status'): legal.append('Status hukum positif: '+_export_scalar(x.get('legal_status')))
    if x.get('legal_analysis'): legal.append('Analisis utama: '+_export_scalar(x.get('legal_analysis')))
    for label,key in [('Mens rea / niat','mens_rea_analysis'),('Actual loss / kerugian nyata','actual_loss_analysis'),('Causal nexus','causation_analysis'),('Personal responsibility','personal_responsibility_analysis'),('Tempus / hukum temporal','temporal_law_analysis')]:
        if x.get(key): legal.append(f'{label}: {_export_scalar(x.get(key))}')
    if x.get('legal_issues'):
        legal.append('Isu hukum:'); legal += ['- '+v for v in _export_item_lines(x.get('legal_issues'))]
    if x.get('element_matrix'):
        legal.append('Matriks unsur:'); legal += ['- '+v for v in _export_item_lines(x.get('element_matrix'))]
    ets=x.get('element_test_summary') or {}
    if ets:
        legal.append(f"Element test: {ets.get('assessed',0)}/{ets.get('total',0)} elemen memiliki mapping sumber ({ets.get('percentage',0)}%); pemenuhan unsur secara hukum belum diklaim.")
    em=x.get('evidence_to_element_mapping') or []
    if em:
        legal.append('Evidence-to-Element:')
        for row in em[:14]:
            legal.append(f"- {row.get('element')} | {row.get('role')} | Source #{row.get('source_index')} | {row.get('statement','')[:260]}")
    issue_tests=x.get('issue_element_tests') or []
    if issue_tests:
        legal.append('ISSUE -> ELEMENT -> EVIDENCE -> COUNTER-EVIDENCE:')
        for issue in issue_tests[:8]:
            legal.append(f"ISSUE: {issue.get('issue','-')} | Status mapping: {issue.get('status','NOT_ESTABLISHED')} | Legal conclusion: {issue.get('legal_conclusion','VERIFICATION_REQUIRED')}")
            for elem in (issue.get('elements') or [])[:6]:
                legal.append(f"  ELEMENT: {elem.get('description','-')} | {elem.get('status','NOT_ESTABLISHED')} | mapping confidence={round(float(elem.get('mapping_confidence') or 0)*100)}%")
                for ev in (elem.get('supporting_evidence') or [])[:2]: legal.append(f"    SUPPORT #{ev.get('source_index')}: {ev.get('statement','')[:220]}")
                for ev in (elem.get('counter_evidence') or [])[:2]: legal.append(f"    COUNTER #{ev.get('source_index')}: {ev.get('statement','')[:220]}")
    risks=x.get('risk_assessment') or []
    if risks:
        legal.append('RISK CLASSIFICATION:')
        for r in risks[:8]: legal.append(f"- {r.get('classification','UNASSESSED')} | {r.get('issue','-')} | {r.get('basis','')}")
    mitigation=x.get('mitigation_strategy') or {}
    if mitigation:
        legal.append(f"MITIGATION: intent={mitigation.get('intent','-')} | impact={mitigation.get('impact','-')} | proportionality={mitigation.get('proportionality','-')}")
        for c in (mitigation.get('corrective_action') or [])[:6]: legal.append(f"- Corrective action #{c.get('source_index')}: {c.get('statement','')[:240]}")
    pleading=x.get('pleading_strategy') or {}
    if pleading.get('strategy_sequence'):
        legal.append('RECOMMENDED PLEADING STRATEGY:')
        legal += [f"- {v}" for v in pleading.get('strategy_sequence')[:10]]
        if pleading.get('note'): legal.append('Catatan: '+str(pleading.get('note')))
    if not wp:
        sections.append(('Analisis Hukum', legal or ['Belum ada analisis hukum terstruktur.']))
        sections.extend(_adaptive_reasoning_export_sections(x))

    applicable=x.get('applicable_law') or []
    _snap_for_law=x.get('case_regulatory_snapshot') or {}
    _funnel_for_law=_snap_for_law.get('retrieval_funnel') or {}
    _verified_law=int(_funnel_for_law.get('verified_applicable') or _funnel_for_law.get('temporal_verified_applicable') or 0)
    law_title='Dasar Hukum Terverifikasi' if _verified_law>0 else 'Kandidat Dasar Hukum yang Perlu Diverifikasi'
    sections.append((law_title, _export_item_lines(applicable) or ['Belum ada kandidat dasar hukum yang terstruktur.']))

    # Case report carries only regulatory essentials. Full corpus/intelligence remains in Regulatory Corpus workspace.
    regs=x.get('regulatory_matches') or []
    snap=x.get('case_regulatory_snapshot') or {}
    regs=[r for r in regs if isinstance(r,dict) and _regulation_allowed_for_case_domains(r, snap)]
    event_year=snap.get('event_year_candidate')
    event_date=snap.get('event_date_candidate')
    reg_lines=[]
    verified_official=[
        r for r in (snap.get('official_results') or [])
        if isinstance(r,dict) and regulation_merits_reportable(r)
    ]
    for r in verified_official[:8]:
        v=r.get('positive_law_verification') or {}
        title=r.get('canonical_title') or r.get('title') or '-'
        line=(f"{title} | Sumber resmi: {'Terkonfirmasi' if v.get('official_source_confirmed') else 'Belum terkonfirmasi'}"
              f" | Teks hukum: {'Tersedia' if v.get('text_retrieved') else 'Belum terverifikasi'}"
              f" | Status norma: {_human_release_status(v.get('legal_status') or 'UNVERIFIED')}"
              f" | Waktu berlaku: {_human_release_status(v.get('tempus_status') or 'TEMPUS_UNVERIFIED')}"
              f" | Acuan waktu: {_human_release_status(v.get('tempus_anchor_type') or 'UNKNOWN')}"
              f" | Keterkaitan perkara: {_human_release_status(v.get('case_nexus_status') or 'CASE_NEXUS_UNCERTAIN')}"
              f" | Status akhir: {_human_release_status(v.get('final_status') or 'UNVERIFIED')}")
        pv=v.get('provision_verification') or {}
        if pv.get('requested_count'):
            refs=', '.join(pv.get('verified') or pv.get('requested') or [])
            line += (f" | Verifikasi pasal: {_human_release_status(pv.get('status') or 'PROVISION_UNVERIFIED')}"
                     f" ({pv.get('verified_count',0)}/{pv.get('requested_count',0)}"
                     + (f": {refs}" if refs else '') + ')')
            cites=pv.get('citations') or []
            if cites and cites[0].get('source_url'):
                line += f" | Provision Citation: {cites[0].get('source_url')}"
        reg_lines.append(line)
    if not reg_lines:
        for r in regs[:8]:
            if not isinstance(r,dict): continue
            g=r.get('regulation') or {}
            title=g.get('qualified_citation') or g.get('nomor') or g.get('tentang') or '-'
            temporal,anchor_type=_tempus_status(g,snap)
            line=f"{title} | Waktu berlaku: {_human_release_status(temporal)} | Acuan waktu: {_human_release_status(anchor_type)}"
            arts=r.get('matched_articles') or []
            if arts:
                refs=[]
                for a in arts[:4]:
                    if isinstance(a,dict): refs.append((a.get('qualified_citation') or a.get('pasal') or a.get('topic') or '').strip())
                if refs: line += ' | Relevansi: ' + '; '.join(refs)
            reg_lines.append(line)
    sections.append(('Regulasi & Tempus', reg_lines or ['Belum ada regulasi material yang dapat dinyatakan applicable tanpa verifikasi sumber resmi.']))

    nc=x.get('norm_conflicts') or {}
    conflict_lines=_norm_conflict_export_lines(nc)
    sections.append(('Analisis Konflik Norma', conflict_lines or ['Tidak ada antinomi material yang terdeteksi; hubungan hierarki/kronologi saja tidak diperlakukan sebagai konflik norma.']))

    action=x.get('action_plan') or x.get('recommendations') or []
    action_lines=[]
    if isinstance(action,dict):
        # Export only WHAT TO DO, matching the UI contract.
        for key in ('what_to_do','actions','priorities','next_steps'):
            if action.get(key): action_lines += _export_item_lines(action.get(key))
        if not action_lines:
            for k,v in action.items():
                if any(word in k.lower() for word in ('action','do','step','priority','recommend')):
                    action_lines += _export_item_lines(v)
    else:
        action_lines=_export_item_lines(action)
    if not wp:
        sections.append(('Action Plan / Langkah Tindak Lanjut', action_lines or ['Belum ada action plan terstruktur.']))

    ov=x.get('official_verification') or {}
    snap=x.get('case_regulatory_snapshot') or {}
    funnel=snap.get('retrieval_funnel') or {}
    verify_lines=[]
    if ov or snap:
        sm=ov.get('summary') or {} if isinstance(ov,dict) else {}
        verify_lines += [
            'Status akses sumber: '+_human_release_status((ov or {}).get('status') if isinstance(ov,dict) else '-'),
            'Waktu pemeriksaan: '+_export_scalar((ov or {}).get('checked_at') if isinstance(ov,dict) else snap.get('fetched_at')),
            'Verifikasi profesional: '+_human_release_status((ov or {}).get('professional_verification') if isinstance(ov,dict) else snap.get('professional_verification') or 'PENDING'),
            f"Sumber otoritatif terjangkau: {sm.get('authoritative_sources_reached',0)}/{sm.get('authoritative_sources_total',0)}",
        ]
        if funnel:
            verify_lines += [
                'Hasil penelusuran: '+str(funnel.get('discovered',0)),
                'Hasil unik setelah penyaringan: '+str(funnel.get('unique_discovered',0)),
                'Kandidat yang berpotensi relevan: '+str(funnel.get('candidate',0)),
                'Relevan secara material: '+str(funnel.get('materially_relevant',0)),
                'Lolos filter tempus awal: '+str(funnel.get('temporal_not_excluded',0)),
                'Sumber otoritatif ditemukan: '+str(funnel.get('authoritative_source_located',0)),
                'Kandidat dokumen hukum: '+str(funnel.get('legal_document_candidates',0)),
                'Konten resmi non-hukum ditolak: '+str(funnel.get('rejected_non_legal_content',0)),
                'Fetch sumber resmi dicoba: '+str(funnel.get('fetch_attempted',0)),
                'Fetch sumber resmi terjangkau: '+str(funnel.get('fetch_reachable',0)),
                'Identitas instrumen terverifikasi: '+str(funnel.get('instrument_identity_verified',0)),
                'Tidak dicoba karena budget verifikasi: '+str(funnel.get('not_attempted_budget_exceeded',0)),
                'Status hukum positif terverifikasi: '+str(funnel.get('positive_law_verified',0)),
                'Tempus terverifikasi: '+str(funnel.get('tempus_verified',0)),
                'Regulasi terverifikasi relevan dan berlaku: '+str(funnel.get('verified_applicable',funnel.get('temporal_verified_applicable',0))),
                'Pasal yang diperiksa: '+str(funnel.get('provision_requested',0)),
                'Pasal ditemukan pada teks resmi: '+str(funnel.get('provision_located',0)),
                'Pasal yang berhasil diverifikasi pada teks resmi: '+str(funnel.get('provision_verified',0)),
            ]
            diagnostics=snap.get('verification_diagnostics') or []
            if diagnostics:
                verify_lines.append('Diagnostik identity untuk pasal located tetapi belum verified:')
                for idx,d in enumerate(diagnostics[:6],1):
                    if not isinstance(d,dict):
                        continue
                    expected=d.get('expected_instrument_key') or '-'
                    exact_lock=bool(d.get('exact_lock_active'))
                    resolved_raw=d.get('resolved_instrument_key')
                    resolved='' if exact_lock and not resolved_raw else (resolved_raw or '-')
                    reason=d.get('identity_match_reason') or '-'
                    nexus=d.get('case_nexus_status') or '-'
                    req=', '.join(str(x) for x in (d.get('requested_provisions') or [])) or '-'
                    loc=', '.join(str(x) for x in (d.get('located_provisions') or [])) or '-'
                    candidates=', '.join(str(x) for x in (d.get('identity_candidates') or [])[:4]) or '-'
                    verify_lines.append(
                        f"DIAG {idx} | expected={expected} | resolved={resolved} | identity={d.get('identity_confirmed')} | reason={reason} | exact_lock={exact_lock} | nexus={nexus} | requested={req} | located={loc} | candidates={candidates} | binding_preserved={bool(d.get('provision_binding_preserved'))}"
                    )
        elif sm:
            verify_lines.append('Hasil penelusuran: '+str(sm.get('results_found',0)))
        if snap.get('event_date_candidate'):
            verify_lines.append('Kandidat tanggal peristiwa material: '+str(snap.get('event_date_candidate')))
        if snap.get('procedural_date_candidate'):
            verify_lines.append('Kandidat tanggal proses/prosedural: '+str(snap.get('procedural_date_candidate')))
        elif snap.get('event_year_candidate'):
            verify_lines.append('Kandidat tahun peristiwa untuk screening tempus: '+str(snap.get('event_year_candidate')))
        domains=snap.get('domains') or []
        if domains:
            verify_lines.append('Ruang lingkup utama:')
            for d in domains[:4]:
                if isinstance(d,dict):
                    verify_lines.append(f"- {d.get('label') or d.get('id')} ({round(float(d.get('confidence',0))*100)}%)")
        verify_lines.append('Catatan: sumber resmi yang dapat dijangkau atau ditemukan belum berarti norma tersebut telah terverifikasi berlaku pada perkara. Verifikasi profesional masih diperlukan.')
    sections.append(('Pemeriksaan Sumber Hukum Resmi', verify_lines or ['Verifikasi sumber resmi tidak dijalankan / tidak tersedia.']))

    coverage=x.get('coverage_note') or 'Verifikasi profesional: Menunggu verifikasi lawyer.'
    sections.append(('Cakupan & Verifikasi Profesional', [coverage, f"Dokumen ini adalah working paper LexiCore untuk {get_identity_profile()['display_name']} dan wajib diverifikasi lawyer sebelum dipakai sebagai dasar tindakan hukum."]))

    # Unified Presentation Sanitizer v1.2.3: one final, presentation-only pass.
    # Civil terminology is gated by a strong civil posture label; universal
    # reader-facing token cleanup is safe across domains.
    _civil_label = LexiCoreCivilPresentationSanitizer.resolve_civil_posture_label(_presentation_source_corpus(x))
    _is_civil = bool(_civil_label) or _reader_case_domain(x) == 'PERDATA'
    sections = [
        (heading, LexiCoreCivilPresentationSanitizer.sanitize_object(lines, is_civil=_is_civil))
        for heading, lines in sections
    ]
    return meta, sections




# Reader-facing export presentation adapter. Kept in canonical common.py to satisfy release hygiene.
_SECTION_TITLES = {
    'Executive Legal Review': 'Ringkasan Analisis Hukum',
    'Konteks Perkara / Sumber': 'Konteks Perkara, Duduk Perkara, dan Sumber',
    'Working Paper Terperinci': 'Analisis Terperinci',
    'Case Readiness / Analysis Completeness': 'Kesiapan dan Kelengkapan Analisis',
    'Case Readiness Review': 'Kesiapan Analisis',
    'Evidence Map / Pemetaan Bukti': 'Pemetaan Bukti',
    'Evidence Map': 'Pemetaan Bukti',
    'Analisis Hukum / Legal Construction': 'Analisis Hukum',
    'Element-by-Element Analysis': 'Analisis Unsur Hukum',
    'Evidence-to-Element Matrix / Counter-Evidence': 'Matriks Bukti terhadap Unsur',
    'Causation / Impact': 'Hubungan Kausal dan Dampak',
    'Risk & Mitigation': 'Risiko dan Mitigasi',
    'Pleading Strategy': 'Strategi Penyusunan',
    'Action Plan / Rencana Tindakan': 'Rencana Tindakan',
    'Action Plan / Langkah Tindak Lanjut': 'Langkah Tindak Lanjut',
    'Regulasi & Tempus': 'Dasar Hukum dan Waktu Berlaku',
    'Pemeriksaan Sumber Hukum Resmi': 'Verifikasi Sumber Hukum Resmi',
    'Cakupan & Verifikasi Profesional': 'Catatan Cakupan dan Verifikasi Profesional',
}

_STATUS_REPLACEMENTS = {
    'WORKING_DRAFT_ONLY': 'Draf kerja — belum untuk dijadikan dasar tindakan',
    'VERIFICATION_REQUIRED': 'Perlu verifikasi',
    'REQUIRES_VERIFICATION': 'Perlu verifikasi',
    'NOT_ESTABLISHED': 'Belum dapat ditetapkan',
    'NOT_ASSESSED': 'Belum dinilai',
    'DISPUTED': 'Masih diperselisihkan',
    'PARTIALLY_SUPPORTED': 'Didukung sebagian',
    'PROVISIONALLY_SUPPORTED': 'Didukung sementara — tetap perlu verifikasi',
    'EVIDENCE_NEXUS_FOUND_LAW_UNVERIFIED': 'Bukti terkait ditemukan — dasar hukum belum terverifikasi',
    'SEMANTIC_NEXUS_ONLY': 'Keterkaitan topik ditemukan — daya bukti belum memadai',
    'MATERIAL_IF_PROVEN': 'Material apabila terbukti',
    'POTENTIAL': 'Potensi risiko',
    'LOWERED_BY_COUNTER_EVIDENCE': 'Risiko berkurang karena bukti kontra',
    'UNASSESSED': 'Belum dinilai',
    'INTENT_EVIDENCE_PRESENT_NEEDS_TEST': 'Indikasi niat tersedia dan perlu diuji',
    'IMPACT_EVIDENCE_PRESENT_NEEDS_NEXUS_TEST': 'Indikasi dampak tersedia dan keterkaitannya perlu diuji',
    'ASSESS_AFTER_ELEMENT_AND_IMPACT_VERIFICATION': 'Dinilai setelah unsur dan dampak terverifikasi',
    'CASE_NEXUS_VERIFIED': 'Keterkaitan dengan perkara terverifikasi',
    'CASE_NEXUS_UNCERTAIN': 'Keterkaitan dengan perkara belum pasti',
    'NO_CASE_NEXUS': 'Tidak memiliki keterkaitan yang cukup dengan perkara',
    'TEMPUS_VERIFIED': 'Waktu berlaku terverifikasi',
    'TEMPUS_UNVERIFIED': 'Waktu berlaku belum terverifikasi',
    'VERIFIED_APPLICABLE': 'Terverifikasi relevan dan berlaku',
    'PROVISION_VERIFIED': 'Pasal terverifikasi pada teks resmi',
    'PROVISION_PARTIALLY_VERIFIED': 'Sebagian pasal terverifikasi',
    'PROVISION_UNVERIFIED': 'Pasal belum terverifikasi',
    'LOCAL_DETERMINISTIC': 'Analisis berbasis dokumen dan aturan verifikasi LexiCore',
    'DETERMINISTIC_FALLBACK': 'Analisis berbasis dokumen dan aturan verifikasi LexiCore',
    'OCR_FALLBACK': 'Pembacaan dengan OCR lokal',
    'LOCAL FALLBACK': 'Pemrosesan lokal',
    'PORTABLE': 'Siap digunakan pada lingkungan yang didukung',
    'PENDING': 'Menunggu verifikasi profesional',
    'HIGH': 'Tinggi',
    'MEDIUM': 'Sedang',
    'LOW': 'Rendah',
    'NONE': 'Belum memadai',
}

_STRATEGY_REPLACEMENTS = {
    'DISTINGUISH AMBIGUOUS FACT AND CAPACITY': 'Pisahkan fakta yang masih ambigu dari kapasitas atau kedudukan para pihak',
    'SHOW CORRECTIVE ACTION': 'Tunjukkan tindakan korektif yang didukung bukti',
    'CHALLENGE OR LIMIT CAUSAL NEXUS': 'Uji atau batasi hubungan sebab-akibat yang belum terbukti',
    'REQUEST PROPORTIONAL OUTCOME IF LIMITED BREACH IS ESTABLISHED': 'Ajukan hasil yang proporsional apabila hanya pelanggaran terbatas yang terbukti',
}


def display_section_heading(heading: str) -> str:
    return _SECTION_TITLES.get(str(heading or ''), str(heading or ''))


def _replace_codes(text: str) -> str:
    out = str(text or '')
    for raw, human in sorted(_STATUS_REPLACEMENTS.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = re.sub(rf'(?<![A-Za-z0-9_]){re.escape(raw)}(?![A-Za-z0-9_])', human, out, flags=re.I)
    for raw, human in _STRATEGY_REPLACEMENTS.items():
        out = re.sub(re.escape(raw), human, out, flags=re.I)
    return out


def present_line(line: str) -> str:
    """Translate internal report vocabulary into professional reader-facing prose."""
    raw = str(line or '')
    if re.match(r'^\s*(?:DIAG\s+\d+\b|Diagnostik identity\b)', raw, re.I):
        return ''
    # Final renderer-boundary pass: _case_export_sections normally sanitizes
    # earlier, but every PDF/DOCX line must pass this function immediately
    # before rendering.  Re-applying universal cleanup here makes the contract
    # fail-safe if a section is assembled after the earlier sanitizer.
    raw = LexiCoreCivilPresentationSanitizer.clean_text(raw, is_civil=False)
    out = _replace_codes(raw)
    replacements = (
        (r'\bISSUE\s+(\d+)\s*:', r'ISU \1:'),
        (r'\bELEMENT\s*:', 'UNSUR:'),
        (r'\bSUPPORT\s*#', 'BUKTI PENDUKUNG #'),
        (r'\bCOUNTER\s*#', 'BUKTI KONTRA #'),
        (r'\bSUPPORT\s*:', 'BUKTI PENDUKUNG:'),
        (r'\bCOUNTER\s*:', 'BUKTI KONTRA:'),
        (r'\bSource\s*#', 'Sumber #'),
        (r'\bMapping confidence\b', 'Tingkat keterkaitan bukti'),
        (r'\bStatus mapping\b', 'Status pemetaan'),
        (r'\bOutput readiness\b', 'Status penyusunan'),
        (r'\bRisk classification per issue\b', 'Penilaian risiko per isu'),
        (r'\bMitigation strategy\b', 'Strategi mitigasi'),
        (r'\bCorrective action\b', 'Tindakan korektif'),
        (r'\bStatus nexus/impact\b', 'Status hubungan sebab-akibat dan dampak'),
        (r'\bElemen nexus\b', 'Unsur keterkaitan'),
        (r'\bnexus/impact\b', 'hubungan sebab-akibat dan dampak'),
        (r'\bnexus normatif\b', 'keterkaitan normatif'),
        (r'\bnexus\b', 'keterkaitan'),
        (r'\bapplicability\b', 'keberlakuan terhadap perkara'),
        (r'\bEvidence-to-element mapping\b', 'Pemetaan bukti terhadap unsur'),
        (r'\bElement mapping\b', 'Pemetaan unsur'),
        (r'\bmapping sumber\b', 'pemetaan sumber'),
        (r'\blegal satisfaction not claimed\b', 'belum ditarik kesimpulan bahwa unsur hukum terpenuhi'),
        (r'\bfail-closed\b', 'konservatif dan tidak menarik kesimpulan tanpa verifikasi'),
        (r'\bCase Readiness\s*/\s*Analysis Completeness\b', 'Kesiapan dan kelengkapan analisis'),
        (r'\bConfidence data/analisis\b', 'Tingkat keyakinan data/analisis'),
        (r'\bOverall readiness\b', 'Kesiapan keseluruhan'),
        (r'\bEvidence Map\b', 'Pemetaan bukti'),
        (r'\bAction Plan\b', 'Rencana tindakan'),
        (r'\bFetch sumber resmi dicoba\b', 'Sumber resmi yang dicoba diakses'),
        (r'\bFetch sumber resmi terjangkau\b', 'Sumber resmi yang berhasil diakses'),
        (r'\bTidak dicoba karena budget verifikasi\b', 'Tidak diperiksa karena batas waktu verifikasi'),
        (r'\bP1\b', 'Prioritas 1'),
        (r'\bP2\b', 'Prioritas 2'),
        (r'\bP3\b', 'Prioritas 3'),
        (r'\bWorking Paper\b', 'Kertas Kerja'),
        (r'\bProfessional Verification\b', 'Verifikasi Profesional'),
    )
    for pattern, replacement in replacements:
        out = re.sub(pattern, replacement, out, flags=re.I)
    out = re.sub(r'\s+\|\s+', ' | ', out)
    return out.strip()


def _present_meta_item(label: str, value: str) -> tuple[str, str] | None:
    label = str(label or '')
    value = str(value or '')
    # Internal engine/diagnostic detail belongs in logs, not in a lawyer-facing export.
    if label in {'OCR Diagnostics', 'AI Pipeline', 'AI Failure Detail', 'OCR Confidence'}:
        return None
    if label == 'Metode analisis':
        return ('Metode analisis', 'Analisis berbasis dokumen, bukti, dan verifikasi hukum')
    if label == 'Pembacaan dokumen':
        m = re.search(r'teks asli\s+(\d+)\s+hlm\s*-\s*OCR\s+(\d+)\s+hlm\s*-\s*belum terbaca\s+(\d+)\s+hlm', value, re.I)
        if m:
            native, ocr, failed = map(int, m.groups())
            parts=[]
            if native:
                parts.append(f'{native} halaman dibaca dari teks asli')
            if ocr:
                parts.append(f'{ocr} halaman dibaca melalui OCR')
            if failed:
                parts.append(f'{failed} halaman belum berhasil dibaca')
            else:
                parts.append('seluruh halaman berhasil dibaca')
            return ('Pembacaan dokumen', '; '.join(parts))
    if label == 'OCR':
        m = re.search(r'(\d+)\s+karakter\s+OCR', value, re.I)
        if m:
            return ('Hasil OCR', f"Berhasil mengekstrak {int(m.group(1)):,} karakter".replace(',', '.'))
        return ('Hasil OCR', 'Pembacaan OCR berhasil')
    if label == 'Pembacaan':
        # Retain completion/coverage information but remove implementation jargon.
        cleaned = present_line(value)
        cleaned = re.sub(r'\s*-\s*(\d+)\s+karakter\s*$', r' — \1 karakter terbaca', cleaned)
        return ('Status pembacaan', cleaned)
    return (label, present_line(value))


def _deduplicate_rendered_action_lines(heading: str, lines: Iterable[str]) -> List[str]:
    """Remove repeated rendered TINDAKAN lines within one canonical chain only.

    This is the final visual safety net.  It intentionally does not deduplicate
    evidence, issues, sources, or the Action Plan section.  The seen-set resets at
    each ``RANTAI`` boundary so identical actions in different chains remain visible.
    """
    values=list(lines or [])
    if display_section_heading(heading) != 'Rantai Penalaran Hukum Kanonik':
        return values
    out=[]
    seen=set()
    for line in values:
        text=str(line or '')
        if re.match(r'^\s*RANTAI\s+\S+', text, re.I):
            seen.clear()
        m=re.match(r'^\s*TINDAKAN:\s*(.+?)\s*$', text, re.I)
        if m:
            fp=' '.join(m.group(1).split()).casefold()
            if fp in seen:
                continue
            seen.add(fp)
        out.append(text)
    return out


def prepare_case_export_for_reader(meta: Iterable[Tuple[str, str]], sections: Iterable[Tuple[str, List[str]]]):
    """Return a presentation-only copy for PDF/DOCX rendering.

    The canonical ``_case_export_sections`` result remains untouched so machine
    contracts and regression tests keep their established schema.
    """
    clean_meta=[]
    for label, value in meta or []:
        row=_present_meta_item(label, value)
        if row is not None:
            clean_meta.append(row)
    clean_sections=[]
    for heading, lines in sections or []:
        rendered=[v for v in (present_line(line) for line in (lines or [])) if v]
        rendered=_deduplicate_rendered_action_lines(heading, rendered)
        clean_sections.append((display_section_heading(heading), rendered))
    return clean_meta, clean_sections
