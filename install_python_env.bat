@echo off
title Python Studio Environment Installer

echo ==== Python Studio 環境セットアップ ====

REM --- ドキュメントフォルダのパス取得 ---
set "DOC=%USERPROFILE%\Documents"
set "ENV=%DOC%\PythonStudioEnv"
set "VENV=%ENV%\venv"

echo 環境フォルダ: %ENV%

REM --- フォルダが無ければ作成 ---
if not exist "%ENV%" (
    mkdir "%ENV%"
)

echo.
echo ==== Python を確認しています ====
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python が見つかりません。winget でインストールします…
    winget install -e --id Python.Python.3.12
) else (
    echo Python は既にインストールされています。
)

echo.
echo ==== pip をアップグレードします ====
python -m pip install --upgrade pip

echo.
echo ==== 仮想環境を作成します ====
if not exist "%VENV%" (
    python -m venv "%VENV%"
    echo 仮想環境を作成しました: %VENV%
) else (
    echo 仮想環境は既に存在します。
)

echo.
echo ==== 仮想環境を有効化します ====
call "%VENV%\Scripts\activate.bat"

echo.
echo ==== 必要なモジュールをインストールします ====
pip install pillow

echo.
echo ==== セットアップ完了しました ====
echo 仮想環境の場所: %VENV%
pause

