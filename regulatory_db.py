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

    {
        'id':'uu_uupa_5_1960','nomor':'UU No. 5 Tahun 1960','tahun':1960,
        'tentang':'Peraturan Dasar Pokok-Pokok Agraria','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'1960-09-24','promulgation_date':'1960-09-24','jdih_source':'JDIH BPK RI / ATR-BPN','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['agraria','pertanahan','hak atas tanah','hak milik','hgu','hgb'],
        'articles':[
            _art('uupa_rights','uu_uupa_5_1960','Hak-hak atas tanah','Korpus kerja mengenai jenis dan karakter hak atas tanah. Identitas pasal spesifik dan status implementasi wajib diverifikasi.','Hak Atas Tanah',['hak milik','hgu','hgb','hak pakai','tanah']),
            _art('uupa_registration','uu_uupa_5_1960','Pendaftaran tanah','Korpus kerja mengenai mandat pendaftaran tanah untuk kepastian hukum; aturan pelaksana wajib dibaca bersama PP pendaftaran tanah yang berlaku.','Pendaftaran Tanah',['pendaftaran tanah','kepastian hukum','sertifikat','sertipikat']),
        ],
    },
    {
        'id':'pp_24_1997_pendaftaran_tanah','nomor':'PP No. 24 Tahun 1997 jo PP No. 18 Tahun 2021','tahun':1997,
        'tentang':'Pendaftaran Tanah sebagaimana diubah antara lain oleh PP No. 18 Tahun 2021','jenis':'PP','hierarchy_rank':4,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'1997-07-08','promulgation_date':'1997-07-08','jdih_source':'JDIH BPK RI / ATR-BPN','official_url':'https://peraturan.bpk.go.id/Details/56273/pp-no-24-tahun-1997',
        'domain_tags':['pertanahan','pendaftaran tanah','sertifikat','sertipikat','bpn','data fisik','data yuridis'],
        'articles':[
            _art('pp24_registration','pp_24_1997_pendaftaran_tanah','Pendaftaran awal & pemeliharaan data','Korpus kerja mengenai pendaftaran pertama kali dan pemeliharaan data pendaftaran tanah. Prosedur dan pasal spesifik wajib diverifikasi.','Pendaftaran & Pemeliharaan Data',['pendaftaran tanah','data fisik','data yuridis','buku tanah']),
            _art('pp24_certificate','pp_24_1997_pendaftaran_tanah','Sertifikat & pembuktian','Korpus kerja mengenai sertifikat sebagai alat bukti dan mekanisme pendaftaran. Baca bersama perubahan PP 18/2021 dan yurisprudensi relevan.','Sertifikat & Pembuktian',['sertifikat','sertipikat','alat bukti','buku tanah']),
        ],
    },
    {
        'id':'uu_hak_tanggungan_4_1996','nomor':'UU No. 4 Tahun 1996','tahun':1996,
        'tentang':'Hak Tanggungan atas Tanah Beserta Benda-Benda yang Berkaitan dengan Tanah','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'1996-04-09','promulgation_date':'1996-04-09','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/Details/46093/uu-no-4-',
        'domain_tags':['hak tanggungan','jaminan','agunan','kredit','pertanahan','eksekusi'],
        'articles':[
            _art('ht_object','uu_hak_tanggungan_4_1996','Objek & pembebanan Hak Tanggungan','Korpus kerja mengenai hak atas tanah yang dapat dibebani dan pembebanan jaminan.','Objek Hak Tanggungan',['hak tanggungan','agunan','jaminan','hak atas tanah']),
            _art('ht_execution','uu_hak_tanggungan_4_1996','Eksekusi Hak Tanggungan','Korpus kerja mengenai titel dan mekanisme eksekusi yang harus diverifikasi terhadap dokumen jaminan dan hukum acara yang berlaku.','Eksekusi Jaminan',['eksekusi','hak tanggungan','kreditur','debitur']),
        ],
    },
    {
        'id':'uu_fidusia_42_1999','nomor':'UU No. 42 Tahun 1999','tahun':1999,
        'tentang':'Jaminan Fidusia','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PUTUSAN_MK',
        'effective_date':'1999-09-30','promulgation_date':'1999-09-30','jdih_source':'JDIH BPK RI / Kemenkum','official_url':'https://peraturan.bpk.go.id/Details/45374/uu-no-42-tahun-1999',
        'domain_tags':['fidusia','jaminan','agunan kendaraan','kredit','eksekusi'],
        'articles':[
            _art('fidusia_registration','uu_fidusia_42_1999','Pembebanan & pendaftaran fidusia','Korpus kerja mengenai pembebanan dan pendaftaran jaminan fidusia. Dokumen akta/sertifikat wajib diverifikasi.','Pembebanan Fidusia',['fidusia','jaminan','pendaftaran fidusia','agunan']),
            _art('fidusia_execution','uu_fidusia_42_1999','Eksekusi fidusia','Korpus kerja mengenai eksekusi fidusia yang harus dibaca bersama Putusan MK No. 18/PUU-XVII/2019 dan perkembangan terkait.','Eksekusi Fidusia',['fidusia','eksekusi','cidera janji','penyerahan sukarela'],related_court_decisions=['Putusan MK No. 18/PUU-XVII/2019']),
        ],
    },
    {
        'id':'uu_peradilan_agama_7_1989','nomor':'UU No. 7 Tahun 1989 jo UU No. 3 Tahun 2006 jo UU No. 50 Tahun 2009','tahun':1989,
        'tentang':'Peradilan Agama beserta perubahannya','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'1989-12-29','promulgation_date':'1989-12-29','jdih_source':'JDIH BPK RI / Mahkamah Agung','official_url':'https://peraturan.bpk.go.id/Details/46804/uu-no-7-',
        'domain_tags':['peradilan agama','kompetensi absolut','perkawinan','waris','wakaf','ekonomi syariah'],
        'articles':[
            _art('pa_49','uu_peradilan_agama_7_1989','Pasal 49 (sebagaimana diubah)','Korpus kerja mengenai kompetensi absolut Pengadilan Agama. Materi perkara dan status para pihak harus diuji terhadap rumusan berlaku.','Kompetensi Absolut Peradilan Agama',['pasal 49','peradilan agama','kompetensi absolut','ekonomi syariah','waris','perkawinan']),
        ],
    },
    {
        'id':'uu_perkawinan_1_1974_16_2019','nomor':'UU No. 1 Tahun 1974 jo UU No. 16 Tahun 2019','tahun':1974,
        'tentang':'Perkawinan sebagaimana diubah','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'1974-01-02','promulgation_date':'1974-01-02','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['perkawinan','perceraian','harta bersama','keluarga','anak'],
        'articles':[
            _art('marriage_validity','uu_perkawinan_1_1974_16_2019','Keabsahan & pencatatan perkawinan','Korpus kerja mengenai keabsahan/pencatatan perkawinan; ketentuan sektoral dan hukum agama yang relevan harus diverifikasi.','Keabsahan Perkawinan',['perkawinan','pencatatan','sah']),
            _art('marriage_divorce','uu_perkawinan_1_1974_16_2019','Perceraian & akibat hukum','Korpus kerja mengenai perceraian dan akibatnya; baca bersama aturan pelaksana dan hukum acara forum yang berwenang.','Perceraian',['perceraian','anak','nafkah','harta bersama']),
        ],
    },
    {
        'id':'uu_pdp_27_2022','nomor':'UU No. 27 Tahun 2022','tahun':2022,
        'tentang':'Pelindungan Data Pribadi','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2022-10-17','promulgation_date':'2022-10-17','jdih_source':'JDIH BPK RI / Setneg','official_url':'https://peraturan.bpk.go.id/Details/229798/uu-no-27-tahun-2022.',
        'domain_tags':['data pribadi','privasi','pengendali data','prosesor data','transfer data','sanksi'],
        'articles':[
            _art('pdp_rights','uu_pdp_27_2022','Hak subjek data pribadi','Korpus kerja hak subjek data dan kewajiban pemrosesan yang relevan. Nomor pasal final wajib diverifikasi.','Hak Subjek Data',['data pribadi','hak subjek data','akses','penghapusan']),
            _art('pdp_controller','uu_pdp_27_2022','Kewajiban pengendali/prosesor','Korpus kerja kewajiban pengendali/prosesor dalam pemrosesan, keamanan dan insiden.','Kewajiban Pengendali/Prosesor',['pengendali data','prosesor data','pemrosesan','keamanan data']),
        ],
    },
    {
        'id':'uu_ite_11_2008_1_2024','nomor':'UU No. 11 Tahun 2008 jo UU No. 19 Tahun 2016 jo UU No. 1 Tahun 2024','tahun':2008,
        'tentang':'Informasi dan Transaksi Elektronik beserta perubahannya','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'2008-04-21','promulgation_date':'2008-04-21','jdih_source':'JDIH BPK RI / Komdigi','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['informasi elektronik','transaksi elektronik','bukti elektronik','sistem elektronik','ite'],
        'articles':[
            _art('ite_evidence','uu_ite_11_2008_1_2024','Informasi/Dokumen Elektronik sebagai alat bukti','Korpus kerja mengenai kedudukan informasi/dokumen elektronik dan syarat relevan.','Bukti Elektronik',['bukti elektronik','dokumen elektronik','informasi elektronik']),
            _art('ite_system','uu_ite_11_2008_1_2024','Penyelenggaraan sistem/transaksi elektronik','Korpus kerja mengenai kewajiban dan aspek transaksi/sistem elektronik yang perlu diverifikasi berdasarkan konteks.','Sistem & Transaksi Elektronik',['sistem elektronik','transaksi elektronik','penyelenggara']),
        ],
    },
    {
        'id':'uu_kepailitan_37_2004','nomor':'UU No. 37 Tahun 2004','tahun':2004,
        'tentang':'Kepailitan dan Penundaan Kewajiban Pembayaran Utang','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2004-10-18','promulgation_date':'2004-10-18','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/Details/40784/uu-no-37-tahun-2004',
        'domain_tags':['kepailitan','pkpu','kreditur','debitur','utang','pengadilan niaga'],
        'articles':[
            _art('bankruptcy_threshold','uu_kepailitan_37_2004','Syarat permohonan pailit','Korpus kerja mengenai syarat permohonan pailit; identitas pasal, pembuktian dan yurisdiksi wajib diverifikasi.','Syarat Pailit',['pailit','dua kreditur','jatuh tempo','utang']),
            _art('pkpu_process','uu_kepailitan_37_2004','PKPU','Korpus kerja proses PKPU dan perdamaian; tenggat dan tahapan wajib diverifikasi.','PKPU',['pkpu','perdamaian','kreditur','debitur']),
        ],
    },
    {
        'id':'uu_advokat_18_2003','nomor':'UU No. 18 Tahun 2003','tahun':2003,
        'tentang':'Advokat','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2003-04-05','promulgation_date':'2003-04-05','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['advokat','penasihat hukum','jasa hukum','imunitas profesi','kode etik'],
        'articles':[
            _art('advocate_duties','uu_advokat_18_2003','Hak, kewajiban & kedudukan advokat','Korpus kerja mengenai kedudukan, hak dan kewajiban profesi advokat.','Profesi Advokat',['advokat','jasa hukum','penasihat hukum','profesi']),
            _art('advocate_immunity','uu_advokat_18_2003','Itikad baik dalam menjalankan profesi','Korpus kerja isu perlindungan pelaksanaan tugas profesi dengan itikad baik; baca bersama putusan pengujian dan kode etik yang relevan.','Perlindungan Profesi',['advokat','itikad baik','imunitas','profesi']),
        ],
    },
    {
        'id':'uu_kekuasaan_kehakiman_48_2009','nomor':'UU No. 48 Tahun 2009','tahun':2009,
        'tentang':'Kekuasaan Kehakiman','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2009-10-29','promulgation_date':'2009-10-29','jdih_source':'JDIH BPK RI / Mahkamah Agung','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['kekuasaan kehakiman','peradilan','hakim','asas peradilan','due process'],
        'articles':[
            _art('judiciary_principles','uu_kekuasaan_kehakiman_48_2009','Asas penyelenggaraan kekuasaan kehakiman','Korpus kerja mengenai asas independensi, peradilan yang adil, sederhana, cepat dan biaya ringan; pasal spesifik wajib diverifikasi.','Asas Peradilan',['kekuasaan kehakiman','hakim','peradilan','due process']),
        ],
    },
    {
        'id':'uu_peradilan_umum_2_1986_49_2009','nomor':'UU No. 2 Tahun 1986 jo UU No. 8 Tahun 2004 jo UU No. 49 Tahun 2009','tahun':1986,
        'tentang':'Peradilan Umum beserta perubahannya','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'1986-03-08','promulgation_date':'1986-03-08','jdih_source':'JDIH BPK RI / Mahkamah Agung','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['peradilan umum','pengadilan negeri','pengadilan tinggi','kompetensi peradilan'],
        'articles':[
            _art('general_court_scope','uu_peradilan_umum_2_1986_49_2009','Kewenangan Peradilan Umum','Korpus kerja struktur dan kewenangan Peradilan Umum. Kompetensi perkara harus dibaca bersama hukum acara dan undang-undang sektoral.','Kompetensi Peradilan Umum',['pengadilan negeri','pengadilan tinggi','peradilan umum','kompetensi']),
        ],
    },
    {
        'id':'uu_ptun_5_1986_51_2009','nomor':'UU No. 5 Tahun 1986 jo UU No. 9 Tahun 2004 jo UU No. 51 Tahun 2009','tahun':1986,
        'tentang':'Peradilan Tata Usaha Negara beserta perubahannya','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'1986-12-29','promulgation_date':'1986-12-29','jdih_source':'JDIH BPK RI / Mahkamah Agung','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['ptun','tata usaha negara','keputusan administrasi','sengketa administrasi'],
        'articles':[
            _art('ptun_object','uu_ptun_5_1986_51_2009','Objek dan kewenangan sengketa TUN','Korpus kerja mengenai objek sengketa dan kompetensi PTUN; harus dibaca bersama UU Administrasi Pemerintahan dan perkembangan putusan.','Sengketa TUN',['ptun','keputusan tata usaha negara','administrasi pemerintahan','kompetensi']),
        ],
    },
    {
        'id':'uu_keuangan_negara_17_2003','nomor':'UU No. 17 Tahun 2003','tahun':2003,
        'tentang':'Keuangan Negara','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2003-04-05','promulgation_date':'2003-04-05','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['keuangan negara','keuangan daerah','apbn','apbd','kekayaan negara dipisahkan'],
        'articles':[
            _art('state_finance_scope','uu_keuangan_negara_17_2003','Ruang lingkup keuangan negara','Korpus kerja ruang lingkup keuangan negara/daerah dan kekayaan negara yang dikelola; penggunaan dalam Tipikor wajib diverifikasi terhadap fakta entitas dan yurisprudensi.','Ruang Lingkup Keuangan Negara',['keuangan negara','keuangan daerah','kekayaan negara','apbd','bumd']),
        ],
    },
    {
        'id':'uu_perbendaharaan_1_2004','nomor':'UU No. 1 Tahun 2004','tahun':2004,
        'tentang':'Perbendaharaan Negara','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2004-01-14','promulgation_date':'2004-01-14','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['perbendaharaan negara','kerugian negara','pengelolaan uang','bendahara'],
        'articles':[
            _art('treasury_loss','uu_perbendaharaan_1_2004','Kerugian negara/daerah dan pertanggungjawaban','Korpus kerja pengelolaan perbendaharaan dan mekanisme pertanggungjawaban kerugian; unsur dan prosedur spesifik wajib diverifikasi.','Kerugian Negara/Daerah',['kerugian negara','kerugian daerah','perbendaharaan','pertanggungjawaban']),
        ],
    },
    {
        'id':'uu_pemeriksaan_keuangan_15_2004','nomor':'UU No. 15 Tahun 2004','tahun':2004,
        'tentang':'Pemeriksaan Pengelolaan dan Tanggung Jawab Keuangan Negara','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2004-07-19','promulgation_date':'2004-07-19','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['pemeriksaan keuangan negara','bpk','audit','kerugian negara','tanggung jawab keuangan'],
        'articles':[
            _art('state_audit_scope','uu_pemeriksaan_keuangan_15_2004','Pemeriksaan pengelolaan dan tanggung jawab keuangan negara','Korpus kerja kerangka pemeriksaan oleh BPK; metode dan hasil pemeriksaan dalam suatu perkara tetap harus diuji pada laporan resmi yang relevan.','Pemeriksaan Keuangan Negara',['bpk','audit','keuangan negara','pemeriksaan']),
        ],
    },
    {
        'id':'uu_bpk_15_2006','nomor':'UU No. 15 Tahun 2006','tahun':2006,
        'tentang':'Badan Pemeriksa Keuangan','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2006-10-30','promulgation_date':'2006-10-30','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['bpk','pemeriksaan keuangan','kerugian negara','audit negara'],
        'articles':[
            _art('bpk_authority','uu_bpk_15_2006','Tugas dan kewenangan BPK','Korpus kerja mengenai kedudukan, tugas, dan kewenangan BPK dalam pemeriksaan keuangan negara.','Kewenangan BPK',['bpk','audit negara','pemeriksaan keuangan','kerugian negara']),
        ],
    },
    {
        'id':'uu_pemda_23_2014','nomor':'UU No. 23 Tahun 2014 jo perubahan terakhir yang relevan','tahun':2014,
        'tentang':'Pemerintahan Daerah beserta perubahannya','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'2014-10-02','promulgation_date':'2014-10-02','jdih_source':'JDIH BPK RI / Kemendagri','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['pemerintahan daerah','otonomi daerah','bumd','kewenangan daerah','kepala daerah'],
        'articles':[
            _art('local_government_bumd','uu_pemda_23_2014','Kerangka Pemerintahan Daerah dan BUMD','Korpus kerja hubungan kewenangan pemerintah daerah dan pengelolaan urusan/entitas daerah; perubahan sektoral wajib diverifikasi menurut tempus.','Pemerintahan Daerah & BUMD',['pemerintah daerah','bumd','perumda','kewenangan daerah']),
        ],
    },
    {
        'id':'pp_bumd_54_2017','nomor':'PP No. 54 Tahun 2017','tahun':2017,
        'tentang':'Badan Usaha Milik Daerah','jenis':'PP','hierarchy_rank':4,'status':'BERLAKU',
        'effective_date':'2017-12-28','promulgation_date':'2017-12-28','jdih_source':'JDIH BPK RI / Kemendagri','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['bumd','perumda','direksi','dewan pengawas','kpm','tata kelola'],
        'articles':[
            _art('bumd_governance','pp_bumd_54_2017','Organ dan tata kelola BUMD','Korpus kerja mengenai organ, pengurusan, pengawasan, dan tata kelola BUMD/Perumda. Ketentuan khusus BPR tetap harus dibaca bersama regulasi OJK.','Tata Kelola BUMD',['bumd','perumda','direksi','dewan pengawas','kpm']),
        ],
    },
    {
        'id':'uu_pelayanan_publik_25_2009','nomor':'UU No. 25 Tahun 2009','tahun':2009,
        'tentang':'Pelayanan Publik','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2009-07-18','promulgation_date':'2009-07-18','jdih_source':'JDIH BPK RI','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['pelayanan publik','administrasi','maladministrasi','standar pelayanan'],
        'articles':[
            _art('public_service_duties','uu_pelayanan_publik_25_2009','Hak, kewajiban dan standar pelayanan publik','Korpus kerja standar penyelenggaraan pelayanan publik dan hak/kewajiban para pihak; pasal spesifik wajib diverifikasi.','Pelayanan Publik',['pelayanan publik','standar pelayanan','maladministrasi','penyelenggara']),
        ],
    },

    {
        'id':'perma_mediasi_1_2016','nomor':'PERMA No. 1 Tahun 2016','tahun':2016,
        'tentang':'Prosedur Mediasi di Pengadilan','jenis':'PERMA','hierarchy_rank':90,'status':'BERLAKU',
        'effective_date':'2016-02-04','promulgation_date':'2016-02-04','jdih_source':'JDIH Mahkamah Agung / JDIH BPK','official_url':'https://peraturan.bpk.go.id/Details/209641/perma-no-1-tahun-2016',
        'domain_tags':['hukum acara perdata','mediasi','pengadilan','perdamaian'],
        'articles':[
            _art('perma_mediasi_scope','perma_mediasi_1_2016','Prosedur Mediasi','Korpus kerja mengenai kewajiban dan prosedur mediasi perkara perdata di pengadilan. Detail pengecualian, tenggat, dan akibat hukum wajib diverifikasi pada naskah resmi.','Mediasi di Pengadilan',['mediasi','perdamaian','hukum acara perdata','mediator']),
        ],
    },
    {
        'id':'perma_gugatan_sederhana_4_2019','nomor':'PERMA No. 4 Tahun 2019 jo PERMA No. 2 Tahun 2015','tahun':2019,
        'tentang':'Perubahan atas Tata Cara Penyelesaian Gugatan Sederhana','jenis':'PERMA','hierarchy_rank':90,'status':'BERLAKU',
        'effective_date':'2019-08-20','promulgation_date':'2019-08-20','jdih_source':'JDIH Mahkamah Agung / JDIH BPK','official_url':'https://peraturan.bpk.go.id/Details/206070/perma-no-4-tahun-2019',
        'domain_tags':['hukum acara perdata','gugatan sederhana','peradilan umum'],
        'articles':[
            _art('small_claims_scope','perma_gugatan_sederhana_4_2019','Tata Cara Gugatan Sederhana','Korpus kerja mengenai penyelesaian gugatan sederhana. Batas nilai, kompetensi, syarat para pihak, dan prosedur wajib diverifikasi terhadap naskah resmi yang berlaku.','Gugatan Sederhana',['gugatan sederhana','small claim','hukum acara perdata']),
        ],
    },
    {
        'id':'inpres_khi_1_1991','nomor':'Inpres No. 1 Tahun 1991','tahun':1991,
        'tentang':'Penyebarluasan Kompilasi Hukum Islam','jenis':'PER_LEMBAGA','hierarchy_rank':6,'status':'BERLAKU_SEBAGAI_RUJUKAN',
        'effective_date':'1991-06-10','promulgation_date':'','jdih_source':'JDIH Pemerintah / JDIH BPK','official_url':'https://peraturan.bpk.go.id/Details/293351/inpres-no-1-tahun-1991',
        'domain_tags':['hukum keluarga islam','waris islam','wakaf','peradilan agama'],
        'articles':[
            _art('khi_scope','inpres_khi_1_1991','Buku I-III KHI','Korpus kerja KHI mencakup perkawinan, kewarisan, dan perwakafan. Pasal spesifik serta relevansi kewenangan Peradilan Agama wajib diverifikasi pada naskah resmi dan praktik yudisial.','Kompilasi Hukum Islam',['perkawinan islam','waris islam','wakaf','peradilan agama']),
        ],
    },
    {
        'id':'uu_kip_14_2008','nomor':'UU No. 14 Tahun 2008','tahun':2008,
        'tentang':'Keterbukaan Informasi Publik','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU',
        'effective_date':'2010-04-30','promulgation_date':'2008-04-30','jdih_source':'JDIH BPK / Komisi Informasi','official_url':'https://peraturan.bpk.go.id/',
        'domain_tags':['keterbukaan informasi','badan publik','informasi publik','sengketa informasi'],
        'articles':[
            _art('kip_scope','uu_kip_14_2008','Hak dan Kewajiban Informasi Publik','Korpus kerja mengenai akses, pengecualian, dan kewajiban badan publik. Klasifikasi informasi dan prosedur sengketa wajib diverifikasi pada sumber resmi.','Keterbukaan Informasi Publik',['informasi publik','badan publik','keterbukaan','komisi informasi']),
        ],
    },
    {
        'id':'uu_penanaman_modal_25_2007','nomor':'UU No. 25 Tahun 2007 jo UU No. 6 Tahun 2023','tahun':2007,
        'tentang':'Penanaman Modal sebagaimana diubah melalui rezim Cipta Kerja','jenis':'UU','hierarchy_rank':3,'status':'BERLAKU_DENGAN_PERUBAHAN',
        'effective_date':'2007-04-26','promulgation_date':'2007-04-26','jdih_source':'JDIH BPK / BKPM','official_url':'https://peraturan.bpk.go.id/Details/39903/uu-no-25-tahun-2007',
        'domain_tags':['penanaman modal','investasi','perizinan berusaha','investor'],
        'articles':[
            _art('investment_scope','uu_penanaman_modal_25_2007','Kerangka Penanaman Modal','Korpus kerja mengenai hak, kewajiban, fasilitas, dan penyelenggaraan penanaman modal. Perubahan Cipta Kerja dan aturan pelaksana wajib diverifikasi sesuai tempus.','Penanaman Modal',['investasi','penanaman modal','perizinan berusaha','investor']),
        ],
    },
    {
        'id':'perma_e_court_7_2022','nomor':'PERMA No. 7 Tahun 2022','tahun':2022,
        'tentang':'Perubahan atas PERMA No. 1 Tahun 2019 tentang Administrasi Perkara dan Persidangan di Pengadilan secara Elektronik','jenis':'PERMA','hierarchy_rank':90,'status':'BERLAKU',
        'effective_date':'2022-10-11','promulgation_date':'2022-10-11','jdih_source':'JDIH Mahkamah Agung','official_url':'https://jdih.mahkamahagung.go.id/',
        'domain_tags':['hukum acara','e-court','persidangan elektronik','administrasi perkara'],
        'articles':[
            _art('ecourt_scope','perma_e_court_7_2022','Administrasi dan Persidangan Elektronik','Korpus kerja mengenai administrasi perkara dan persidangan elektronik. Penerapan pada jenis perkara dan tahapan tertentu wajib diverifikasi pada naskah resmi dan kebijakan pengadilan.','E-Court / E-Litigation',['e-court','e-litigation','persidangan elektronik','administrasi perkara']),
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


def retrieve_for_case(text: str, provision_refs: List[str] | None = None, limit: int = 10,
                      allowed_domains: List[str] | None = None) -> List[Dict[str, Any]]:
    """Local corpus retrieval constrained by the case-domain contract."""
    low=(text or '').lower(); allowed=set(allowed_domains or [])
    domain_queries={
        'corruption':['korupsi penyalahgunaan kewenangan kerugian negara tipikor','UU Tipikor'],
        'financial_services':['bpr kredit analisis kredit prinsip kehati-hatian manajemen risiko','bpr tata kelola direksi kredit'],
        'criminal':['kuhap tersangka praperadilan upaya paksa advokat','asas legalitas tempus delicti kuhp'],
        'regional_government':['bumd perumda direksi pemerintah daerah'],
        'civil_contract':['wanprestasi perjanjian somasi pasal 1238 1243 1320 1338','perbuatan melawan hukum pasal 1365'],
        'civil_procedure':['hukum acara perdata eksepsi obscuur libel plurium litis consortium','kompetensi absolut gugatan perdata'],
        'land_property':['uupa pendaftaran tanah sertipikat hak milik','pp 24 1997 pendaftaran tanah hak tanggungan'],
        'religious_court':['uu peradilan agama pasal 49 kompetensi absolut'],
        'employment':['ketenagakerjaan phk pesangon pkwt pp 35 2021','perselisihan hubungan industrial bipartit'],
        'corporate':['perseroan terbatas direksi komisaris rups business judgment rule'],
        'consumer':['perlindungan konsumen klausula baku'],
        'data_privacy':['pelindungan data pribadi bukti elektronik ite'],
        'bankruptcy':['kepailitan pkpu kreditur debitur'],
        'arbitration':['arbitrase klausul arbitrase alternatif penyelesaian sengketa'],
        'administrative':['ptun keputusan tata usaha negara administrasi pemerintahan aaupb','upaya administratif peradilan tata usaha negara'],
        'public_information':['keterbukaan informasi publik badan publik komisi informasi'],
        'investment':['penanaman modal investasi perizinan berusaha'],
    }
    if not allowed:
        try:
            from services.case_domain_classifier import classify_case
            allowed=set(classify_case(text).get('domain_contract') or [])
        except Exception:
            allowed=set()
    queries=[]
    # Qualified references from the document remain valid discovery anchors but
    # never override the domain gate by themselves.
    for ref in (provision_refs or [])[:10]:
        if ref and ref not in queries: queries.append(ref)
    for did in allowed:
        queries.extend(domain_queries.get(did,[]))
    if not queries:
        queries=[' '.join(re.findall(r'\b[\w-]{4,}\b',(text or '')[:1200],flags=re.UNICODE)[:10])]

    merged={}
    for qx in queries[:16]:
        for hit in search_regulations(qx,limit=max(limit,12)):
            reg=hit['regulation']; tags=' '.join(reg.get('domain_tags') or []).lower(); title=(reg.get('tentang','')+' '+reg.get('nomor','')).lower()
            # Hard domain guard. Qualified references are allowed only when the
            # regulation also has material overlap with an active domain.
            vocab={
                'corruption':('korupsi','tipikor','penyalahgunaan wewenang','kerugian negara'),
                'financial_services':('perbankan','bpr','kredit','ojk','manajemen risiko','tata kelola'),
                'criminal':('pidana','kuhp','kuhap','tersangka','praperadilan'),
                'regional_government':('bumd','perumda','pemerintah daerah'),
                'civil_contract':('perdata','perikatan','kontrak','wanprestasi','pmh'),
                'civil_procedure':('acara perdata','gugatan','eksepsi','kompetensi'),
                'land_property':('agraria','pertanahan','pendaftaran tanah','hak tanggungan','fidusia'),
                'religious_court':('peradilan agama','kompetensi absolut','perkawinan','waris','wakaf'),
                'employment':('ketenagakerjaan','phk','pkwt','hubungan industrial'),
                'corporate':('perseroan','direksi','komisaris','rups'),
                'consumer':('konsumen','klausula baku'),
                'data_privacy':('data pribadi','informasi elektronik','ite'),
                'bankruptcy':('kepailitan','pkpu'),
                'arbitration':('arbitrase','alternatif penyelesaian sengketa'),
                'administrative':('tata usaha negara','administrasi pemerintahan','ptun','aaupb'),
                'public_information':('keterbukaan informasi publik','komisi informasi','badan publik'),
                'investment':('penanaman modal','investasi','perizinan berusaha'),
            }
            hay=title+' '+tags
            if allowed and not any(any(k in hay for k in vocab.get(d,())) for d in allowed):
                continue
            rid=reg['id']
            if rid not in merged or hit['score']>merged[rid]['score']: merged[rid]=hit
    out=sorted(merged.values(),key=lambda x:x['score'],reverse=True)[:limit]
    for item in out:
        item['verification_status']='LOCAL_DATABASE_MATCH — OFFICIAL SOURCE VERIFICATION REQUIRED'
        item['professional_verification']='PENDING'
    return out

