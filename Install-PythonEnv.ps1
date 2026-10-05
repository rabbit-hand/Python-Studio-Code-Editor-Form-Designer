Write-Host "==== Python Studio 環境セットアップ ====" -ForegroundColor Cyan

# ドキュメントフォルダに専用環境を作成
$docPath = [Environment]::GetFolderPath("MyDocuments")
$envPath = "$docPath\PythonStudioEnv"
$venvPath = "$envPath\venv"

Write-Host "環境フォルダ: $envPath"

# フォルダが無ければ作成
if (-not (Test-Path $envPath)) {
    New-Item -ItemType Directory -Path $envPath | Out-Null
}

Write-Host ""
Write-Host "==== Python を確認しています ===="

# Python があるかチェック
$python = Get-Command python -ErrorAction SilentlyContinue

if (-not $python) {
    Write-Host "Python が見つかりません。winget でインストールします…" -ForegroundColor Yellow
    winget install -e --id Python.Python.3.12
} else {
    Write-Host "Python は既にインストールされています。" -ForegroundColor Green
}

Write-Host ""
Write-Host "==== pip をアップグレードします ===="
python -m pip install --upgrade pip

Write-Host ""
Write-Host "==== 仮想環境を作成します ===="

# 仮想環境が無ければ作成
if (-not (Test-Path $venvPath)) {
    python -m venv $venvPath
    Write-Host "仮想環境を作成しました: $venvPath" -ForegroundColor Green
} else {
    Write-Host "仮想環境は既に存在します。" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==== 仮想環境を有効化します ===="
$activate = "$venvPath\Scripts\Activate.ps1"
& $activate

Write-Host ""
Write-Host "==== 必要なモジュールをインストールします ===="

# あなたの import 群はほぼ標準ライブラリなので Pillow だけでOK
pip install pillow

Write-Host ""
Write-Host "==== セットアップ完了しました ====" -ForegroundColor Cyan
Write-Host "仮想環境の場所: $venvPath"
Write-Host "Python Studio からこの仮想環境を使えます。"
Pause

