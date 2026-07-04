@echo off
title Minar Camera Attendance
cd /d "%~dp0"

set CONDA_PYTHON=%USERPROFILE%\miniconda3\envs\minar\python.exe

if not exist "%CONDA_PYTHON%" (
    echo [XATO] Conda "minar" muhiti topilmadi.
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
"%CONDA_PYTHON%" service.py
echo.
echo [%time%] Servis to'xtadi. 5 soniyadan keyin qayta ishga tushadi...
timeout /t 5 /nobreak >nul
goto restart
