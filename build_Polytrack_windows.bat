@echo off
setlocal

echo Installing/updating PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo.
    echo Could not install PyInstaller.
    echo Make sure Python is installed.
    pause
    exit /b 1
)

echo.
echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo Building Polytrack.exe...
python -m PyInstaller --clean --noconfirm Polytrack_singlefile.spec
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Finished:
echo dist\Polytrack.exe
echo.
pause