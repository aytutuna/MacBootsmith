# PyInstaller spec for the MacBootsmith Windows build (onedir, windowed).
# Build from the repository root:  python -m PyInstaller --noconfirm --clean packaging/macbootsmith.spec
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.dirname(SPECPATH)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def data(relative, target):
    return (os.path.join(ROOT, *relative.split("/")), target)


datas = [
    data("OpCore-Simplify.py", "."),
    data("Scripts/usb_enum.cs", "Scripts"),
    data("Scripts/datasets/background_picker.icns", "Scripts/datasets"),
]
datas += [(path, "docs/reference") for path in sorted(glob.glob(os.path.join(ROOT, "docs", "reference", "*.md")))]

hiddenimports = ["updater"] + collect_submodules("Scripts")

a = Analysis(
    [os.path.join(ROOT, "MacBootsmith.pyw")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tests", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MacBootsmith",
    console=False,
    debug=False,
    strip=False,
    upx=False,
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MacBootsmith",
)
