@echo off
REM ============================================================
REM build.bat -- Windows release build script (developer use only)
REM ============================================================
REM
REM Produces:
REM     dist\HydrogenSpectroscopy\HydrogenSpectroscopy.exe
REM
REM The end user never runs this script -- they just receive the
REM dist\HydrogenSpectroscopy\ folder (or a zip of it) and double-click
REM the .exe inside it. This script is for whoever is cutting the
REM release build.
REM
REM Usage: double-click build.bat, or run it from a terminal:
REM     build.bat
REM ============================================================

setlocal enabledelayedexpansion

echo ==============================================
echo  Hydrogen Quantum Spectroscopy - Windows Build
echo ==============================================
echo.

REM --- 1. Locate Python -----------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and make sure "Add python.exe to PATH" is checked during install.
    exit /b 1
)

for /f "delims=" %%v in ('python --version') do echo Found: %%v
echo.

REM --- 2. Create/activate a build virtual environment ------------------
if not exist ".venv-build" (
    echo Creating build virtual environment .venv-build ...
    python -m venv .venv-build
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        exit /b 1
    )
)

call .venv-build\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate .venv-build
    exit /b 1
)

REM --- 3. Install dependencies ------------------------------------------
echo.
echo Installing requirements...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.txt
    exit /b 1
)

echo.
echo Installing PyInstaller...
pip install "pyinstaller>=6.3,<7.0"
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller
    exit /b 1
)

REM --- 4. Clean stale build artifacts -----------------------------------
echo.
echo Cleaning previous build\ and dist\ ...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM --- 5. Run PyInstaller -------------------------------------------------
echo.
echo Running PyInstaller (this can take a few minutes)...
pyinstaller HydrogenSpectroscopy.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed. See output above.
    exit /b 1
)

REM --- 6. Report result -----------------------------------------------
echo.
if exist "dist\HydrogenSpectroscopy\HydrogenSpectroscopy.exe" (
    echo ==============================================
    echo  BUILD SUCCEEDED
    echo  Executable: dist\HydrogenSpectroscopy\HydrogenSpectroscopy.exe
    echo  Ship the entire dist\HydrogenSpectroscopy\ folder together --
    echo  the .exe depends on the _internal\ folder next to it.
    echo ==============================================
) else (
    echo [ERROR] Expected output not found: dist\HydrogenSpectroscopy\HydrogenSpectroscopy.exe
    echo         Check the PyInstaller log above for what went wrong.
    exit /b 1
)

endlocal
