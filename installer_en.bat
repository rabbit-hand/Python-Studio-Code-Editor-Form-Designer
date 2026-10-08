@echo off
title Python Studio Installer
echo ===============================
echo      Python Studio Installer
echo ===============================
echo.

REM --- Check Python ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing...
    winget install Python.Python.3 --silent
)

for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i
echo Using Python: %PYTHON_PATH%
echo.

REM --- Upgrade pip ---
"%PYTHON_PATH%" -m pip install --upgrade pip

REM --- Install required modules ---
"%PYTHON_PATH%" -m pip install pillow pywin32 pygments tk autopep8

REM --- Install Python Studio ---
set TARGET=C:\PythonStudio
if not exist "%TARGET%" mkdir "%TARGET%"

powershell -Command ^
 "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/rabbit-hand/Python-Studio-Code-Editor-Form-Designer/main/jp-Python%20Studio%20%E2%80%93%20Code%20Editor%20%26%20Form%20Designer.pyw','%TARGET%\PythonStudio.pyw')"

echo.

REM --- Virtual environment path (same as Python Studio) ---
set DESKTOP=%USERPROFILE%\Desktop
set VENV_PATH=%DESKTOP%\Pythonエディター_仮想環境

echo Virtual environment path: %VENV_PATH%

if not exist "%VENV_PATH%" (
    echo Creating virtual environment...
    "%PYTHON_PATH%" -m venv "%VENV_PATH%"
)

echo %VENV_PATH% > "%TARGET%\venv_path.txt"

echo Installation complete!
pause

