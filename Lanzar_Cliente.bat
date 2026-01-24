@echo off
title WPlace Commander - Cliente
echo Iniciando WPlace Commander...
cd /d "%~dp0"

:: Ejecuta el script de Python
start /b pythonw wplace_client.py

:: Si el programa se cierra por error, mantiene la ventana abierta
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] El script se detuvo inesperadamente.
    pause
)