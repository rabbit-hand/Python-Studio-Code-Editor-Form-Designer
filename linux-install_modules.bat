#!/bin/bash
set -e

echo "========================================================"
echo "Python Studio Editor (Linux) 必要モジュール セットアップ"
echo "========================================================"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
    echo "[エラー] python3 が見つかりませんでした。"
    echo "先にPython 3をインストールしてください。"
    exit 1
fi

echo "1. Tkinter / venv パッケージを確認・インストールします..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3-tk python3-venv
else
    echo "[注意] apt-get が見つかりません。ディストリビューションのパッケージ管理ツールで python3-tk と python3-venv を導入してください。"
fi

VENV_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/python-studio-editor/project-venv"

echo ""
echo "2. 専用仮想環境を作成・確認します: $VENV_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
if [ ! -x "$VENV_DIR/bin/python" ]; then
    python3 -m venv --system-site-packages "$VENV_DIR"
fi

echo ""
echo "3. 必要なPythonモジュールをインストールします..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install autopep8 pynput pystray Pillow

echo ""
echo "========================================================"
echo "セットアップが完了しました！"
echo "========================================================"
read -rp "Enterキーを押して終了します..." _
