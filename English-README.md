Python Studio Editor の英語版（`Python Studio Editor v0.2.4 English.pyw`）のコード内容をベースに、バージョン 0.2.4 の変更点や最新の仕様をしっかりと反映させた日本語と英語の取扱説明書（README）を、リンクを使わずにすべての説明文をマークダウン形式で直接記述した形でそれぞれ作成しました。

用途に合わせて使い分けてみてください。

---

### 日本語版 取扱説明書 (README.md)

```markdown
# Python Studio Editor 取扱説明書

Python Studio Editor は、プログラミング初心者・学習者・ホビーストのために開発された、軽量でシンプルな Python GUI コードエディター & Tkinter フォームデザイナーです。
複雑な環境構築を必要とせず、直感的な操作で Python/Tkinter を使ったデスクトップアプリの作成や学習が行えます。

## 目次

1. 主な機能
2. 動作環境
3. インストール・起動方法
4. 基本的な使い方
   - コードエディター
   - 初心者向け作品カタログ
   - Tkinter フォームデザイナー
   - ホットキー・ボタン作成ツール
5. バージョン 0.2.4 の新機能・変更点
6. 免責事項

---

## 主な機能

* **シンプル＆軽量コードエディター**
  * 構文ハイライト（キーワード・文字列・コメントの色分け表示）
  * 行番号表示、フォントサイズ調整、ライト/ダークテーマ切り替え
  * 検索・置換機能、PEP8（autopep8）によるコード自動整形
* **豊富なお手本・作品カタログ**
  * 電卓、じゃんけん、ToDoリスト、ファイルマネージャー、JSONエディター、カレンダーなどの実用サンプルコードを標準搭載
  * 1クリックでエディターへ読み込み・即時実行が可能
* **直感的な Tkinter フォームデザイナー**
  * ドラッグ＆ドロップ感覚でボタンやラベルなどの GUI パーツ（ウィジェット）を配置
  * 配置したレイアウトから Python/Tkinter の実行コードを自動生成
* **ホットキー・ボタン作成ツール**
  * ショートカットキーやボタン操作で「URLを開く」「アプリ起動」「キー送信」などを行うタスク化コードを自動作成
  * タスクトレイ（システムトレイ）常駐機能の組み込みに対応

---

## 動作環境

* **対応OS**: Windows 10 / 11 (推奨) / Linux
* **Python**: Python 3.8 以降
* **依存ライブラリ**: Python 標準ライブラリ (tkinter, ctypes, json, subprocess など)
  * ※一部の拡張機能では外部ライブラリ (autopep8, pystray, pillow, keyboard) を使用します。

---

## インストール・起動方法

1. リポジトリから Python Studio Editor v0.2.4 English.pyw （または該当する .pyw / .py ファイル）をダウンロードします。
2. Python がインストールされている環境で、ファイルをダブルクリックして起動します。
3. ターミナルやコマンドプロンプトから起動する場合は以下のコマンドを実行します。

```bash
python "Python Studio Editor v0.2.4 English.pyw"

```

---

## 基本的な使い方

### 1. コードエディター

* メイン画面のエディターで直接 Python コードを記述できます。
* 上部ツールバーから「保存」「上書き保存」「開く」などのファイル操作が行えます。
* ショートカットキーで「検索・置換」ダイアログを呼び出したり、コードの整形を実行できます。

### 2. 初心者向け作品カタログ

* 「初心者向け作品一覧」を開くと、カテゴリー別に分類されたサンプルプログラムが閲覧できます。
* 試してみたい作品を選び「コードをエディターに読み込む」をクリックすると、すぐに実行可能なコードがセットされます。

### 3. Tkinter フォームデザイナー

* 「フォーム作成」タブを選択すると、ビジュアルデザイナーが起動します。
* 画面上にボタン、ラベル、テキスト入力欄などのパーツを追加・配置し、プロパティ（テキストやサイズ）を調整します。
* 「コード生成」ボタンを押すと、作成した画面に対応する Python コードが自動生成されます。

### 4. ホットキー・ボタン作成ツール

* 任意のキー入力（例: Alt+A）やボタン押下に対して、特定のアクション（Webサイト表示、ファイル起動など）を割り当てられます。
* 設定完了後、タスクトレイに常駐して動作する自分専用の便利ツールコードを書き出せます。

---

## バージョン 0.2.4 の新機能・変更点

* **ファイル保存・トレイアイコンの改善**
* save_as_file 関数のリファクタリングを実施し、ファイル保存処理の安定性と挙動を改善しました。
* form_use_tray（フォームおよびホットキービルダーにおけるトレイ機能）のデフォルト設定を見直し、よりスムーズな動作を実現しました。


* **ホットキー・ボタン作成ツールの拡張**
* 生成されるコードの安定性が向上し、外部ライブラリ（keyboard / pystray）との連携オプションがより使いやすく調整されました。



---

## 免責事項

1. **自己責任での利用**
* 本ソフトウェア（Python Studio Editor）は、現状有姿（As-Is）で提供されます。
* 本ソフトウェアの使用、または使用不能によって生じた直接的・間接的な損害（データ消失、システム障害、業務中断、その他あらゆる損害を含む）について、開発者および権利者は一切の責任を負いません。すべて利用者の自己責任においてご使用ください。


2. **生成されるコードおよびサンプルの動作保証**
* 本ソフトウェア内で提供されるサンプルコード、および各種ツールによって自動生成されるコードの正確性、完全性、安全性、特定目的への適合性について、明示・黙示を問わずいかなる保証も行いません。


3. **外部ライブラリおよび環境依存**
* 本ソフトウェアは OS 固有の API（Windows API 等）や外部コマンドを実行する機能を含みます。環境や実行権限によっては意図しない動作をする場合がありますので、十分に動作確認を行った上でご利用ください。


4. **仕様変更およびサポート**
* 本ソフトウェアの仕様は、予告なく変更または開発・提供が中止される場合があります。個別の機能改善や不具合修正等のサポート義務を負うものではありません。



```

