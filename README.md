# FM Skin Studio

Desktop tool for building Football Manager 27 skin packs: edit theme colours/fonts/sizes and screen panel layouts,
then save the result as a new skin pack the player picks in FM27's Preferences.

Research and spec: `../re-work/fm27-skinning/` (`findings.md`, `spec.md`).

## Layout
- `core/` — Python engine and sidecar (`fmskin`). Reads the game's own data from the local install at runtime,
  writes skin packs, validates them against the game's rules, manages layouts and backups.
- `app/` — Electron + React desktop UI. Tabs: Global settings (main surfaces, link-all, every token by group,
  contrast check), Bars & backgrounds, Fonts, Screens & layouts (grid editor with the game's limits), Check & share.

## Run the app (development)
```
cd app
npm install
npm run build:web      # or: npm run dev:web + set FMSKIN_DEV_URL=http://localhost:5174
npm start              # opens the desktop window; it starts the Python core itself
node scripts/check-sidecar.cjs   # smoke test of the core <-> app protocol
```
In a normal browser (UI work only): `npm run dev:core` + `npm run dev:web`, open http://localhost:5174.

## Core quick start
```
cd core
python -m pip install -e ".[dev]"
python -m fmskin.cli paths          # detected game + user folders
python -m fmskin.cli index          # build the local game index (~40 s, cached per game build)
python -m fmskin.cli new "My Skin"  # creates skins/my-skin/ (never touches existing skins)
python -m fmskin.cli set my-skin "--layout-modules-block-surface=rgba(0, 60, 40, 0.85)"
python -m fmskin.cli validate my-skin
python -m pytest -q
```

## Safety rules
- Every project is its own new pack folder marked with `fmskinstudio.json`; folders without the marker
  (including the player's current skin) are never written, renamed or deleted.
- Layouts are stored inside the pack and only copied to the game's `CustomGridCompositions` on an explicit
  apply, after backing up the player's files (`restore-layouts` undoes it).
- Packs and exports contain only the creator's files — never game assets.
