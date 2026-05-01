@echo off
echo ============================================
echo  LeadGen Pro — First Time Setup
echo ============================================
echo.

:: Check Python
python --version 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install from python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Create virtual environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

:: Activate and install packages
echo Installing packages...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet --upgrade

:: Copy .env if missing
if not exist .env (
    copy .env.example .env
    echo.
    echo [IMPORTANT] .env file created. Open it and add your free API keys.
    echo   - Serper.dev key (free 2500/month): https://serper.dev
    echo   - YouTube key (free 10k/day): console.cloud.google.com
    echo   - Meta token (free): developers.facebook.com/tools/explorer
    echo   - Apify token (free $5/month): apify.com
    echo.
)

echo.
echo ============================================
echo  Setup complete! Run START.bat to launch.
echo ============================================
pause
