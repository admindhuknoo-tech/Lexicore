from pathlib import Path


def test_schema_v12_contains_single_profile_table():
    from database import SCHEMA_VERSION, EXPECTED_COLUMNS
    assert SCHEMA_VERSION >= 12
    fields = {name for name, _ in EXPECTED_COLUMNS['app_profile']}
    assert {'professional_name','firm_name','credentials','office_address','phone','email','watermark_text','branding_mode'} <= fields


def test_profile_is_single_source_and_persists(monkeypatch, tmp_path):
    import database
    db = tmp_path / 'profile.db'
    monkeypatch.setattr(database, 'DB_PATH', str(db))
    database.init_database()
    saved = database.AppProfileManager.save({
        'professional_name':'Ayu Pratama', 'firm_name':'Ayu Legal', 'credentials':'S.H.',
        'office_address':'Malang', 'email':'ayu@example.test', 'branding_mode':'co_brand'
    })
    assert saved['firm_name'] == 'Ayu Legal'
    import identity_profile
    p = identity_profile.get_identity_profile()
    assert p['display_name'] == 'Ayu Legal'
    assert p['signatory_name'] == 'Ayu Pratama, S.H.'
    assert p['configured'] is True


def test_commercial_production_identity_has_no_elf_literal():
    root = Path(__file__).resolve().parents[1]
    production = [
        root/'app.py', root/'client_communication.py', root/'legal_drafting.py',
        root/'static'/'index.html', root/'exporters'/'case_pdf.py',
        root/'exporters'/'case_docx.py', root/'exporters'/'common.py', root/'version.py'
    ]
    joined='\n'.join(p.read_text(encoding='utf-8',errors='ignore') for p in production)
    assert "Erfan's Law Firm" not in joined
    assert 'Erfan’s Law Firm' not in joined
    assert 'ELF - Erfan' not in joined


def test_profile_api_contract_is_present():
    root = Path(__file__).resolve().parents[1]
    app_source=(root/'app.py').read_text(encoding='utf-8')
    assert "@app.route('/api/profile', methods=['GET','PUT','POST'])" in app_source
    assert "AppProfileManager.save(data)" in app_source

