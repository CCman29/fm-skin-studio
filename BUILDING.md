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

> **Paused (2026-10-31):** releases are Windows-only for now. The Mac jobs in `.github/workflows/build.yml` only run
> when the repository variable `BUILD_MAC` is `true`; while it isn't, each release carries a placeholder
> `latest-mac.yml` (version 1.0.0), so installed Mac copies stay on the version they have and report "up to date".
> The Mac downloads were removed from releases 1.0.0–1.0.9. To resume: set `BUILD_MAC` to `true` and tag a release.

A Mac app has to be built on a Mac. On a Mac, run the same steps with `npm run dist:mac` at the end. Result:
`app/release/FM-Skin-Studio-<version>-arm64.dmg` (Apple Silicon) or `-x64.dmg` (Intel; build on an Intel Mac or the
`macos-13` runner).

Without a Mac: put this folder in a GitHub repository and run **Actions › Build installers › Run workflow**
(`.github/workflows/build.yml`). It builds Windows, Apple Silicon and Intel installers on GitHub's machines (free for
public repositories; private repositories use free monthly minutes, and macOS minutes count 10x). Download them from the
run's Artifacts.

## Releasing an update

1. Raise `"version"` in `app/package.json` (for example 1.0.1) and commit.
2. Tag and push: `git tag -a v1.0.1 -m "FM Skin Studio 1.0.1"` then `git push origin main v1.0.1`.
3. GitHub builds Windows, Apple Silicon and Intel installers and publishes them as the release `v1.0.1`.
4. Installed copies see it: the version chip in the top bar shows a dot. Clicking the chip checks straight away and
   offers **Install now**: the app closes, installs the new version and reopens. Windows runs the new installer silently;
   macOS downloads the release's .zip for that Mac's chip and swaps the app in place (if the app's folder can't be
   written without admin rights, it opens the release page instead). Microsoft Store copies are updated by the Store.

To withdraw a bad release, delete it and its tag on GitHub; installed copies then see the previous release as latest.
Support/test hook: `"FM Skin Studio.exe" --update-now` checks, downloads and installs an update without the window.

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

## Skin installer (installer packages)

Check and Save > Installer package turns a skin into "<Skin> Installer.zip": `Install <Skin>.exe`, the skin, and a
README. The .exe is `core/packaging/skin-installer.spec` (one windowed file that asks for administrator rights), built
by `npm run build:core` and by the release workflow, and shipped in the app's `resources/installer` folder.

What it does on a player's PC (`core/src/fmskin/gamepatch.py`): finds FM27 (Game Pass, Steam, Epic), copies every game
file it will change into a backup folder the player picks (with RESTORE.txt), builds any fonts and artwork the skin takes
from the player's own FM27 (recipes in the skin's `fmskinstudio.json` "fromGame", never shipped in the zip), installs the
skin, and optionally recolours FM27's club/team/player names in
`fm_Data/StreamingAssets/aa/StandaloneWindows64/gamemodules_assets_gameworldmatch.bundle`. "Restore a backup" undoes it.
Windows only for now.
