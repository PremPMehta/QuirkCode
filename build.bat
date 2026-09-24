@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo  QuirkCode - Windows build
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python is not on PATH.
  echo Install Python 3.11+ from https://www.python.org/downloads/
  echo and check "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv
    pause
    exit /b 1
  )
)

echo Installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo pip install failed
  pause
  exit /b 1
)

echo.
echo Building QuirkCode.exe ...
pyinstaller --noconfirm build_windows.spec
if errorlevel 1 (
  echo PyInstaller failed
  pause
  exit /b 1
)

if not exist "dist\QuirkCode.exe" (
  echo Build finished but dist\QuirkCode.exe was not found.
  pause
  exit /b 1
)

echo.
echo Preparing share folder...
if exist "dist\QuirkCode_Share" rmdir /s /q "dist\QuirkCode_Share"
mkdir "dist\QuirkCode_Share"
mkdir "dist\QuirkCode_Share\logs"
mkdir "dist\QuirkCode_Share\assets"
copy /Y "dist\QuirkCode.exe" "dist\QuirkCode_Share\QuirkCode.exe" >nul
copy /Y "config.json" "dist\QuirkCode_Share\config.json" >nul
copy /Y "HOW_TO_USE.txt" "dist\QuirkCode_Share\HOW_TO_USE.txt" >nul
copy /Y "assets\quirkcode.ico" "dist\QuirkCode_Share\assets\quirkcode.ico" >nul
if exist "assets\quirkcode.png" copy /Y "assets\quirkcode.png" "dist\QuirkCode_Share\assets\quirkcode.png" >nul
if exist "assets\quirkcode_256.png" copy /Y "assets\quirkcode_256.png" "dist\QuirkCode_Share\assets\quirkcode_256.png" >nul

echo.
echo Creating zip (if tar/powershell available)...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\QuirkCode_Share\*' -DestinationPath 'dist\QuirkCode_Share.zip' -Force" 2>nul
if exist "dist\QuirkCode_Share.zip" (
  echo ZIP ready to share:
  echo   %cd%\dist\QuirkCode_Share.zip
) else (
  echo Zip step skipped. Manually zip this folder:
  echo   %cd%\dist\QuirkCode_Share
)

echo.
echo DONE.
echo Share either:
echo   - dist\QuirkCode_Share.zip
echo   - or the folder dist\QuirkCode_Share
echo.
echo Contents of share folder:
dir /b "dist\QuirkCode_Share"
echo.
pause
