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
Write-Host "==== 必要なモジュールをインストールします ===="

# あなたの import 群はほぼ標準ライブラリなので Pillow だけ入れればOK
python -m pip install pillow

Write-Host ""
Write-Host "==== インストール完了しました ====" -ForegroundColor Cyan
Pause
