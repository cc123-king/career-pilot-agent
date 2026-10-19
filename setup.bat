@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto :error
if not exist ".env" copy ".env.example" ".env" >nul
echo Setup complete. Use run_ui.bat to open the combined app.
pause
exit /b 0
:error
echo Setup failed. See the command output above.
pause
exit /b 1
