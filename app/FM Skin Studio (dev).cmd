@echo off
rem Development launcher: opens FM Skin Studio (needs Python with the fmskin core installed and npm install done).
cd /d "%~dp0"
if not exist dist\index.html call npm run build:web
call npx electron .
