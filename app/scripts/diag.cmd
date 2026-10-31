@echo off
rem Writes what the desktop app sees (real AppData, outside Claude's sandbox) to diag.txt next to this script.
set OUT=%~dp0diag.txt
echo === cache > "%OUT%"
dir /b /s "%LOCALAPPDATA%\FMSkinStudio\cache\*manifest.json" >> "%OUT%" 2>&1
for /r "%LOCALAPPDATA%\FMSkinStudio\cache" %%f in (manifest.json) do if exist "%%f" type "%%f" >> "%OUT%"
echo === settings >> "%OUT%"
type "%APPDATA%\FMSkinStudio\settings.json" >> "%OUT%" 2>&1
echo === skins >> "%OUT%"
dir /b "%USERPROFILE%\Documents\Sports Interactive\Football Manager 27\skins" >> "%OUT%" 2>&1
echo === core >> "%OUT%"
cd /d "%~dp0.."
python -c "from fmskin.service import Service; s=Service(); print(s.index_status()); print([p['id'] for p in s.packs()]); print(s.pack('white-sky-sports')['sheets'] if any(p['id']=='white-sky-sports' for p in s.packs()) else 'no white-sky-sports')" >> "%OUT%" 2>&1
echo done >> "%OUT%"
