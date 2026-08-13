@echo off
REM ============================================================
REM Reco Love Gold Beach (PCSG00782) EN patch -- STEP 1: extract
REM
REM Edit the three paths below, then double-click this file.
REM See README.md for what each one is and where to get it.
REM ============================================================

setlocal
set HERE=%~dp0

set INSTALL_DIR=C:\path\to\your\decrypted\PCSG00782
set RECOG_BIN=C:\path\to\your\recog.bin
set OUT_DIR=%HERE%..\..\work\extracted

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    echo Install Python 3 from https://www.python.org/downloads/ and check
    echo "Add Python to PATH" during setup.
    pause & exit /b 1
)

python "%HERE%1_extract_resources.py" "%INSTALL_DIR%" "%RECOG_BIN%" "%OUT_DIR%"
pause
