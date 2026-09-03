"""LexiCore Local Regulatory Corpus.

v1.3.5 expands the curated working corpus and strengthens domain-aware
retrieval.  The corpus is intentionally *not* treated as final legal
authority.  Every record/article remains subject to official-source and
professional verification before it is used as a legal basis.

Design rules:
- A bare article number never becomes a final citation.
- Every article belongs to a regulation and is returned with that parent.
- Temporal applicability is explicit for amended/repealed instruments.
- Official-source URLs are metadata for verification, not proof that the
  local summary text is exhaustive or verbatim.
"""
from __future__ import annotations
from typing import Any, Dict, List
import re

REGULATION_HIERARCHY_WEIGHTS = {
    'UUD': 1, 'TAP_MPR': 2, 'UU': 3, 'PERPPU': 3, 'PP': 4, 'PERPRES': 5,
    'POJK': 6, 'PER_MENTERI': 6, 'PER_LEMBAGA': 6,
    'PERDA_PROV': 7, 'PERDA_KAB': 8, 'PERMA': 90, 'SEMA': 91,
}


def _art(aid: str, rid: str, pasal: str, content: str, topic: str, keywords: List[str], **extra) -> Dict[str, Any]:
    row = {
        'id': aid, 'regulation_id': rid, 'pasal': pasal, 'content': content,
        'topic': topic, 'keywords': keywords,
    }
    row.update(extra)
    return row


