from pathlib import Path


def test_profile_onboarding_is_persistent_install_state(monkeypatch, tmp_path):
    import database
    db = tmp_path / "onboarding.db"
    monkeypatch.setattr(database, "DB_PATH", str(db))
    database.init_database()
    import identity_profile
    before = identity_profile.get_identity_profile()
    assert before["configured"] is False
    assert before["first_run_required"] is True
    database.AppProfileManager.mark_onboarding_seen()
    after = identity_profile.get_identity_profile()
    assert after["onboarding_seen"] is True
    assert after["first_run_required"] is False


def test_profile_schema_v13_has_onboarding_seen_at():
    import database
    assert database.SCHEMA_VERSION >= 13
    fields = {name for name, _ in database.EXPECTED_COLUMNS["app_profile"]}
    assert "onboarding_seen_at" in fields


def test_ui_first_run_prompt_is_not_session_or_menu_scoped():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "j.data.first_run_required" in html
    assert "fetch('/api/profile',{method:'POST'})" in html
    assert "sessionStorage.getItem('lc_profile_prompted')" not in html
    assert "sessionStorage.setItem('lc_profile_prompted'" not in html


def test_profile_modal_closes_when_user_changes_main_menu():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    marker = "function activatePanel(panel){"
    start = html.index(marker)
    block = html[start:start+700]
    assert "profileModal.classList.contains('open')" in block
    assert "closeProfileModal()" in block


def test_manual_profile_button_remains_available():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert 'onclick="openProfileModal()"' in html
    assert 'title="Identitas pengguna/firma untuk seluruh dokumen"' in html
