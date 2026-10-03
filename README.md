# 📘 **Python Studio – Code Editor & Form Designer**  
### **README（日本語版 & English Version）**

---

# 🇯🇵 **日本語版 README**

## 📌 概要
**Python Studio** は、1つの `.pyw` ファイルで動作する **軽量 IDE & GUI フォームデザイナー**です。  
Visual Basic や Delphi のような **ドラッグ配置型 GUI 開発**を Python で再現し、コードエディターとフォームデザイナーを統合しています。

最新版では以下の更新が含まれています：

- **ホットキービルダー機能の追加**  
- フォームデザイナーの安定化  
- コードエディターの強化（検索・置換・ハイライト）  
- 内部構造の整理（イベント管理・クラス分割）  
- **`.py` だけでなく `.pyw` 形式でも保存可能になりました** ← ★追加点

---

## 🧩 機能一覧

### 🎨 GUI フォームデザイナー
- ウィジェットをドラッグ＆ドロップで配置  
- プロパティ編集（位置・サイズ・テキスト・色など）  
- Python コードとして自動生成  
- コードとフォームを同一画面で編集可能  
- **ホットキービルダーでショートカット割り当てが可能**

### ✏️ コードエディター
- Python シンタックスハイライト  
- Undo / Redo  
- 検索・置換  
- 自動インデント  
- `.py` / `.pyw` の読み書き・保存に対応 ← ★追加点  
- フォームコードとの連携

### ⚙️ 環境チェック
- Python 実行環境の存在確認  
- 必要モジュールの簡易チェック  
- 単体ファイルで動作するポータブル設計  

---

## 📁 ファイル構成
本プロジェクトは **単一の `.pyw` ファイル**で構成されています。

- `jp-Python Studio – Code Editor & Form Designer.pyw`  
  - メインウィンドウ  
  - コードエディター  
  - フォームデザイナー  
  - ホットキービルダー  
  - プロパティエディター  
  - イベント管理  
  - ファイル入出力（`.py` / `.pyw` 保存対応）  
  - Python 実行チェック  

---

## 🔧 必要環境
- **OS:** Windows 推奨  
- **Python:** 3.x  
- **依存ライブラリ:** 標準ライブラリ（tkinter など）

---

## 📥 インストール
1. `.pyw` ファイルをダウンロード  
2. Python がインストールされていることを確認  
3. `.pyw` をダブルクリックして起動  
   - または  
     ```bash
     python "jp-Python Studio – Code Editor & Form Designer.pyw"
     ```

---

## 🖱️ 使い方

### 1. GUI フォームを作成
- ウィジェットをドラッグして配置  
- プロパティでサイズ・色・テキストを編集  
- ホットキービルダーでショートカットを設定  

### 2. コードを編集
- 自動生成されたコードを確認  
- イベント処理を追加  
- `.py` または `.pyw` として保存可能 ← ★追加点  
- 保存したファイルはそのまま Python で実行できます

### 3. ホットキービルダー
- GUI 操作用のショートカットを設定  
- フォームイベントに割り当て可能  
- 設定はコードに反映される

---

## ⚠️ 免責事項
このソフトウェアは **「現状のまま」提供** されます。

- 動作保証なし  
- バグ・不具合の保証なし  
- データ消失の責任なし  
- 商用利用・教育利用によるトラブルの責任なし  
- サポート・補償なし  

すべて利用者自身の判断と責任で使用してください。

---

## 📄 ライセンス
リポジトリ内の `LICENSE` を参照してください。

---

## 👤 クレジット
- Repository: rabbit-hand / Python-Studio-Code-Editor-Form-Designer  
- File: jp-Python Studio – Code Editor & Form Designer.pyw  

---

---

# 🇺🇸 **English Version README**

## 📌 Overview
**Python Studio** is a lightweight **IDE & GUI Form Designer** that runs entirely from a single `.pyw` file.  
It recreates a Visual Basic / Delphi–style **drag-and-drop GUI development experience** in Python, combining a code editor and a form designer in one environment.

Recent updates include:

- **Hotkey Builder feature added**  
- Improved form designer stability  
- Enhanced code editor (search, replace, syntax highlight)  
- Internal structure cleanup (event management, class organization)  
- **Supports saving files as both `.py` and `.pyw`** ← ★New

---

## 🧩 Features

### 🎨 GUI Form Designer
- Drag-and-drop widget placement  
- Property editor (position, size, text, color, etc.)  
- Auto-generates Python code  
- Edit form and code in the same window  
- **Hotkey Builder for assigning shortcuts**

### ✏️ Code Editor
- Python syntax highlighting  
- Undo / Redo  
- Search & Replace  
- Auto indentation  
- Load and save `.py` and `.pyw` files ← ★New  
- Integrated with form-generated code

### ⚙️ Environment Check
- Detects Python interpreter  
- Checks required modules  
- Portable single-file design  

---

## 📁 File Structure
This project consists of **one `.pyw` file**:

- `jp-Python Studio – Code Editor & Form Designer.pyw`  
  - Main window  
  - Code editor  
  - Form designer  
  - Hotkey builder  
  - Property editor  
  - Event manager  
  - File I/O (`.py` / `.pyw` support)  
  - Python environment check  

---

## 🔧 Requirements
- **OS:** Windows recommended  
- **Python:** 3.x  
- **Libraries:** Standard libraries only (tkinter, etc.)

---

## 📥 Installation
1. Download the `.pyw` file  
2. Ensure Python is installed  
3. Launch by double-clicking or via command:

```bash
python "jp-Python Studio – Code Editor & Form Designer.pyw"
```

---

## 🖱️ Usage

### 1. Create a GUI Form
- Drag widgets onto the canvas  
- Edit properties (size, color, text)  
- Assign shortcuts using Hotkey Builder  

### 2. Edit Code
- Review auto-generated Python code  
- Add event handlers  
- Save as `.py` **or `.pyw`** ← ★New  
- Run the saved file directly with Python

### 3. Hotkey Builder
- Configure shortcuts for GUI operations  
- Bind them to form events  
- Settings are reflected in the generated code

---

## ⚠️ Disclaimer
This software is provided **“as is”** without warranty of any kind.

- No guarantee of operation  
- No guarantee against bugs  
- No responsibility for data loss  
- No liability for commercial or educational use  
- No support or compensation  

Use at your own risk.

---

## 📄 License
See the `LICENSE` file in the repository.

---

## 👤 Credits
- Repository: rabbit-hand / Python-Studio-Code-Editor-Form-Designer  
- File: jp-Python Studio – Code Editor & Form Designer.pyw  
