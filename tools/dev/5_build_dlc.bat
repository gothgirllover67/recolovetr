@echo off
REM ============================================================
REM Reco Love Gold Beach (PCSG00782) EN patch -- DLC (story routes)
REM
REM Only touches Script.cpk (story) and Table.cpk (event/item
REM titles) inside each DLC -- see the top of 5_build_dlc.py for
REM why the rest of each DLC's files are left alone.
REM ============================================================

setlocal
set HERE=%~dp0

set DLC_ADDCONT_DIR=C:\path\to\your\decrypted\addcont\PCSG00782
set WORK_DIR=%HERE%..\..\work
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

python "%HERE%5_build_dlc.py" "%DLC_ADDCONT_DIR%" "%WORK_DIR%" "%CPKMAKEC%"

echo.
echo If every DLC above printed [PASS], the patched files are ready in:
echo   %WORK_DIR%\dlc_output\^<content_id^>\media\cpk\
pause
