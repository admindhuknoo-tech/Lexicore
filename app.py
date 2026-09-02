"""LexiCore - Lawyer Operating System API."""
import os, re, shutil, tempfile
from datetime import datetime
from io import BytesIO
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from docx import Document

from contract_review import ContractReviewEngine, DocumentExtractor
from database import (init_database, DraftManager, AnalysisManager, ResearchManager,
                      RiskAssessmentManager, CommunicationManager, CaseAnalysisManager, LegalSourceVerificationManager, AuditLogger)
from legal_sources import verify_queries, source_health, federated_search, public_source_registry

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__, static_folder='static')
CORS(app)
app.config.update(MAX_CONTENT_LENGTH=50*1024*1024, UPLOAD_FOLDER=os.path.join(BASE_DIR,'uploads'), ALLOWED_EXTENSIONS={'pdf','docx'})
os.makedirs(app.config['UPLOAD_FOLDER'],exist_ok=True)
init_database()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def risk_level(risks):
    high=sum(1 for r in risks if r.get('risk_level')=='HIGH'); med=sum(1 for r in risks if r.get('risk_level')=='MEDIUM')
    return 'HIGH' if high>=2 else ('MEDIUM' if high or med>=3 else 'LOW')

def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text or '') if len(s.strip())>20]

@app.route('/')
def index(): return send_from_directory(app.static_folder,'index.html')

@app.route('/api/drafts',methods=['GET','POST'])
def drafts():
    if request.method=='GET':
        data=DraftManager.get_all_drafts(request.args.get('limit',50,type=int)); return jsonify(success=True,data=data,count=len(data))
    data=request.get_json(silent=True) or {}
    if not data.get('content','').strip(): return jsonify(success=False,error='Konten draft wajib diisi'),400
    i=DraftManager.create_draft(data); return jsonify(success=True,draft_id=i,message='Draft berhasil disimpan')

@app.route('/api/drafts/<int:draft_id>',methods=['GET','PUT','DELETE'])
def draft_detail(draft_id):
    if request.method=='GET':
        d=DraftManager.get_draft(draft_id); return (jsonify(success=True,data=d) if d else (jsonify(success=False,error='Draft tidak ditemukan'),404))
    if request.method=='DELETE':
        return jsonify(success=DraftManager.delete_draft(draft_id))
    ok=DraftManager.update_draft(draft_id,request.get_json(silent=True) or {}); return jsonify(success=ok)

@app.route('/api/generate/draft',methods=['POST'])
def generate_draft():
    data=request.get_json(silent=True) or {}; doc_type=data.get('doc_type','Perjanjian Kerjasama'); p1=data.get('party1') or '[PIHAK PERTAMA]'; p2=data.get('party2') or '[PIHAK KEDUA]'; date=data.get('effective_date') or datetime.now().strftime('%Y-%m-%d'); duration=max(1,int(data.get('duration') or 12)); prompt=(data.get('prompt') or '').strip()
    clauses=[('TUJUAN',f'{p1} dan {p2} sepakat mengikatkan diri dalam {doc_type.lower()} sesuai ruang lingkup yang disepakati.'),('JANGKA WAKTU',f'Perjanjian berlaku sejak {date} selama {duration} bulan, kecuali diakhiri lebih dahulu sesuai perjanjian.'),('HAK DAN KEWAJIBAN','Para pihak wajib melaksanakan prestasi secara itikad baik, tepat waktu, dan memberikan informasi yang material bagi pelaksanaan perjanjian.'),('PEMBAYARAN DAN PAJAK','Nilai, jadwal, bukti pembayaran, kewajiban perpajakan, serta konsekuensi keterlambatan harus dinyatakan secara tertulis.'),('KERAHASIAAN','Informasi rahasia hanya digunakan untuk tujuan perjanjian, dengan pengecualian bagi informasi publik atau yang wajib diungkap berdasarkan hukum.'),('PERLINDUNGAN DATA','Pemrosesan data pribadi dilakukan secara terbatas, sah, aman, dan sesuai peraturan yang berlaku.'),('FORCE MAJEURE','Pihak terdampak wajib memberitahukan keadaan kahar dan melakukan upaya wajar untuk mengurangi dampaknya.'),('PENGAKHIRAN','Pengakhiran karena pelanggaran material dilakukan setelah pemberitahuan tertulis dan kesempatan perbaikan yang wajar.'),('PENYELESAIAN SENGKETA','Sengketa diselesaikan terlebih dahulu melalui musyawarah; bila gagal, para pihak menentukan forum penyelesaian yang disepakati.'),('PENUTUP','Perubahan perjanjian hanya sah apabila dibuat tertulis dan disetujui para pihak.')]
    if prompt: clauses.insert(-2,('KLAUSUL KHUSUS',f'Instruksi penyusunan: {prompt}. Klausul ini wajib ditelaah dan disesuaikan lawyer terhadap fakta, posisi klien, dan hukum yang berlaku.'))
    body=[f'{doc_type.upper()}\n',f'Pada {date}, dibuat antara:\n1. {p1} (“Pihak Pertama”); dan\n2. {p2} (“Pihak Kedua”).\n']
    for n,(title,text) in enumerate(clauses,1): body.append(f'PASAL {n}\n{title}\n{text}\n')
    body.append(f'Dibuat pada {date}.\n\nPIHAK PERTAMA\n{p1}\n\nPIHAK KEDUA\n{p2}')
    content='\n'.join(body); wc=len(content.split()); cc=len(clauses)
    i=DraftManager.create_draft(dict(title=f'{doc_type} — {p1} / {p2}',doc_type=doc_type,party1=p1,party2=p2,effective_date=date,duration=duration,content=content,word_count=wc,clause_count=cc,status='generated'))
    return jsonify(success=True,draft_id=i,content=content,word_count=wc,clause_count=cc,message='Draft berhasil digenerate')

