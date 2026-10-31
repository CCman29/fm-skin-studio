# Building the FM Skin Studio installers

The app has two parts: the Electron interface (`app/`) and the Python engine (`core/`). Each installer contains both: the
engine is bundled into a standalone program with PyInstaller, so users don't need Python.

## Windows (on a Windows PC)

```
cd core
python -m pip install . "pyinstaller>=6.16"
python -m PyInstaller --noconfirm --distpath pkg --workpath build packaging/fmskin-core.spec
cd ../app
npm ci
npm run dist:win
```

Result: `app/release/FM-Skin-Studio-Setup-<version>.exe` (installs per user, no admin rights needed; lets the user pick the
folder; adds Start menu and desktop shortcuts; uninstalls from Settings › Apps and keeps the user's skins and settings).

## macOS (on a Mac, or with GitHub Actions)

A Mac app has to be built on a Mac. On a Mac, run the same steps with `npm run dist:mac` at the end. Result:
`app/release/FM-Skin-Studio-<version>-arm64.dmg` (Apple Silicon) or `-x64.dmg` (Intel; build on an Intel Mac or the
`macos-13` runner).

Without a Mac: put this folder in a GitHub repository and run **Actions › Build installers › Run workflow**
(`.github/workflows/build.yml`). It builds Windows, Apple Silicon and Intel installers on GitHub's machines (free for
public repositories; private repositories use free monthly minutes, and macOS minutes count 10x). Download them from the
run's Artifacts.

## Signing (optional, but removes the security warnings)

Unsigned builds work, but Windows SmartScreen shows "Windows protected your PC" (users click More info › Run anyway), and
macOS refuses to open an unsigned, un-notarised app until the user allows it in System Settings › Privacy & Security.

| Option | Cost | Notes |
|---|---|---|
| Microsoft Store | Free for individuals and companies | Store signs and hosts the app and handles updates. Identity check required. Needs an MSIX or Store-ready package. |
| Azure Artifact Signing (was Trusted Signing) | Monthly Azure subscription | Check the live price and whether individuals in your country are eligible. |
| Code-signing certificate (OV) from a CA | Typically a few hundred USD a year | Since 2023 the key must live on a hardware token or cloud HSM. SmartScreen warnings fade as the app builds reputation. |
| Apple Developer Program (for macOS) | 99 USD a year | Needed to sign and notarise for macOS. |

GitHub Actions secrets used when present: `CSC_LINK` (base64 .p12 or a URL) and `CSC_KEY_PASSWORD` for the signing
certificate; `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD` and `APPLE_TEAM_ID` for macOS notarisation.
