@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set ROOT=%~dp0
set ROOT=%ROOT:~0,-1%
cd /d "%ROOT%"

:: Try to find conda and use base environment
set "PY_EXE=python"
where conda >nul 2>nul
if !ERRORLEVEL! equ 0 (
    echo [INFO] Detected conda, attempting to use base environment...
    :: We use 'conda run' to ensure we use the correct environment's python
    set "PY_EXE=conda run -n base --no-capture-output python"
) else (
    echo [INFO] Conda not found, using system python.
)

echo [INFO] Using Python: !PY_EXE!

if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"

echo [INFO] Installing dependencies...
call !PY_EXE! -m pip install -r "requirements.txt"
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b !ERRORLEVEL!
)

call !PY_EXE! -m pip install pyinstaller
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b !ERRORLEVEL!
)

echo ===================================================
echo Building ArknightsCostBarRuler
echo ===================================================
:: Destination is set to 'ruler/locales' to match the relative path from the script's entry point.
call !PY_EXE! -m PyInstaller --clean --noconfirm --onedir --windowed ^
    --name ArknightsCostBarRuler ^
    --distpath "dist" ^
    --workpath "build\ArknightsCostBarRuler" ^
    --add-data "ruler\locales;ruler\locales" ^
    --add-data "icons;icons" ^
    "ruler\main.py"

if !ERRORLEVEL! neq 0 (
    echo [ERROR] Failed to build ArknightsCostBarRuler.
    pause
    exit /b !ERRORLEVEL!
)

echo ===================================================
echo Building ArknightsTimelineTool
echo ===================================================
call !PY_EXE! -m PyInstaller --clean --noconfirm --onedir --windowed ^
    --name ArknightsTimelineTool ^
    --distpath "dist" ^
    --workpath "build\ArknightsTimelineTool" ^
    --add-data "timeline_tool\locales;timeline_tool\locales" ^
    --add-data "icons;icons" ^
    "timeline_tool\main.py"

if !ERRORLEVEL! neq 0 (
    echo [ERROR] Failed to build ArknightsTimelineTool.
    pause
    exit /b !ERRORLEVEL!
)

echo.
echo Build complete.
dir "%ROOT%\dist"
echo.
pause
