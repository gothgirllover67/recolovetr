@echo off
REM ============================================================
REM Reco Love Gold Beach (PCSG00782) EN patch -- simple install
REM
REM This is the easy path: no cpkmakec.exe, no recog.bin, just
REM xdelta3 and your own decrypted copy of the game. Edit the two
REM paths below, then double-click this file.
REM
REM Needs xdelta3 on your PATH -- install it (apt/brew/choco
REM install xdelta3, or a Windows build from the xdelta project's
REM releases) if the step below says it's missing.
REM ============================================================

setlocal
set HERE=%~dp0

set INSTALL_DIR=C:\path\to\your\decrypted\PCSG00782
set OUTPUT_DIR=%HERE%..\..\work\xdelta_output

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    echo Install Python 3 from https://www.python.org/downloads/ and check
    echo "Add Python to PATH" during setup.
    pause & exit /b 1
)

python "%HERE%apply_xdelta_patch.py" "%INSTALL_DIR%" "%OUTPUT_DIR%"

echo.
echo Copy the files above over your own decrypted install, then
echo reinstall/reboot so the game picks up the new archives.
pause
