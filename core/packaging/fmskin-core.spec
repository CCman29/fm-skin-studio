# PyInstaller recipe for the engine the desktop app ships with. Build from core/:  python -m PyInstaller packaging/fmskin-core.spec
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = collect_data_files("fmskin")  # bundled OFL fonts and licences
binaries, hiddenimports = [], []
for pkg in ("UnityPy", "texture2ddecoder", "etcpak", "astc_encoder", "fmod_toolkit", "archspec"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

a = Analysis(["fmskin_core.py"], pathex=["../src"], binaries=binaries, datas=datas, hiddenimports=hiddenimports + ["fmskin"],
             excludes=["tkinter", "pytest", "matplotlib", "numpy.tests", "pyarrow", "pandas", "lxml", "IPython", "jupyter_client", "scipy"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="fmskin-core", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="fmskin-core")
