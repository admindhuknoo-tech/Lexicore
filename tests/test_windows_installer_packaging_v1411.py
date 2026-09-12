from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_installer_script_packages_only_dist_bundle():
    text = (ROOT / "installer" / "LexiCore.iss").read_text(encoding="utf-8")
    assert 'Source: "..\\dist\\LexiCore\\*"' in text
    assert 'DestDir: "{app}"' in text
    assert "recursesubdirs" in text


def test_installer_build_requires_public_key_in_dist():
    text = (ROOT / "build_installer.bat").read_text(encoding="utf-8")
    assert "dist\\LexiCore\\license_public_key.pem" in text
    assert "Inno Setup 6" in text


def test_desktop_build_installs_pytest_before_regression():
    text = (ROOT / "build_desktop.bat").read_text(encoding="utf-8")
    install_pos = text.index("python -m pip install pytest")
    test_pos = text.index("python -m pytest -q")
    assert install_pos < test_pos
