@echo off
echo ============================================
echo  LeadGen Pro — AmmarBuilds
echo  Starting on http://localhost:8001
echo ============================================
echo.

if not exist venv (
    echo [ERROR] Run SETUP.bat first!
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

:: Open browser after 2 seconds
start /min cmd /c "timeout /t 2 >nul && start http://localhost:8001"

echo Server starting... Browser will open automatically.
echo Press Ctrl+C to stop.
echo.
python server.py
