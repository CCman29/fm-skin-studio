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

## Game Link plugin (optional add-on)

`gamelink/` is a small BepInEx 6 (IL2CPP) plugin that the studio can install into FM27 on request. It listens on
127.0.0.1:47827 with a per-launch token, reloads skins, takes screenshots and applies the selected skin's name colour
(`systemText.names` in the skin's fmskinstudio.json, via FM's text style sheet); it never touches saves or game logic.

The plugin compiles against bindings BepInEx generates from the player's own game on first launch, so it can't be built
in CI. Build it on a PC with FM27:

1. Install Game Link once from the studio (Advanced Editor → Game Link), start FM27 and let BepInEx finish its first launch.
2. `dotnet build -c Release` in `gamelink/` (set `GameDir` if FM27 isn't in `C:\XboxGames\Football Manager 27\Content`).
3. Copy `bin/Release/net6.0/FMSkinStudio.GameLink.dll` to `gamelink/dist/` and commit it. The installer bundles that file.

Never commit `gamelink/bin`, `gamelink/obj` or anything from the game's `BepInEx/interop` folder: they're derived from
Unity's and Sports Interactive's code.
