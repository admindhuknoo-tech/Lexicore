from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"
TEXT = HTML.read_text(encoding="utf-8")


def test_mobile_profile_modal_is_full_screen_and_above_frozen_header():
    assert "#profileModal.review-modal{z-index:320!important" in TEXT
    assert "height:100dvh!important" in TEXT
    assert "max-height:100dvh!important" in TEXT
    assert "border-radius:0!important" in TEXT


def test_mobile_profile_form_collapses_to_single_column():
    assert "#profileModal .review-body .row{grid-template-columns:1fr!important" in TEXT
    assert "#profileModal input,#profileModal textarea{width:100%!important" in TEXT


def test_profile_modal_locks_background_scroll():
    assert "document.body.classList.add('profile-modal-open')" in TEXT
    assert "document.body.classList.remove('profile-modal-open')" in TEXT
    assert "body.profile-modal-open{overflow:hidden" in TEXT
