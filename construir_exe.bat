@echo off
title Compilador de WPlace Commander
echo ===================================================
echo   1. Generando Icono Multicapa (.ico)
echo ===================================================
python generar_icono.py

echo.
echo ===================================================
echo   2. Verificando / Instalando PyInstaller
echo ===================================================
python -m pip install pyinstaller pillow requests pyperclip >nul 2>&1

echo.
echo ===================================================
echo   3. Compilando Ejecutable con PyInstaller
echo ===================================================
python -m PyInstaller --noconfirm --onedir --windowed --icon="wplace_icon.ico" --add-data "wplace_icon.ico;." wplace_client.py

echo.
echo ===================================================
echo   ✅ Compilacion Finalizada con Exito
echo   Ubicacion: dist\wplace_client\wplace_client.exe
echo ===================================================
pause