@echo off
title Minar Camera Attendance
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [XATO] Virtual muhit topilmadi.
    echo Birinchi setup.bat ni ishga tushiring.
    pause
    exit /b 1
)

if not exist .env (
    echo [XATO] .env fayli topilmadi!
    echo .env.example dan nusxa olib to'ldiring.
    pause
    exit /b 1
)

:restart
echo.
echo [%time%] Minar Camera servisi ishga tushmoqda...
call venv\Scripts\activate.bat
python service.py
echo.
echo [%time%] Servis to'xtadi. 5 soniyadan keyin qayta ishga tushadi...
timeout /t 5 /nobreak >nul
goto restart
