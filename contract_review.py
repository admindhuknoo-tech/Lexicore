"""
LEXICORE - Contract Review & Analysis Engine

Deterministic contract review. The engine separates:
1) document/entity extraction,
2) contract-type classification,
3) clause coverage,
4) internal consistency,
5) obligation mapping,
6) risk findings and recommendations.

It does not invent legal citations or declare a clause unlawful merely from a
keyword. Positive-law conclusions must be verified through the Regulatory
Corpus / Legal Research layer.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict

import docx
from services.document_ocr import extract_pdf_text, extract_image_text
from services.legal_ocr_postprocess import postprocess_legal_ocr


# ============================================
# 1. DATA MODEL
# ============================================

@dataclass
class RiskClause:
    clause_text: str
    risk_level: str  # HIGH / MEDIUM / LOW
    category: str
    recommendation: str
    line_number: int


@dataclass
class ContractAnalysisResult:
    filename: str
    total_pages: int
    word_count: int
    parties: List[str]
    effective_date: str
    termination_date: str
    risks: List[RiskClause]
    summary: str
    review_timestamp: str
    contract_type: str
    contract_type_confidence: int
    key_terms: Dict[str, str]
    clause_coverage: List[Dict]
    missing_clauses: List[Dict]
    inconsistencies: List[Dict]
    obligations: List[Dict]
    clause_evaluations: List[Dict]
    review_framework: str = "DETERMINISTIC_DEEP_CLAUSE_EVALUATION_V3"


# ============================================
# 2. TEXT EXTRACTOR
# ============================================

class DocumentExtractor:
    @staticmethod
    def extract_text(file_path: str) -> str:
        ext = file_path.lower().rsplit('.', 1)[-1] if '.' in file_path else ''
        if ext == 'pdf':
            return DocumentExtractor._extract_pdf(file_path)
        if ext == 'docx':
            return DocumentExtractor._extract_docx(file_path)
        if ext in {'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff'}:
            text, _ = extract_image_text(file_path)
            return text
        raise ValueError("Format dokumen tidak didukung. Gunakan PDF, DOCX, PNG, JPG/JPEG, WEBP, atau TIFF.")

    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        text, _ = extract_pdf_text(file_path)
        return text

    @staticmethod
    def extract_with_diagnostics(file_path: str):
        """Return (text, ingestion diagnostics) for Case Analysis/audit UI."""
        ext = file_path.lower().rsplit('.', 1)[-1] if '.' in file_path else ''
        if ext == 'pdf':
            text, diag = extract_pdf_text(file_path)
            if (diag or {}).get('pages_ocr'):
                text, pp = postprocess_legal_ocr(text)
                diag['legal_ocr_postprocess'] = pp
            return text, diag
        if ext in {'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff'}:
            text, diag = extract_image_text(file_path)
            if text:
                text, pp = postprocess_legal_ocr(text)
                diag['legal_ocr_postprocess'] = pp
            return text, diag
        if ext == 'docx':
            text = DocumentExtractor._extract_docx(file_path)
            return text, {
                'enabled': False, 'available': False, 'engine': None, 'language': None,
                'mode': 'DOCX_TEXT', 'pages_total': 0, 'pages_native': 0, 'pages_ocr': 0,
                'pages_failed': 0, 'characters_native': len(text), 'characters_ocr': 0,
                'tesseract_cmd': None, 'warnings': []
            }
        raise ValueError("Format dokumen tidak didukung. Gunakan PDF, DOCX, PNG, JPG/JPEG, WEBP, atau TIFF.")

    @staticmethod
    def _extract_docx(file_path: str) -> str:
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)


# ============================================
# 3. ENTITY & COMMERCIAL TERM EXTRACTION
# ============================================

class EntityExtractor:
    MONTHS = "Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember"
    DATE = rf"\d{{1,2}}\s+(?:{MONTHS})\s+\d{{4}}"

    @staticmethod
    def _clean_party(value: str) -> str:
        value = re.sub(r'\s+', ' ', value or '').strip(' :-\t')
        return value[:120]

    @staticmethod
    def extract_parties(text: str) -> List[str]:
        """Extract the defining names, not later references to PIHAK PERTAMA/KEDUA."""
        parties: List[str] = []

        # Common compact format: "Pihak Pertama: PT X".
        for label in ('PIHAK PERTAMA', 'PIHAK KEDUA'):
            m = re.search(rf'{label}\s*[:\-]\s*([^\n,\.]+)', text, re.I)
            if m:
                value = EntityExtractor._clean_party(m.group(1))
                if len(value) > 2 and value not in parties:
                    parties.append(value)

        # Common Indonesian deed/contract identity block:
        # Nama: X ... Dalam hal ini ... selanjutnya disebut PIHAK PERTAMA.
        if len(parties) < 2:
            for label in ('PIHAK PERTAMA', 'PIHAK KEDUA'):
                m = re.search(
                    rf'Nama\s*:\s*([^\n]+)(?:(?!Nama\s*:).){{0,700}}?selanjutnya\s+(?:disebut\s+)?{label}',
                    text, re.I | re.S,
                )
                if m:
                    value = EntityExtractor._clean_party(m.group(1))
                    if value and not re.fullmatch(r'[-_. ]+', value) and value not in parties:
                        parties.append(value)

        if not parties:
            m = re.search(r'antara\s+([^\n]+?)\s+dengan\s+([^\n]+?)(?:,|\.|\n)', text, re.I)
            if m:
                parties = [EntityExtractor._clean_party(m.group(1)), EntityExtractor._clean_party(m.group(2))]

        return parties[:3] if parties else ["Tidak terdeteksi"]

    @staticmethod
    def extract_dates(text: str) -> Dict[str, str]:
        dates = {"effective_date": "Tidak ditemukan", "termination_date": "Tidak ditemukan"}
        dp = EntityExtractor.DATE

        # Best signal for Indonesian lease agreements.
        m = re.search(rf'(?:terhitung\s+)?(?:sejak|mulai)\s+(?:tanggal\s+)?({dp}).{{0,100}}?(?:sampai\s+dengan|hingga|berakhir\s+pada)\s+(?:tanggal\s+)?({dp})', text, re.I | re.S)
        if m:
            dates['effective_date'] = re.sub(r'\s+', ' ', m.group(1)).strip()
            dates['termination_date'] = re.sub(r'\s+', ' ', m.group(2)).strip()
            return dates

        m = re.search(rf'(?:efektif|berlaku|dimulai)\s*(?:pada|sejak|tanggal)?\s*({dp})', text, re.I)
        if m:
            dates['effective_date'] = m.group(1)
        m = re.search(rf'(?:berakhir|sampai\s+dengan|terminasi|expiry|termination)\s*(?:pada|tanggal)?\s*({dp})', text, re.I)
        if m:
            dates['termination_date'] = m.group(1)
        return dates

    @staticmethod
    def extract_key_terms(text: str, contract_type: str, dates: Dict[str, str]) -> Dict[str, str]:
        terms: Dict[str, str] = {
            'effective_date': dates.get('effective_date', 'Tidak ditemukan'),
            'termination_date': dates.get('termination_date', 'Tidak ditemukan'),
        }
        money = re.search(r'Rp\.?\s*[\d\.]+(?:,\d+)?', text, re.I)
        if money:
            terms['amount_detected'] = money.group(0)

        if contract_type == 'SEWA_MENYEWA':
            if re.search(r'\btempat\s+tinggal\b', text, re.I):
                terms['use'] = 'Tempat tinggal'
            else:
                use = re.search(r'(?:untuk\s+keperluan|dipergunakan\s+untuk|penggunaan)\s*[:\-]?\s*([^\n\.]{3,100})', text, re.I)
                if use:
                    terms['use'] = re.sub(r'\s+', ' ', use.group(1)).strip()

            address = re.search(r'Alamat\s*:\s*([^\n]{5,180})', text, re.I)
            if address:
                val = re.sub(r'\s+', ' ', address.group(1)).strip()
                if not re.fullmatch(r'[-_. ]+', val):
                    terms['object_address'] = val

            if re.search(r'pelunasan\s+(?:dari\s+)?seluruh\s+jumlah\s+uang\s+sewa|tanda\s+pelunasan', text, re.I):
                terms['payment_structure'] = 'Pembayaran di muka/pelunasan terindikasi'
            elif re.search(r'per\s+bulan|setiap\s+bulan|bulanan', text, re.I):
                terms['payment_structure'] = 'Pembayaran periodik/bulanan terindikasi'

            terms['deposit'] = 'Disebut' if re.search(r'\bdeposit\b|uang\s+jaminan', text, re.I) else 'Tidak terdeteksi'
        return terms


# ============================================
# 4. CONTRACT TYPE CLASSIFIER
# ============================================

class ContractTypeClassifier:
    RULES = {
        'SEWA_MENYEWA': [
            (r'\bsewa[\s-]*menyewa\b', 5), (r'\bpemberi\s+sewa\b', 4), (r'\bpenyewa\b', 3),
            (r'\bharga\s+sewa\b', 3), (r'\bobjek\s+sewa\b|rumah\s+yang\s+disewa', 3),
        ],
        'UTANG_PIUTANG': [(r'utang\s*piutang|hutang\s*piutang', 5), (r'\bdebitur\b', 3), (r'\bkreditur\b', 3), (r'pelunasan\s+utang', 2)],
        'KERJASAMA': [(r'perjanjian\s+kerja\s*sama|perjanjian\s+kerjasama', 5), (r'ruang\s+lingkup\s+kerja\s*sama', 3)],
        'KETENAGAKERJAAN': [(r'perjanjian\s+kerja', 5), (r'\bpekerja\b|\bkaryawan\b', 3), (r'\bupah\b|gaji', 2)],
        'NDA_KERAHASIAAN': [(r'non[-\s]?disclosure|perjanjian\s+kerahasiaan', 5), (r'informasi\s+rahasia', 3)],
        'JASA': [(r'perjanjian\s+jasa', 5), (r'pemberi\s+jasa|penerima\s+jasa', 3), (r'deliverable', 2)],
    }

    @staticmethod
    def detect(text: str) -> Tuple[str, int]:
        scores = {}
        for name, rules in ContractTypeClassifier.RULES.items():
            score = sum(weight for pat, weight in rules if re.search(pat, text, re.I))
            scores[name] = score
        best = max(scores, key=scores.get)
        best_score = scores[best]
        if best_score <= 0:
            return 'KONTRAK_UMUM', 30
        confidence = min(98, 45 + best_score * 6)
        return best, confidence


# ============================================
# 5. CLAUSE COVERAGE / CONSISTENCY / OBLIGATIONS
# ============================================

class ClauseAnalyzer:
    LEASE_REQUIREMENTS = [
        ('object', 'Objek sewa & identifikasi', (r'objek\s+sewa', r'rumah\s+(?:tersebut|yang\s+disewa)', r'ukuran\s+bangunan', r'luas\s*:')),
        ('use', 'Tujuan penggunaan', (r'tempat\s+tinggal', r'dipergunakan\s+untuk', r'keperluan\s+tempat')),
        ('term', 'Jangka waktu', (r'jangka\s+waktu', r'selama\s+\d+\s+(?:tahun|bulan)', r'terhitung\s+sejak')),
        ('rent', 'Harga & pembayaran sewa', (r'harga\s+sewa', r'uang\s+sewa', r'pelunasan')),
        ('deposit', 'Deposit / uang jaminan bila disepakati', (r'\bdeposit\b', r'uang\s+jaminan')),
        ('authority', 'Kewenangan/status Pemberi Sewa', (r'hak\s+pihak\s+pertama', r'bebas\s+dari\s+sengketa', r'kewenangan\s+menyewakan')),
        ('handover', 'Serah terima & kondisi awal', (r'serah\s+terima', r'berita\s+acara', r'kondisi\s+awal', r'inventaris')),
        ('utilities', 'Utilitas & biaya', (r'listrik', r'PDAM|air', r'tagihan|rekening')),
        ('maintenance', 'Pemeliharaan & perbaikan', (r'merawat|memelihara|pemeliharaan', r'kerusakan')),
        ('restrictions', 'Larangan pengalihan/perubahan', (r'mengalihkan\s+hak\s+sewa', r'pihak\s+ketiga', r'mengubah\s+struktur', r'tanpa\s+(?:adanya\s+)?i[sz]in')),
        ('access', 'Akses / pemeriksaan objek', (r'pemeriksaan\s+objek', r'memasuki\s+objek', r'akses\s+(?:ke|atas)\s+objek')),
        ('force_majeure', 'Force majeure', (r'force\s+majeure', r'keadaan\s+memaksa')),
        ('default', 'Cidera janji / pelanggaran', (r'melanggar|lalai', r'cidera\s+janji|wanprestasi')),
        ('early_termination', 'Pengakhiran sebelum waktunya', (r'memutuskan\s+hubungan\s+sewa', r'sebelum\s+jangka\s+waktu.*berakhir')),
        ('return', 'Pengosongan & pengembalian', (r'mengosongkan\s+rumah', r'menyerahkan(?:nya)?\s+kembali', r'pengembalian\s+objek')),
        ('renewal', 'Perpanjangan', (r'memperpanjang\s+sewa', r'perpanjangan')),
        ('notice', 'Mekanisme pemberitahuan', (r'pemberitahuan\s+tertulis', r'memberitahukan.*tertulis')),
        ('dispute', 'Penyelesaian sengketa', (r'penyelesaian\s+(?:sengketa|perselisihan)', r'musyawarah.*(?:sengketa|perselisihan)', r'pengadilan\s+negeri|arbitrase')),
    ]

    GENERAL_REQUIREMENTS = [
        ('parties', 'Identitas para pihak', (r'pihak\s+pertama', r'pihak\s+kedua')),
        ('object', 'Objek/ruang lingkup', (r'objek|ruang\s+lingkup|tujuan',)),
        ('term', 'Jangka waktu', (r'jangka\s+waktu|berlaku\s+sejak|berakhir',)),
        ('payment', 'Pembayaran/imbal balik', (r'pembayaran|harga|nilai\s+kontrak|imbalan',)),
        ('obligations', 'Hak & kewajiban', (r'wajib|berhak|kewajiban',)),
        ('default', 'Pelanggaran/cidera janji', (r'wanprestasi|cidera\s+janji|melanggar|lalai',)),
        ('termination', 'Pengakhiran', (r'pengakhiran|mengakhiri|memutus',)),
        ('force_majeure', 'Force majeure', (r'force\s+majeure|keadaan\s+memaksa',)),
        ('dispute', 'Penyelesaian sengketa', (r'penyelesaian\s+(?:sengketa|perselisihan)|arbitrase|pengadilan',)),
    ]

    @staticmethod
    def coverage(text: str, contract_type: str) -> Tuple[List[Dict], List[Dict]]:
        reqs = ClauseAnalyzer.LEASE_REQUIREMENTS if contract_type == 'SEWA_MENYEWA' else ClauseAnalyzer.GENERAL_REQUIREMENTS
        rows, missing = [], []
        for key, label, patterns in reqs:
            matched = [p for p in patterns if re.search(p, text, re.I | re.S)]
            present = bool(matched)
            row = {'key': key, 'label': label, 'status': 'PRESENT' if present else 'MISSING'}
            rows.append(row)
            if not present:
                priority = 'HIGH' if key in {'object', 'rent', 'parties'} else ('MEDIUM' if key in {'handover', 'default', 'termination', 'early_termination', 'dispute'} else 'LOW')
                missing.append({'key': key, 'label': label, 'priority': priority})
        return rows, missing

    @staticmethod
    def inconsistencies(text: str, contract_type: str) -> List[Dict]:
        out: List[Dict] = []
        nums = [int(x) for x in re.findall(r'(?im)^\s*Pasal\s+(\d+)\s*$', text)]
        if len(nums) >= 3:
            unique = sorted(set(nums))
            gaps = [n for n in range(unique[0], unique[-1] + 1) if n not in unique]
            if gaps:
                out.append({
                    'severity': 'MEDIUM', 'category': 'Penomoran Pasal',
                    'finding': 'Nomor pasal tidak berurutan; pasal yang tidak ditemukan: ' + ', '.join(map(str, gaps)) + '.',
                    'recommendation': 'Periksa apakah pasal terhapus atau hanya terjadi kesalahan penomoran sebelum dokumen ditandatangani.'
                })

        if contract_type == 'SEWA_MENYEWA':
            if (re.search(r'pelunasan\s+(?:dari\s+)?seluruh\s+jumlah\s+uang\s+sewa|tanda\s+pelunasan', text, re.I)
                    and re.search(r'lala[iy]\s+membayar\s+harga\s+sewa|harga\s+sewa.{0,80}jatuh\s+tempo', text, re.I | re.S)):
                out.append({
                    'severity': 'MEDIUM', 'category': 'Konsistensi Pembayaran',
                    'finding': 'Dokumen mengindikasikan sewa telah dilunasi di muka, tetapi juga memuat mekanisme tunggakan harga sewa setelah jatuh tempo.',
                    'recommendation': 'Samakan klausul pembayaran dan klausul cidera janji: pilih skema lunas di muka atau pembayaran periodik, lalu hapus konsekuensi yang tidak relevan.'
                })
            if (re.search(r'memutuskan\s+hubungan\s+sewa.{0,120}sebelum\s+jangka\s+waktu.*berakhir', text, re.I | re.S)
                    and re.search(r'sekurang-kurangnya\s+1\s+bulan\s+sebelum\s+berakhirnya\s+jangka\s+waktu', text, re.I)):
                out.append({
                    'severity': 'MEDIUM', 'category': 'Pengakhiran Dini',
                    'finding': 'Klausul pengakhiran sebelum jatuh tempo menggunakan batas pemberitahuan yang dihitung dari "berakhirnya jangka waktu", sehingga titik waktunya dapat dibaca ambigu.',
                    'recommendation': 'Nyatakan pemberitahuan dihitung sebelum tanggal pengakhiran yang dikehendaki dan tentukan akibat finansialnya secara tegas.'
                })
            fm = re.search(r'force\s+majeure|keadaan\s+memaksa', text, re.I)
            if fm and not re.search(r'force\s+majeure.{0,800}(pemberitahuan|memberitahukan|mitigasi)', text, re.I | re.S):
                out.append({
                    'severity': 'LOW', 'category': 'Force Majeure',
                    'finding': 'Force majeure disebut, tetapi mekanisme pemberitahuan/mitigasi tidak terdeteksi dalam bagian yang berdekatan.',
                    'recommendation': 'Tambahkan batas waktu pemberitahuan, kewajiban mitigasi, dan akibat terhadap kewajiban/sewa selama objek tidak dapat digunakan.'
                })
        return out

    @staticmethod
    def obligations(text: str) -> List[Dict]:
        out = []
        for idx, raw in enumerate(text.splitlines(), 1):
            line = re.sub(r'\s+', ' ', raw).strip()
            if len(line) < 12:
                continue
            low = line.lower()
            actor = None
            if 'pihak pertama' in low or 'pemberi sewa' in low:
                actor = 'PIHAK PERTAMA / PEMBERI SEWA'
            elif 'pihak kedua' in low or 'penyewa' in low:
                actor = 'PIHAK KEDUA / PENYEWA'
            if actor and re.search(r'\b(wajib|berkewajiban|berhak|tidak\s+dibenarkan|dilarang|harus)\b', low):
                kind = 'PROHIBITION' if re.search(r'tidak\s+dibenarkan|dilarang', low) else ('RIGHT' if 'berhak' in low else 'OBLIGATION')
                out.append({'actor': actor, 'type': kind, 'text': line[:260], 'line_number': idx})
            if len(out) >= 24:
                break
        return out


# ============================================
# 5B. DEEP CLAUSE EVALUATION TABLE
# ============================================

class ClauseDeepEvaluator:
    """Build a source-faithful, clause-by-clause evaluation table.

    The original clause text is preserved verbatim (aside from surrounding
    whitespace normalization). Recommendations are drafting proposals, not
    declarations that the existing wording is unlawful.
    """

    @staticmethod
    def extract_articles(text: str) -> List[Dict]:
        pattern = re.compile(r'(?im)^\s*Pasal\s+(\d+[A-Za-z]?)\s*$')
        matches = list(pattern.finditer(text or ''))
        rows: List[Dict] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            raw = (text[start:end] or '').strip()
            # Remove page-number artefacts that OCR/text extraction often places
            # alone at article boundaries, while preserving substantive wording.
            raw = re.sub(r'(?im)^\s*\d+\s*\|\s*P\s*a\s*g\s*e\s*$', '', raw).strip()
            if raw:
                rows.append({'article_number': m.group(1), 'original_text': raw})
        return rows

    @staticmethod
    def _contains(text: str, pattern: str) -> bool:
        return bool(re.search(pattern, text or '', re.I | re.S))

    @staticmethod
    def _lease_eval(article: Dict, full_text: str, inconsistencies: List[Dict]) -> Dict:
        original = article['original_text']
        num = article['article_number']
        low = original.lower()
        risks: List[str] = []
        recs: List[str] = []

        if ClauseDeepEvaluator._contains(original, r'ukuran\s+bangunan|luas\s*:|alamat\s*:|rumah\s+(?:tersebut|yang\s+disewa)'):
            risks.append('Identifikasi objek belum tentu cukup untuk mencegah sengketa mengenai batas, kondisi awal, inventaris, fasilitas, atau bagian bangunan yang termasuk/tidak termasuk objek sewa.')
            recs.append('Objek sewa adalah rumah yang beralamat di [ALAMAT LENGKAP], dengan luas kurang lebih [●] m², berikut fasilitas dan inventaris sebagaimana Lampiran I. Kondisi fisik, angka meter listrik/air, kunci, dan inventaris pada saat penyerahan dituangkan dalam Berita Acara Serah Terima yang menjadi bagian tidak terpisahkan dari Perjanjian ini.')
        if ClauseDeepEvaluator._contains(original, r'tempat\s+tinggal|dipergunakan\s+untuk|keperluan'):
            risks.append('Tujuan penggunaan disebut, tetapi batas kegiatan yang diperbolehkan serta prosedur perubahan penggunaan dapat menimbulkan perbedaan tafsir bila kebutuhan Penyewa berubah.')
            recs.append('PIHAK KEDUA wajib menggunakan objek sewa hanya untuk tempat tinggal dan kegiatan rumah tangga yang wajar. Perubahan penggunaan hanya dapat dilakukan setelah memperoleh persetujuan tertulis PIHAK PERTAMA. Persetujuan tidak boleh dianggap diberikan hanya karena PIHAK PERTAMA mengetahui penggunaan tersebut.')
        if ClauseDeepEvaluator._contains(original, r'selama\s+\d+\s+(?:tahun|bulan)|terhitung\s+sejak|harga\s+sewa|uang\s+sewa|pelunasan'):
            risks.append('Jangka waktu dan pembayaran berada dalam satu rangkaian klausul, tetapi perlu dipastikan tanggal mulai/berakhir, bukti pelunasan, konsekuensi keterlambatan, serta hubungan dengan klausul pengakhiran konsisten.')
            if ClauseDeepEvaluator._contains(full_text, r'pelunasan\s+(?:dari\s+)?seluruh\s+jumlah\s+uang\s+sewa|tanda\s+pelunasan') and ClauseDeepEvaluator._contains(full_text, r'lala[iy]\s+membayar\s+harga\s+sewa|harga\s+sewa.{0,80}jatuh\s+tempo'):
                risks.append('Dokumen juga memuat mekanisme tunggakan harga sewa walaupun pembayaran dinyatakan lunas di muka; ini merupakan inkonsistensi yang dapat memicu sengketa mengenai kewajiban pembayaran.')
            recs.append('Jangka waktu sewa berlaku sejak tanggal [●] sampai dengan tanggal [●]. Harga sewa untuk seluruh jangka waktu tersebut adalah Rp[●] ([TERBILANG]) dan dibayar [LUNAS DI MUKA / SECARA BERTAHAP SESUAI JADWAL]. Setiap pembayaran wajib dibuktikan dengan tanda terima. Tidak ada kewajiban pembayaran harga sewa lain di luar jadwal yang secara tegas dicantumkan dalam Perjanjian ini.')
        if ClauseDeepEvaluator._contains(original, r'bebas\s+dari\s+sengketa|hak\s+pihak\s+pertama|tidak\s+dalam\s+keadaan\s+disewakan|diganggu\s+gugat'):
            risks.append('Jaminan status objek sudah membantu Penyewa, namun tidak menjelaskan dokumen dasar penguasaan, kewenangan Pemberi Sewa, dan tanggung jawab bila klaim pihak ketiga ternyata muncul.')
            recs.append('PIHAK PERTAMA menjamin bahwa PIHAK PERTAMA berwenang secara sah untuk menyewakan objek sewa dan bahwa pada tanggal penandatanganan objek sewa tidak sedang berada dalam sengketa atau terikat sewa kepada pihak lain yang menghalangi pelaksanaan Perjanjian ini. Apabila klaim pihak ketiga mengakibatkan PIHAK KEDUA tidak dapat menggunakan objek sewa, PIHAK PERTAMA wajib segera menyelesaikannya dan para pihak wajib menyepakati pemulihan yang proporsional, termasuk pengembalian bagian sewa untuk masa penggunaan yang hilang bila relevan.')
        if ClauseDeepEvaluator._contains(original, r'listrik|PDAM|air|tagihan|rekening'):
            risks.append('Pembagian biaya utilitas sudah ada, tetapi tidak terlihat pemisahan tagihan sebelum dan sesudah serah terima serta pencatatan angka meter awal/akhir.')
            recs.append('Tagihan listrik, air, internet, dan utilitas lain yang timbul sejak tanggal serah terima sampai tanggal pengembalian objek menjadi tanggung jawab PIHAK KEDUA. Tunggakan yang timbul sebelum serah terima tetap menjadi tanggung jawab PIHAK PERTAMA. Angka meter awal dan akhir dicatat dalam Berita Acara Serah Terima/Pengembalian.')
        if ClauseDeepEvaluator._contains(original, r'merawat|menjaga\s+keadaan|pemeliharaan|kerusakan\s+struktur'):
            risks.append('Tanggung jawab pemeliharaan/kerusakan belum secara tegas membedakan kerusakan karena pemakaian, keausan wajar, cacat yang telah ada, dan kerusakan struktural yang bukan akibat Penyewa.')
            recs.append('PIHAK KEDUA wajib merawat objek sewa secara wajar dan bertanggung jawab atas kerusakan yang terbukti timbul karena kesengajaan atau kelalaiannya. Keausan wajar, cacat tersembunyi, kerusakan struktural yang tidak disebabkan oleh PIHAK KEDUA, dan kerusakan yang telah ada sebelum serah terima menjadi tanggung jawab PIHAK PERTAMA, kecuali para pihak menyepakati lain secara tertulis.')
        if ClauseDeepEvaluator._contains(original, r'mengalihkan\s+hak\s+sewa|pihak\s+ketiga|mengubah\s+struktur|tanpa\s+(?:adanya\s+)?i[sz]in|membuat\s+bangunan'):
            risks.append('Larangan pengalihan/perubahan cukup luas; tanpa mekanisme permohonan dan persetujuan tertulis, tindakan kecil dapat diperdebatkan sebagai pelanggaran material.')
            recs.append('PIHAK KEDUA tidak boleh mengalihkan hak sewa, menyewakan kembali, atau melakukan perubahan struktural tanpa persetujuan tertulis PIHAK PERTAMA. Perubahan non-struktural yang bersifat sementara dapat dilakukan sepanjang tidak merusak objek dan dikembalikan ke kondisi semula pada akhir sewa. Permohonan persetujuan wajib menjelaskan bentuk perubahan yang diminta.')
        if ClauseDeepEvaluator._contains(original, r'force\s+majeure|bencana\s+alam|huru-hara|kerusuhan'):
            risks.append('Definisi force majeure ada, tetapi mekanisme pemberitahuan, mitigasi, pembuktian, durasi, dan akibat terhadap kewajiban pembayaran/pengakhiran belum lengkap.')
            recs.append('Pihak yang mengalami keadaan memaksa wajib memberitahukan secara tertulis kepada pihak lainnya paling lambat [●] hari sejak mengetahui kejadian tersebut, disertai penjelasan dampak dan upaya mitigasi. Kewajiban yang secara langsung terhalang ditangguhkan selama hambatan berlangsung. Apabila objek tidak dapat digunakan selama lebih dari [●] hari berturut-turut, para pihak wajib bermusyawarah mengenai penyesuaian sewa atau pengakhiran tanpa penalti untuk masa yang belum dijalankan.')
        if ClauseDeepEvaluator._contains(original, r'memutuskan\s+hubungan\s+sewa|sebelum\s+jangka\s+waktu.*berakhir|memberitahukan.*tertulis'):
            risks.append('Hak pengakhiran dini perlu membedakan pengakhiran tanpa pelanggaran dan pengakhiran karena cidera janji; waktu pemberitahuan harus dihitung dari tanggal pengakhiran yang diinginkan, bukan dari akhir masa sewa.')
            recs.append('PIHAK yang bermaksud mengakhiri sewa sebelum berakhirnya jangka waktu wajib menyampaikan pemberitahuan tertulis sekurang-kurangnya [30] hari sebelum tanggal pengakhiran yang dikehendaki. Pemberitahuan wajib menyebutkan tanggal efektif pengakhiran, dasar pengakhiran, kewajiban yang masih harus diselesaikan, serta mekanisme pengembalian objek dan perhitungan pembayaran yang telah diterima.')
        if ClauseDeepEvaluator._contains(original, r'melanggar|lalai\s+melaksanakan|lalai\s+membayar|jatuh\s+tempo'):
            risks.append('Pemutusan oleh Pemberi Sewa dapat terjadi segera setelah pelanggaran tanpa klasifikasi pelanggaran material, notice terukur, dan kesempatan memperbaiki pelanggaran yang masih dapat diperbaiki.')
            recs.append('PIHAK PERTAMA dapat mengakhiri Perjanjian apabila PIHAK KEDUA melakukan pelanggaran material dan tidak memperbaikinya dalam waktu [7/14] hari kalender setelah menerima pemberitahuan tertulis yang menjelaskan pelanggaran tersebut. Untuk pelanggaran yang secara wajar tidak dapat diperbaiki, pengakhiran dapat dilakukan sesuai sifat pelanggaran dengan tetap memperhitungkan hak dan kewajiban yang telah timbul sebelum tanggal pengakhiran.')
        if ClauseDeepEvaluator._contains(original, r'mengosongkan\s+rumah|menyerahkan(?:nya)?\s+kembali|setelah\s+berakhir'):
            risks.append('Kewajiban pengembalian objek ada, tetapi prosedur pemeriksaan, berita acara, kondisi yang dapat diterima, penyelesaian utilitas, dan pengembalian deposit bila ada belum terinci.')
            recs.append('Pada akhir masa sewa, PIHAK KEDUA wajib mengosongkan dan menyerahkan kembali objek sewa melalui Berita Acara Pengembalian yang mencatat kondisi objek, inventaris, kunci, angka meter, serta tagihan yang masih terutang. Kerusakan yang menjadi tanggung jawab PIHAK KEDUA harus dibuktikan melalui pemeriksaan bersama dan tidak mencakup keausan wajar.')
        if ClauseDeepEvaluator._contains(original, r'hal-hal\s+yang\s+belum\s+tercantum|dimusyawarahkan\s+bersama'):
            risks.append('Klausul musyawarah umum belum membentuk mekanisme penyelesaian sengketa jika musyawarah gagal, sehingga forum dan tata cara penyelesaian dapat diperdebatkan.')
            recs.append('Setiap perselisihan terlebih dahulu diselesaikan melalui musyawarah selama paling lama [30] hari kalender sejak salah satu pihak menyampaikan pemberitahuan sengketa secara tertulis. Apabila tidak tercapai penyelesaian, para pihak sepakat menyelesaikannya melalui forum yang secara tertulis dipilih dalam Perjanjian ini setelah mempertimbangkan kompetensi absolut dan relatif yang berlaku.')
        if ClauseDeepEvaluator._contains(original, r'rangkap\s+2|mater[ae]i|ditandatangani|berlaku\s+mulai'):
            risks.append('Ketentuan penutup perlu konsisten dengan tanggal mulai sewa di pasal jangka waktu serta perlu memastikan lampiran/berita acara menjadi bagian perjanjian.')
            recs.append('Perjanjian ini dibuat dalam [2] rangkap asli yang masing-masing mempunyai kekuatan pembuktian yang sama dan ditandatangani pada tanggal [●]. Perjanjian berlaku sesuai tanggal mulai sewa yang ditetapkan dalam Pasal [●]. Seluruh lampiran dan berita acara yang ditandatangani para pihak merupakan bagian yang tidak terpisahkan dari Perjanjian ini.')

        # Pull through article-specific structural findings when relevant.
        for inc in inconsistencies or []:
            finding = inc.get('finding', '')
            if inc.get('category') == 'Penomoran Pasal' and ('Pasal 12' in original or 'Pasal 14' in original):
                risks.append(finding)
                recs.append('Perbaiki penomoran pasal secara berurutan dan pastikan tidak ada klausul yang terhapus sebelum penandatanganan.')

        if not risks:
            risks.append('Tidak terdeteksi kelemahan spesifik yang dapat dinilai secara deterministik dari bunyi pasal ini. Tetap perlu diuji terhadap keseluruhan kontrak, fakta transaksi, dan hukum positif yang relevan.')
            recs.append('Pertahankan substansi pasal ini, tetapi selaraskan istilah, rujukan pasal, definisi, tanggal, dan mekanisme pelaksanaannya dengan ketentuan lain dalam kontrak.')

        return {
            'article_number': num,
            'existing_clause': original,
            'risk_loophole': ' '.join(dict.fromkeys(risks)),
            'recommended_redraft': '\n\n'.join(dict.fromkeys(recs)),
        }

    @staticmethod
    def evaluate(text: str, contract_type: str, missing: List[Dict] | None = None, inconsistencies: List[Dict] | None = None) -> List[Dict]:
        articles = ClauseDeepEvaluator.extract_articles(text)
        if contract_type == 'SEWA_MENYEWA':
            rows = [ClauseDeepEvaluator._lease_eval(a, text, inconsistencies or []) for a in articles]
        else:
            rows = []
            for a in articles:
                rows.append({
                    'article_number': a['article_number'],
                    'existing_clause': a['original_text'],
                    'risk_loophole': 'Uji kejelasan subjek, objek, pemicu kewajiban, batas waktu, pembuktian, konsekuensi pelanggaran, dan keterkaitannya dengan pasal lain. Kesimpulan hukum positif memerlukan verifikasi terpisah.',
                    'recommended_redraft': 'Pertahankan substansi yang disepakati para pihak, lalu redaksikan kembali pasal ini dengan menyebut secara eksplisit: pihak yang berkewajiban/berhak, objek kewajiban, batas waktu, kondisi pemicu, bukti pelaksanaan, dan akibat jika tidak dipenuhi.',
                })

        # Missing material clauses are appended as explicit gap rows so the table
        # remains the single required review surface. They never masquerade as
        # source text.
        gap_templates = {
            'handover': 'PASAL [●] — SERAH TERIMA DAN KONDISI AWAL\nPara pihak melakukan pemeriksaan bersama pada saat penyerahan objek dan menandatangani Berita Acara Serah Terima yang memuat kondisi fisik, inventaris, kunci, angka meter, serta catatan kerusakan yang telah ada.',
            'access': 'PASAL [●] — AKSES DAN PEMERIKSAAN\nPIHAK PERTAMA dapat memeriksa objek sewa setelah memberikan pemberitahuan tertulis sekurang-kurangnya [24/48] jam sebelumnya, kecuali dalam keadaan darurat. Pemeriksaan dilakukan pada waktu yang wajar dan tidak boleh mengganggu penggunaan secara tidak patut.',
            'dispute': 'PASAL [●] — PENYELESAIAN PERSELISIHAN\nPerselisihan diselesaikan terlebih dahulu melalui musyawarah paling lama [30] hari kalender sejak pemberitahuan tertulis. Jika tidak selesai, para pihak memilih forum penyelesaian yang sesuai kompetensi absolut dan relatif yang berlaku.',
            'deposit': 'PASAL [●] — UANG JAMINAN\nApabila para pihak menyepakati uang jaminan, jumlahnya sebesar Rp[●], hanya dapat dipotong untuk kewajiban yang terbukti belum dipenuhi, dan sisanya dikembalikan paling lambat [●] hari setelah pengembalian objek dan penyelesaian tagihan.',
        }
        for m in missing or []:
            if m.get('key') in gap_templates and m.get('priority') in {'HIGH', 'MEDIUM'}:
                rows.append({
                    'article_number': 'USULAN',
                    'existing_clause': f"— Tidak ada pasal eksisting mengenai {m.get('label', '').lower()}.",
                    'risk_loophole': (
                        'Ketiadaan klausul penyelesaian perselisihan/sengketa membuat forum, tahapan, dan tata cara penyelesaian tidak cukup jelas bila terjadi sengketa.'
                        if m.get('key') == 'dispute' else
                        f"Ketiadaan klausul {m.get('label', '').lower()} membuat prosedur, alokasi tanggung jawab, atau bukti pelaksanaan tidak cukup jelas bila terjadi perselisihan."
                    ),
                    'recommended_redraft': gap_templates[m['key']],
                })
        return rows


# ============================================
# 6. RISK DETECTION ENGINE
# ============================================

class RiskDetector:
    RISK_RULES = [
        {
            'keywords': ['denda', 'penalti', 'penalty', 'late payment', 'keterlambatan'],
            'category': 'Pembayaran / Denda', 'risk_level': 'MEDIUM',
            'recommendation': 'Periksa dasar pengenaan, formula, batas, periode, pemicu, dan proporsionalitas denda. Pastikan tidak ada perhitungan ganda atau ketentuan yang bertentangan dengan hukum yang berlaku.'
        },
        {
            'keywords': ['indemnifikasi', 'indemnity', 'ganti rugi', 'hold harmless'],
            'exclude_patterns': [r'dibebaskan\s+dari.{0,50}ganti\s+rugi', r'tidak\s+bertanggung\s+jawab.{0,50}ganti\s+rugi'],
            'category': 'Ganti Rugi / Indemnifikasi', 'risk_level': 'HIGH',
            'recommendation': 'Periksa cakupan kerugian, penyebab, batas tanggung jawab, pembuktian, kewajiban mitigasi, dan apakah klausul membebankan risiko pihak lain secara tidak proporsional.'
        },
        {
            'keywords': ['force majeure', 'keadaan memaksa', 'di luar kendali'],
            'category': 'Force Majeure', 'risk_level': 'LOW',
            'recommendation': 'Periksa definisi kejadian, kewajiban pemberitahuan, mitigasi, hubungan kausal, durasi, serta konsekuensi terhadap kewajiban dan hak pengakhiran.'
        },
        {
            'keywords': ['terminasi sepihak', 'unilateral termination', 'putus kontrak sepihak'],
            'patterns': [
                r'(?:pihak\s+(?:pertama|kedua)|salah\s+satu\s+pihak|perusahaan|pemberi\s+kerja|vendor|klien).{0,90}(?:dapat|berhak|boleh).{0,80}(?:mengakhiri|memutus|menghentikan|membatalkan).{0,100}(?:sepihak|tanpa\s+(?:persetujuan|pemberitahuan|alasan)|sewaktu-waktu)',
                r'(?:mengakhiri|memutus|menghentikan|membatalkan).{0,100}(?:tanpa\s+(?:persetujuan|pemberitahuan|alasan)|secara\s+sepihak|sewaktu-waktu)',
            ],
            'category': 'Terminasi Sepihak', 'risk_level': 'HIGH',
            'recommendation': 'Uji dasar terminasi, materialitas pelanggaran, notice, kesempatan perbaikan (cure period), keseimbangan hak para pihak, dan akibat pembayaran/pengembalian.'
        },
        {
            'keywords': ['rahasia', 'confidential', 'kerahasiaan', 'nda'],
            'category': 'Kerahasiaan', 'risk_level': 'MEDIUM',
            'recommendation': 'Periksa definisi informasi rahasia, pengecualian, penerima yang diperbolehkan, tujuan penggunaan, durasi, dan kewajiban setelah kontrak berakhir.'
        },
        {
            'keywords': ['yurisdiksi', 'jurisdiction', 'pengadilan', 'hukum yang berlaku', 'arbitrase'],
            'category': 'Penyelesaian Sengketa / Forum', 'risk_level': 'MEDIUM',
            'recommendation': 'Pastikan pilihan hukum/forum konsisten dengan subjek, objek, kompetensi, lokasi, dan mekanisme penyelesaian sengketa yang benar-benar disepakati.'
        },
        {
            'keywords': ['hak kekayaan intelektual', 'intellectual property', 'hki'],
            'category': 'HKI', 'risk_level': 'HIGH',
            'recommendation': 'Perjelas kepemilikan awal dan hasil pekerjaan, ruang lingkup lisensi, wilayah, jangka waktu, penggunaan ulang, dan pengakhiran lisensi.'
        },
        {
            'keywords': ['exclusivity', 'eksklusif', 'hak tunggal'],
            'category': 'Eksklusivitas', 'risk_level': 'MEDIUM',
            'recommendation': 'Periksa ruang lingkup, wilayah, durasi, target kinerja, pengecualian dan mekanisme penghentian eksklusivitas.'
        },
    ]

    @staticmethod
    def analyze(text: str, contract_type: str | None = None, missing_clauses: List[Dict] | None = None, inconsistencies: List[Dict] | None = None) -> List[RiskClause]:
        detected: List[RiskClause] = []
        lines = text.split('\n')
        for idx, line in enumerate(lines):
            low = line.lower()
            for rule in RiskDetector.RISK_RULES:
                keyword_found = any(re.search(r'(?<!\w)' + re.escape(kw.lower()) + r'(?!\w)', low, re.I) for kw in rule.get('keywords', []))
                pattern_found = any(re.search(pat, low, re.I) for pat in rule.get('patterns', []))
                excluded = any(re.search(pat, low, re.I) for pat in rule.get('exclude_patterns', []))
                if (keyword_found or pattern_found) and not excluded:
                    if not any(r.clause_text.strip() == line.strip() and r.category == rule['category'] for r in detected):
                        detected.append(RiskClause(line.strip()[:220], rule['risk_level'], rule['category'], rule['recommendation'], idx + 1))
                    break

        # Convert only material coverage gaps into risks; all gaps remain visible in coverage.
        for item in (missing_clauses or []):
            if item.get('priority') not in {'HIGH', 'MEDIUM'}:
                continue
            detected.append(RiskClause(
                f"Klausul/komponen tidak terdeteksi: {item['label']}", item['priority'], 'Kelengkapan Kontrak',
                f"Tambahkan atau pertegas bagian mengenai {item['label'].lower()} jika memang relevan dengan transaksi ini.", 0
            ))

        for item in (inconsistencies or []):
            detected.append(RiskClause(
                item.get('finding', '')[:220], item.get('severity', 'MEDIUM'), item.get('category', 'Konsistensi'),
                item.get('recommendation', 'Periksa dan selaraskan klausul sebelum penandatanganan.'), 0
            ))

        # Deduplicate semantically identical generated findings.
        unique, seen = [], set()
        for risk in detected:
            key = (risk.category.lower(), re.sub(r'\W+', ' ', risk.clause_text.lower())[:120])
            if key not in seen:
                seen.add(key); unique.append(risk)
        return unique[:30]


# ============================================
# 7. SUMMARY
# ============================================

class AISummarizer:
    @staticmethod
    def generate_summary(text: str, parties: List[str], contract_type: str = 'KONTRAK_UMUM', key_terms: Dict | None = None,
                         coverage: List[Dict] | None = None, missing: List[Dict] | None = None,
                         inconsistencies: List[Dict] | None = None) -> str:
        coverage = coverage or []; missing = missing or []; inconsistencies = inconsistencies or []; key_terms = key_terms or {}
        present = sum(1 for x in coverage if x.get('status') == 'PRESENT')
        completeness = round((present / max(1, len(coverage))) * 100)
        party_str = ' dan '.join(parties) if parties else 'Tidak terdeteksi'
        type_label = contract_type.replace('_', ' ').title()
        missing_labels = ', '.join(x['label'] for x in missing[:6]) or 'Tidak ada gap utama yang terdeteksi oleh matriks klausul.'
        incons = '; '.join(x['finding'] for x in inconsistencies[:4]) or 'Tidak ada inkonsistensi struktural utama yang terdeteksi.'
        terms = '; '.join(f"{k}: {v}" for k, v in key_terms.items()) or 'Tidak ada term komersial yang cukup jelas untuk diekstrak.'
        return (
            "RINGKASAN REVIEW KONTRAK\n"
            f"• Jenis terdeteksi: {type_label}\n"
            f"• Para pihak: {party_str}\n"
            f"• Kelengkapan klausul: {present}/{len(coverage)} ({completeness}%)\n"
            f"• Term utama: {terms}\n"
            f"• Gap utama: {missing_labels}\n"
            f"• Konsistensi: {incons}\n"
            "• Catatan: klasifikasi risiko bersifat screening kontraktual. Kesimpulan mengenai keabsahan, keberlakuan, atau akibat hukum klausul memerlukan verifikasi hukum positif dan fakta transaksi."
        )


# ============================================
# 8. MAIN ENGINE
# ============================================

class ContractReviewEngine:
    @staticmethod
    def review(file_path: str, use_ai: bool = False) -> Dict:
        text = DocumentExtractor.extract_text(file_path)
        if not text or len(text.strip()) < 50:
            raise ValueError("Dokumen kosong atau tidak terbaca. Pastikan file berisi teks.")

        parties = EntityExtractor.extract_parties(text)
        dates = EntityExtractor.extract_dates(text)
        contract_type, confidence = ContractTypeClassifier.detect(text)
        key_terms = EntityExtractor.extract_key_terms(text, contract_type, dates)
        coverage, missing = ClauseAnalyzer.coverage(text, contract_type)
        inconsistencies = ClauseAnalyzer.inconsistencies(text, contract_type)
        obligations = ClauseAnalyzer.obligations(text)
        clause_evaluations = ClauseDeepEvaluator.evaluate(text, contract_type, missing, inconsistencies)
        risks = RiskDetector.analyze(text, contract_type, missing, inconsistencies)
        summary = AISummarizer.generate_summary(text, parties, contract_type, key_terms, coverage, missing, inconsistencies)

        word_count = len(text.split())
        page_count = max(1, (word_count + 299) // 300)
        result = ContractAnalysisResult(
            filename=file_path.replace('\\', '/').split('/')[-1], total_pages=page_count, word_count=word_count,
            parties=parties, effective_date=dates['effective_date'], termination_date=dates['termination_date'],
            risks=risks, summary=summary, review_timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            contract_type=contract_type, contract_type_confidence=confidence, key_terms=key_terms,
            clause_coverage=coverage, missing_clauses=missing, inconsistencies=inconsistencies, obligations=obligations,
            clause_evaluations=clause_evaluations,
        )
        return asdict(result)


# ============================================
# 9. CLI INTERFACE
# ============================================

def main():
    print('=' * 60)
    print('LEXICORE - Contract Review Engine')
    print('=' * 60)
    file_path = input('Masukkan path file kontrak (PDF/DOCX): ').strip()
    try:
        result = ContractReviewEngine.review(file_path)
        print(result['summary'])
        print(f"\nRisiko: {len(result['risks'])}")
        for i, risk in enumerate(result['risks'], 1):
            print(f"{i}. [{risk['risk_level']}] {risk['category']}: {risk['clause_text']}")
    except Exception as exc:
        print(f'Error: {exc}')


if __name__ == '__main__':
    main()
