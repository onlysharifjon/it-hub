@echo off
title Minar Camera - Windows Autorun O'rnatish
cd /d "%~dp0"

set "TASK_NAME=MinarCameraAttendance"
set "BAT_PATH=%~dp0start_camera.bat"

echo ============================================
echo   Minar Camera - Autorun O'rnatish
echo ============================================
echo.
echo Task: %TASK_NAME%
echo Fayl: %BAT_PATH%
echo.

:: Eski taskni o'chirish (agar bo'lsa)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Yangi task yaratish — foydalanuvchi tizimga kirganida, 1 daqiqa kechikish bilan
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%BAT_PATH%\"" ^
    /sc ONLOGON ^
    /delay 0001:00 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f

if errorlevel 1 (
    echo [XATO] Task yaratib bolmadi. Administrator sifatida ishga tushiring.
    pause
    exit /b 1
)

echo.
echo [OK] Autorun muvaffaqiyatli o'rnatildi!
echo Kompyuter yonganda 1 daqiqadan keyin kamera servis avtomatik ishga tushadi.
echo.
echo Autorunni o'chirish uchun:
echo   schtasks /delete /tn "%TASK_NAME%" /f
echo.
pause
