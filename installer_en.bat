@echo off
title Python Studio Installer
echo ===============================
echo      Python Studio Installer
echo ===============================
echo.

REM --- Check if Python exists ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Installing Python...
    winget install Python.Python.3 --silent
)

echo Checking Python path...
set PYTHON_PATH=
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

echo Using Python: %PYTHON_PATH%
echo.

REM --- Upgrade pip ---
echo Upgrading pip...
"%PYTHON_PATH%" -m pip install --upgrade pip

REM --- Install required modules ---
echo Installing required modules...
"%PYTHON_PATH%" -m pip install pillow pywin32 pygments tk

REM --- Install Python Studio main program ---
echo Installing Python Studio...
set TARGET=C:\PythonStudio
if not exist "%TARGET%" mkdir "%TARGET%"

powershell -Command ^
 "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/rabbit-hand/Python-Studio-Code-Editor-Form-Designer/main/jp-Python%20Studio%20%E2%80%93%20Code%20Editor%20%26%20Form%20Designer.pyw','%TARGET%\PythonStudio.pyw')"

echo.

REM --- Determine virtual environment path (same logic as Python Studio) ---
echo Determining virtual environment location...

set VENV_FOLDER_NAME=pythonstudio-venv

REM Get Documents folder
for /f "tokens=2,*" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Personal') do set DOCUMENTS=%%b

set VENV_PATH=%DOCUMENTS%\%VENV_FOLDER_NAME%

echo Virtual environment path: %VENV_PATH%

REM --- Create virtual environment ---
if not exist "%VENV_PATH%" (
    echo Creating virtual environment...
    "%PYTHON_PATH%" -m venv "%VENV_PATH%"
)

REM --- Save virtual environment path to file ---
echo %VENV_PATH% > "%TARGET%\venv_path.txt"

echo Saved virtual environment path to venv_path.txt.
echo.

echo Installation complete!
pause