INITIAL_REGULATORY_CORPUS: List[Dict[str, Any]] = [
    {
        'id':'uud_1945','nomor':'UUD 1945','tahun':1945,
        'tentang':'Undang-Undang Dasar Negara Republik Indonesia Tahun 1945 (Pasca Perubahan I-IV)',
        'jenis':'UUD','hierarchy_rank':1,'status':'BERLAKU','effective_date':'1945-08-18','promulgation_date':'1945-08-18',
        'jdih_source':'Setneg / Mahkamah Konstitusi','official_url':'https://jdih.setneg.go.id/',
        'domain_tags':['konstitusi','hak asasi','kepastian hukum'],
        'articles':[
            _art('uud1945_1_3','uud_1945','Pasal 1 ayat (3)','Negara Indonesia adalah negara hukum.','Prinsip Negara Hukum (Rechtsstaat)',['negara hukum','rechtsstaat','kepastian hukum','due process']),
            _art('uud1945_28d_1','uud_1945','Pasal 28D ayat (1)','Hak atas pengakuan, jaminan, perlindungan, kepastian hukum yang adil, dan perlakuan yang sama di hadapan hukum.','Hak Atas Kepastian Hukum & Keadilan',['kepastian hukum yang adil','equality before the law','hak asasi']),
        ],
    },
    {
        'id':'kuhp_2023_2026','nomor':'UU No. 1 Tahun 2023 jo UU No. 1 Tahun 2026','tahun':2023,
        'tentang':'Kitab Undang-Undang Hukum Pidana (KUHP Nasional) sebagaimana disesuaikan dengan UU No. 1 Tahun 2026',
        'jenis':'UU','hierarchy_rank':3,'status':'BERLAKU','effective_date':'2026-01-02','promulgation_date':'2023-01-02',
        'jdih_source':'JDIH Setneg / BPK / Kemenkum','official_url':'https://peraturan.bpk.go.id/Details/234935/uu-no-1-tahun-2023',
        'domain_tags':['pidana materiil','korupsi','penipuan','penggelapan','tempus'],
        'articles':[
            _art('kuhp_1_1','kuhp_2023_2026','Pasal 1 ayat (1)','Asas legalitas: pemidanaan harus berdasar aturan pidana yang telah ada sebelum perbuatan dilakukan.','Asas Legalitas & Non-Retroaktif',['asas legalitas','nullum delictum','tempus delicti','non-retroaktif']),
            _art('kuhp_20','kuhp_2023_2026','Pasal 20','Korpus kerja mengenai pertanggungjawaban pelaku/penyertaan yang dirujuk dalam analisis pidana. Bunyi dan konstruksi ayat wajib diverifikasi pada naskah resmi.','Penyertaan / Pertanggungjawaban Pelaku',['penyertaan','turut serta','pelaku','pertanggungjawaban pidana']),
            _art('kuhp_603','kuhp_2023_2026','Pasal 603','Korpus kerja tindak pidana korupsi terkait perbuatan melawan hukum, pengayaan, dan kerugian keuangan/perekonomian negara. Bunyi pasal wajib diverifikasi ke sumber resmi.','Tindak Pidana Korupsi - Kerugian Negara Melawan Hukum',['korupsi','memperkaya diri','kerugian keuangan negara','melawan hukum'],cross_references=['uu_tipikor_31_1999']),
            _art('kuhp_604','kuhp_2023_2026','Pasal 604','Korpus kerja tindak pidana korupsi terkait tujuan menguntungkan dan penyalahgunaan kewenangan karena jabatan/kedudukan. Bunyi pasal wajib diverifikasi.','Tindak Pidana Korupsi - Penyalahgunaan Kewenangan',['penyalahgunaan kewenangan','jabatan','mens rea','kerugian negara'],cross_references=['uu_tipikor_31_1999','uu_administrasi_pemerintahan_30_2014']),
            _art('kuhp_492','kuhp_2023_2026','Pasal 492','Korpus kerja mengenai penipuan dalam KUHP Nasional; unsur pasal wajib diverifikasi ke sumber resmi.','Tindak Pidana Penipuan',['penipuan','tipu muslihat','nama palsu','rangkaian kebohongan']),
            _art('kuhp_486','kuhp_2023_2026','Pasal 486','Korpus kerja mengenai penggelapan dalam KUHP Nasional; unsur pasal wajib diverifikasi ke sumber resmi.','Tindak Pidana Penggelapan',['penggelapan','penguasaan barang','melawan hukum']),
        ],
    },
    {
        'id':'kuhperdata_bw','nomor':'Staatsblad 1847 No. 23','tahun':1847,
        'tentang':'Kitab Undang-Undang Hukum Perdata (Burgerlijk Wetboek)','jenis':'UU','hierarchy_rank':3,'status':'PARTIAL',
        'effective_date':'1848-05-01','promulgation_date':'1847-04-30','jdih_source':'JDIH Mahkamah Agung / sumber resmi terkait','official_url':'https://jdih.mahkamahagung.go.id/',
        'domain_tags':['perdata','perikatan','kontrak','wanprestasi','pmh'],
        'articles':[
            _art('bw_1233','kuhperdata_bw','Pasal 1233','Korpus kerja mengenai sumber perikatan yang lahir karena persetujuan atau undang-undang.','Sumber Perikatan',['perikatan','persetujuan','undang-undang','kewajiban']),
            _art('bw_1234','kuhperdata_bw','Pasal 1234','Korpus kerja mengenai prestasi untuk memberikan sesuatu, berbuat sesuatu, atau tidak berbuat sesuatu.','Jenis Prestasi',['prestasi','kewajiban kontraktual','berbuat','tidak berbuat']),
            _art('bw_1238','kuhperdata_bw','Pasal 1238','Korpus kerja mengenai keadaan lalai/ingebrekestelling; penerapan dan pengecualian wajib dibaca bersama perjanjian dan norma sektoral.','Somasi dan Keadaan Lalai',['somasi','lalai','wanprestasi','teguran tertulis']),
            _art('bw_1243','kuhperdata_bw','Pasal 1243','Korpus kerja mengenai ganti biaya, rugi, dan bunga karena wanprestasi setelah keadaan lalai.','Wanprestasi dan Ganti Kerugian',['wanprestasi','somasi','ingkar janji','ganti rugi']),
            _art('bw_1244_1245','kuhperdata_bw','Pasal 1244-1245','Korpus kerja mengenai keadaan memaksa/force majeure dan pembebasan dari ganti rugi dalam kondisi tertentu; penerapan harus diuji terhadap fakta dan kontrak.','Force Majeure / Keadaan Memaksa',['force majeure','keadaan memaksa','overmacht','ganti rugi']),
            _art('bw_1266_1267','kuhperdata_bw','Pasal 1266-1267','Korpus kerja mengenai pembatalan/pemutusan perjanjian timbal balik dan tuntutan pemenuhan atau ganti rugi; status penerapan harus diverifikasi kontekstual.','Pemutusan Perjanjian dan Upaya Hukum',['pemutusan perjanjian','pembatalan','ganti rugi','wanprestasi']),
            _art('bw_1313','kuhperdata_bw','Pasal 1313','Korpus kerja mengenai pengertian persetujuan/perjanjian; digunakan sebagai titik awal identifikasi hubungan kontraktual.','Pengertian Perjanjian',['perjanjian','persetujuan','kontrak','hubungan hukum']),
            _art('bw_1320','kuhperdata_bw','Pasal 1320','Syarat sah perjanjian: kesepakatan, kecakapan, objek tertentu, dan sebab yang tidak dilarang.','Syarat Sahnya Perjanjian',['syarat sah perjanjian','kesepakatan','kecakapan','kausa halal','objek tertentu']),
            _art('bw_1337','kuhperdata_bw','Pasal 1337','Korpus kerja mengenai sebab yang terlarang karena bertentangan dengan undang-undang, kesusilaan, atau ketertiban umum.','Kausa Terlarang',['kausa terlarang','ketertiban umum','kesusilaan','illegal contract']),
            _art('bw_1338','kuhperdata_bw','Pasal 1338','Asas pacta sunt servanda, pembatasan penarikan kembali, dan pelaksanaan perjanjian dengan itikad baik.','Asas Pacta Sunt Servanda & Itikad Baik',['pacta sunt servanda','itikad baik','kebebasan berkontrak']),
            _art('bw_1365','kuhperdata_bw','Pasal 1365','Korpus kerja mengenai perbuatan melawan hukum dan kewajiban mengganti kerugian akibat kesalahan.','Perbuatan Melawan Hukum (Onrechtmatige Daad)',['perbuatan melawan hukum','pmh','onrechtmatige daad','kausalitas','kerugian perdata']),
        ],
    },
    {
        'id':'uu_tipikor_31_1999','nomor':'UU No. 31 Tahun 1999 jo UU No. 20 Tahun 2001','tahun':1999,
        'tentang':'Pemberantasan Tindak Pidana Korupsi','jenis':'UU','hierarchy_rank':3,
        'status':'BERLAKU_DENGAN_PENCABUTAN_SEBAGIAN_SEJAK_2026','effective_date':'1999-08-16','promulgation_date':'1999-08-16',
        'jdih_source':'JDIH BPK RI / KPK RI','official_url':'https://peraturan.bpk.go.id/Details/45350/uu-no-31-tahun-1999',
        'temporal_note':'BPK mencatat antara lain Pasal 2 ayat (1) dan Pasal 3 dicabut sebagian/beralih melalui KUHP Nasional; analisis harus memperhatikan tempus dan aturan transisi.',
        'domain_tags':['tipikor','korupsi','kerugian negara','penyalahgunaan wewenang'],
        'articles':[
            _art('tipikor_2','uu_tipikor_31_1999','Pasal 2 ayat (1)','Korpus kerja: unsur melawan hukum, pengayaan, dan kerugian keuangan/perekonomian negara; dampak perubahan/pengujian wajib diverifikasi pada sumber primer.','Korupsi Memperkaya Diri - Actual Loss',['korupsi','kerugian keuangan negara','actual loss','putusan mk 25'],related_court_decisions=['Putusan MK No. 25/PUU-XIV/2016']),
            _art('tipikor_3','uu_tipikor_31_1999','Pasal 3','Korpus kerja: tujuan menguntungkan, penyalahgunaan kewenangan/kesempatan/sarana karena jabatan atau kedudukan, dan kerugian negara; status temporal wajib diverifikasi.','Korupsi Penyalahgunaan Wewenang',['penyalahgunaan wewenang','mens rea','jabatan','bpr','direksi']),
            _art('tipikor_9','uu_tipikor_31_1999','Pasal 9','Korpus kerja mengenai tindak pidana terkait pemalsuan/rekayasa buku atau daftar yang secara khusus diatur UU Tipikor; bunyi unsur wajib diverifikasi.','Tipikor - Buku/Daftar Administratif',['pasal 9','buku','daftar','administrasi','tipikor']),
            _art('tipikor_18','uu_tipikor_31_1999','Pasal 18','Korpus kerja mengenai pidana tambahan/pemulihan aset, termasuk isu uang pengganti dan perampasan; penerapan wajib diverifikasi pada naskah resmi dan putusan.','Pidana Tambahan & Pemulihan Aset',['pasal 18','uang pengganti','perampasan','pemulihan aset']),
        ],
    },
    {
        'id':'uu_administrasi_pemerintahan_30_2014','nomor':'UU No. 30 Tahun 2014','tahun':2014,
        'tentang':'Administrasi Pemerintahan','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'2014-10-17','promulgation_date':'2014-10-17','jdih_source':'JDIH BPK RI / Setneg','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['administrasi pemerintahan','wewenang','penyalahgunaan wewenang','diskresi'],
        'articles':[
            _art('ap_17','uu_administrasi_pemerintahan_30_2014','Pasal 17','Korpus kerja mengenai larangan penyalahgunaan wewenang oleh badan/pejabat pemerintahan. Ruang lingkup dan perubahan wajib diverifikasi.','Larangan Penyalahgunaan Wewenang',['penyalahgunaan wewenang','melampaui wewenang','mencampuradukkan wewenang','sewenang-wenang']),
            _art('ap_18','uu_administrasi_pemerintahan_30_2014','Pasal 18','Korpus kerja mengenai kategori penyalahgunaan wewenang dalam hukum administrasi. Jangan otomatis disamakan dengan unsur pidana tanpa analisis norma khusus.','Kategori Penyalahgunaan Wewenang',['wewenang','administratif','diskresi','penyalahgunaan wewenang']),
        ],
    },
    {
        'id':'uu_pt_40_2007','nomor':'UU No. 40 Tahun 2007','tahun':2007,'tentang':'Perseroan Terbatas','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'2007-08-16','promulgation_date':'2007-08-16','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/Details/39901/uu-no-40-tahun-2007',
        'domain_tags':['perseroan','direksi','komisaris','pemegang saham','tanggung jawab'],
        'articles':[
            _art('pt_92','uu_pt_40_2007','Pasal 92','Korpus kerja mengenai pengurusan perseroan oleh Direksi untuk kepentingan dan sesuai maksud/tujuan perseroan.','Wewenang Pengurusan Direksi',['direksi','pengurusan perseroan','kewenangan direksi','maksud tujuan perseroan']),
            _art('pt_97','uu_pt_40_2007','Pasal 97 ayat (2) & (5)','Korpus kerja mengenai tanggung jawab Direksi dan kondisi pengecualian tanggung jawab apabila memenuhi standar itikad baik, kehati-hatian, tanpa benturan kepentingan, dan upaya pencegahan.','Tanggung Jawab Direksi & Business Judgment Rule (BJR)',['business judgment rule','bjr','fiduciary duty','direksi','tanggung jawab pribadi']),
            _art('pt_98','uu_pt_40_2007','Pasal 98','Korpus kerja mengenai kewenangan Direksi mewakili Perseroan di dalam dan di luar pengadilan, dengan pembatasan yang harus dibaca bersama anggaran dasar/UU.','Representasi Perseroan oleh Direksi',['direksi','mewakili perseroan','representasi','kewenangan']),
            _art('pt_102','uu_pt_40_2007','Pasal 102','Korpus kerja mengenai tindakan pengalihan/penjaminan kekayaan Perseroan dalam jumlah material dan kebutuhan persetujuan RUPS pada kondisi tertentu.','Transaksi Material Aset Perseroan',['aset perseroan','rups','pengalihan kekayaan','jaminan utang']),
            _art('pt_114','uu_pt_40_2007','Pasal 114','Korpus kerja mengenai tugas, tanggung jawab, dan pertanggungjawaban Dewan Komisaris dalam pengawasan dan pemberian nasihat.','Tanggung Jawab Dewan Komisaris',['dewan komisaris','pengawasan','nasihat','tanggung jawab']),
        ],
    },
    {
        'id':'uu_ketenagakerjaan_13_2003_6_2023','nomor':'UU No. 13 Tahun 2003 jo UU No. 6 Tahun 2023','tahun':2003,
        'tentang':'Ketenagakerjaan sebagaimana diubah melalui rezim Cipta Kerja','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'2003-03-25','promulgation_date':'2003-03-25','jdih_source':'JDIH BPK RI / Kemnaker','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['ketenagakerjaan','hubungan kerja','phk','pesangon','upah'],
        'articles':[
            _art('ketenagakerjaan_50_51','uu_ketenagakerjaan_13_2003_6_2023','Pasal 50-51','Korpus kerja mengenai dasar hubungan kerja dan bentuk perjanjian kerja; perubahan dan ketentuan pelaksana wajib diverifikasi.','Hubungan Kerja & Perjanjian Kerja',['hubungan kerja','perjanjian kerja','pekerja','pengusaha']),
            _art('ketenagakerjaan_56','uu_ketenagakerjaan_13_2003_6_2023','Pasal 56 (sebagaimana diubah)','Korpus kerja mengenai PKWT/PKWTT; harus dibaca bersama PP No. 35 Tahun 2021.','PKWT dan PKWTT',['pkwt','pkwtt','kontrak kerja','jangka waktu']),
            _art('ketenagakerjaan_88','uu_ketenagakerjaan_13_2003_6_2023','Pasal 88 dan ketentuan terkait (sebagaimana diubah)','Korpus kerja mengenai kebijakan pengupahan dan hak pekerja atas penghidupan yang layak; norma rinci wajib diverifikasi pada teks berlaku.','Pengupahan',['upah','pengupahan','hak pekerja','upah minimum']),
            _art('ketenagakerjaan_151','uu_ketenagakerjaan_13_2003_6_2023','Pasal 151 (sebagaimana diubah)','Korpus kerja mengenai prosedur dan pemberitahuan pemutusan hubungan kerja. Bunyi, perubahan, pengecualian, dan prosedur wajib diverifikasi.','Pemutusan Hubungan Kerja - Prosedur',['phk','pemutusan hubungan kerja','pemberitahuan phk','perselisihan hubungan industrial']),
            _art('ketenagakerjaan_156','uu_ketenagakerjaan_13_2003_6_2023','Pasal 156 (sebagaimana diubah)','Korpus kerja mengenai hak pekerja akibat pemutusan hubungan kerja, termasuk komponen kompensasi yang harus dibaca bersama aturan pelaksana.','PHK - Pesangon dan Hak Pekerja',['pesangon','uang penghargaan masa kerja','uang penggantian hak','phk']),
        ],
    },
    {
        'id':'pp_35_2021','nomor':'PP No. 35 Tahun 2021','tahun':2021,
        'tentang':'PKWT, Alih Daya, Waktu Kerja dan Waktu Istirahat, dan Pemutusan Hubungan Kerja','jenis':'PP','hierarchy_rank':4,'status':'BERLAKU',
        'effective_date':'2021-02-02','promulgation_date':'2021-02-02','jdih_source':'JDIH BPK RI / Setneg','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['ketenagakerjaan','pkwt','alih daya','phk','kompensasi'],
        'articles':[
            _art('pp35_pkwt','pp_35_2021','Ketentuan PKWT','Korpus kerja aturan pelaksana mengenai jangka waktu/selesainya pekerjaan tertentu, pencatatan, dan hak terkait PKWT. Nomor pasal spesifik wajib diverifikasi.','PKWT',['pkwt','kontrak kerja','jangka waktu','kompensasi pkwt']),
            _art('pp35_kompensasi_pkwt','pp_35_2021','Ketentuan uang kompensasi PKWT','Korpus kerja mengenai uang kompensasi bagi pekerja PKWT sesuai syarat dan masa kerja tertentu. Formula final wajib diverifikasi pada naskah resmi.','Kompensasi PKWT',['uang kompensasi','pkwt','masa kerja']),
            _art('pp35_phk','pp_35_2021','Ketentuan alasan dan prosedur PHK','Aturan pelaksana utama untuk alasan dan prosedur PHK. Alasan spesifik dan prosedur wajib diverifikasi pada naskah resmi.','PHK - Alasan & Prosedur',['phk','pemutusan hubungan kerja','alasan phk','pemberitahuan']),
            _art('pp35_hak_phk','pp_35_2021','Ketentuan hak akibat PHK','Korpus kerja formula hak akibat PHK yang harus dipasangkan dengan alasan PHK dan masa kerja.','PHK - Kompensasi',['pesangon','uang penghargaan masa kerja','uang penggantian hak','kompensasi']),
        ],
    },
    {
        'id':'uu_pphi_2_2004','nomor':'UU No. 2 Tahun 2004','tahun':2004,
        'tentang':'Penyelesaian Perselisihan Hubungan Industrial','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2005-01-14','promulgation_date':'2004-01-14','jdih_source':'JDIH BPK RI / Kemnaker','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['ketenagakerjaan','phi','perselisihan hubungan industrial','bipartit','mediasi'],
        'articles':[
            _art('pphi_2','uu_pphi_2_2004','Pasal 2','Mengelompokkan perselisihan hubungan industrial ke dalam perselisihan hak, kepentingan, PHK, dan antar-serikat dalam satu perusahaan.','Jenis Perselisihan Hubungan Industrial',['perselisihan hak','perselisihan kepentingan','perselisihan phk','serikat pekerja']),
            _art('pphi_3','uu_pphi_2_2004','Pasal 3','Korpus kerja mengenai kewajiban mengupayakan penyelesaian perselisihan melalui perundingan bipartit sebelum jalur berikutnya.','Perundingan Bipartit',['bipartit','perundingan','perselisihan hubungan industrial','phk']),
            _art('pphi_mediation','uu_pphi_2_2004','Mediasi/Konsiliasi dan Pengadilan Hubungan Industrial','Korpus kerja alur penyelesaian perselisihan setelah bipartit sesuai jenis perselisihan. Tenggat dan prosedur spesifik wajib diverifikasi.','Prosedur Penyelesaian PHI',['mediasi','konsiliasi','pengadilan hubungan industrial','phi']),
        ],
    },
    {
        'id':'uu_cipta_kerja_6_2023','nomor':'UU No. 6 Tahun 2023','tahun':2023,
        'tentang':'Penetapan Perppu No. 2 Tahun 2022 tentang Cipta Kerja Menjadi Undang-Undang','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2023-03-31','promulgation_date':'2023-03-31','jdih_source':'JDIH BPK RI / Setneg','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['cipta kerja','ketenagakerjaan','perizinan','perseroan','usaha'],
        'articles':[
            _art('cipta_kerja_ketenagakerjaan','uu_cipta_kerja_6_2023','Klaster Ketenagakerjaan','Mengubah sejumlah ketentuan ketenagakerjaan. LexiCore harus menelusuri pasal asal dan pasal perubahan secara qualified citation, bukan memakai label Cipta Kerja secara umum.','Perubahan Ketenagakerjaan',['cipta kerja','ketenagakerjaan','phk','pkwt','upah','pesangon'],cross_references=['uu_ketenagakerjaan_13_2003_6_2023','pp_35_2021']),
        ],
    },
    {
        'id':'uu_perbankan_7_1992_p2sk','nomor':'UU No. 7 Tahun 1992 jo UU No. 10 Tahun 1998 jo UU No. 4 Tahun 2023','tahun':1992,
        'tentang':'Perbankan sebagaimana terakhir diubah antara lain melalui UU P2SK','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'1992-03-25','promulgation_date':'1992-03-25','jdih_source':'JDIH BPK RI / OJK','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['perbankan','bpr','kredit','prinsip kehati-hatian','bank'],
        'articles':[
            _art('perbankan_8','uu_perbankan_7_1992_p2sk','Pasal 8 (kredit)','Korpus kerja mengenai kewajiban bank memiliki keyakinan berdasarkan analisis mendalam atas itikad dan kemampuan/kesanggupan debitur dalam pemberian kredit. Bunyi dan perubahan wajib diverifikasi.','Analisis Kredit & Keyakinan Bank',['pasal 8','kredit','debitur','analisis kredit','kemampuan bayar','itikad']),
            _art('perbankan_20b','uu_perbankan_7_1992_p2sk','Pasal 20B (mandat tata kelola BPR)','Korpus kerja mandat penguatan tata kelola BPR yang menjadi salah satu dasar POJK tata kelola terbaru.','Mandat Tata Kelola BPR',['pasal 20b','bpr','tata kelola','p2sk'],cross_references=['pojk_9_2024_tata_kelola_bpr']),
            _art('perbankan_29','uu_perbankan_7_1992_p2sk','Pasal 29 dan ketentuan terkait','Korpus kerja mengenai kesehatan bank dan prinsip kehati-hatian dalam kegiatan usaha bank. Identitas ayat dan perubahan wajib diverifikasi menurut tempus.','Prinsip Kehati-hatian Perbankan',['prinsip kehati-hatian','kesehatan bank','prudential banking','risiko kredit']),
            _art('perbankan_bpr','uu_perbankan_7_1992_p2sk','Ketentuan BPR/BPR Syariah','Korpus kerja mengenai kegiatan usaha dan kerangka kelembagaan BPR. Identitas pasal spesifik wajib diverifikasi menurut tempus.','Perbankan dan BPR',['bpr','bank perekonomian rakyat','bank perkreditan rakyat','kredit','perbankan']),
        ],
    },
    {
        'id':'pojk_4_2015_tata_kelola_bpr','nomor':'POJK No. 4/POJK.03/2015','tahun':2015,
        'tentang':'Penerapan Tata Kelola bagi Bank Perkreditan Rakyat','jenis':'POJK','hierarchy_rank':6,'status':'DICABUT_MULAI_2024_RELEVAN_UNTUK_TEMPUS_SEBELUMNYA',
        'effective_date':'2015-04-01','promulgation_date':'2015-04-01','jdih_source':'OJK','official_url':'https://ojk.go.id/id/regulasi/Pages/POJK-tentang-Penerapan-Tata-Kelola-bagi-Bank-Perkreditan-Rakyat.aspx',
        'temporal_note':'Relevan untuk perkara sebelum 1 Juli 2024; dicabut oleh POJK No. 9 Tahun 2024. Ketentuan pelaksanaan lama dapat tetap berlaku sepanjang tidak bertentangan dengan POJK 9/2024.',
        'domain_tags':['bpr','tata kelola','direksi','kepatuhan','audit'],
        'articles':[
            _art('pojk4_direksi','pojk_4_2015_tata_kelola_bpr','Pilar tugas dan tanggung jawab Direksi','Korpus kerja tata kelola tugas/tanggung jawab Direksi BPR pada rezim sebelum POJK 9/2024.','Direksi BPR',['bpr','direksi','tanggung jawab','tata kelola','2022']),
            _art('pojk4_kepatuhan','pojk_4_2015_tata_kelola_bpr','Fungsi Kepatuhan','Korpus kerja mengenai fungsi kepatuhan dalam tata kelola BPR. Ketentuan spesifik wajib diverifikasi pada teks resmi.','Fungsi Kepatuhan BPR',['kepatuhan','pe kepatuhan','bpr','opini kepatuhan']),
            _art('pojk4_audit','pojk_4_2015_tata_kelola_bpr','Fungsi Audit Intern','Korpus kerja mengenai fungsi audit intern/pengendalian dalam tata kelola BPR.','Audit Intern BPR',['audit intern','spi','pengendalian internal','bpr']),
        ],
    },
    {
        'id':'pojk_13_2015_manajemen_risiko_bpr','nomor':'POJK No. 13/POJK.03/2015','tahun':2015,
        'tentang':'Penerapan Manajemen Risiko bagi Bank Perkreditan Rakyat','jenis':'POJK','hierarchy_rank':6,'status':'BERLAKU_DENGAN_PERUBAHAN_PELAKSANAAN',
        'effective_date':'2015-11-12','promulgation_date':'2015-11-12','jdih_source':'OJK','official_url':'https://ojk.go.id/id/regulasi/Pages/POJK-tentang-Penerapan-Manajemen-Risiko-bagi-Bank-Perkreditan-Rakyat.aspx',
        'domain_tags':['bpr','manajemen risiko','risiko kredit','risiko kepatuhan','pengendalian intern'],
        'articles':[
            _art('pojk13_scope','pojk_13_2015_manajemen_risiko_bpr','Ruang Lingkup Manajemen Risiko','Korpus kerja mencakup pengawasan Direksi/Komisaris, kecukupan kebijakan/prosedur/limit, proses dan sistem, serta pengendalian intern.','Kerangka Manajemen Risiko BPR',['manajemen risiko','direksi','komisaris','kebijakan','limit','pengendalian intern']),
            _art('pojk13_credit','pojk_13_2015_manajemen_risiko_bpr','Risiko Kredit','Korpus kerja mengenai risiko akibat kegagalan debitur/pihak lain memenuhi kewajiban kepada BPR.','Risiko Kredit BPR',['risiko kredit','debitur','gagal bayar','kredit bermasalah']),
            _art('pojk13_compliance','pojk_13_2015_manajemen_risiko_bpr','Risiko Kepatuhan','Korpus kerja mengenai risiko akibat BPR tidak memenuhi atau tidak melaksanakan peraturan/ketentuan yang berlaku.','Risiko Kepatuhan BPR',['risiko kepatuhan','pelanggaran ketentuan','bpr','legal risk']),
        ],
    },
    {
        'id':'pojk_23_2022_bmpk_bpr','nomor':'POJK No. 23 Tahun 2022','tahun':2022,
        'tentang':'Batas Maksimum Pemberian Kredit Bank Perkreditan Rakyat dan Batas Maksimum Penyaluran Dana Bank Pembiayaan Rakyat Syariah','jenis':'POJK','hierarchy_rank':6,'status':'BERLAKU',
        'effective_date':'2022-11-23','promulgation_date':'2022-11-23','jdih_source':'OJK','official_url':'https://ojk.go.id/id/regulasi/Pages/Batas-Maksimum-Pemberian-Kredit-Bank-Perkreditan-Rakyat-dan-Batas-Maksimum-Penyaluran-Dana-Bank-Pembiayaan-Rakyat-Syariah.aspx',
        'temporal_note':'Mulai berlaku 23 November 2022. Tidak boleh digunakan sebagai dasar langsung untuk menilai keputusan kredit September 2022 tanpa analisis tempus; sebelum itu perlu identifikasi ketentuan BMPK yang berlaku pada tanggal peristiwa.',
        'domain_tags':['bpr','bmpk','kredit','prinsip kehati-hatian','pihak terkait'],
        'articles':[
            _art('pojk23_prudential','pojk_23_2022_bmpk_bpr','Prinsip kehati-hatian dalam penyediaan dana','Korpus kerja kewajiban menerapkan prinsip kehati-hatian dalam pemberian penyediaan dana/penyaluran dana.','Prinsip Kehati-hatian BMPK',['bmpk','prinsip kehati-hatian','penyediaan dana','kredit']),
            _art('pojk23_related_party','pojk_23_2022_bmpk_bpr','Pihak Terkait & Konsentrasi Penyediaan Dana','Korpus kerja mengenai pihak terkait dan pengelolaan konsentrasi penyediaan dana. Batas persentase spesifik wajib diverifikasi.','Pihak Terkait & Konsentrasi Kredit',['pihak terkait','konsentrasi kredit','bmpk','hubungan pengendalian']),
        ],
    },
    {
        'id':'seojk_11_2023_bmpk_bpr','nomor':'SEOJK No. 11/SEOJK.03/2023','tahun':2023,
        'tentang':'Batas Maksimum Pemberian Kredit Bank Perekonomian Rakyat dan Batas Maksimum Penyaluran Dana Bank Perekonomian Rakyat Syariah','jenis':'PER_LEMBAGA','hierarchy_rank':6,'status':'BERLAKU',
        'effective_date':'2023-08-15','promulgation_date':'2023-08-15','jdih_source':'OJK','official_url':'https://ojk.go.id/id/regulasi/Pages/Batas-Maksimum-Pemberian-Kredit-BPR-dan-Batas-Maksimum-Penyaluran-Dana-BPRS.aspx',
        'domain_tags':['bpr','bmpk','pelaporan','pihak terkait','kredit'],
        'articles':[
            _art('seojk11_bmpk','seojk_11_2023_bmpk_bpr','Ketentuan pelaksanaan BMPK/BMPD','Korpus kerja tindak lanjut POJK 23/2022, termasuk kriteria pengendalian pihak terkait, pelanggaran/pelampauan BMPK, dan pelaporan.','Pelaksanaan BMPK BPR',['bmpk','pelampauan bmpk','pelanggaran bmpk','pelaporan','pihak terkait'],cross_references=['pojk_23_2022_bmpk_bpr']),
        ],
    },
    {
        'id':'pojk_9_2024_tata_kelola_bpr','nomor':'POJK No. 9 Tahun 2024','tahun':2024,
        'tentang':'Penerapan Tata Kelola bagi Bank Perekonomian Rakyat dan Bank Perekonomian Rakyat Syariah','jenis':'POJK','hierarchy_rank':6,'status':'BERLAKU',
        'effective_date':'2024-07-01','promulgation_date':'2024-07-01','jdih_source':'OJK','official_url':'https://ojk.go.id/id/regulasi/Pages/POJK-9-2024-Penerapan-Tata-Kelola-bagi-BPR-dan-BPRS.aspx',
        'temporal_note':'Berlaku sejak 1 Juli 2024 dan mencabut POJK 4/2015. Tidak boleh dipakai retroaktif untuk menilai peristiwa 2022 tanpa analisis tempus.',
        'domain_tags':['bpr','bprs','tata kelola','direksi','kepatuhan','audit','anti fraud'],
        'articles':[
            _art('pojk9_principles','pojk_9_2024_tata_kelola_bpr','Prinsip dan pilar tata kelola','Korpus kerja tata kelola BPR/BPRS yang mencakup pemegang saham, Direksi, Dewan Komisaris, komite, benturan kepentingan, audit, kepatuhan, manajemen risiko/anti-fraud, BMPK, pelaporan, TI, dan rencana bisnis.','Pilar Tata Kelola BPR/BPRS',['tata kelola','direksi','komisaris','kepatuhan','audit','anti fraud','bmpk']),
            _art('pojk9_transition','pojk_9_2024_tata_kelola_bpr','Ketentuan pencabutan/peralihan','Korpus kerja mencatat POJK 4/2015 dicabut pada berlakunya POJK 9/2024, sementara ketentuan pelaksanaan lama dapat tetap berlaku sepanjang tidak bertentangan.','Transisi POJK Tata Kelola BPR',['pojk 4 2015','pojk 9 2024','dicabut','transisi','tempus'],cross_references=['pojk_4_2015_tata_kelola_bpr']),
        ],
    },
    {
        'id':'kuhap_2025','nomor':'UU No. 20 Tahun 2025 / KUHAP','tahun':2025,
        'tentang':'Kitab Undang-Undang Hukum Acara Pidana','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2026-01-02','promulgation_date':'2025-12-17','jdih_source':'JDIH Setneg / BPK','official_url':'https://peraturan.bpk.go.id/Details/337302',
        'temporal_note':'Berlaku 2 Januari 2026 dan mencabut UU No. 8 Tahun 1981. Perkara yang prosesnya melintasi tanggal transisi harus dianalisis berdasarkan ketentuan peralihan yang tepat.',
        'domain_tags':['acara pidana','tersangka','advokat','praperadilan','upaya paksa','restorative justice'],
        'articles':[
            _art('kuhap_rights','kuhap_2025','Hak Tersangka/Terdakwa dan peran Advokat','Korpus kerja mengenai penguatan hak tersangka/terdakwa dan peran advokat. Nomor pasal spesifik wajib diverifikasi pada naskah resmi.','Hak Tersangka & Advokat',['hak tersangka','advokat','penasihat hukum','pendampingan hukum']),
            _art('kuhap_due_process','kuhap_2025','Praperadilan & Upaya Paksa','Korpus kerja isu upaya paksa dan penguatan mekanisme praperadilan. Nomor pasal, aturan transisi, dan putusan terkait wajib diverifikasi.','Praperadilan & Due Process',['tersangka','bukti permulaan','praperadilan','upaya paksa'],related_court_decisions=['Putusan MK No. 21/PUU-XII/2014','Putusan MK No. 130/PUU-XIII/2015']),
            _art('kuhap_restorative','kuhap_2025','Keadilan Restoratif','Korpus kerja mengenai mekanisme keadilan restoratif dalam KUHAP baru; syarat dan tahap penerapan wajib diverifikasi.','Keadilan Restoratif',['restorative justice','keadilan restoratif','penghentian perkara']),
        ],
    },
    {
        'id':'uu_arbitrase_30_1999','nomor':'UU No. 30 Tahun 1999','tahun':1999,
        'tentang':'Arbitrase dan Alternatif Penyelesaian Sengketa','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'1999-08-12','promulgation_date':'1999-08-12','jdih_source':'JDIH BPK RI / Setneg','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['arbitrase','alternatif penyelesaian sengketa','kontrak','klausul arbitrase'],
        'articles':[
            _art('arb_agreement','uu_arbitrase_30_1999','Perjanjian/Klausul Arbitrase','Korpus kerja mengenai perjanjian arbitrase tertulis dan konsekuensinya terhadap forum penyelesaian sengketa. Nomor pasal spesifik wajib diverifikasi.','Klausul Arbitrase',['arbitrase','klausul arbitrase','forum sengketa','kompetensi absolut']),
            _art('arb_adr','uu_arbitrase_30_1999','Alternatif Penyelesaian Sengketa','Korpus kerja mengenai penyelesaian sengketa di luar pengadilan berdasarkan kesepakatan para pihak.','Alternatif Penyelesaian Sengketa',['mediasi','negosiasi','konsiliasi','alternatif penyelesaian sengketa']),
        ],
    },
    {
        'id':'uu_perlindungan_konsumen_8_1999','nomor':'UU No. 8 Tahun 1999','tahun':1999,
        'tentang':'Perlindungan Konsumen','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2000-04-20','promulgation_date':'1999-04-20','jdih_source':'JDIH BPK RI / Setneg','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['konsumen','klausula baku','ganti rugi','pelaku usaha'],
        'articles':[
            _art('upk_rights','uu_perlindungan_konsumen_8_1999','Hak konsumen & kewajiban pelaku usaha','Korpus kerja mengenai hak konsumen, kewajiban pelaku usaha, dan standar perlindungan. Pasal spesifik wajib diverifikasi.','Hak Konsumen & Kewajiban Pelaku Usaha',['konsumen','pelaku usaha','hak konsumen','kewajiban pelaku usaha']),
            _art('upk_standard_clause','uu_perlindungan_konsumen_8_1999','Klausula Baku','Korpus kerja mengenai pembatasan klausula baku tertentu yang merugikan konsumen. Gunakan qualified citation setelah verifikasi pasal yang tepat.','Klausula Baku',['klausula baku','exoneration clause','pengalihan tanggung jawab','konsumen']),
        ],
    },
]


