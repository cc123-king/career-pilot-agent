@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Creating virtual environment...
if not exist ".venv\Scripts\python.exe" (
  if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    "%LocalAppData%\Programs\Python\Python312\python.exe" -m venv .venv
  ) else (
    py -3.12 -m venv .venv
  )
)
if errorlevel 1 goto :error

echo [2/4] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/4] Installing CareerPilot Agent...
".venv\Scripts\python.exe" -m pip install -e ".[dev]"
if errorlevel 1 goto :error

echo [4/4] Preparing configuration...
if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Setup completed. Double-click run_ui.bat to start the application.
pause
exit /b 0

:error
echo.
echo Setup failed. Copy the error output and send it to your assistant.
pause
exit /b 1

