"""
LEXICORE - Contract Review & Analysis Engine
Fungsi: Ekstrak teks dari dokumen legal, deteksi klausul berisiko, dan berikan rekomendasi.
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Tuple
import PyPDF2
import docx
from dataclasses import dataclass, asdict

# ============================================
# 1. DATA MODEL
# ============================================

@dataclass
class RiskClause:
    clause_text: str
    risk_level: str  # "HIGH", "MEDIUM", "LOW"
    category: str    # "Pembayaran", "Force Majeure", "Indemnifikasi", "Terminasi"
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

# ============================================
# 2. TEXT EXTRACTOR (Support PDF & DOCX)
# ============================================

class DocumentExtractor:
    @staticmethod
    def extract_text(file_path: str) -> str:
        """Ekstrak teks dari PDF atau DOCX"""
        if file_path.lower().endswith('.pdf'):
            return DocumentExtractor._extract_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            return DocumentExtractor._extract_docx(file_path)
        else:
            raise ValueError("Hanya support file .pdf atau .docx")
    
    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    @staticmethod
    def _extract_docx(file_path: str) -> str:
        doc = docx.Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text

# ============================================
# 3. ENTITY EXTRACTION (Sederhana dengan Regex)
# ============================================

class EntityExtractor:
    @staticmethod
    def extract_parties(text: str) -> List[str]:
        """Cari nama pihak berdasarkan pola 'PIHAK PERTAMA', 'PIHAK KEDUA', dll"""
        parties = []
        patterns = [
            r'PIHAK PERTAMA\s*[:\-]?\s*([^\n,]+)',
            r'PIHAK KEDUA\s*[:\-]?\s*([^\n,]+)',
            r'PHAK PERTAMA\s*[:\-]?\s*([^\n,]+)',
            r'PHAK KEDUA\s*[:\-]?\s*([^\n,]+)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()[:50]  # Batasi panjang
                if name and len(name) > 3:
                    parties.append(name)
        
        # Jika tidak ditemukan, coba cari kata "antara" atau "dengan"
        if not parties:
            antara_match = re.search(r'antara\s+([^\n]+?)\s+dengan\s+([^\n]+?)(?:,|\.|\n)', text, re.IGNORECASE)
            if antara_match:
                parties = [antara_match.group(1).strip(), antara_match.group(2).strip()]
        
        return parties[:3] if parties else ["Tidak terdeteksi"]
    
    @staticmethod
    def extract_dates(text: str) -> Dict[str, str]:
        """Ekstrak tanggal efektif dan terminasi"""
        dates = {
            "effective_date": "Tidak ditemukan",
            "termination_date": "Tidak ditemukan"
        }
        
        # Pattern tanggal (contoh: 1 Januari 2025 atau 01/01/2025)
        date_pattern = r'\b(\d{1,2}\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})\b'
        date_pattern_alt = r'\b(\d{2}/\d{2}/\d{4})\b'
        
        # Cari efektif
        eff_match = re.search(r'(efektif|berlaku|effective)\s*(?:pada|tanggal|date)?\s*' + date_pattern, text, re.IGNORECASE)
        if eff_match:
            dates["effective_date"] = eff_match.group(2)
        
        # Cari terminasi / berakhir
        term_match = re.search(r'(terminasi|berakhir|berhenti|expiry|termination)\s*(?:pada|tanggal|date)?\s*' + date_pattern, text, re.IGNORECASE)
        if term_match:
            dates["termination_date"] = term_match.group(2)
        
        return dates

# ============================================
# 4. RISK DETECTION ENGINE
# ============================================

class RiskDetector:
    # Database aturan risiko berdasarkan keyword
    RISK_RULES = [
        {
            "keywords": ["denda", "penalti", "penalty", "late payment", "keterlambatan"],
            "category": "Pembayaran",
            "risk_level": "MEDIUM",
            "recommendation": "Pastikan besaran denda tidak melebihi suku bunga acuan BI (max 14%/tahun). Pertimbangkan masa tenggang (grace period)."
        },
        {
            "keywords": ["indemnifikasi", "indemnity", "ganti rugi", "hold harmless"],
            "category": "Indemnifikasi",
            "risk_level": "HIGH",
            "recommendation": "Klausul ini sangat memberatkan. Batasi lingkup indemnifikasi hanya pada kelalaian berat (gross negligence) dan bukan kesalahan pihak lain."
        },
        {
            "keywords": ["force majeure", "keadaan memaksa", "di luar kendali"],
            "category": "Force Majeure",
            "risk_level": "LOW",
            "recommendation": "Standard clause. Pastikan mencakup pandemi, perang, dan bencana alam. Tambahkan kewajiban pemberitahuan tertulis."
        },
        {
            "keywords": ["terminasi sepihak", "unilateral termination", "putus kontrak sepihak"],
            "category": "Terminasi",
            "risk_level": "HIGH",
            "recommendation": "Berisiko tinggi! Pastikan terminasi sepihak hanya untuk pelanggaran material dan beri kesempatan perbaikan (cure period) 14-30 hari."
        },
        {
            "keywords": ["rahasia", "confidential", "kerahasiaan", "NDA"],
            "category": "Kerahasiaan",
            "risk_level": "MEDIUM",
            "recommendation": "Periksa durasi kerahasiaan (jangan terlalu lama >5 tahun). Pastikan pengecualian untuk informasi publik jelas."
        },
        {
            "keywords": ["yurisdiksi", "jurisdiction", "pengadilan", "hukum yang berlaku"],
            "category": "Hukum yang Berlaku",
            "risk_level": "MEDIUM",
            "recommendation": "Pastikan memilih yurisdiksi Indonesia jika kedua pihak di Indonesia. Hindari klausul 'arbitrase luar negeri' jika tidak perlu."
        },
        {
            "keywords": ["hak kekayaan intelektual", "IP", "intellectual property", "HKI"],
            "category": "HKI",
            "risk_level": "HIGH",
            "recommendation": "Perjelas kepemilikan HKI hasil kerjasama. Siapa yang punya? Apakah ada lisensi kembali (grant-back license)?"
        },
        {
            "keywords": ["exclusivity", "eksklusif", "hak tunggal"],
            "category": "Eksklusivitas",
            "risk_level": "MEDIUM",
            "recommendation": "Kewaspadaan: kontrak eksklusif membatasi peluang bisnis. Pertimbangkan durasi eksklusivitas yang wajar."
        }
    ]
    
    @staticmethod
    def analyze(text: str) -> List[RiskClause]:
        """Deteksi risiko berdasarkan keyword dalam teks"""
        detected_risks = []
        lines = text.split('\n')
        
        for idx, line in enumerate(lines):
            line_lower = line.lower()
            
            for rule in RiskDetector.RISK_RULES:
                # Cek apakah ada keyword dalam line
                keyword_found = any(kw.lower() in line_lower for kw in rule["keywords"])
                
                if keyword_found:
                    # Cegah duplikasi untuk line yang sama
                    if not any(r.clause_text.strip() == line.strip() for r in detected_risks):
                        risk = RiskClause(
                            clause_text=line.strip()[:200],
                            risk_level=rule["risk_level"],
                            category=rule["category"],
                            recommendation=rule["recommendation"],
                            line_number=idx + 1
                        )
                        detected_risks.append(risk)
                        break  # Hanya ambil satu risiko per line
        
        # Tambahkan analisis tambahan: jika kontrak terlalu pendek
        word_count = len(text.split())
        if word_count < 500:
            detected_risks.append(RiskClause(
                clause_text="Kontrak ini sangat pendek (kurang dari 500 kata).",
                risk_level="MEDIUM",
                category="Kelengkapan",
                recommendation="Kontrak singkat berisiko karena banyak hal tidak diatur. Pertimbangkan untuk menambahkan klausul standar seperti Force Majeure, Penyelesaian Sengketa, dan Kerahasiaan.",
                line_number=0
            ))
        
        return detected_risks

# ============================================
# 5. AI SUMMARIZATION (Mock / Bisa integrasi OpenAI)
# ============================================

class AISummarizer:
    @staticmethod
    def generate_summary(text: str, parties: List[str]) -> str:
        """Buat ringkasan kontrak"""
        # Ekstrak kalimat pertama yang berisi tujuan
        sentences = text.split('.')
        purpose = ""
        for sent in sentences[:10]:  # Cek 10 kalimat pertama
            if any(kw in sent.lower() for kw in ["tujuan", "maksud", "perjanjian", "agree", "purpose"]):
                purpose = sent.strip()
                break
        
        if not purpose:
            purpose = "Tujuan kontrak tidak tercantum di awal dokumen."
        
        word_count = len(text.split())
        party_str = " dan ".join(parties) if parties else "Pihak-pihak"
        
        summary = f"""
        📄 RINGKASAN KONTRAK:
        • Para Pihak: {party_str}
        • Tujuan: {purpose[:200]}...
        • Jumlah Kata: {word_count} kata
        • Analisis: Kontrak ini {'cukup komprehensif' if word_count > 1000 else 'relatif singkat'}. 
        {'Perlu penambahan klausul standar.' if word_count < 500 else 'Struktur sudah mencakup poin-poin utama.'}
        • Rekomendasi Umum: Pastikan semua definisi istilah diatur di awal kontrak dan periksa konsistensi tanggal.
        """
        return summary.strip()

# ============================================
# 6. MAIN ENGINE
# ============================================

class ContractReviewEngine:
    @staticmethod
    def review(file_path: str, use_ai: bool = False) -> Dict:
        """
        Fungsi utama untuk menganalisis kontrak
        Returns: Dictionary dengan semua hasil analisis
        """
        # 1. Ekstrak teks
        text = DocumentExtractor.extract_text(file_path)
        
        if not text or len(text.strip()) < 50:
            raise ValueError("Dokumen kosong atau tidak terbaca. Pastikan file berisi teks.")
        
        # 2. Ekstrak entitas
        parties = EntityExtractor.extract_parties(text)
        dates = EntityExtractor.extract_dates(text)
        
        # 3. Deteksi risiko
        risks = RiskDetector.analyze(text)
        
        # 4. Ringkasan
        summary = AISummarizer.generate_summary(text, parties)
        
        # 5. Statistik
        word_count = len(text.split())
        page_count = max(1, word_count // 300)  # Estimasi halaman
        
        # 6. Build result
        result = ContractAnalysisResult(
            filename=file_path.split('/')[-1],
            total_pages=page_count,
            word_count=word_count,
            parties=parties,
            effective_date=dates["effective_date"],
            termination_date=dates["termination_date"],
            risks=risks,
            summary=summary,
            review_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # Konversi ke dictionary
        return asdict(result)

# ============================================
# 7. CLI INTERFACE (untuk testing)
# ============================================

def main():
    print("="*60)
    print("🕵️ LEXICORE - Contract Review Engine")
    print("="*60)
    
    file_path = input("Masukkan path file kontrak (PDF/DOCX): ").strip()
    
    try:
        result = ContractReviewEngine.review(file_path)
        
        print("\n" + "="*60)
        print("📊 HASIL ANALISIS KONTRAK")
        print("="*60)
        print(f"📄 Nama File: {result['filename']}")
        print(f"📑 Jumlah Halaman (estimasi): {result['total_pages']}")
        print(f"📝 Jumlah Kata: {result['word_count']}")
        print(f"🤝 Para Pihak: {', '.join(result['parties'])}")
        print(f"📅 Tanggal Efektif: {result['effective_date']}")
        print(f"⏰ Tanggal Terminasi: {result['termination_date']}")
        
        print("\n" + "-"*60)
        print("⚠️ RISIKO YANG DITEMUKAN:")
        print("-"*60)
        
        if result['risks']:
            for i, risk in enumerate(result['risks'], 1):
                print(f"\n{i}. [LEVEL: {risk['risk_level']}] {risk['category']}")
                print(f"   Teks: \"{risk['clause_text']}\"")
                print(f"   💡 Rekomendasi: {risk['recommendation']}")
        else:
            print("✅ Tidak ada risiko signifikan yang terdeteksi.")
        
        print("\n" + "-"*60)
        print("📝 RINGKASAN:")
        print("-"*60)
        print(result['summary'])
        
        print("\n" + "="*60)
        print(f"✅ Review selesai pada: {result['review_timestamp']}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    # Contoh penggunaan langsung
    # main()
    
    # Atau contoh demo dengan teks dummy
    print("🚀 DEMO CONTRACT REVIEW (tanpa file)")
    print("-"*60)
    
    dummy_text = """
    PERJANJIAN KERJASAMA
    
    PIHAK PERTAMA: PT Maju Jaya, beralamat di Jakarta.
    PIHAK KEDUA: CV Sukses Abadi, beralamat di Bandung.
    
    Pasal 1: Tujuan
    Kedua belah pihak sepakat untuk bekerjasama dalam bidang pemasaran produk.
    
    Pasal 2: Jangka Waktu
    Perjanjian ini berlaku efektif pada 1 Januari 2026 dan akan berakhir pada 31 Desember 2026.
    
    Pasal 3: Denda
    Jika PIHAK KEDUA terlambat membayar, akan dikenakan denda 5% per bulan.
    
    Pasal 4: Force Majeure
    Tidak ada klausul force majeure dalam perjanjian ini.
    
    Pasal 5: Terminasi
    PIHAK PERTAMA berhak melakukan terminasi sepihak tanpa pemberitahuan.
    
    Pasal 6: Kerahasiaan
    Kedua pihak wajib menjaga kerahasiaan data bisnis.
    """
    
    # Simulasi dengan teks dummy
    class DummyExtractor:
        @staticmethod
        def extract_text(file_path):
            return dummy_text
    
    # Override untuk demo
    original_extract = DocumentExtractor.extract_text
    DocumentExtractor.extract_text = lambda x: dummy_text
    
    try:
        result = ContractReviewEngine.review("dummy_contract.docx")
        
        print(f"📄 File: {result['filename']}")
        print(f"🤝 Pihak: {', '.join(result['parties'])}")
        print(f"📅 Efektif: {result['effective_date']}")
        print(f"\n⚠️ Ditemukan {len(result['risks'])} risiko:")
        for risk in result['risks']:
            print(f"  - [{risk['risk_level']}] {risk['category']}: {risk['clause_text'][:60]}...")
        
        print(f"\n📝 Ringkasan:\n{result['summary']}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Restore
        DocumentExtractor.extract_text = original_extract