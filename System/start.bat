@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0ctxmenu.py" (
    echo.
    echo  [!] ctxmenu.py not found in the same folder as start.bat
    echo  Please make sure both files are in the same directory.
    echo.
    pause
    exit /b 1
)

python -c "import sys" >nul 2>&1
if not errorlevel 1 goto run

echo.
echo  [!] Python not found. Trying to install...
echo.

winget --version >nul 2>&1
if errorlevel 1 goto no_winget

echo  [*] Installing Python via winget...
echo.
winget install --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
goto after_install

:no_winget
echo  [!] winget not found. Choose an option:
echo.
echo    [1] Auto-download Python installer
echo    [2] Open Python website
echo    [q] Quit
echo.
:menu
set /p choice=Enter option:
if /i "%choice%"=="1" goto download
if /i "%choice%"=="2" goto website
if /i "%choice%"=="q" goto quit
goto menu

:website
start https://www.python.org/downloads/
echo  Re-run after installation.
pause
goto quit

:download
echo.
echo  [*] Downloading Python 3.12...
echo.
curl -L --progress-bar -o "%TEMP%\python_setup.exe" "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" 2>nul
if errorlevel 1 (
    echo  [*] Trying PowerShell...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%TEMP%\python_setup.exe' -UseBasicParsing"
)
if errorlevel 1 goto dl_fail
echo.
echo  [OK] Download complete. NOTE: Check "Add Python to PATH"
echo.
"%TEMP%\python_setup.exe"
goto after_install

:dl_fail
echo  [!] Download failed. Visit: https://www.python.org/downloads/
pause
goto quit

:after_install
echo.
python -c "import sys" >nul 2>&1
if not errorlevel 1 goto run
echo  [!] Please restart this program to apply PATH changes.
pause
goto quit

:run
rem Launch GUI via pythonw so no console window lingers
where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "%~dp0ctxmenu.py"
) else (
    start "" python "%~dp0ctxmenu.py"
)
goto quit

:quit
exit /b 0
