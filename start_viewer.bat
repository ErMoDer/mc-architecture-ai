@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if not exist ".venv\Scripts\python.exe" (
  echo [错误] 找不到 .venv，请先创建虚拟环境并安装依赖：
  echo   python -m venv .venv
  echo   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  echo   .\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import customtkinter,matplotlib" 1>nul 2>nul
if errorlevel 1 (
  echo [提示] 缺少预览依赖，正在安装 requirements-app.txt ...
  ".venv\Scripts\python.exe" -m pip install -r requirements-app.txt
  if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
  )
)
echo 启动 MC Architecture 预览 GUI ...
".venv\Scripts\python.exe" "scripts\viewer_app.py"
if errorlevel 1 (
  echo.
  echo 程序异常退出，按任意键关闭。
  pause
)