def _clone_regulation(reg: Dict[str, Any]) -> Dict[str, Any]:
    return {**reg, 'articles':[dict(a) for a in reg.get('articles',[])]}


def get_all_regulations() -> List[Dict[str, Any]]:
    return [_clone_regulation(r) for r in INITIAL_REGULATORY_CORPUS]


def get_regulation_by_id(reg_id: str) -> Dict[str, Any] | None:
    for reg in INITIAL_REGULATORY_CORPUS:
        if reg.get('id') == reg_id:
            return _clone_regulation(reg)
    return None


def corpus_stats() -> Dict[str, Any]:
    regs = INITIAL_REGULATORY_CORPUS
    articles = sum(len(r.get('articles', [])) for r in regs)
    domains = sorted({d for r in regs for d in (r.get('domain_tags') or [])})
    return {'regulations': len(regs), 'articles': articles, 'domains': len(domains), 'domain_tags': domains}


def _query_terms(text: str) -> List[str]:
    return [w for w in re.findall(r'[\w-]+', (text or '').lower(), flags=re.UNICODE) if len(w) > 2]


def search_regulations(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Domain-aware local retrieval.

    This deliberately rewards domain/title matches more heavily than generic
    article-token matches.  The change prevents sparse-corpus behaviour where
    a query such as "PHK" could accidentally rank an unrelated Tipikor/KUHP
    provision merely because of common words in long summaries.
    """
    q = (query or '').lower().strip()
    if not q:
        return [{'regulation':_clone_regulation(r),'matched_articles':[dict(a) for a in r.get('articles',[])],'score':1} for r in INITIAL_REGULATORY_CORPUS[:limit]]

    words = _query_terms(q)
    results=[]
    for reg in INITIAL_REGULATORY_CORPUS:
        title = f"{reg.get('tentang','')} {reg.get('nomor','')}".lower()
        domains = ' '.join(reg.get('domain_tags') or []).lower()
        score = 0
        domain_hits = 0
        for w in words:
            if w in title:
                score += 7
            if w in domains:
                score += 9
                domain_hits += 1
        if q in title or q in domains:
            score += 18

        matched=[]
        for art in reg.get('articles',[]):
            art_text=' '.join([
                art.get('pasal',''), art.get('content',''), art.get('topic',''),
                ' '.join(art.get('keywords',[]))
            ]).lower()
            art_score = 0
            for w in words:
                if w in art_text:
                    art_score += 3
            if q in art_text:
                art_score += 12
            if art_score > 0:
                matched.append(dict(art))
                score += art_score

        # Require at least a meaningful match. Generic one-token collisions in
        # article prose are deliberately down-ranked unless the regulation's
        # title/domain also matches.
        if score > 0:
            if domain_hits == 0 and len(matched) == 1 and score <= 3:
                continue
            results.append({'regulation':_clone_regulation(reg),'matched_articles':matched or [dict(a) for a in reg.get('articles',[])[:3]],'score':score})

    results.sort(key=lambda x:(x['score'], x['regulation'].get('tahun') or 0), reverse=True)
    return results[:max(1,limit)]


def retrieve_for_case(text: str, provision_refs: List[str] | None = None, limit: int = 10) -> List[Dict[str, Any]]:
    queries=[]
    for ref in (provision_refs or [])[:10]:
        if ref and ref not in queries:
            queries.append(ref)
    low=(text or '').lower()
    topic_hints=[]
    for keys,q in [
        (['korupsi','tipikor','kerugian negara','pasal 603','pasal 604'],'korupsi penyalahgunaan kewenangan actual loss tipikor'),
        (['penyalahgunaan wewenang','diskresi','pejabat pemerintahan'],'administrasi pemerintahan penyalahgunaan wewenang diskresi'),
        (['kredit','bpr','agunan','slik','bank perkreditan rakyat','bank perekonomian rakyat'],'bpr kredit analisis kredit prinsip kehati-hatian manajemen risiko'),
        (['bmpk','pihak terkait','konsentrasi kredit'],'bpr bmpk pihak terkait konsentrasi kredit'),
        (['wanprestasi','perjanjian','kontrak','somasi'],'wanprestasi perjanjian somasi pasal 1238 1243 1320 1338'),
        (['force majeure','keadaan memaksa','overmacht'],'force majeure keadaan memaksa pasal 1244 1245'),
        (['perbuatan melawan hukum','pmh'],'perbuatan melawan hukum pasal 1365'),
        (['arbitrase','klausul arbitrase','alternatif penyelesaian sengketa'],'arbitrase klausul arbitrase alternatif penyelesaian sengketa'),
        (['konsumen','klausula baku','pelaku usaha'],'perlindungan konsumen klausula baku'),
        (['tersangka','praperadilan','upaya paksa','penasihat hukum','advokat'],'kuhap tersangka praperadilan upaya paksa advokat due process'),
        (['tempus','non-retroaktif','kuhp nasional'],'asas legalitas tempus delicti kuhp'),
        (['phk','ketenagakerjaan','pesangon','pekerja','buruh','pkwt','pkwtt'],'ketenagakerjaan phk pesangon pkwt pp 35 2021'),
        (['bipartit','perselisihan hubungan industrial','phi'],'perselisihan hubungan industrial bipartit mediasi phi'),
        (['perseroan','direksi','komisaris','pemegang saham','rups'],'perseroan terbatas direksi komisaris rups business judgment rule'),
    ]:
        if any(k in low for k in keys):
            topic_hints.append(q)
    queries.extend(topic_hints)

    merged={}
    for qx in queries[:14]:
        for hit in search_regulations(qx,limit=limit):
            rid=hit['regulation']['id']
            if rid not in merged or hit['score']>merged[rid]['score']:
                merged[rid]=hit
    out=sorted(merged.values(),key=lambda x:x['score'],reverse=True)[:limit]
    for item in out:
        item['verification_status']='LOCAL_CORPUS_MATCH — OFFICIAL SOURCE VERIFICATION REQUIRED'
        item['professional_verification']='PENDING'
    return out
