# PyInstaller recipe for the skin installer bundled into every installer package.
# Build from core/:  python -m PyInstaller --noconfirm --distpath pkg --workpath build packaging/skin-installer.spec
# One windowed .exe that asks for administrator rights (FM27 on Steam lives in Program Files).
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("UnityPy", "texture2ddecoder", "etcpak", "astc_encoder", "fmod_toolkit", "archspec"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

a = Analysis(["skin_installer.py"], pathex=["../src"], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports + ["fmskin.installer_app", "fmskin.gamepatch"],
             excludes=["pytest", "matplotlib", "numpy.tests", "pyarrow", "pandas", "lxml", "IPython", "jupyter_client", "scipy",
                       "fontTools"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="FM27-Skin-Installer", console=False, upx=False, uac_admin=True,
          icon="../../app/build/icon.ico")
