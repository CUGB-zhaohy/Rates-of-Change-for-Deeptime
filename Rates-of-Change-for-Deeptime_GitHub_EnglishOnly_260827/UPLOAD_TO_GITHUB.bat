@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0UPLOAD_TO_GITHUB.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo Upload failed. Please send a screenshot of this window.
) else (
    echo Upload process finished.
)
pause
exit /b %EXIT_CODE%
