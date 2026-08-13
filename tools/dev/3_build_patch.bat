@echo off
REM ============================================================
REM Reco Love Gold Beach (PCSG00782) EN patch -- STEP 3: build
REM
REM Needs your own copy of cpkmakec.exe (CRI Middleware's archive
REM tool -- not included, see README.md). Point CPKMAKEC at it.
REM ============================================================

setlocal
set HERE=%~dp0

set INSTALL_DIR=C:\path\to\your\decrypted\PCSG00782
set EXTRACTED_DIR=%HERE%..\..\work\extracted
set PATCHED_DIR=%HERE%..\..\work\patched
set OUTPUT_DIR=%HERE%..\..\work\output
set CPKMAKEC=C:\path\to\your\cpkmakec.exe

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    pause & exit /b 1
)
if not exist "%CPKMAKEC%" (
    echo ERROR: cpkmakec.exe not found at %CPKMAKEC%
    echo Edit CPKMAKEC in this .bat to point at your own copy.
    pause & exit /b 1
)

python "%HERE%3_build_patch.py" "%INSTALL_DIR%" "%EXTRACTED_DIR%" "%PATCHED_DIR%" "%OUTPUT_DIR%" "%CPKMAKEC%"

echo.
echo If every archive above printed [PASS], the patch is ready in:
echo   %OUTPUT_DIR%
pause
