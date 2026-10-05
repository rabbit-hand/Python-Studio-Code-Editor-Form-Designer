@echo off
title Python Studio Module Installer

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
echo ==== 必要なモジュールをインストールします ====

REM --- 標準ライブラリなので不要 ---
REM tkinter / messagebox / filedialog / colorchooser / ttk
REM subprocess / sys / re / threading / tempfile / os / json
REM datetime / random / webbrowser / urllib.parse / platform / shutil

REM --- 外部モジュール（必要なものだけ） ---
python -m pip install pillow

echo.
echo ==== インストール完了しました ====
pause
