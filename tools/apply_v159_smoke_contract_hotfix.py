from pathlib import Path
import sys

path = Path('tests/test_smoke.py')
if not path.exists():
    raise SystemExit('ERROR: tests/test_smoke.py tidak ditemukan. Jalankan dari root LexiCore.')

text = path.read_text(encoding='utf-8')
old = """    assert x['domain_classification']['primary_domain'] in {'civil_procedure', 'land_property', 'civil_contract'}\n"""
new = """    assert x['domain_classification']['primary_domain'] == 'inheritance'\n    assert x['domain_classification']['posture'] == 'PERDATA_LITIGASI'\n    assert 'civil_procedure' in set(x['domain_classification']['domain_contract'])\n    assert 'land_property' in set(x['domain_classification']['domain_contract'])\n"""

if new in text:
    print('PASS: smoke contract sudah pada versi baru; tidak ada perubahan.')
    sys.exit(0)

count = text.count(old)
if count != 1:
    raise SystemExit(f'ABORT: assertion lama ditemukan {count} kali; tidak mengubah file secara otomatis.')

path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('UPDATED: tests/test_smoke.py')
print('Contract: inheritance primary + PERDATA_LITIGASI + civil_procedure/land_property secondary')
