@echo off
echo ===========================================
echo   GHOSTLINK BT // BUILD_RECOVERY
echo ===========================================
echo.

echo [1/4] ADJUSTING PATHS...
:: Ensure we are in project root
cd /d "%~dp0"

echo [2/4] CLEANING ARTIFACTS...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

echo [3/4] EXECUTING PYINSTALLER...
:: Using the VENV Python to ensure dependencies are met
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe -m PyInstaller --clean --noconfirm ^
        --onefile ^
        --windowed ^
        --name "GhostLinkBT" ^
        --icon "assets\ghostbt.ico" ^
        --add-data "assets\ghost_wallpaper.png;assets" ^
        --add-data "assets\ghostbt.ico;assets" ^
        run.py
) else (
    echo [ERROR] VENV NOT FOUND. Running with system python...
    python -m PyInstaller --clean --noconfirm ^
        --onefile ^
        --windowed ^
        --name "GhostLinkBT" ^
        --icon "assets\ghostbt.ico" ^
        --add-data "assets\ghost_wallpaper.png;assets" ^
        --add-data "assets\ghostbt.ico;assets" ^
        run.py
)

echo.
if exist "dist\GhostLinkBT.exe" (
    echo [4/4] BUILD SUCCESSFUL.
    echo ===========================================
    echo   TARGET: dist\GhostLinkBT.exe
    echo ===========================================
) else (
    echo [ERROR] BUILD FAILED.
)
pause