@app.route('/api/drafts/<int:draft_id>/export/docx')
def export_docx(draft_id):
    d=DraftManager.get_draft(draft_id)
    if not d: return jsonify(success=False,error='Draft tidak ditemukan'),404
    doc=Document(); doc.add_heading(d['title'],0)
    for block in d['content'].split('\n\n'):
        if block.strip(): doc.add_paragraph(block.strip())
    bio=BytesIO(); doc.save(bio); bio.seek(0); safe=secure_filename(d['title']) or 'lexicore-draft'
    return send_file(bio,as_attachment=True,download_name=f'{safe}.docx',mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

@app.route('/api/review',methods=['POST'])
def review_contract():
    f=request.files.get('file')
    if not f or not f.filename: return jsonify(success=False,error='Pilih file PDF/DOCX'),400
    if not allowed_file(f.filename): return jsonify(success=False,error='Hanya PDF dan DOCX yang didukung'),400
    td=tempfile.mkdtemp()
    try:
        path=os.path.join(td,secure_filename(f.filename)); f.save(path); result=ContractReviewEngine.review(path); result['risk_score']=risk_level(result.get('risks',[])); result['analysis_id']=AnalysisManager.save_analysis(result); return jsonify(success=True,data=result)
    finally: shutil.rmtree(td,ignore_errors=True)

@app.route('/api/analyses')
def analyses():
    data=AnalysisManager.get_all_analyses(request.args.get('limit',50,type=int)); return jsonify(success=True,data=data,count=len(data))

@app.route('/api/research/summarize',methods=['POST'])
def research_summarize():
    d=request.get_json(silent=True) or {}; text=(d.get('source_text') or '').strip()
    if len(text)<80: return jsonify(success=False,error='Masukkan teks sumber hukum minimal 80 karakter'),400

    source_type=d.get('source_type','putusan_pengadilan')
    source_labels={
      'kuhp_2023':'KUHP Nasional — UU No. 1 Tahun 2023 sebagaimana disesuaikan/diubah dengan UU No. 1 Tahun 2026',
      'penyesuaian_pidana_2026':'UU No. 1 Tahun 2026 tentang Penyesuaian Pidana',
      'kuhperdata_bw':'Kitab Undang-Undang Hukum Perdata (KUHPerdata / Burgerlijk Wetboek)',
      'uud1945':'UUD Negara Republik Indonesia Tahun 1945','tap_mpr':'Ketetapan MPR (TAP MPR)',
      'uu':'Undang-Undang (UU)','perppu':'Peraturan Pemerintah Pengganti Undang-Undang (Perppu)',
      'pp':'Peraturan Pemerintah (PP)','perpres':'Peraturan Presiden (Perpres)',
      'perda_prov':'Peraturan Daerah Provinsi','perda_kab_kota':'Peraturan Daerah Kabupaten/Kota',
      'per_mpr':'Peraturan MPR','per_dpr':'Peraturan DPR','per_dpd':'Peraturan DPD','per_bpk':'Peraturan BPK',
      'per_bi':'Peraturan Bank Indonesia','per_menteri':'Peraturan Menteri','per_lembaga':'Peraturan Badan / Lembaga / Komisi',
      'per_gubernur':'Peraturan Gubernur','per_bupati':'Peraturan Bupati','per_walikota':'Peraturan Wali Kota','per_desa':'Peraturan Desa / yang setingkat',
      'putusan_ma':'Putusan Mahkamah Agung','putusan_mk':'Putusan Mahkamah Konstitusi','putusan_pengadilan':'Putusan Pengadilan',
      'perma':'Peraturan Mahkamah Agung (PERMA)','sema':'Surat Edaran Mahkamah Agung (SEMA)',
      'per_mk':'Peraturan Mahkamah Konstitusi (PMK)','per_ky':'Peraturan Komisi Yudisial','reg_yudisial_lain':'Regulasi / Pedoman Instansi Yudikatif Lainnya',
      'legal_opinion':'Legal Opinion / Pendapat Hukum','doctrine':'Doktrin / Buku / Jurnal','memo':'Memo / Literatur',
      'case':'Putusan Pengadilan','statute':'Peraturan Perundang-undangan'
    }
    case_types={'putusan_ma','putusan_mk','putusan_pengadilan','case'}
    secondary_types={'legal_opinion','doctrine','memo'}
    ss=sentences(text)

    if source_type in case_types:
        issue=d.get('issue') or next((s for s in ss if any(k in s.lower() for k in ['apakah','sengketa','masalah','permohonan','gugatan','dakwaan'])), ss[0] if ss else '')
        holding=next((s for s in ss if any(k in s.lower() for k in ['mengadili','memutus','menetapkan','dikabulkan','ditolak','putusan'])), ss[-1] if ss else '')
        reasoning=' '.join(ss[1:5])[:1200] if len(ss)>1 else text[:1200]
        issue_label='ISU HUKUM'; result_label='AMAR / HASIL'; reasoning_label='PERTIMBANGAN / REASONING'
    elif source_type in secondary_types:
        issue=d.get('issue') or (ss[0] if ss else text[:500])
        holding=' '.join(ss[1:3])[:900] if len(ss)>1 else text[:900]
        reasoning=' '.join(ss[3:6])[:1200] if len(ss)>3 else text[:1200]
        issue_label='TOPIK / ISU'; result_label='POKOK PENDAPAT'; reasoning_label='ARGUMEN / ANALISIS'
    else:
        issue=d.get('issue') or next((s for s in ss if any(k in s.lower() for k in ['menimbang','mengingat','berdasarkan','ketentuan','mengatur','dimaksud'])), ss[0] if ss else '')
        holding=next((s for s in ss if any(k in s.lower() for k in ['wajib','dilarang','berhak','berwenang','harus','dapat','ditetapkan','diatur'])), ss[1] if len(ss)>1 else (ss[0] if ss else ''))
        reasoning=' '.join(ss[1:5])[:1200] if len(ss)>1 else text[:1200]
        issue_label='RUANG LINGKUP / ISU PENGATURAN'; result_label='NORMA / POKOK PENGATURAN'; reasoning_label='KONTEKS / ANALISIS'

    words=re.findall(r'\b[a-zA-ZÀ-ÿ]{5,}\b',text.lower()); stop={'dengan','dalam','bahwa','untuk','adalah','karena','kepada','tersebut','sebagai','pihak','serta','yang','dari'}; freq={w:words.count(w) for w in set(words) if w not in stop}; keywords=[w for w,_ in sorted(freq.items(),key=lambda x:x[1],reverse=True)[:8]]
    record=dict(title=d.get('title') or 'Legal Research Note',jurisdiction=d.get('jurisdiction','Indonesia'),citation=d.get('citation',''),source_type=source_type,source_text=text,issue=issue,holding=holding,reasoning=reasoning,keywords=keywords)
    record['research_id']=ResearchManager.save(record)
    record.update(source_label=source_labels.get(source_type,source_type),issue_label=issue_label,result_label=result_label,reasoning_label=reasoning_label)
    return jsonify(success=True,data=record)

@app.route('/api/research')
def research_list(): return jsonify(success=True,data=ResearchManager.all(request.args.get('limit',30,type=int)))

@app.route('/api/compliance/assess',methods=['POST'])
def compliance_assess():
    d=request.get_json(silent=True) or {}; a=d.get('answers') or {}; weights={'license':20,'privacy':20,'contracts':15,'employment':15,'tax':15,'aml':15}; findings=[]; rec=[]; score=0
    labels={'license':'Perizinan','privacy':'Perlindungan Data','contracts':'Kontrak','employment':'Ketenagakerjaan','tax':'Pajak','aml':'AML/KYC'}
    for key,w in weights.items():
        val=str(a.get(key,'yes')).lower()
        if val=='no': score+=w; findings.append(f'{labels[key]}: kontrol belum tersedia'); rec.append(f'Prioritaskan remediasi area {labels[key]} dan dokumentasikan PIC serta target waktunya.')
        elif val=='partial': score+=round(w*0.5); findings.append(f'{labels[key]}: kontrol baru sebagian'); rec.append(f'Lengkapi bukti kepatuhan dan SOP {labels[key]}.')
    level='HIGH' if score>=60 else ('MEDIUM' if score>=30 else 'LOW'); record=dict(title=d.get('title','Compliance & Risk Assessment'),entity=d.get('entity',''),category=d.get('category','General'),answers=a,score=score,risk_level=level,findings=findings,recommendations=rec)
    record['assessment_id']=RiskAssessmentManager.save(record); return jsonify(success=True,data=record)

@app.route('/api/compliance')
def compliance_list(): return jsonify(success=True,data=RiskAssessmentManager.all(request.args.get('limit',30,type=int)))

# Case Analysis uses a local issue-spotting/rule registry. It does NOT claim an exhaustive live corpus.
CASE_LAW_REGISTRY = [
    {'domain':'Konstitusi & Hak Dasar','keywords':['konstitusi','hak asasi','diskriminasi','kebebasan','kewenangan negara','uji materi'],'sources':['UUD Negara Republik Indonesia Tahun 1945','Putusan Mahkamah Konstitusi yang relevan']},
    {'domain':'Pidana Materiil','keywords':['pidana','tersangka','terdakwa','dakwaan','penipuan','penggelapan','pencurian','penganiayaan','ancaman','pemalsuan','korupsi'],'sources':['UU No. 1 Tahun 2023 tentang KUHP','UU No. 1 Tahun 2026 tentang Penyesuaian Pidana','Undang-undang pidana khusus yang relevan']},
    {'domain':'Acara Pidana','keywords':['penyidikan','penyelidikan','penangkapan','penahanan','penggeledahan','penyitaan','praperadilan','penuntutan','saksi','barang bukti'],'sources':['UU No. 20 Tahun 2025 tentang Kitab Undang-Undang Hukum Acara Pidana','PERMA/SEMA dan putusan pengadilan yang relevan']},
    {'domain':'Perdata & Perikatan','keywords':['wanprestasi','perjanjian','utang','piutang','ganti rugi','jual beli','sewa','perbuatan melawan hukum','kontrak'],'sources':['KUHPerdata / Burgerlijk Wetboek (periksa status pasal secara spesifik)','Undang-undang sektoral yang menyimpangi atau menggantikan BW','Yurisprudensi yang relevan']},
    {'domain':'Perusahaan & Komersial','keywords':['perseroan','direksi','komisaris','pemegang saham','pt ','perusahaan','merger','akuisisi','usaha'],'sources':['Undang-undang perseroan/perusahaan yang berlaku','Peraturan pelaksana dan regulasi sektor usaha yang relevan']},
    {'domain':'Ketenagakerjaan','keywords':['pekerja','buruh','karyawan','phk','upah','hubungan kerja','pesangon'],'sources':['Peraturan ketenagakerjaan yang berlaku beserta perubahan dan peraturan pelaksananya','Putusan PHI/MA yang relevan']},
    {'domain':'Pertanahan & Properti','keywords':['tanah','sertifikat','shm','hgb','hak milik','waris tanah','bpn','agraria'],'sources':['UUPA dan peraturan pertanahan yang berlaku','Peraturan ATR/BPN dan putusan yang relevan']},
    {'domain':'Keluarga & Peradilan Agama','keywords':['perkawinan','cerai','talak','nafkah','hak asuh','waris islam','wakaf'],'sources':['Peraturan perkawinan/keluarga yang berlaku','Kompilasi Hukum Islam jika relevan','PERMA/SEMA dan putusan peradilan agama yang relevan']},
    {'domain':'Konsumen','keywords':['konsumen','pelaku usaha','garansi','produk','jasa','kerugian konsumen'],'sources':['Undang-undang perlindungan konsumen dan peraturan pelaksananya']},
    {'domain':'Teknologi, ITE & Data','keywords':['data pribadi','privasi','elektronik','internet','digital','sistem elektronik','informasi elektronik'],'sources':['Peraturan perlindungan data pribadi yang berlaku','Peraturan informasi dan transaksi elektronik yang berlaku beserta perubahannya','Peraturan pelaksana sektor digital yang relevan']},
    {'domain':'Administrasi Pemerintahan','keywords':['keputusan tata usaha','pejabat','izin','perizinan','administrasi pemerintahan','ptun'],'sources':['Peraturan administrasi pemerintahan dan peradilan tata usaha negara yang berlaku','Peraturan sektoral pemberi kewenangan']},
]

def _case_issue_spot(text):
    low=text.lower(); matched=[]
    for item in CASE_LAW_REGISTRY:
        hits=[k for k in item['keywords'] if k in low]
        if hits: matched.append((len(hits),item,hits))
    matched.sort(key=lambda x:x[0],reverse=True)
    return matched


def _unique(items, limit=None):
    out=[]; seen=set()
    for item in items:
        key=re.sub(r'\s+',' ',str(item or '')).strip().lower()
        if not key or key in seen: continue
        seen.add(key); out.append(item)
        if limit and len(out)>=limit: break
    return out


def _money_values(text):
    vals=[]
    for m in re.finditer(r'Rp\.?\s*([0-9][0-9\.\,]*)', text, re.I):
        raw=m.group(0).replace('\n',' ')
        if raw not in vals: vals.append(raw)
    return vals[:12]


def _date_values(text):
    pats=[r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b',r'\b\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}\b',r'\b(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}\b']
    vals=[]
    for pat in pats:
        vals += re.findall(pat,text,re.I)
    return _unique(vals,12)


def _provision_refs(text):
    refs=[]
    patterns=[
      r'Pasal\s+\d+[A-Za-z]?(?:\s+ayat\s*\([^\)]*\))?(?:\s+huruf\s+[a-z])?',
      r'Undang-Undang(?:\s+Republik Indonesia)?\s+Nomor\s+\d+\s+Tahun\s+\d{4}[^\n\.;]{0,120}',
      r'UU\s+No\.?\s*\d+\s+Tahun\s+\d{4}[^\n\.;]{0,100}',
      r'Peraturan\s+Otoritas\s+Jasa\s+Keuangan[^\n\.;]{0,120}',
      r'PERMA\s+Nomor\s+\d+\s+Tahun\s+\d{4}',r'SEMA\s+Nomor\s+\d+\s+Tahun\s+\d{4}'
    ]
    for pat in patterns:
        refs += re.findall(pat,text,re.I)
    return _unique([re.sub(r'\s+',' ',x).strip() for x in refs],20)


def _select_sentences(text, markers, limit=8, exclude=None):
    exclude=exclude or []
    out=[]
    for s in sentences(text):
        low=s.lower()
        if any(k in low for k in markers) and not any(k in low for k in exclude):
            out.append(s[:900])
    return _unique(out,limit)


def _deep_case_profile(text):
    low=text.lower(); ss=sentences(text)
    is_criminal=any(k in low for k in ['tersangka','terdakwa','dakwaan','penyidik','pidana','kejaksaan','korupsi'])
    is_corruption=any(k in low for k in ['korupsi','tipikor','pemberantasan tindak pidana korupsi','pasal 603'])
    is_credit=any(k in low for k in ['kredit','bpr','debitur','perkreditan','agunan','5c','slik'])

    incr_markers=['mengakui','benar','saya setujui','saya menyetujui','pemutus kredit','menyimpang','menyimpangi','tidak membuat justifikasi','tanpa survey','tanpa survei','tidak memeriksa','tidak sesuai ketentuan','bertentangan dengan ketentuan','memiliki kewenangan untuk menolak','saya acc','saya memutuskan']
    mitig_markers=['tidak pernah memerintah','tidak pernah melarang','percaya kepada','berdasarkan pertimbangan','komite kredit','kredit sebelumnya','riwayat pembayaran lancar','bpkb','agunan','fidusia','dokumen fiat','dokumen analisa','tidak menerima','tidak mengetahui','tidak ikut langsung','bagian marketing','kewenangan bagian kredit']
    incr=_select_sentences(text,incr_markers,10)
    mitig=_select_sentences(text,mitig_markers,10)

    facts=[]
    for s in ss:
        l=s.lower()
        if any(k in l for k in ['rp.','rp ','tanggal','tahun 20','direktur','debitur','perjanjian kredit','pemutus kredit','agunan','survei','survey']): facts.append(s[:700])
    facts=_unique(facts,12) or ss[:8]

    issues=[]
    if is_corruption:
        issues += [
          'Apakah penyimpangan prosedur/tata kelola perkreditan dapat dibuktikan sebagai perbuatan koruptif, bukan semata keputusan bisnis/perbankan yang buruk?',
          'Apakah terdapat kesengajaan atau tujuan menguntungkan diri sendiri, orang lain, atau korporasi yang dapat diatribusikan secara personal kepada pihak yang dianalisis?',
          'Apakah kerugian keuangan negara/daerah telah dihitung sebagai kerugian nyata (actual loss), dengan memperhitungkan pembayaran, outstanding, agunan, dan hasil pemulihan?',
          'Apakah terdapat hubungan kausal langsung antara keputusan pihak yang dianalisis dengan kerugian, atau terdapat kontribusi pihak lain/intervening acts?',
          'Apakah pembagian tanggung jawab antara pemutus akhir, komite kredit, pejabat pemasaran, kepatuhan, SPI, dewan pengawas, dan debitur telah dipetakan secara individual?'
        ]
    if is_credit:
        issues += [
          'Apakah SOP/PKPB dan aturan internal yang dipakai penyidik benar-benar masih berlaku pada tempus perbuatan?',
          'Apakah deviasi dari batas agunan, survei, analisa 5C, provisi/administrasi, atau prosedur internal mempunyai mekanisme pengecualian/justifikasi?',
          'Siapa yang secara fungsional wajib melakukan survei, verifikasi pendapatan, SLIK, penilaian agunan, dan monitoring pascapencairan?'
        ]
    if is_criminal:
        issues += ['Apakah hak tersangka, pendampingan penasihat hukum, pemberitahuan sangkaan, dan proses pemeriksaan telah dipenuhi sesuai hukum acara yang berlaku?']

    years=sorted(set(int(x) for x in re.findall(r'\b(20\d{2})\b',text)))
    temporal=False
    if years and min(years)<=2022 and any(y>=2023 for y in years):
        temporal=True
        issues.append('Isu tempus/ketentuan peralihan: perbuatan disebut terjadi sebelum berlakunya sebagian norma yang dirujuk dalam proses 2026; perlu comparative-law analysis untuk menentukan norma yang sah dan paling menguntungkan sesuai ketentuan peralihan.')

    elements=[]
    if is_corruption:
        elements=[
          {'element':'Perbuatan melawan hukum/penyalahgunaan kewenangan','prosecution_support':'Ada indikasi deviasi prosedur dan kewenangan pemutus akhir jika fakta/dokumen membuktikannya.','defense_focus':'Pisahkan pelanggaran SOP/administratif dari kualitas perbuatan pidana; uji status berlaku SOP dan adanya collective decision process.','status':'DISPUTED'},
          {'element':'Mens rea / tujuan menguntungkan','prosecution_support':'Dapat diinferensikan dari keputusan yang sadar menyimpang jika dibarengi bukti motif/benefit.','defense_focus':'Cari atau bantah bukti fee, kickback, afiliasi, aliran dana, atau keuntungan personal; motif peningkatan kinerja bank tidak identik dengan motif koruptif.','status':'EVIDENCE NEEDED'},
          {'element':'Kerugian keuangan negara/daerah nyata','prosecution_support':'Kredit bermasalah dapat menjadi basis perhitungan jika auditor membuktikan actual loss.','defense_focus':'Minta LHP/PKKN, outstanding, pembayaran, pencadangan, nilai dan realisasi agunan, serta metode audit; plafon kredit tidak otomatis sama dengan kerugian.','status':'MUST BE PROVEN'},
          {'element':'Kausalitas','prosecution_support':'Jaksa dapat menghubungkan persetujuan kredit dengan pencairan dan kerugian.','defense_focus':'Uji tindakan debitur, kualitas analisa staf, monitoring, kondisi usaha, dan tindakan setelah pencairan sebagai faktor kausal/intervening.','status':'DISPUTED'},
          {'element':'Personal responsibility','prosecution_support':'Pemutus akhir dapat diposisikan sebagai pihak yang memiliki final authority.','defense_focus':'Buat responsibility matrix per fungsi; tandatangan final tidak otomatis berarti seluruh fakta teknis diketahui atau dibuat oleh pemutus akhir.','status':'MUST BE INDIVIDUALIZED'}
        ]

    gaps=[]
    if is_corruption:
        gaps += ['Laporan hasil perhitungan kerugian keuangan negara/daerah lengkap beserta metode dan tanggal cut-off','Bukti aliran dana/keuntungan pribadi, afiliasi, gratifikasi, fee, kickback, atau hubungan khusus dengan debitur','Status pembayaran kredit, outstanding principal, bunga, kolektibilitas, CKPN/pencadangan, dan pemulihan','Status dan nilai aktual agunan serta tindakan eksekusi fidusia/penjualan agunan']
    if is_credit:
        gaps += ['PKPB/SOP yang berlaku tepat pada tanggal keputusan kredit','Seluruh SK/SE Direksi dan perubahan/revokasinya','POJK/aturan eksternal yang berlaku pada tempus kredit','SLIK, berita acara survei, analisa 5C, analisa pendapatan, appraisal agunan, opinion kepatuhan, notulen/lembar komite, fiat, dan bukti pencairan','Laporan SPI/internal audit dan tindak lanjut atas temuan']
    if is_criminal:
        gaps += ['BAP saksi lain, ahli, dokumen penyitaan, audit, dan alat bukti yang dipakai untuk menghubungkan masing-masing unsur pasal']

    strategy=[]
    if is_corruption:
        strategy += [
          'Jangan membangun pembelaan utama dengan menyangkal seluruh penyimpangan jika dokumen/BAP justru mengakuinya; akui area tata kelola yang memang terbukti lalu pisahkan dari unsur pidana korupsi.',
          'Susun element-by-element defense matrix: fakta → bukti → unsur pasal → bukti jaksa → bantahan → bukti pembelaan → status pembuktian.',
          'Prioritaskan audit actual loss dan causal chain sebelum menyimpulkan terpenuhinya unsur kerugian negara.',
          'Audit hubungan pihak yang dianalisis dengan debitur dan lakukan financial tracing untuk menguji ada/tidaknya keuntungan personal.',
          'Ajukan saksi a de charge dan ahli yang relevan (perbankan/BPR, audit kerugian, tata kelola, dan bila perlu hukum pidana) berdasarkan gap bukti yang ditemukan.'
        ]
    if is_credit:
        strategy += ['Rekonstruksi credit approval chain dari permohonan sampai monitoring pascapencairan dan petakan siapa mengetahui apa, kapan, serta berdasarkan dokumen apa.']
    if temporal:
        strategy += ['Buat matriks tempus delicti vs norma lama/norma baru/ketentuan peralihan dan bandingkan unsur serta ancaman pidana untuk memastikan penerapan hukum yang sah dan lebih menguntungkan bila relevan.']

    conclusion=('Dokumen menunjukkan risiko hukum material pada aspek tata kelola/prosedur. Namun pelanggaran prosedur tidak otomatis membuktikan tindak pidana; kesimpulan pidana memerlukan pembuktian unsur secara individual, termasuk mens rea, actual loss, causal connection, dan personal responsibility.' if is_corruption else 'Dokumen memerlukan pengujian unsur hukum secara terstruktur terhadap fakta, bukti, kewenangan, status norma, dan hubungan kausal sebelum kesimpulan final dibuat.')

    return {
      'facts':facts,'incriminating_facts':incr,'mitigating_facts':mitig,'legal_issues':_unique(issues,14),
      'element_matrix':elements,'evidentiary_gaps':_unique(gaps,18),'strategy':_unique(strategy,14),
      'conclusion':conclusion,'temporal_issue':temporal,'money_values':_money_values(text),'date_values':_date_values(text),'provision_refs':_provision_refs(text),
      'is_criminal':is_criminal,'is_corruption':is_corruption,'is_credit':is_credit
    }


def _case_analysis_payload(text,title='Case Analysis',input_type='narrative',filename='',official_verification=None):
    matched=_case_issue_spot(text); profile=_deep_case_profile(text)
    applicable=[]
    for _,item,hits in matched[:7]:
        for src in item['sources']:
            if not any(x.get('source')==src for x in applicable):
                applicable.append({'domain':item['domain'],'source':src,'status':'PERLU VERIFIKASI PASAL, PERUBAHAN, STATUS BERLAKU, DAN RELEVANSI TERHADAP FAKTA'})
    for ref in profile['provision_refs'][:12]:
        if not any(ref.lower() in x['source'].lower() for x in applicable):
            applicable.insert(0,{'domain':'Norma disebut dalam dokumen','source':ref,'status':'WAJIB DICEK KE SUMBER RESMI + TEMPUS/STATUS BERLAKU'})
    if not applicable:
        applicable=[{'domain':'Umum','source':'Peraturan dan putusan resmi yang relevan setelah isu diklasifikasikan','status':'PERLU IDENTIFIKASI LANJUT'}]

    official_verification=official_verification or {}
    verification_status=official_verification.get('status','NOT_RUN')
    legal_status=('AKSES SUMBER RESMI OTORITATIF LENGKAP — ANALISIS SUBSTANTIF TETAP PROFESSIONAL REVIEW PENDING' if verification_status=='FULL_OFFICIAL_SOURCE_ACCESS' else
                  'AKSES SUMBER RESMI OTORITATIF PARSIAL — DASAR HUKUM BELUM BOLEH DINYATAKAN LENGKAP' if verification_status=='PARTIAL_OFFICIAL_SOURCE_ACCESS' else
                  'SUMBER RESMI OTORITATIF BELUM TERVERIFIKASI')

    evidence=['Kronologi bertanggal dan identitas/kapasitas seluruh pihak','Dokumen asli yang membentuk hubungan hukum dan kewenangan','Bukti elektronik/keuangan beserta metadata bila relevan']
    evidence += profile['evidentiary_gaps']
    risks=['Analisis berbasis dokumen yang diunggah; fakta di luar dokumen dapat mengubah kesimpulan.','Pengakuan dalam BAP/dokumen harus dibaca bersama dokumen primer, BAP pihak lain, audit, dan alat bukti lain; satu dokumen tidak boleh diperlakukan sebagai keseluruhan berkas perkara.','Status berlaku, perubahan, pencabutan, ketentuan peralihan, lex specialis/lex posterior, serta putusan pengujian wajib diverifikasi pada sumber resmi.']

    pros=[]
    if profile['mitigating_facts']:
        pros += ['Fakta yang berpotensi mendukung pembelaan/mitigasi harus diuji terhadap dokumen primer: '+x for x in profile['mitigating_facts'][:5]]
    cons=[]
    if profile['incriminating_facts']:
        cons += ['Fakta yang berpotensi digunakan penuntut/lawan: '+x for x in profile['incriminating_facts'][:5]]
    if not pros: pros=['Belum teridentifikasi fakta meringankan yang kuat hanya dari teks; diperlukan pembacaan bukti lain.']
    if not cons: cons=['Belum teridentifikasi fakta memberatkan yang kuat hanya dari teks; diperlukan pembacaan bukti lain.']

    analysis=profile['conclusion']
    if profile['is_corruption']:
        analysis += ' Fokus analisis tidak berhenti pada apakah SOP dilanggar, tetapi pada apakah jaksa dapat membuktikan setiap unsur pidana di luar keraguan yang wajar. Untuk kasus berbasis kredit/perbankan, actual loss, causal chain, pembagian fungsi organisasi, dan bukti keuntungan personal harus dipisahkan secara tegas.'
    if profile['temporal_issue']:
        analysis += ' Terdapat pula isu temporal law yang harus diaudit karena dokumen memuat tahun perbuatan dan norma yang berbeda masa berlakunya.'

    return dict(
      title=title,input_type=input_type,filename=filename,source_text=text,
      facts=profile['facts'],incriminating_facts=profile['incriminating_facts'],mitigating_facts=profile['mitigating_facts'],
      legal_issues=profile['legal_issues'],applicable_law=applicable,legal_analysis=analysis,
      element_matrix=profile['element_matrix'],arguments_for=pros,arguments_against=cons,
      evidence_needed=_unique(evidence,24),evidentiary_gaps=profile['evidentiary_gaps'],risks=risks,
      recommendations=profile['strategy'] or ['Susun matriks Fakta → Bukti → Norma → Unsur → Kesimpulan → Risiko.'],
      money_values=profile['money_values'],date_values=profile['date_values'],provision_refs=profile['provision_refs'],
      official_verification=official_verification,legal_status=legal_status,
      analytical_method='DEEP_CASE_ANALYSIS_V2',
      coverage_note='LexiCore v1.2.2 membaca dokumen dengan pendekatan source-grounded: fakta material, fakta memberatkan/meringankan, issue spotting, element-by-element analysis, evidentiary gaps, mens rea, actual loss, causal chain, personal responsibility, tempus/ketentuan peralihan, dan strategi langkah hukum. Official JDIH Federation digunakan untuk verifikasi sumber; kesimpulan final tetap Professional Verification: PENDING.'
    )


def _case_verification_queries(text,title):
    matched=_case_issue_spot(text); profile=_deep_case_profile(text); queries=[]
    if title and title.lower()!='case analysis': queries.append(title)
    # Statutes explicitly named in the uploaded document receive first priority.
    for ref in profile['provision_refs'][:6]: queries.append(ref)
    for _,item,hits in matched[:5]:
        q=' '.join(hits[:3]).strip(); queries.append((item['domain']+' '+q).strip())
        for src in item['sources'][:2]:
            if any(k in src.lower() for k in ('uu no.','undang-undang','kuhp','kuhperdata','perma','sema','putusan')):
                queries.append(src.replace('yang relevan','').replace('yang berlaku','').strip())
    if not queries:
        queries=[' '.join(re.findall(r'\b[\w-]{4,}\b',text[:1000],flags=re.UNICODE)[:8])]
    return _unique([q for q in queries if len(q)>=4],6)

@app.route('/api/legal-sources')
def legal_sources_registry():
    return jsonify(success=True,data=public_source_registry(),count=len(public_source_registry()))

@app.route('/api/legal-sources/health')
def legal_sources_health():
    data=source_health(); auth=[x for x in data if x.get('authoritative')]; directory=[x for x in data if not x.get('authoritative')]; return jsonify(success=True,data=data,reachable=sum(1 for x in auth if x.get('reachable')),count=len(auth),directory={'reachable':sum(1 for x in directory if x.get('reachable')),'count':len(directory)},checked_at=datetime.now().isoformat())

@app.route('/api/legal-sources/search')
def legal_sources_search():
    q=(request.args.get('q') or '').strip()
    if len(q)<3: return jsonify(success=False,error='Query minimal 3 karakter'),400
    return jsonify(success=True,query=q,data=federated_search(q))

@app.route('/api/case-analysis',methods=['GET','POST'])
def case_analysis():
    if request.method=='GET': return jsonify(success=True,data=CaseAnalysisManager.all(request.args.get('limit',30,type=int)))
    text=''; title='Case Analysis'; input_type='narrative'; filename=''; has_document=False; extracted=''
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        title=(request.form.get('title') or 'Case Analysis').strip(); narrative=(request.form.get('narrative') or '').strip(); text=narrative; f=request.files.get('file')
        if f and f.filename:
            has_document=True
            if not allowed_file(f.filename): return jsonify(success=False,error='Dokumen Case Analysis hanya mendukung PDF/DOCX'),400
            td=tempfile.mkdtemp()
            try:
                filename=secure_filename(f.filename); path=os.path.join(td,filename); f.save(path); extracted=DocumentExtractor.extract_text(path).strip()
                if not extracted:
                    return jsonify(success=False,error='Dokumen berhasil diunggah tetapi teks tidak dapat diekstrak. Pastikan PDF memiliki text layer atau gunakan DOCX.'),400
                text=(narrative+'\n\n'+extracted).strip(); input_type='document' if not narrative else 'narrative+document'
            finally: shutil.rmtree(td,ignore_errors=True)
        elif len(narrative)<120:
            return jsonify(success=False,error='Untuk analisis tanpa dokumen, narasi minimal 120 karakter diperlukan.'),400
    else:
        d=request.get_json(silent=True) or {}; title=(d.get('title') or 'Case Analysis').strip(); text=(d.get('narrative') or d.get('source_text') or '').strip()
        if len(text)<120: return jsonify(success=False,error='Untuk analisis tanpa dokumen, narasi minimal 120 karakter diperlukan.'),400
    verify_online=True
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        verify_online=(request.form.get('verify_online','true').lower() not in ('0','false','no'))
    else:
        verify_online=bool((d if 'd' in locals() else {}).get('verify_online',True))
    official=None
    if verify_online:
        official=verify_queries(_case_verification_queries(text,title),include_health=True)
    result=_case_analysis_payload(text,title,input_type,filename,official); result['case_analysis_id']=CaseAnalysisManager.save(result)
    if official:
        result['verification_id']=LegalSourceVerificationManager.save(result['case_analysis_id'],official)
    return jsonify(success=True,data=result)

@app.route('/api/communications',methods=['GET','POST'])
def communications():
    if request.method=='GET': return jsonify(success=True,data=CommunicationManager.all(request.args.get('limit',30,type=int)))
    d=request.get_json(silent=True) or {}
    if not d.get('message','').strip(): return jsonify(success=False,error='Isi komunikasi wajib diisi'),400
    i=CommunicationManager.save(d); return jsonify(success=True,communication_id=i,message='Komunikasi tersimpan')

@app.route('/api/communication/generate',methods=['POST'])
def generate_communication():
    d=request.get_json(silent=True) or {}; kind=d.get('document_type','client_update'); client=d.get('client_name') or 'Klien'; matter=d.get('matter') or 'perkara/pekerjaan hukum Anda'; next_step=d.get('next_step') or 'kami akan melanjutkan penelaahan dan menginformasikan perkembangan berikutnya'
    templates={
      'client_update':(f'Pembaruan Perkara — {matter}',f'Yth. {client},\n\nKami menyampaikan pembaruan mengenai {matter}. Berdasarkan penelaahan saat ini, proses berjalan sesuai tahapan yang sedang ditangani. Langkah berikutnya: {next_step}.\n\nApabila terdapat dokumen atau informasi tambahan yang relevan, mohon disampaikan agar dapat kami masukkan dalam penelaahan.\n\nHormat kami,\nTim Hukum'),
      'document_request':(f'Permintaan Dokumen — {matter}',f'Yth. {client},\n\nUntuk melengkapi penanganan {matter}, mohon menyiapkan dan mengirimkan dokumen/informasi pendukung yang relevan. Dokumen akan digunakan terbatas untuk kepentingan penanganan hukum.\n\nLangkah berikutnya setelah dokumen diterima: {next_step}.\n\nHormat kami,\nTim Hukum'),
      'legal_notice':(f'Pemberitahuan Hukum — {matter}',f'Yth. {client},\n\nSurat ini merupakan pemberitahuan terkait {matter}. {next_step}. Isi final harus diverifikasi lawyer terhadap fakta, bukti, tenggat, dan dasar hukum sebelum dikirim kepada pihak tujuan.\n\nHormat kami,\nTim Hukum')}
    subject,message=templates.get(kind,templates['client_update']); return jsonify(success=True,data={'subject':subject,'message':message})

@app.route('/api/audit/logs')
def audit(): return jsonify(success=True,data=AuditLogger.get_recent_logs(request.args.get('limit',50,type=int)))

@app.route('/api/health')
def health(): return jsonify(status='online',timestamp=datetime.now().isoformat(),version='1.2.3',modules=['legal_drafting','contract_review','legal_research','compliance_risk','case_analysis','official_jdih_federation','client_communication'])

if __name__=='__main__':
    print('LexiCore v1.2.2 — Deep Case Analysis + Official JDIH Federation — http://localhost:5000'); app.run(debug=True,host='0.0.0.0',port=5000)
