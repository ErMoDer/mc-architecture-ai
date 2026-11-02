@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo [错误] 找不到 .venv
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\export_litematic.py %*
if errorlevel 1 pause
