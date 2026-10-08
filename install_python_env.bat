@echo off
title Python Studio Installer
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
set PYTHON_PATH=
for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

echo 使用する Python: %PYTHON_PATH%
echo.

REM --- pip 最新化 ---
echo pip をアップグレード中...
"%PYTHON_PATH%" -m pip install --upgrade pip

REM --- 必要モジュール ---
echo 必要モジュールをインストール中...
"%PYTHON_PATH%" -m pip install pillow pywin32 pygments tk

REM --- Python Studio 本体配置 ---
echo Python Studio を配置中...
set TARGET=C:\PythonStudio
if not exist "%TARGET%" mkdir "%TARGET%"

powershell -Command ^
 "(New-Object Net.WebClient).DownloadFile('https://raw.githubusercontent.com/rabbit-hand/Python-Studio-Code-Editor-Form-Designer/main/jp-Python%20Studio%20%E2%80%93%20Code%20Editor%20%26%20Form%20Designer.pyw','%TARGET%\PythonStudio.pyw')"

echo.

REM --- 仮想環境の保存場所を決定（Python Studio と同じロジック） ---
echo 仮想環境の保存場所を決定中...

set VENV_FOLDER_NAME=pythonstudio-venv

REM ドキュメントフォルダを取得
for /f "tokens=2,*" %%a in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Personal') do set DOCUMENTS=%%b

set VENV_PATH=%DOCUMENTS%\%VENV_FOLDER_NAME%

echo 仮想環境の場所: %VENV_PATH%

REM --- 仮想環境作成 ---
if not exist "%VENV_PATH%" (
    echo 仮想環境を作成中...
    "%PYTHON_PATH%" -m venv "%VENV_PATH%"
)

REM --- 仮想環境パスをファイル保存 ---
echo %VENV_PATH% > "%TARGET%\venv_path.txt"

echo 仮想環境のパスを venv_path.txt に保存しました。
echo.

echo インストール完了！
pause

