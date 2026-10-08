@echo off
title Python Studio インストーラー
echo ===============================
echo  Python Studio インストーラー
echo ===============================
echo.

REM --- Python があるか確認 ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python が見つかりません。インストールします...
    winget install Python.Python.3 --silent
)

echo Python のパス確認...
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i
echo 使用する Python: %PYTHON_PATH%
echo.

REM --- pip 最新化 ---
"%PYTHON_PATH%" -m pip install --upgrade pip

REM --- 必要モジュール ---
"%PYTHON_PATH%" -m pip install pillow pywin32 pygments tk autopep8

REM --- Python Studio 本体配置 ---
set TARGET=C:\PythonStudio
if not exist "%TARGET%" mkdir "%TARGET%"

powershell -Command ^
 "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/rabbit-hand/Python-Studio-Code-Editor-Form-Designer/main/jp-Python%20Studio%20%E2%80%93%20Code%20Editor%20%26%20Form%20Designer.pyw','%TARGET%\PythonStudio.pyw')"

echo.

REM --- 仮想環境の保存場所（Python Studio と同じ） ---
set DESKTOP=%USERPROFILE%\Desktop
set VENV_PATH=%DESKTOP%\Pythonエディター_仮想環境

echo 仮想環境の場所: %VENV_PATH%

if not exist "%VENV_PATH%" (
    echo 仮想環境を作成中...
    "%PYTHON_PATH%" -m venv "%VENV_PATH%"
)

echo %VENV_PATH% > "%TARGET%\venv_path.txt"

echo インストール完了！
pause