---

### 英語版 取扱説明書 (README_EN.md)

```markdown
# Python Studio Editor User Manual

Python Studio Editor is a lightweight and simple Python GUI code editor and Tkinter form designer designed for beginners, learners, and hobbyists. It allows you to create desktop applications and learn Python/Tkinter intuitively without complex environment setup.

## Table of Contents

1. Key Features
2. System Requirements
3. Installation & Startup
4. Basic Usage
   - Code Editor
   - Beginner Project Catalog
   - Tkinter Form Designer
   - Hotkey & Button Creator
5. Version 0.2.4 New Features & Changes
6. Disclaimer

---

## Key Features

* **Simple & Lightweight Code Editor**
  * Syntax highlighting (color-coded keywords, strings, and comments)
  * Line number display, font size adjustment, and light/dark theme switching
  * Search and replace functions, alongside automated code formatting via PEP8 (autopep8)
* **Beginner Project Catalog**
  * Comes standard with practical sample codes such as calculators, rock-paper-scissors, ToDo lists, file managers, JSON editors, and calendars
  * Instantly load samples into the editor with a single click
* **Intuitive Tkinter Form Designer**
  * Drag-and-drop style placement of GUI widgets such as buttons and labels
  * Automatically generates executable Python/Tkinter code from your visual layouts
* **Hotkey & Button Creator**
  * Automatically generates task automation code for opening URLs, launching applications, or sending keystrokes via custom shortcuts or button actions
  * Supports system tray resident functionality

---

## System Requirements

* **Supported OS**: Windows 10 / 11 (Recommended) / Linux
* **Python**: Python 3.8 or later
* **Dependencies**: Python standard libraries (tkinter, ctypes, json, subprocess, etc.)
  * *Note: External libraries (autopep8, pystray, pillow, keyboard) are utilized for certain extended features.*

---

## Installation & Startup

1. Download Python Studio Editor v0.2.4 English.pyw (or the relevant .pyw / .py file) from the repository.
2. Double-click the file in an environment where Python is installed.
3. If running from a terminal or command prompt, execute the following command:

```bash
python "Python Studio Editor v0.2.4 English.pyw"

```

---

## Basic Usage

### 1. Code Editor

* You can write Python code directly in the main editor screen.
* Perform file operations such as "Save", "Save As", and "Open" from the top toolbar.
* Trigger search/replace dialogs or execute code formatting using keyboard shortcuts.

### 2. Beginner Project Catalog

* Open the beginner project list to browse sample programs categorized by type.
* Select a project and click "Load code to editor" to immediately populate the workspace with executable code.

### 3. Tkinter Form Designer

* Select the "Form Creation" tab to launch the visual designer.
* Add and arrange widgets like buttons, labels, and text input fields, and adjust properties such as text and dimensions.
* Click the "Generate Code" button to automatically output the corresponding Python code for your screen layout.

### 4. Hotkey & Button Creator

* Assign specific actions (such as displaying web pages or launching files) to desired key inputs (e.g., Alt+A) or button clicks.
* Once configured, export custom utility code designed to run persistently in the system tray.

---

## Version 0.2.4 New Features & Changes

* **Improvements to File Saving & Tray Icons**
* Refactored the save_as_file function to enhance stability and behavior during file save operations.
* Revised the default settings for form_use_tray (tray functionality in forms and hotkey builders) for a smoother user experience.


* **Expansion of Hotkey & Button Creator**
* Improved the stability of generated code and adjusted integration options with external libraries (keyboard / pystray) for easier usability.



---

## Disclaimer

1. **Use at Your Own Risk**
* This software (Python Studio Editor) is provided "as-is" without warranty of any kind.
* The developers and rights holders assume no responsibility for any direct or indirect damages (including data loss, system failures, business interruptions, or any other damages) arising from the use or inability to use this software. Please use it entirely at your own risk.


2. **No Warranty for Generated Code and Samples**
* No guarantees, explicit or implicit, are made regarding the accuracy, completeness, safety, or fitness for a particular purpose of the sample codes provided within this software or the codes automatically generated by various tools.


3. **External Libraries and Environment Dependencies**
* This software includes features that execute OS-specific APIs (such as Windows APIs) or external commands. Depending on your environment and execution permissions, unexpected behaviors may occur, so please thoroughly test functionality before use.


4. **Specifications Changes and Support**
* The specifications of this software are subject to change, or development and provision may be discontinued without prior notice. There is no obligation to provide support for individual feature improvements or bug fixes.



```

```
