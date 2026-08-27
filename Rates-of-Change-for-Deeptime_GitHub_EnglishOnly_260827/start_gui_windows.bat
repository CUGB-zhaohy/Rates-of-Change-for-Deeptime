@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================================
echo RoC Workflow Launcher
echo ============================================================
echo Project folder:
echo %cd%
echo.

REM ------------------------------------------------------------
REM 1. Check Python
REM ------------------------------------------------------------
set PYTHON_CMD=

where python >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set PYTHON_CMD=py -3
    )
)

if "%PYTHON_CMD%"=="" (
    echo Python was not found on this computer.
    echo.
    echo This software requires Python 3.10 or later.
    echo.
    set /p OPENPY="Open the Python download page now? [Y/N]: "

    if /I "!OPENPY!"=="Y" (
        start https://www.python.org/downloads/
    )

    echo.
    echo After installing Python, please double-click start_gui.bat again.
    pause
    exit /b 1
)

echo Python detected:
%PYTHON_CMD% --version
echo.

REM ------------------------------------------------------------
REM 2. Create virtual environment if needed
REM ------------------------------------------------------------
if not exist "venv\Scripts\python.exe" (
    echo No virtual environment was found.
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv venv

    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )

    echo Virtual environment created successfully.
    echo.
) else (
    echo Existing virtual environment found.
    echo.
)

REM ------------------------------------------------------------
REM 3. Activate virtual environment
REM ------------------------------------------------------------
call "venv\Scripts\activate"

if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 4. Install requirements
REM ------------------------------------------------------------
if not exist ".gui_runtime" (
    mkdir ".gui_runtime"
)

if not exist ".gui_runtime\requirements_installed.flag" (
    echo Python dependencies have not been installed for this copy.
    echo.
    set /p INSTALLREQ="Install packages from requirements.txt now? [Y/N]: "

    if /I "!INSTALLREQ!"=="Y" (
        echo.
        echo Installing requirements...
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt

        if errorlevel 1 (
            echo.
            echo Failed to install requirements.
            echo Please check your internet connection or install manually:
            echo python -m pip install -r requirements.txt
            pause
            exit /b 1
        )

        echo requirements installed successfully. > ".gui_runtime\requirements_installed.flag"
        echo.
        echo Requirements installed successfully.
    ) else (
        echo.
        echo Requirements were not installed.
        echo The GUI may fail if required packages are missing.
        echo.
        set /p CONTINUE="Continue anyway? [Y/N]: "

        if /I not "!CONTINUE!"=="Y" (
            pause
            exit /b 1
        )
    )
) else (
    echo Requirements were already installed for this copy.
    echo.
)

REM ------------------------------------------------------------
REM 5. Start GUI
REM ------------------------------------------------------------
echo Starting RoC Workflow GUI...
echo.
python gui.py

echo.
echo GUI closed.
pause