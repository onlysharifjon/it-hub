@echo off
title Minar Camera - Birinchi Sozlash
cd /d "%~dp0"

echo ============================================
echo   Minar Camera Attendance - Setup
echo ============================================
echo.

:: Python tekshirish
python --version >nul 2>&1
if errorlevel 1 (
    echo [XATO] Python topilmadi! Python 3.10+ o'rnating.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Virtual muhit yaratilmoqda...
python -m venv venv
if errorlevel 1 (
    echo [XATO] Venv yaratib bolmadi.
    pause
    exit /b 1
)

echo [2/3] Kerakli paketlar o'rnatilmoqda (5-10 daqiqa ketadi)...
call venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo [XATO] Paketlar o'rnatilmadi.
    pause
    exit /b 1
)

echo [3/3] .env fayli tekshirilmoqda...
if not exist .env (
    echo [OGOHLANTIRISH] .env fayli topilmadi!
    echo .env.example faylidan nusxa olib to'ldiring.
) else (
    echo .env fayli mavjud. OK.
)

echo.
echo ============================================
echo   Setup tugadi!
echo   Endi start_camera.bat ni ishga tushiring.
echo   Autorun uchun: install_autorun.bat
echo ============================================
pause
