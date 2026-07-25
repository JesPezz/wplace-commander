@echo off
title WPlace Commander - Depuración
echo Iniciando WPlace Commander en modo consola para ver errores...
cd /d "%~dp0"

:: Ejecuta Python de forma normal para ver la salida en vivo
python wplace_client.py

echo.
echo [PROGRAMA FINALIZADO]
pause