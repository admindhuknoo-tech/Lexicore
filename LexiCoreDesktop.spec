# PyInstaller onedir specification for LexiCore Desktop.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
datas = [
    (str(root / 'static'), 'static'),
    (str(root / 'schemas'), 'schemas'),
    (str(root / 'golden_datasets'), 'golden_datasets'),
]

license_public_key = root / 'license_public_key.pem'
if license_public_key.exists():
    datas.append((str(license_public_key), '.'))

hiddenimports = []
# OCR/runtime packages may load submodules dynamically.
for pkg in ('rapidocr', 'onnxruntime'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LexiCore',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LexiCore',
)
