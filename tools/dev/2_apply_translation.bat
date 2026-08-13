@echo off
REM ============================================================
REM Reco Love Gold Beach (PCSG00782) EN patch -- STEP 2: translate
REM
REM Uses the English translation shipped in ..\translation\ by default.
REM To use your own translation instead, edit TRANSLATION_DIR below to
REM point at a folder with the same four files (see README.md).
REM ============================================================

setlocal
set HERE=%~dp0

set EXTRACTED_DIR=%HERE%..\..\work\extracted
set PATCHED_DIR=%HERE%..\..\work\patched
REM set TRANSLATION_DIR=C:\path\to\your\own\translation

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    pause & exit /b 1
)

if defined TRANSLATION_DIR (
    python "%HERE%2_apply_translation.py" "%EXTRACTED_DIR%" "%PATCHED_DIR%" --translation-dir "%TRANSLATION_DIR%"
) else (
    python "%HERE%2_apply_translation.py" "%EXTRACTED_DIR%" "%PATCHED_DIR%"
)
pause
