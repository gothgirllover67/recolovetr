@echo off
REM ============================================================
REM MAINTAINER-ONLY: build the xdelta patches shipped in patches\
REM Run this AFTER 3_build_patch.bat has produced work\output\.
REM Needs xdelta3 on PATH.
REM ============================================================

setlocal
set HERE=%~dp0

set INSTALL_DIR=C:\path\to\your\decrypted\PCSG00782
set BUILT_DIR=%HERE%..\..\work\output

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    pause & exit /b 1
)

python "%HERE%4_build_xdelta_release.py" "%INSTALL_DIR%" "%BUILT_DIR%"
pause
