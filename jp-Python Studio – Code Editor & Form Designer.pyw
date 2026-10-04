import tkinter as tk
from tkinter import messagebox, filedialog, colorchooser, ttk
import subprocess
import sys
import re
from threading import Thread
import tempfile
import os
import json
import datetime
import random
import webbrowser
import urllib.parse
import platform
import shutil

# Windows専用
try:
    import winsound
except ImportError:
    winsound = None

# 設定
SETTINGS_FOLDER = os.path.join(os.path.expanduser("~"), "UltimatePythonIDE_Settings")
THEME_SETTINGS_FILE = 'theme_settings.json'
HOTKEY_BUILDER_SETTINGS_FILE = 'hotkey_builder.json'

current_theme = 'dark'
current_font_size = 11
test_timeout_seconds = 20

THEMES = {
    'light': {
        'bg': '#f8f9fa', 'text_bg': '#ffffff', 'button_bg': '#e9ecef',
        'text_fg': '#212529', 'cursor': '#000000', 'border': '#ced4da',
        'accent': '#0d6efd', 'sidebar_bg': '#f1f3f5', 'match_bg': '#fff3cd'
    },
    'dark': {
        'bg': '#1e1e1e', 'text_bg': '#252526', 'button_bg': '#333333',
        'text_fg': '#d4d4d4', 'cursor': '#aeafad', 'border': '#3f3f46',
        'accent': '#007acc', 'sidebar_bg': '#2d2d2d', 'match_bg': '#264f78'
    }
}

text_modified = False
last_saved_content = ""
search_window = None
last_search_index = "1.0"
VENV_FOLDER_NAME = "Pythonエディター_仮想環境"

def get_desktop_path():
    if os.name == "nt":
        try:
            import ctypes
            desktop_path = ctypes.create_unicode_buffer(260)
            result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, desktop_path)
            if result == 0 and desktop_path.value:
                return desktop_path.value
        except (AttributeError, OSError):
            pass
    return os.path.join(os.path.expanduser("~"), "Desktop")

VIRTUALENV_PATH = os.path.join(get_desktop_path(), VENV_FOLDER_NAME)

def get_virtualenv_path():
    return VIRTUALENV_PATH

def get_virtualenv_python():
    venv_path = get_virtualenv_path()
    python_path = os.path.join(venv_path, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv_path, "bin", "python")
    if not os.path.isfile(python_path):
        os.makedirs(os.path.dirname(venv_path), exist_ok=True)
        try:
            subprocess.run([sys.executable, "-m", "venv", venv_path], check=True,
                           capture_output=True, text=True, timeout=120)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e.stderr.strip() or str(e)) from e
    if not os.path.isfile(python_path):
        raise RuntimeError("仮想環境のPythonを作成できませんでした。")
    return python_path

def get_settings_path(filename):
    if not os.path.exists(SETTINGS_FOLDER):
        try:
            os.makedirs(SETTINGS_FOLDER, exist_ok=True)
        except Exception:
            pass
    return os.path.join(SETTINGS_FOLDER, filename)

def load_settings():
    global current_theme, current_font_size, test_timeout_seconds, VIRTUALENV_PATH
    path = get_settings_path(THEME_SETTINGS_FILE)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                current_theme = data.get('theme', 'dark')
                current_font_size = data.get('font_size', 11)
                saved_timeout = int(data.get('test_timeout_seconds', 20))
                if saved_timeout == 5:
                    saved_timeout = 20
                test_timeout_seconds = min(max(saved_timeout, 1), 3600)
                VIRTUALENV_PATH = os.path.abspath(os.path.expanduser(
                    data.get('virtualenv_path') or VIRTUALENV_PATH
                ))
        except Exception:
            pass

def save_settings():
    path = get_settings_path(THEME_SETTINGS_FILE)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'theme': current_theme,
                'font_size': current_font_size,
                'test_timeout_seconds': test_timeout_seconds,
                'virtualenv_path': VIRTUALENV_PATH
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def update_text_modified_state(event=None):
    global text_modified, last_saved_content
    current_content = text.get("1.0", tk.END)
    text_modified = current_content.rstrip('\n') != last_saved_content.rstrip('\n')

def safe_exit():
    global text_modified
    if text_modified:
        res = messagebox.askyesnocancel("確認", "変更が保存されていません。保存しますか？")
        if res is None:
            return
        elif res:
            if not quick_save():
                return
    root.quit()

def quick_save():
    global last_saved_content, text_modified
    content = text.get("1.0", tk.END).strip()
    if hasattr(quick_save, 'current_file_path') and quick_save.current_file_path:
        try:
            with open(quick_save.current_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            last_saved_content = content + "\n"
            text_modified = False
            update_status_bar()
            messagebox.showinfo("保存完了", f"ファイルを上書き保存しました:\n{os.path.basename(quick_save.current_file_path)}")
            return True
        except Exception as e:
            messagebox.showerror("エラー", f"保存失敗: {e}")
            return False
    else:
        return save_as_file()

def save_as_file():
    global last_saved_content, text_modified
    content = text.get("1.0", tk.END).strip()
    selected_filetype = tk.StringVar(root)
    path = filedialog.asksaveasfilename(
        filetypes=[
            ("Python ファイル (*.py)", "*.py"),
            ("Python ウィンドウなし (*.pyw)", "*.pyw"),
            ("All Files", "*.*")
        ],
        typevariable=selected_filetype
    )
    if path:
        if not os.path.splitext(path)[1]:
            extension = ".pyw" if ".pyw" in selected_filetype.get() else ".py"
            path += extension
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            quick_save.current_file_path = path
            last_saved_content = content + "\n"
            text_modified = False
            update_status_bar()
            messagebox.showinfo("保存完了", f"ファイルを保存しました:\n{os.path.basename(path)}")
            return True
        except Exception as e:
            messagebox.showerror("エラー", f"保存失敗: {e}")
    return False

def open_file():
    global last_saved_content, text_modified
    path = filedialog.askopenfilename(
        filetypes=[("Python Files", "*.py;*.pyw"), ("All Files", "*.*")]
    )
    if path:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            text.delete('1.0', tk.END)
            text.insert('1.0', content)
            apply_syntax_highlighting()
            quick_save.current_file_path = path
            last_saved_content = text.get("1.0", tk.END)
            text_modified = False
            update_status_bar()
            update_line_numbers()
        except Exception as e:
            messagebox.showerror("エラー", f"読み込み失敗: {e}")

def new_file():
    global text_modified, last_saved_content
    if text_modified and not messagebox.askyesno("確認", "現在の内容を破棄して新規作成しますか？"):
        return
    text.delete("1.0", tk.END)
    apply_syntax_highlighting()
    last_saved_content = ""
    text_modified = False
    quick_save.current_file_path = None
    update_line_numbers()
    update_status_bar()

PROJECT_EXAMPLES = [
    {
        "category": "練習用ミニアプリ", "name": "電卓", "kind": "code",
        "description": "2つの数と計算方法を選んで結果を表示する、シンプルなGUI電卓です。",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("かんたん電卓")
root.geometry("320x220")
first = tk.Entry(root)
first.pack(padx=12, pady=(16, 6), fill="x")
operation = tk.StringVar(value="+")
tk.OptionMenu(root, operation, "+", "-", "*", "/").pack()
second = tk.Entry(root)
second.pack(padx=12, pady=6, fill="x")
result = tk.Label(root, text="答え: ")
result.pack(pady=8)

def calculate():
    try:
        left, right = float(first.get()), float(second.get())
        op = operation.get()
        if op == "+": answer = left + right
        elif op == "-": answer = left - right
        elif op == "*": answer = left * right
        elif right == 0: raise ZeroDivisionError
        else: answer = left / right
        result.config(text=f"答え: {answer:g}")
    except ValueError:
        messagebox.showerror("入力エラー", "2つの欄に数字を入力してください。")
    except ZeroDivisionError:
        messagebox.showerror("計算エラー", "0で割ることはできません。")

tk.Button(root, text="計算", command=calculate).pack(pady=4)
root.mainloop()
'''
    },
    {
        "category": "練習用ミニアプリ", "name": "じゃんけんゲーム", "kind": "code",
        "description": "ボタンを押してコンピューターと対戦します。勝敗数も表示します。",
        "code": '''import random
import tkinter as tk

root = tk.Tk()
root.title("じゃんけん")
root.geometry("340x220")
score = {"勝ち": 0, "負け": 0, "あいこ": 0}
result = tk.Label(root, text="手を選んでください", font=("Meiryo UI", 14))
result.pack(pady=20)
score_label = tk.Label(root, text="勝ち 0  負け 0  あいこ 0")
score_label.pack(pady=8)

def play(player):
    computer = random.choice(["グー", "チョキ", "パー"])
    if player == computer:
        outcome = "あいこ"
    elif (player, computer) in [("グー", "チョキ"), ("チョキ", "パー"), ("パー", "グー")]:
        outcome = "勝ち"
    else:
        outcome = "負け"
    score[outcome] += 1
    result.config(text=f"あなた: {player} / 相手: {computer}  → {outcome}")
    score_label.config(text=f"勝ち {score['勝ち']}  負け {score['負け']}  あいこ {score['あいこ']}")

for hand in ("グー", "チョキ", "パー"):
    tk.Button(root, text=hand, command=lambda value=hand: play(value)).pack(side="left", expand=True, padx=8)
root.mainloop()
'''
    },
    {
        "category": "練習用ミニアプリ", "name": "数当てゲーム", "kind": "code",
        "description": "1から100の数字を推理します。入力欄に数字を入れて判定します。",
        "code": '''import random
import tkinter as tk

root = tk.Tk()
root.title("数当てゲーム")
root.geometry("340x220")
answer = random.randint(1, 100)
tries = 0
message = tk.Label(root, text="1から100の数字を当ててください")
message.pack(pady=24)
guess = tk.Entry(root, justify="center")
guess.pack(pady=6)

def check_guess():
    global tries
    try:
        number = int(guess.get())
        if not 1 <= number <= 100:
            raise ValueError
    except ValueError:
        message.config(text="1から100までの整数を入力してください")
        return
    tries += 1
    if number == answer:
        message.config(text=f"正解！ {tries}回で当たりました")
    elif number < answer:
        message.config(text="もっと大きい数字です")
    else:
        message.config(text="もっと小さい数字です")

tk.Button(root, text="判定", command=check_guess).pack(pady=8)
root.mainloop()
'''
    },
    {
        "category": "練習用ミニアプリ", "name": "タイマー", "kind": "code",
        "description": "秒数を指定してカウントダウンするタイマーです。",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("タイマー")
root.geometry("300x190")
seconds_left = 0
running = False
display = tk.Label(root, text="00:00", font=("Meiryo UI", 32))
display.pack(pady=12)
seconds_input = tk.Entry(root, justify="center")
seconds_input.insert(0, "60")
seconds_input.pack()

def tick():
    global seconds_left, running
    if not running:
        return
    minutes, seconds = divmod(seconds_left, 60)
    display.config(text=f"{minutes:02}:{seconds:02}")
    if seconds_left <= 0:
        running = False
        messagebox.showinfo("タイマー", "時間です！")
        return
    seconds_left -= 1
    root.after(1000, tick)

def start():
    global seconds_left, running
    try:
        seconds_left = int(seconds_input.get())
        if seconds_left <= 0: raise ValueError
    except ValueError:
        messagebox.showerror("入力エラー", "1以上の秒数を入力してください。")
        return
    running = True
    tick()

tk.Button(root, text="スタート", command=start).pack(pady=10)
root.mainloop()
'''
    },
    {
        "category": "日常で使える実用品", "name": "ToDoリスト", "kind": "code",
        "description": "タスクの追加と完了した項目の削除ができます。",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("ToDoリスト")
root.geometry("420x360")
task_input = tk.Entry(root)
task_input.pack(fill="x", padx=12, pady=12)
tasks = tk.Listbox(root, font=("Meiryo UI", 11))
tasks.pack(fill="both", expand=True, padx=12)

def add_task():
    task = task_input.get().strip()
    if task:
        tasks.insert(tk.END, "□ " + task)
        task_input.delete(0, tk.END)

def remove_task():
    selected = tasks.curselection()
    if selected:
        tasks.delete(selected[0])
    else:
        messagebox.showinfo("確認", "削除するタスクを選んでください。")

buttons = tk.Frame(root)
buttons.pack(pady=10)
tk.Button(buttons, text="追加", command=add_task).pack(side="left", padx=5)
tk.Button(buttons, text="選択した項目を削除", command=remove_task).pack(side="left", padx=5)
root.mainloop()
'''
    },
    {
        "category": "日常で使える実用品", "name": "メモ帳", "kind": "code",
        "description": "文章を編集し、テキストファイルとして開いたり保存したりできます。",
        "code": '''import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("かんたんメモ帳")
root.geometry("640x440")
editor = tk.Text(root, wrap="word", undo=True)
editor.pack(fill="both", expand=True, padx=8, pady=8)

def open_note():
    path = filedialog.askopenfilename(filetypes=[("テキスト", "*.txt"), ("すべて", "*.*")])
    if path:
        try:
            with open(path, encoding="utf-8") as file:
                editor.delete("1.0", tk.END)
                editor.insert("1.0", file.read())
        except OSError as error:
            messagebox.showerror("読み込みエラー", str(error))

def save_note():
    path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("テキスト", "*.txt")])
    if path:
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(editor.get("1.0", "end-1c"))
            messagebox.showinfo("保存", "メモを保存しました。")
        except OSError as error:
            messagebox.showerror("保存エラー", str(error))

toolbar = tk.Frame(root)
toolbar.pack(fill="x")
tk.Button(toolbar, text="開く", command=open_note).pack(side="left", padx=6, pady=4)
tk.Button(toolbar, text="名前を付けて保存", command=save_note).pack(side="left", padx=6, pady=4)
root.mainloop()
'''
    },
    {
        "category": "日常で使える実用品", "name": "パスワード生成器", "kind": "code",
        "description": "指定した長さのランダムなパスワードを作成します。",
        "code": '''import secrets
import string
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("パスワード生成器")
root.geometry("380x190")
tk.Label(root, text="文字数（8〜128）").pack(pady=(18, 4))
length = tk.Entry(root, justify="center")
length.insert(0, "16")
length.pack()
result = tk.Entry(root, justify="center", width=38)
result.pack(padx=12, pady=12)

def generate():
    try:
        size = int(length.get())
        if not 8 <= size <= 128: raise ValueError
    except ValueError:
        messagebox.showerror("入力エラー", "8から128までの整数を入力してください。")
        return
    alphabet = string.ascii_letters + string.digits + "!@#$%&*+-_"
    result.delete(0, tk.END)
    result.insert(0, "".join(secrets.choice(alphabet) for _ in range(size)))

tk.Button(root, text="生成", command=generate).pack()
root.mainloop()
'''
    },
    {
        "category": "日常で使える実用品", "name": "ファイル名まとめて変更", "kind": "code",
        "description": "選んだフォルダー内のファイル名に、接頭語を付けてまとめて変更します。変更前に確認します。",
        "code": '''import os
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("ファイル名まとめて変更")
root.geometry("430x210")
folder = tk.StringVar()
prefix = tk.StringVar(value="整理_")

def choose_folder():
    selected = filedialog.askdirectory()
    if selected:
        folder.set(selected)

tk.Label(root, text="対象フォルダー").pack(anchor="w", padx=12, pady=(12, 2))
tk.Entry(root, textvariable=folder).pack(fill="x", padx=12)
tk.Button(root, text="フォルダーを選ぶ", command=choose_folder).pack(anchor="e", padx=12, pady=4)
tk.Label(root, text="ファイル名の先頭に付ける文字").pack(anchor="w", padx=12, pady=(6, 2))
tk.Entry(root, textvariable=prefix).pack(fill="x", padx=12)

def rename_files():
    path, start = folder.get(), prefix.get()
    if not path or not start:
        messagebox.showerror("入力エラー", "フォルダーと接頭語を指定してください。")
        return
    files = [name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name)) and not name.startswith(start)]
    if not files:
        messagebox.showinfo("確認", "変更するファイルがありません。")
        return
    if not messagebox.askyesno("変更確認", f"{len(files)}個のファイル名を変更します。続けますか？"):
        return
    renamed = 0
    for name in files:
        old = os.path.join(path, name)
        new = os.path.join(path, start + name)
        if not os.path.exists(new):
            os.rename(old, new)
            renamed += 1
    messagebox.showinfo("完了", f"{renamed}個のファイル名を変更しました。")

tk.Button(root, text="まとめて変更", command=rename_files).pack(pady=10)
root.mainloop()
'''
    },
    {
        "category": "日常で使える実用品", "name": "CSVの整理・集計", "kind": "code",
        "description": "CSVファイルを開き、各列の件数と数値の合計を表示します。",
        "code": '''import csv
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("CSVかんたん集計")
root.geometry("900x620")
root.minsize(720, 500)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

toolbar = tk.Frame(root, padx=16, pady=14)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Label(toolbar, text="CSVファイルを集計", font=("Meiryo UI", 15, "bold")).pack(side="left")
output_frame = tk.Frame(root, padx=16, pady=12)
output_frame.grid(row=1, column=0, sticky="nsew")
output_frame.grid_columnconfigure(0, weight=1)
output_frame.grid_rowconfigure(0, weight=1)
output = tk.Text(output_frame, wrap="none", font=("Meiryo UI", 11), padx=10, pady=8)
output.grid(row=0, column=0, sticky="nsew")
scrollbar = tk.Scrollbar(output_frame, orient="vertical", command=output.yview)
scrollbar.grid(row=0, column=1, sticky="ns")
output.config(yscrollcommand=scrollbar.set)
status = tk.Label(root, text="CSVファイルを選択すると、列ごとの件数と数値合計を表示します。",
              anchor="w", font=("Meiryo UI", 10), padx=16)
status.grid(row=2, column=0, sticky="ew", pady=(0, 6))

def summarize():
    path = filedialog.askopenfilename(filetypes=[("CSVファイル", "*.csv"), ("すべて", "*.*")])
    if not path:
        return
    try:
        with open(path, newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
        if not rows:
            messagebox.showinfo("確認", "CSVにデータ行がありません。")
            return
        lines = [f"データ行数: {len(rows)}"]
        for column in rows[0]:
            values = [row.get(column, "").strip() for row in rows]
            numbers = []
            for value in values:
                try:
                    numbers.append(float(value.replace(",", "")))
                except ValueError:
                    pass
            lines.append(f"{column}: 入力 {sum(bool(v) for v in values)}件")
            if numbers:
                lines.append(f"  数値合計: {sum(numbers):g}")
        output.delete("1.0", tk.END)
        output.insert("1.0", "\\n".join(lines))
        status.config(text=f"集計完了: {len(rows)}行")
    except (OSError, csv.Error) as error:
        messagebox.showerror("読み込みエラー", str(error))

tk.Button(toolbar, text="CSVを選択して集計", command=summarize,
          font=("Meiryo UI", 12, "bold"), padx=28, pady=12).pack(side="right")
root.mainloop()
'''
    },
    {
        "category": "少し背伸びした作品", "name": "Webページからタイトル取得", "kind": "code",
        "description": "URLを入力すると、標準ライブラリでWebページのタイトルを取得します。",
        "code": '''from html.parser import HTMLParser
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data

root = tk.Tk()
root.title("Webページのタイトル取得")
root.geometry("480x180")
url = tk.Entry(root)
url.insert(0, "https://example.com")
url.pack(fill="x", padx=12, pady=16)
result = tk.Label(root, text="取得結果がここに表示されます", wraplength=440)
result.pack(pady=8)

def fetch_title():
    address = url.get().strip()
    if not address.startswith(("https://", "http://")):
        messagebox.showerror("URLエラー", "http:// または https:// から始まるURLを入力してください。")
        return
    try:
        request = Request(address, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as response:
            parser = TitleParser()
            parser.feed(response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace"))
        result.config(text=parser.title.strip() or "タイトルが見つかりませんでした。")
    except Exception as error:
        messagebox.showerror("取得エラー", str(error))

tk.Button(root, text="タイトルを取得", command=fetch_title).pack()
root.mainloop()
'''
    },
    {
        "category": "少し背伸びした作品", "name": "天気を取得するアプリ", "kind": "code",
        "description": "都市名から天気を取得します。Open-Meteoの無料APIを使うため、APIキーは不要です。",
        "code": '''import json
from urllib.parse import urlencode
from urllib.request import urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("かんたん天気")
root.geometry("360x210")
city = tk.Entry(root, justify="center")
city.insert(0, "Tokyo")
city.pack(fill="x", padx=18, pady=(20, 8))
result = tk.Label(root, text="都市名を入力してください", font=("Meiryo UI", 12), wraplength=320)
result.pack(pady=12)

def get_weather():
    name = city.get().strip()
    if not name:
        messagebox.showerror("入力エラー", "都市名を入力してください。")
        return
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({"name": name, "count": 1, "language": "ja", "format": "json"})
        with urlopen(geo_url, timeout=10) as response:
            places = json.load(response).get("results", [])
        if not places:
            result.config(text="都市が見つかりませんでした")
            return
        place = places[0]
        query = urlencode({"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,relative_humidity_2m,weather_code"})
        with urlopen("https://api.open-meteo.com/v1/forecast?" + query, timeout=10) as response:
            current = json.load(response)["current"]
        result.config(text=f"{place['name']}\\n気温 {current['temperature_2m']}℃ / 湿度 {current['relative_humidity_2m']}%\\n天気コード {current['weather_code']}")
    except Exception as error:
        messagebox.showerror("取得エラー", str(error))

tk.Button(root, text="天気を取得", command=get_weather).pack()
root.mainloop()
'''
    },
    {
        "category": "少し背伸びした作品", "name": "Discord Webhook送信", "kind": "code",
        "description": "Webhook URLとメッセージを入力してDiscordへ送信します。追加ライブラリやBotトークンは不要です。Webhook URLは秘密情報として扱ってください。",
        "code": '''import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Discord Webhook送信")
root.geometry("640x440")
root.minsize(560, 390)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(3, weight=1)

tk.Label(root, text="Discord Webhook URL", font=("Meiryo UI", 11, "bold")).grid(
    row=0, column=0, sticky="w", padx=18, pady=(18, 4)
)
webhook_input = tk.Entry(root, font=("Consolas", 10))
webhook_input.grid(row=1, column=0, sticky="ew", padx=18)
tk.Label(root, text="送信するメッセージ", font=("Meiryo UI", 11, "bold")).grid(
    row=2, column=0, sticky="w", padx=18, pady=(14, 4)
)
message_input = tk.Text(root, height=7, wrap="word", font=("Meiryo UI", 11))
message_input.grid(row=3, column=0, sticky="nsew", padx=18)
status = tk.Label(root, text="Webhook URLとメッセージを入力してください。", anchor="w")
status.grid(row=4, column=0, sticky="ew", padx=18, pady=8)

def send_message():
    webhook = webhook_input.get().strip()
    content = message_input.get("1.0", "end-1c").strip()
    parsed = urlparse(webhook)
    if parsed.scheme != "https" or parsed.netloc not in ("discord.com", "discordapp.com") or not parsed.path.startswith("/api/webhooks/"):
        messagebox.showerror("URLエラー", "DiscordのWebhook URLを入力してください。")
        return
    if not content:
        messagebox.showerror("入力エラー", "送信するメッセージを入力してください。")
        return
    if len(content) > 2000:
        messagebox.showerror("入力エラー", "メッセージは2000文字以内にしてください。")
        return
    request = Request(webhook, data=json.dumps({"content": content}).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Discordから予期しない応答がありました: {response.status}")
        status.config(text="送信しました。")
    except HTTPError as error:
        messagebox.showerror("Discordエラー", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}")
    except (URLError, TimeoutError, RuntimeError) as error:
        messagebox.showerror("送信エラー", str(error))

tk.Button(root, text="Discordへ送信", command=send_message,
          font=("Meiryo UI", 12, "bold"), padx=24, pady=10).grid(
              row=5, column=0, sticky="e", padx=18, pady=(0, 16)
          )
root.mainloop()
'''
    },
    {
        "category": "少し背伸びした作品", "name": "LINE通知（公式Messaging API）", "kind": "code",
        "description": "LINE公式APIでメッセージを送信するGUIです。チャネルアクセストークンと送信先IDが必要です。Webhook URLだけでは公式LINEへ送信できません。",
        "code": '''import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("LINE メッセージ送信")
root.geometry("620x520")
root.minsize(540, 470)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(7, weight=1)

tk.Label(root, text="LINE Messaging APIでメッセージ送信", font=("Meiryo UI", 14, "bold")).grid(
    row=0, column=0, sticky="w", padx=18, pady=(18, 4)
)
tk.Label(root, text="Webhook URLではなく、チャネルアクセストークンと送信先IDを使います。",
         wraplength=570, justify="left").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 10))
tk.Label(root, text="チャネルアクセストークン", font=("Meiryo UI", 10, "bold")).grid(
    row=2, column=0, sticky="w", padx=18, pady=(4, 3)
)
token_input = tk.Entry(root, show="*", font=("Consolas", 10))
token_input.grid(row=3, column=0, sticky="ew", padx=18)
tk.Label(root, text="送信先のユーザーIDまたはグループID", font=("Meiryo UI", 10, "bold")).grid(
    row=4, column=0, sticky="w", padx=18, pady=(10, 3)
)
recipient_input = tk.Entry(root, font=("Consolas", 10))
recipient_input.grid(row=5, column=0, sticky="ew", padx=18)
tk.Label(root, text="メッセージ", font=("Meiryo UI", 10, "bold")).grid(
    row=6, column=0, sticky="w", padx=18, pady=(8, 3)
)
message_input = tk.Text(root, height=5, wrap="word", font=("Meiryo UI", 11))
message_input.grid(row=7, column=0, sticky="nsew", padx=18)
status = tk.Label(root, text="入力したトークンは保存しません。", anchor="w")
status.grid(row=8, column=0, sticky="ew", padx=18, pady=8)

def send_message():
    token = token_input.get().strip()
    recipient = recipient_input.get().strip()
    content = message_input.get("1.0", "end-1c").strip()
    if not token or not recipient or not content:
        messagebox.showerror("入力エラー", "トークン、送信先ID、メッセージをすべて入力してください。")
        return
    payload = {"to": recipient, "messages": [{"type": "text", "text": content}]}
    request = Request(
        "https://api.line.me/v2/bot/message/push",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"LINEから予期しない応答がありました: {response.status}")
        status.config(text="LINEへ送信しました。")
    except HTTPError as error:
        messagebox.showerror("LINE APIエラー", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}")
    except (URLError, TimeoutError, RuntimeError) as error:
        messagebox.showerror("送信エラー", str(error))

tk.Button(root, text="LINEへ送信", command=send_message,
          font=("Meiryo UI", 12, "bold"), padx=24, pady=10).grid(
              row=9, column=0, sticky="e", padx=18, pady=(0, 16)
          )
root.mainloop()
'''
    },
    {
        "category": "少し背伸びした作品", "name": "GUIフォーム（デザイナー）", "kind": "designer",
        "description": "ボタン・ラベル・入力欄を配置してGUIを作ります。フォーム作成タブへ移動します。",
        "code": ""
    },
]

def load_project_code(code):
    global last_saved_content, text_modified
    if text_modified:
        answer = messagebox.askyesnocancel("未保存の変更", "現在のコードを保存してから作品を読み込みますか？")
        if answer is None:
            return False
        if answer and not quick_save():
            return False
    text.delete("1.0", tk.END)
    text.insert("1.0", code.rstrip() + "\n")
    quick_save.current_file_path = None
    last_saved_content = ""
    text_modified = True
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    return True

def open_hotkey_builder():
    win = tk.Toplevel(root)
    win.title("ホットキー・ボタン作成")
    win.geometry("980x680")
    win.minsize(820, 580)
    win.transient(root)
    win.update_idletasks()
    center_x = root.winfo_rootx() + (root.winfo_width() - win.winfo_width()) // 2
    center_y = root.winfo_rooty() + (root.winfo_height() - win.winfo_height()) // 2
    win.geometry(f"+{max(0, center_x)}+{max(0, center_y)}")

    builder_config_path = get_settings_path(HOTKEY_BUILDER_SETTINGS_FILE)
    try:
        with open(builder_config_path, "r", encoding="utf-8") as config_file:
            builder_config = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        builder_config = {}
    if not isinstance(builder_config, dict):
        builder_config = {}
    saved_actions = builder_config.get("actions", [])
    actions = []
    if isinstance(saved_actions, list):
        for item in saved_actions:
            if not isinstance(item, dict):
                continue
            try:
                wait_seconds = float(item.get("wait", 0))
            except (TypeError, ValueError):
                continue
            if not 0 <= wait_seconds <= 3600:
                continue
            actions.append({
                "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                "kind": str(item.get("kind", "URLを開く")), "target": str(item.get("target", "")),
                "wait": wait_seconds, "followup": str(item.get("followup", ""))
            })
    content = tk.Frame(win, padx=14, pady=12)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="ホットキーとボタンの動作を登録", font=("Meiryo UI", 14, "bold")).pack(anchor="w")

    settings = tk.Frame(content)
    settings.pack(fill="x", pady=(10, 8))
    tk.Label(settings, text="ウィンドウ名").pack(side="left")
    title_value = tk.StringVar(value=str(builder_config.get("title", "かんたんホットキー")))
    ttk.Entry(settings, textvariable=title_value, width=24).pack(side="left", padx=(6, 16))
    tk.Label(settings, text="幅").pack(side="left")
    width_value = tk.StringVar(value=str(builder_config.get("width", 240)))
    ttk.Entry(settings, textvariable=width_value, width=7).pack(side="left", padx=6)
    tk.Label(settings, text="高さ").pack(side="left")
    height_value = tk.StringVar(value=str(builder_config.get("height", 420)))
    ttk.Entry(settings, textvariable=height_value, width=7).pack(side="left", padx=6)
    tk.Label(settings, text="アイコン操作").pack(side="left", padx=(10, 4))
    tray_click_value = tk.StringVar(value=builder_config.get("tray_click_exit", "double"))
    ttk.Combobox(settings, textvariable=tray_click_value,
                 values=("シングルクリックで終了", "ダブルクリックで終了"),
                 state="readonly", width=22).pack(side="left")
    if tray_click_value.get() not in ("シングルクリックで終了", "ダブルクリックで終了"):
        tray_click_value.set("ダブルクリックで終了")

    icon_settings = tk.Frame(content)
    icon_settings.pack(fill="x", pady=(0, 8))
    tk.Label(icon_settings, text="トレイアイコン").pack(side="left")
    tray_icon_style_value = tk.StringVar(value=builder_config.get("tray_icon_style", "オリジナル（H）"))
    icon_style_options = ("オリジナル（H）", "情報", "警告", "エラー", "ICOファイル")
    if tray_icon_style_value.get() not in icon_style_options:
        tray_icon_style_value.set(icon_style_options[0])
    ttk.Combobox(icon_settings, textvariable=tray_icon_style_value,
                 values=icon_style_options, state="readonly", width=17).pack(side="left", padx=6)
    tray_icon_path_value = tk.StringVar(value=str(builder_config.get("tray_icon_path", "")))
    ttk.Entry(icon_settings, textvariable=tray_icon_path_value, state="readonly").pack(
        side="left", fill="x", expand=True, padx=6
    )

    def choose_tray_icon():
        selected_path = filedialog.askopenfilename(
            parent=win, title="トレイアイコンを選択", filetypes=[("アイコンファイル", "*.ico")]
        )
        if selected_path:
            tray_icon_path_value.set(selected_path)
            tray_icon_style_value.set("ICOファイル")

    ttk.Button(icon_settings, text="ICOを選択...", command=choose_tray_icon).pack(side="left")

    body = tk.Frame(content)
    body.pack(fill="both", expand=True)
    columns = ("shortcut", "button", "kind", "target")
    table = ttk.Treeview(body, columns=columns, show="headings", height=9, selectmode="browse")
    for column, label, width in (("shortcut", "ホットキー", 125), ("button", "ボタン名", 145), ("kind", "動作", 145), ("target", "内容", 400)):
        table.heading(column, text=label)
        table.column(column, width=width, minwidth=70, stretch=column == "target")
    table.pack(side="left", fill="both", expand=True)
    table_scroll = ttk.Scrollbar(body, orient="vertical", command=table.yview)
    table_scroll.pack(side="right", fill="y")
    table.configure(yscrollcommand=table_scroll.set)

    form = tk.LabelFrame(content, text="動作の追加・編集", padx=10, pady=8)
    form.pack(fill="x", pady=(10, 4))
    shortcut_value = tk.StringVar()
    button_value = tk.StringVar()
    kind_value = tk.StringVar(value="URLを開く")
    target_value = tk.StringVar()
    wait_value = tk.StringVar(value="0")
    followup_value = tk.StringVar()

    tk.Label(form, text="キー (例: Alt+a)").grid(row=0, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="ボタン名 (任意)").grid(row=0, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="動作").grid(row=1, column=0, sticky="w", padx=4, pady=3)
    kind_menu = ttk.Combobox(form, textvariable=kind_value, values=("URLを開く", "アプリ/ファイル起動", "キー送信", "コマンド実行"), state="readonly", width=18)
    kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="URL / パス / キー / コマンド").grid(row=1, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="実行後に待つ秒数").grid(row=2, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
    tk.Label(form, text="待機後に送るキー (任意)").grid(row=2, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=followup_value).grid(row=2, column=3, sticky="ew", padx=4, pady=3)
    form.columnconfigure(1, weight=1)
    form.columnconfigure(3, weight=2)
    tk.Label(content, text="キー送信の例: Ctrl+w、Alt+F4、Left。キー欄を空にするとボタンだけで実行します。", anchor="w").pack(fill="x", pady=(2, 4))

    def refresh_table(select_index=None):
        table.delete(*table.get_children())
        for index, item in enumerate(actions):
            table.insert("", "end", iid=str(index), values=(item["shortcut"], item["button"], item["kind"], item["target"]))
        if select_index is not None and 0 <= select_index < len(actions):
            table.selection_set(str(select_index))
            table.focus(str(select_index))

    def configuration_data():
        return {"title": title_value.get(), "width": width_value.get(),
                "height": height_value.get(), "tray_click_exit": tray_click_value.get(),
                "tray_icon_style": tray_icon_style_value.get(),
                "tray_icon_path": tray_icon_path_value.get(),
                "actions": actions}

    def persist_configuration():
        try:
            with open(builder_config_path, "w", encoding="utf-8") as config_file:
                json.dump(configuration_data(), config_file, ensure_ascii=False, indent=2)
        except OSError as error:
            messagebox.showerror("設定保存エラー", str(error), parent=win)

    def save_configuration_as():
        path = filedialog.asksaveasfilename(
            parent=win, title="ホットキー設定を保存", defaultextension=".json",
            filetypes=[("JSON設定", "*.json"), ("すべてのファイル", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as config_file:
                json.dump(configuration_data(), config_file, ensure_ascii=False, indent=2)
            persist_configuration()
            messagebox.showinfo("設定保存", "設定を保存しました。", parent=win)
        except OSError as error:
            messagebox.showerror("設定保存エラー", str(error), parent=win)

    def load_configuration():
        path = filedialog.askopenfilename(
            parent=win, title="ホットキー設定を読み込み", filetypes=[("JSON設定", "*.json"), ("すべてのファイル", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as config_file:
                loaded = json.load(config_file)
            if not isinstance(loaded, dict) or not isinstance(loaded.get("actions"), list):
                raise ValueError("設定ファイルの形式が正しくありません。")
            loaded_actions = loaded["actions"]
            normalized_actions = []
            for item in loaded_actions:
                if not isinstance(item, dict):
                    raise ValueError("動作一覧の形式が正しくありません。")
                wait_seconds = float(item.get("wait", 0))
                if not 0 <= wait_seconds <= 3600:
                    raise ValueError("待ち時間は0から3600秒の範囲で指定してください。")
                normalized_actions.append({
                    "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                    "kind": str(item.get("kind", "URLを開く")), "target": str(item.get("target", "")),
                    "wait": wait_seconds, "followup": str(item.get("followup", ""))
                })
            actions[:] = normalized_actions
            title_value.set(str(loaded.get("title", "かんたんホットキー")))
            width_value.set(str(loaded.get("width", 240)))
            height_value.set(str(loaded.get("height", 420)))
            tray_click_value.set(loaded.get("tray_click_exit", "ダブルクリックで終了"))
            if tray_click_value.get() not in ("シングルクリックで終了", "ダブルクリックで終了"):
                tray_click_value.set("ダブルクリックで終了")
            tray_icon_style_value.set(loaded.get("tray_icon_style", "オリジナル（H）"))
            if tray_icon_style_value.get() not in icon_style_options:
                tray_icon_style_value.set(icon_style_options[0])
            tray_icon_path_value.set(str(loaded.get("tray_icon_path", "")))
            refresh_table()
            clear_form()
            persist_configuration()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showerror("設定読み込みエラー", str(error), parent=win)

    def clear_form():
        table.selection_remove(table.selection())
        shortcut_value.set("")
        button_value.set("")
        kind_value.set("URLを開く")
        target_value.set("")
        wait_value.set("0")
        followup_value.set("")

    def show_selected(event=None):
        selection = table.selection()
        if not selection:
            return
        item = actions[int(selection[0])]
        shortcut_value.set(item["shortcut"])
        button_value.set(item["button"])
        kind_value.set(item["kind"])
        target_value.set(item["target"])
        wait_value.set(str(item["wait"]))
        followup_value.set(item["followup"])

    def save_action():
        shortcut = shortcut_value.get().strip()
        button = button_value.get().strip()
        kind = kind_value.get()
        target = target_value.get().strip()
        if not shortcut and not button:
            messagebox.showerror("入力エラー", "ホットキーまたはボタン名を入力してください。", parent=win)
            return
        if not target:
            messagebox.showerror("入力エラー", "動作の内容を入力してください。", parent=win)
            return
        try:
            wait = float(wait_value.get())
            if not 0 <= wait <= 3600:
                raise ValueError
        except ValueError:
            messagebox.showerror("入力エラー", "待ち時間は0から3600秒の数値で入力してください。", parent=win)
            return
        item = {"shortcut": shortcut, "button": button, "kind": kind, "target": target,
                "wait": wait, "followup": followup_value.get().strip()}
        selection = table.selection()
        if selection:
            index = int(selection[0])
            actions[index] = item
        else:
            index = len(actions)
            actions.append(item)
        refresh_table(index)
        persist_configuration()

    def delete_action():
        selection = table.selection()
        if selection:
            del actions[int(selection[0])]
            refresh_table()
            clear_form()
            persist_configuration()

    def close_builder():
        persist_configuration()
        win.destroy()

    def make_code():
        if not actions:
            messagebox.showerror("入力エラー", "ホットキーまたはボタンを1つ以上登録してください。", parent=win)
            return
        try:
            window_width = int(width_value.get())
            window_height = int(height_value.get())
            if not 120 <= window_width <= 3000 or not 120 <= window_height <= 3000:
                raise ValueError
        except ValueError:
            messagebox.showerror("入力エラー", "幅と高さは120から3000の整数で入力してください。", parent=win)
            return
        seen_shortcuts = set()
        for item in actions:
            key = item["shortcut"].lower().replace(" ", "")
            if key and key in seen_shortcuts:
                messagebox.showerror("入力エラー", f"ホットキーが重複しています: {item['shortcut']}", parent=win)
                return
            seen_shortcuts.add(key)
        if tray_icon_style_value.get() == "ICOファイル" and not os.path.isfile(tray_icon_path_value.get()):
            messagebox.showerror("アイコンエラー", "選択したICOファイルが見つかりません。", parent=win)
            return

        action_data = [{key: item[key] for key in ("shortcut", "button", "kind", "target", "wait", "followup")} for item in actions]
        persist_configuration()
        source = r'''import ctypes
from ctypes import wintypes
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser

WINDOW_TITLE = __TITLE__
WINDOW_WIDTH = __WIDTH__
WINDOW_HEIGHT = __HEIGHT__
TRAY_EXIT_ON = __TRAY_EXIT_ON__
TRAY_ICON_STYLE = __TRAY_ICON_STYLE__
TRAY_ICON_PATH = __TRAY_ICON_PATH__
ACTIONS = __ACTIONS__

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_GETICON = 0x007F
ICON_SMALL = 0
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
HOTKEY_MODIFIERS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
                    "shift": MOD_SHIFT, "win": MOD_WIN, "windows": MOD_WIN}
SPECIAL_KEYS = {"backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
                "esc": 0x1B, "escape": 0x1B, "space": 0x20, "left": 0x25,
                "up": 0x26, "right": 0x27, "down": 0x28, "delete": 0x2E,
                "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22}
for number in range(1, 13):
    SPECIAL_KEYS[f"f{number}"] = 0x70 + number - 1

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
hotkey_events = queue.Queue()
hotkey_thread_id = 0
tray_added = False
previous_window_proc = None
tray_click_after_id = None
closing = False

class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

class TimeoutOrVersion(ctypes.Union):
    _fields_ = [("uTimeout", wintypes.UINT), ("uVersion", wintypes.UINT)]

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("timeout_or_version", TimeoutOrVersion),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                            wintypes.WPARAM, wintypes.LPARAM)
set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
set_window_long.restype = ctypes.c_void_p
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.CallWindowProcW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

def get_key_code(name):
    name = name.strip().lower()
    if name in SPECIAL_KEYS:
        return SPECIAL_KEYS[name]
    if len(name) == 1:
        result = user32.VkKeyScanW(ord(name))
        if result != -1:
            return result & 0xFF
    raise ValueError(f"未対応のキーです: {name}")

def parse_hotkey(shortcut):
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    modifiers = 0
    key = None
    for part in parts:
        if part in HOTKEY_MODIFIERS:
            modifiers |= HOTKEY_MODIFIERS[part]
        else:
            if key is not None:
                raise ValueError(f"キーは1つだけ指定してください: {shortcut}")
            key = get_key_code(part)
    if key is None:
        raise ValueError(f"キーが指定されていません: {shortcut}")
    return modifiers | MOD_NOREPEAT, key

def send_keys(sequence):
    names = [part.strip().lower() for part in sequence.split("+") if part.strip()]
    modifier_codes = {"ctrl": 0x11, "control": 0x11, "alt": 0x12,
                      "shift": 0x10, "win": 0x5B, "windows": 0x5B}
    codes = [modifier_codes[name] if name in modifier_codes else get_key_code(name) for name in names]
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, 0x0002, 0)

def run_action(index):
    action = ACTIONS[index]
    try:
        kind, target = action["kind"], action["target"]
        if kind == "URLを開く":
            webbrowser.open(target, new=2)
        elif kind == "アプリ/ファイル起動":
            os.startfile(target)
        elif kind == "コマンド実行":
            subprocess.Popen(target, shell=True)
        elif kind == "キー送信":
            send_keys(target)
        if action["wait"]:
            time.sleep(action["wait"])
        if action["followup"]:
            send_keys(action["followup"])
    except Exception as error:
        hotkey_events.put(("error", f"{action['button'] or action['shortcut']}: {error}"))

def hotkey_loop():
    global hotkey_thread_id
    hotkey_thread_id = kernel32.GetCurrentThreadId()
    registered = []
    try:
        for index, action in enumerate(ACTIONS):
            if not action["shortcut"]:
                continue
            try:
                modifiers, key = parse_hotkey(action["shortcut"])
                if not user32.RegisterHotKey(None, index + 1, modifiers, key):
                    raise OSError("このキーは登録できませんでした。別のアプリで使用中かもしれません。")
                registered.append(index + 1)
            except Exception as error:
                hotkey_events.put(("error", f"{action['shortcut']}: {error}"))
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                hotkey_events.put(("run", message.wParam - 1))
    finally:
        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)

root = tk.Tk()
root.title(WINDOW_TITLE)
root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
tray_image = tk.PhotoImage(width=32, height=32)
tray_image.put("#1769aa", to=(0, 0, 32, 32))
tray_image.put("#ffffff", to=(6, 6, 10, 26))
tray_image.put("#ffffff", to=(22, 6, 26, 26))
tray_image.put("#ffffff", to=(10, 16, 22, 20))
tray_image.put("#f5c542", to=(13, 6, 19, 10))
root.iconphoto(True, tray_image)
for index, action in enumerate(ACTIONS):
    if action["button"]:
        tk.Button(root, text=action["button"], command=lambda i=index: threading.Thread(
            target=run_action, args=(i,), daemon=True).start()).pack(fill="x", padx=8, pady=4)

def process_events():
    while not hotkey_events.empty():
        kind, value = hotkey_events.get_nowait()
        if kind == "run":
            threading.Thread(target=run_action, args=(value,), daemon=True).start()
        else:
            messagebox.showerror("ホットキー", value, parent=root)
    root.after(50, process_events)

def restore_window():
    root.deiconify()
    root.state("normal")
    root.lift()
    root.focus_force()

def show_tray_menu():
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="ウィンドウを表示", command=restore_window)
    menu.add_separator()
    menu.add_command(label="終了", command=close_window)
    try:
        menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
    finally:
        menu.grab_release()

@WNDPROC
def tray_window_proc(hwnd, message, wparam, lparam):
    if message == WM_TRAYICON:
        event = lparam & 0xFFFF
        if event == WM_LBUTTONUP:
            if TRAY_EXIT_ON == "single":
                root.after(0, close_window)
            else:
                global tray_click_after_id
                if not closing:
                    tray_click_after_id = root.after(300, restore_window)
            return 0
        if event == WM_LBUTTONDBLCLK:
            if TRAY_EXIT_ON == "double":
                if tray_click_after_id is not None:
                    root.after_cancel(tray_click_after_id)
                    tray_click_after_id = None
                root.after(0, close_window)
            else:
                root.after(0, restore_window)
            return 0
        if event == WM_RBUTTONUP:
            root.after(0, show_tray_menu)
            return 0
    return user32.CallWindowProcW(previous_window_proc, hwnd, message, wparam, lparam)

def install_tray_icon():
    global previous_window_proc, tray_added
    root.update_idletasks()
    hwnd = wintypes.HWND(root.winfo_id())
    icon_handle = 0
    if TRAY_ICON_STYLE == "ICOファイル" and os.path.isfile(TRAY_ICON_PATH):
        user32.LoadImageW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.LoadImageW.restype = wintypes.HICON
        icon_handle = user32.LoadImageW(None, TRAY_ICON_PATH, 1, 0, 0, 0x0010)
    elif TRAY_ICON_STYLE in ("情報", "警告", "エラー"):
        user32.LoadIconW.restype = wintypes.HICON
        stock_icons = {"情報": 32516, "警告": 32515, "エラー": 32513}
        icon_handle = user32.LoadIconW(None, stock_icons[TRAY_ICON_STYLE])
    if not icon_handle:
        icon_handle = user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0)
    if not icon_handle:
        user32.LoadIconW.restype = wintypes.HICON
        icon_handle = user32.LoadIconW(None, 32512)
    icon_data = NOTIFYICONDATAW()
    icon_data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    icon_data.hWnd = hwnd
    icon_data.uID = 1
    icon_data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    icon_data.uCallbackMessage = WM_TRAYICON
    icon_data.hIcon = icon_handle
    icon_data.szTip = f"{WINDOW_TITLE} - 起動中"
    previous_window_proc = set_window_long(hwnd, -4, ctypes.cast(tray_window_proc, ctypes.c_void_p))
    tray_added = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(icon_data)))
    if tray_added:
        root.withdraw()
    else:
        root.deiconify()
        messagebox.showerror("タスクトレイ", "通知領域へアイコンを登録できませんでした。ウィンドウを表示します。", parent=root)

def close_window():
    global closing, tray_click_after_id
    if closing:
        return
    closing = True
    if tray_click_after_id is not None:
        try:
            root.after_cancel(tray_click_after_id)
        except tk.TclError:
            pass
        tray_click_after_id = None
    if tray_added:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(icon_data))
    if hotkey_thread_id:
        user32.PostThreadMessageW(hotkey_thread_id, WM_QUIT, 0, 0)
    root.destroy()

icon_data = NOTIFYICONDATAW()
icon_data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
icon_data.hWnd = wintypes.HWND(root.winfo_id())
icon_data.uID = 1
icon_data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
icon_data.uCallbackMessage = WM_TRAYICON
icon_data.hIcon = user32.SendMessageW(icon_data.hWnd, WM_GETICON, ICON_SMALL, 0)
icon_data.szTip = f"{WINDOW_TITLE} - 起動中"
root.protocol("WM_DELETE_WINDOW", close_window)
threading.Thread(target=hotkey_loop, daemon=True).start()
root.after(50, process_events)
root.withdraw()
root.after(100, install_tray_icon)
root.mainloop()
'''
        source = source.replace("__TITLE__", repr(title_value.get().strip() or "かんたんホットキー"))
        source = source.replace("__WIDTH__", str(window_width)).replace("__HEIGHT__", str(window_height))
        source = source.replace("__TRAY_EXIT_ON__", repr(
            "single" if tray_click_value.get() == "シングルクリックで終了" else "double"
        ))
        source = source.replace("__TRAY_ICON_STYLE__", repr(tray_icon_style_value.get()))
        source = source.replace("__TRAY_ICON_PATH__", repr(tray_icon_path_value.get()))
        source = source.replace("__ACTIONS__", json.dumps(action_data, ensure_ascii=False, indent=4))
        if load_project_code(source):
            win.destroy()

    row_buttons = tk.Frame(content)
    row_buttons.pack(fill="x", pady=(4, 8))
    ttk.Button(row_buttons, text="新しい行", command=clear_form).pack(side="left")
    ttk.Button(row_buttons, text="追加 / 更新", command=save_action).pack(side="left", padx=6)
    ttk.Button(row_buttons, text="選択行を削除", command=delete_action).pack(side="left")
    ttk.Button(row_buttons, text="設定を読み込み", command=load_configuration).pack(side="left", padx=(12, 0))
    ttk.Button(row_buttons, text="設定を保存", command=save_configuration_as).pack(side="left", padx=6)
    ttk.Button(row_buttons, text="コード生成", command=make_code).pack(side="right")
    ttk.Button(row_buttons, text="閉じる", command=close_builder).pack(side="right", padx=6)
    refresh_table()
    table.bind("<<TreeviewSelect>>", show_selected)
    win.protocol("WM_DELETE_WINDOW", close_builder)


def open_project_catalog():
    win = tk.Toplevel(root)
    win.title("初心者向け 作品一覧")
    win.geometry("930x600")
    win.minsize(760, 480)
    win.transient(root)

    main = tk.Frame(win, padx=12, pady=12)
    main.pack(fill="both", expand=True)
    tk.Label(main, text="作りたいものを選んでください", font=("Meiryo UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
    body = tk.Frame(main)
    body.pack(fill="both", expand=True)
    tree = ttk.Treeview(body, show="tree", selectmode="browse")
    tree.column("#0", width=250, minwidth=200, stretch=False)
    tree.pack(side="left", fill="y")
    tree_scroll = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    tree_scroll.pack(side="left", fill="y")
    tree.configure(yscrollcommand=tree_scroll.set)

    details = tk.Frame(body, padx=14)
    details.pack(side="left", fill="both", expand=True)
    name_label = tk.Label(details, text="作品を選択してください", anchor="w", font=("Meiryo UI", 13, "bold"))
    name_label.pack(fill="x", pady=(0, 6))
    description = tk.Label(details, text="", anchor="nw", justify="left", wraplength=580)
    description.pack(fill="x", pady=(0, 8))
    preview = tk.Text(details, wrap="word", height=18, font=("Consolas", 9), state="disabled")
    preview.pack(fill="both", expand=True)

    item_projects = {}
    category_items = {}
    for project in PROJECT_EXAMPLES:
        category = project["category"]
        if category not in category_items:
            category_items[category] = tree.insert("", "end", text=category, open=True)
        item = tree.insert(category_items[category], "end", text=project["name"])
        item_projects[item] = project

    selected_project = {"value": None}
    buttons = tk.Frame(main)
    buttons.pack(fill="x", pady=(10, 0))
    load_button = tk.Button(buttons, text="コードをエディターに読み込む", state="disabled")
    load_button.pack(side="right", padx=(6, 0))
    designer_button = tk.Button(buttons, text="フォーム作成を開く", state="disabled")
    designer_button.pack(side="right")
    tk.Button(buttons, text="閉じる", command=win.destroy).pack(side="left")

    def show_selection(event=None):
        selection = tree.selection()
        project = item_projects.get(selection[0]) if selection else None
        if project is None and selection:
            children = tree.get_children(selection[0])
            if children:
                tree.item(selection[0], open=True)
                tree.selection_set(children[0])
                tree.focus(children[0])
                project = item_projects.get(children[0])
        selected_project["value"] = project
        if project is None:
            return
        name_label.config(text=project["name"])
        description.config(text=project["description"])
        preview.config(state="normal")
        preview.delete("1.0", tk.END)
        preview.insert("1.0", project["code"] or "この作品はフォーム作成タブを使います。")
        preview.config(state="disabled")
        is_designer = project["kind"] == "designer"
        load_button.config(state="disabled" if is_designer else "normal")
        designer_button.config(state="normal" if is_designer else "disabled")

    def load_selected():
        project = selected_project["value"]
        if project and load_project_code(project["code"]):
            win.destroy()
            if project["kind"] == "guide":
                messagebox.showinfo("セットアップ案内", "この作品は外部サービスの設定が必要です。コード内のコメントを確認してください。")

    def open_designer():
        top_notebook.select(tab_designer)
        win.destroy()

    load_button.config(command=load_selected)
    designer_button.config(command=open_designer)
    tree.bind("<<TreeviewSelect>>", show_selection)
    for category_item in category_items.values():
        tree.item(category_item, open=True)
    first_project = next(iter(item_projects), None)
    if first_project:
        tree.selection_set(first_project)
        tree.focus(first_project)
        show_selection()

def undo_action():
    try:
        text.edit_undo()
    except Exception:
        pass

def redo_action():
    try:
        text.edit_redo()
    except Exception:
        pass

def select_all(event=None):
    text.tag_add(tk.SEL, "1.0", tk.END)
    text.mark_set(tk.INSERT, "1.0")
    text.see(tk.INSERT)
    return 'break'

def update_status_bar(event=None):
    pos = text.index(tk.INSERT)
    line, col = pos.split('.')
    char_count = len(text.get("1.0", tk.END)) - 1
    fname = os.path.basename(quick_save.current_file_path) if hasattr(quick_save, 'current_file_path') and quick_save.current_file_path else "無題のファイル"
    mod = " ●" if text_modified else ""
    status_label.config(text=f" 📂 {fname}{mod}   |   行: {line}  列: {col}  文字数: {char_count} ")
    update_text_modified_state(event)

def apply_theme(theme_name):
    global current_theme
    current_theme = theme_name
    th = THEMES[theme_name]
    root.configure(bg=th['bg'])
    text.configure(bg=th['text_bg'], fg=th['text_fg'], insertbackground=th['cursor'])
    line_numbers.configure(bg=th['sidebar_bg'], fg=th['text_fg'])
    text_frame.configure(bg=th['bg'])
    status_bar.configure(bg=th['sidebar_bg'])
    status_label.configure(bg=th['sidebar_bg'], fg=th['text_fg'])
    top_btn_frame.configure(bg=th['bg'])
    apply_syntax_highlighting()
    save_settings()

def toggle_theme():
    apply_theme('light' if current_theme == 'dark' else 'dark')

def apply_syntax_highlighting():
    try:
        content = text.get("1.0", tk.END)
    except Exception:
        return
    for tag in ("string", "comment", "keyword"):
        text.tag_remove(tag, "1.0", tk.END)

    string_re = r'(\"\"\".*?\"\"\"|\'\'\'.*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
    comment_re = r'(?m)#.*$'
    keyword_re = r'\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b'

    colors = {'keyword': '#569cd6', 'comment': '#6a9955', 'string': '#ce9178'} if current_theme == 'dark' else {
        'keyword': '#0000ff', 'comment': '#008000', 'string': '#a31515'
    }
    text.tag_configure("string", foreground=colors['string'])
    text.tag_configure("comment", foreground=colors['comment'])
    text.tag_configure("keyword", foreground=colors['keyword'])

    for m in re.finditer(string_re, content, flags=re.DOTALL):
        s, e = m.span()
        text.tag_add("string", f"1.0 + {s}c", f"1.0 + {e}c")
    for m in re.finditer(comment_re, content, flags=re.MULTILINE):
        s, e = m.span()
        if "string" in text.tag_names(f"1.0 + {s}c"):
            continue
        text.tag_add("comment", f"1.0 + {s}c", f"1.0 + {e}c")
    for m in re.finditer(keyword_re, content):
        s, e = m.span()
        tags = text.tag_names(f"1.0 + {s}c")
        if "string" in tags or "comment" in tags:
            continue
        text.tag_add("keyword", f"1.0 + {s}c", f"1.0 + {e}c")

def update_highlight_on_idle(event=None):
    if hasattr(update_highlight_on_idle, '_after_id'):
        try:
            root.after_cancel(update_highlight_on_idle._after_id)
        except Exception:
            pass
    update_highlight_on_idle._after_id = root.after(400, apply_syntax_highlighting)

def change_font_size(delta):
    global current_font_size
    current_font_size = max(8, min(28, current_font_size + delta))
    new_font = ("Consolas", current_font_size)
    text.configure(font=new_font)
    line_numbers.configure(font=new_font)
    save_settings()

def open_search_dialog(event=None):
    global search_window
    if search_window and search_window.winfo_exists():
        search_window.lift()
        return 'break'
    search_window = tk.Toplevel(root)
    search_window.title("検索と置換")
    search_window.geometry("420x180")
    search_window.resizable(False, False)
    th = THEMES[current_theme]
    search_window.configure(bg=th['bg'])

    tk.Label(search_window, text="検索:", bg=th['bg'], fg=th['text_fg']).place(x=20, y=20)
    q_entry = tk.Entry(search_window, width=32, font=("Consolas", 10))
    q_entry.place(x=90, y=20)
    q_entry.focus_set()

    tk.Label(search_window, text="置換:", bg=th['bg'], fg=th['text_fg']).place(x=20, y=60)
    r_entry = tk.Entry(search_window, width=32, font=("Consolas", 10))
    r_entry.place(x=90, y=60)

    def do_find():
        q = q_entry.get()
        if not q:
            return
        global last_search_index
        text.tag_remove("match", "1.0", tk.END)
        pos = text.search(q, last_search_index, stopindex=tk.END)
        if not pos:
            pos = text.search(q, "1.0", stopindex=tk.END)
        if pos:
            end_pos = f"{pos}+{len(q)}c"
            text.tag_add("match", pos, end_pos)
            text.tag_config("match", background=th['match_bg'])
            text.see(pos)
            text.mark_set(tk.INSERT, end_pos)
            last_search_index = end_pos
        else:
            messagebox.showinfo("検索", "見つかりませんでした。")

    def do_replace():
        q = q_entry.get()
        r = r_entry.get()
        if not q:
            return
        try:
            if text.tag_ranges("match"):
                start = text.tag_ranges("match")[0]
                end = text.tag_ranges("match")[1]
                text.delete(start, end)
                text.insert(start, r)
                apply_syntax_highlighting()
                do_find()
            else:
                do_find()
        except Exception:
            do_find()

    def do_replace_all():
        q = q_entry.get()
        r = r_entry.get()
        if not q:
            return
        content = text.get("1.0", tk.END)
        new_content = content.replace(q, r)
        if content != new_content:
            text.delete("1.0", tk.END)
            text.insert("1.0", new_content)
            apply_syntax_highlighting()
            update_line_numbers()
            messagebox.showinfo("置換完了", "すべて置換しました。")
        else:
            messagebox.showinfo("置換", "該当箇所がありませんでした。")

    tk.Button(search_window, text="次を検索", command=do_find, width=12).place(x=90, y=110)
    tk.Button(search_window, text="置換", command=do_replace, width=10).place(x=200, y=110)
    tk.Button(search_window, text="すべて置換", command=do_replace_all, width=12).place(x=290, y=110)
    return 'break'

def format_code():
    code = text.get("1.0", tk.END).strip()
    if not code:
        return
    try:
        venv_python = get_virtualenv_python()
    except Exception as e:
        messagebox.showerror("エラー", f"仮想環境を準備できませんでした:\n{e}")
        return
    try:
        availability = subprocess.run([venv_python, "-m", "autopep8", "--version"],
                                      capture_output=True, text=True, timeout=15)
    except Exception as e:
        messagebox.showerror("エラー", f"autopep8 の確認に失敗しました:\n{e}")
        return
    if availability.returncode != 0:
        if messagebox.askyesno("確認", "autopep8 がインストールされていません。\nインストールしますか？"):
            try:
                subprocess.run([venv_python, "-m", "pip", "install", "autopep8"],
                               check=True, capture_output=True, text=True, timeout=60)
            except Exception as e:
                messagebox.showerror("エラー", f"インストール失敗:\n{e}")
                return
        else:
            return
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(code)
            tpath = tf.name
        subprocess.run([venv_python, "-m", "autopep8", "--in-place", "--aggressive", tpath],
                       check=True, capture_output=True, text=True, timeout=15)
        with open(tpath, "r", encoding="utf-8") as f:
            formatted = f.read()
        text.delete("1.0", tk.END)
        text.insert("1.0", formatted)
        apply_syntax_highlighting()
        update_line_numbers()
        messagebox.showinfo("整形完了", "コードをPEP8準拠に自動整形しました。")
    except Exception as e:
        messagebox.showerror("エラー", f"整形に失敗しました:\n{e}")
    finally:
        if 'tpath' in locals() and os.path.exists(tpath):
            try:
                os.unlink(tpath)
            except Exception:
                pass

def test_python_code():
    global text_modified
    if text_modified:
        if messagebox.askyesno("確認", "未保存の変更があります。保存してからテスト実行しますか？"):
            if not quick_save():
                return
    code = text.get("1.0", tk.END).strip()
    if not code:
        return
    try:
        python_executable = get_virtualenv_python()
    except Exception as e:
        messagebox.showerror("エラー", f"仮想環境を準備できませんでした:\n{e}")
        return
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(code)
        tpath = tf.name

    def run():
        try:
            res = subprocess.run([python_executable, tpath], capture_output=True, text=True, timeout=test_timeout_seconds)
            error_output = res.stderr.strip() or res.stdout.strip() or f"終了コード: {res.returncode}"
            out = res.stdout if res.returncode == 0 else f"【エラー】\n{error_output}"
            if res.returncode == 0 and not out.strip():
                out = "テスト実行が正常に終了しました。\n標準出力はありません。"
            if res.returncode == 0:
                root.after(0, lambda: messagebox.showinfo("テスト実行結果", out[:1500] + ("\n...(以下省略)" if len(out) > 1500 else "")))
            else:
                root.after(0, lambda: messagebox.showerror("テスト実行エラー", out))
        except subprocess.TimeoutExpired:
            root.after(0, lambda: messagebox.showerror("タイムアウト", f"実行が設定された制限時間（{test_timeout_seconds}秒）を超えました。"))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("実行エラー", str(e)))
        finally:
            try:
                os.unlink(tpath)
            except Exception:
                pass
    Thread(target=run, daemon=True).start()

def parse_and_install_code_modules():
    code = text.get("1.0", tk.END)
    if not code.strip():
        messagebox.showwarning("注意", "エディターにコードがありません。")
        return
    import_matches = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', code, re.MULTILINE)
    modules = list(set(import_matches))
    stdlib_set = {
        'os', 'sys', 're', 'math', 'time', 'datetime', 'json', 'random', 'subprocess',
        'threading', 'tempfile', 'tkinter', 'webbrowser', 'urllib', 'winsound', 'pathlib',
        'collections', 'itertools', 'functools', 'io', 'shutil', 'glob', 'sqlite3', 'csv',
        'hashlib', 'hmac', 'uuid', 'smtplib', 'imaplib', 'http', 'socket', 'asyncio', 'logging',
        'platform', 'typing', 'dataclasses', 'enum', 'abc', 'copy', 'pprint', 'argparse'
    }
    candidate_modules = [m for m in modules if m not in stdlib_set]
    if not candidate_modules:
        messagebox.showinfo("確認", "追加でインストールが必要な未導入の外部モジュールは見つかりませんでした！")
        return
    try:
        python_executable = get_virtualenv_python()
        check_script = "import importlib.util, json, sys; names=json.loads(sys.argv[1]); print(json.dumps([name for name in names if importlib.util.find_spec(name) is None]))"
        result = subprocess.run([python_executable, "-c", check_script, json.dumps(candidate_modules)],
                                check=True, capture_output=True, text=True, timeout=30)
        target_modules = json.loads(result.stdout)
    except Exception as e:
        messagebox.showerror("エラー", f"仮想環境のモジュール確認に失敗しました:\n{e}")
        return
    if not target_modules:
        messagebox.showinfo("確認", "追加でインストールが必要な未導入の外部モジュールは見つかりませんでした！")
        return
    win = tk.Toplevel(root)
    win.title("モジュール自動インストール")
    win.geometry("450x320")
    win.resizable(False, False)
    win.configure(bg="#f8f9fa")
    tk.Label(win, text="📦 未導入の外部モジュールが見つかりました", font=("Meiryo UI", 11, "bold"),
             bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    tk.Label(win, text="以下のモジュールを pip でインストールしますか？", font=("Meiryo UI", 9), bg="#f8f9fa").pack(anchor="w", padx=15, pady=(10, 5))
    list_frame = tk.Frame(win, bg="white", bd=1, relief="sunken")
    list_frame.pack(fill="both", expand=True, padx=15, pady=5)
    lb = tk.Listbox(list_frame, font=("Consolas", 10), selectmode=tk.MULTIPLE, borderwidth=0)
    lb.pack(side="left", fill="both", expand=True)
    for m in target_modules:
        lb.insert(tk.END, m)
    lb.select_set(0, tk.END)
    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=lb.yview)
    scrollbar.pack(side="right", fill="y")
    lb.config(yscrollcommand=scrollbar.set)

    def do_install():
        selected_indices = lb.curselection()
        if not selected_indices:
            messagebox.showwarning("注意", "モジュールを選択してください。")
            return
        success_list, fail_list = [], []
        for idx in selected_indices:
            mname = lb.get(idx)
            try:
                res = subprocess.run([python_executable, "-m", "pip", "install", mname],
                                     capture_output=True, text=True, timeout=90)
                if res.returncode == 0:
                    success_list.append(mname)
                else:
                    fail_list.append(mname)
            except Exception:
                fail_list.append(mname)
        msg = f"インストール完了: {', '.join(success_list) if success_list else 'なし'}"
        if fail_list:
            msg += f"\n失敗: {', '.join(fail_list)}"
        messagebox.showinfo("インストール結果", msg)
        win.destroy()
    tk.Button(win, text="🚀 選択したモジュールをインストール実行", command=do_install,
              bg="#198754", fg="white", font=("Meiryo UI", 10, "bold"), padx=10, pady=8, cursor="hand2").pack(side="bottom", fill="x", padx=15, pady=15)


# ==================== メインUI ====================
root = tk.Tk()
root.title("Python Studio - Code & Form Designer")

original_showerror = messagebox.showerror

def showerror_with_clipboard(title, message, **options):
    error_text = str(message)
    try:
        root.clipboard_clear()
        root.clipboard_append(error_text)
        root.update()
    except Exception:
        pass
    if len(error_text) > 1500:
        display_text = error_text[:1500] + "\n...(省略。全文をクリップボードにコピーしました)"
    else:
        display_text = error_text + "\n\nエラー内容をクリップボードにコピーしました。"
    return original_showerror(title, display_text, **options)

messagebox.showerror = showerror_with_clipboard

if platform.system() == "Windows":
    root.after(10, lambda: root.state('zoomed'))
else:
    try:
        root.attributes('-zoomed', True)
    except Exception:
        root.geometry("1200x800")

load_settings()

style = ttk.Style()
style.theme_use('clam')
style.configure('TNotebook', background=THEMES[current_theme]['bg'], borderwidth=0)
style.configure('TNotebook.Tab', padding=[14, 8], font=('Meiryo UI', 10, 'bold'))

top_notebook = ttk.Notebook(root)
top_notebook.pack(expand=True, fill="both", padx=6, pady=6)

tab_editor = ttk.Frame(top_notebook)
top_notebook.add(tab_editor, text="📝 コードエディター")

tab_samples = ttk.Frame(top_notebook)
top_notebook.add(tab_samples, text="🧩 サンプル一覧")

tab_hotkey = ttk.Frame(top_notebook)
top_notebook.add(tab_hotkey, text="⌨ ホットキー作成")

tab_designer = ttk.Frame(top_notebook)
top_notebook.add(tab_designer, text="🎨 フォーム作成")

tab_tools = ttk.Frame(top_notebook)
top_notebook.add(tab_tools, text="🛠 ツール・環境情報")


# ---------- タブ1：コードエディター ----------
top_btn_frame = tk.Frame(tab_editor, bg=THEMES[current_theme]['bg'])
top_btn_frame.pack(fill="x", pady=6, padx=6)

def add_btn(parent, text, cmd, bg="#333333", fg="white"):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat",
                  padx=10, pady=5, font=("Meiryo UI", 9, "bold"), cursor="hand2")
    b.pack(side="left", padx=3)
    return b

add_btn(top_btn_frame, "📄 新規", new_file, "#495057")
add_btn(top_btn_frame, "📂 開く", open_file, "#495057")
add_btn(top_btn_frame, "💾 保存", quick_save, "#0d6efd")
add_btn(top_btn_frame, "✨ 自動整形", format_code, "#6c757d")
add_btn(top_btn_frame, "▶ テスト実行", test_python_code, "#198754")
add_btn(top_btn_frame, "📦 コード内モジュール検出", parse_and_install_code_modules, "#6610f2")
add_btn(top_btn_frame, "🔍 検索", open_search_dialog, "#6c757d")
add_btn(top_btn_frame, "🌓 テーマ切替", toggle_theme, "#ffc107", "#000")

text_frame = tk.Frame(tab_editor)
text_frame.pack(expand=True, fill="both", padx=6, pady=2)

font_spec = ("Consolas", current_font_size)
line_numbers = tk.Text(text_frame, width=4, padx=4, takefocus=0, border=0,
                       background=THEMES[current_theme]['sidebar_bg'],
                       fg=THEMES[current_theme]['text_fg'], state='disabled',
                       wrap='none', font=font_spec)
line_numbers.pack(side="left", fill="y")

text = tk.Text(text_frame, font=font_spec, bg=THEMES[current_theme]['text_bg'],
               fg=THEMES[current_theme]['text_fg'], insertbackground=THEMES[current_theme]['cursor'],
               undo=True, maxundo=-1, wrap='none', borderwidth=0)
text.pack(side="left", expand=True, fill="both")

scrollbar_y = ttk.Scrollbar(text_frame, orient="vertical")
scrollbar_y.pack(side="right", fill="y")

def on_text_scroll(*args):
    scrollbar_y.set(*args)
    line_numbers.yview_moveto(args[0])

def on_scrollbar(*args):
    text.yview(*args)
    line_numbers.yview(*args)

text.config(yscrollcommand=on_text_scroll)
scrollbar_y.config(command=on_scrollbar)

def update_line_numbers(event=None):
    line_numbers.config(state='normal')
    line_numbers.delete('1.0', tk.END)
    lc = int(text.index('end-1c').split('.')[0])
    line_numbers.insert('1.0', "\n".join(str(i) for i in range(1, lc + 1)))
    line_numbers.config(state='disabled')

status_bar = tk.Frame(tab_editor, bg=THEMES[current_theme]['sidebar_bg'], height=28)
status_bar.pack(fill="x", side="bottom")
status_label = tk.Label(status_bar, text=" 📂 無題のファイル   |   行: 1  列: 0  文字数: 0 ",
                        bg=THEMES[current_theme]['sidebar_bg'], fg=THEMES[current_theme]['text_fg'],
                        anchor="w", font=("Meiryo UI", 9))
status_label.pack(side="left", padx=6)

text.bind("<KeyRelease>", lambda e: (update_line_numbers(), update_status_bar(), update_highlight_on_idle()))
text.bind("<ButtonRelease-1>", update_status_bar)
text.bind("<Control-MouseWheel>", lambda e: (change_font_size(1 if e.delta > 0 else -1), "break"))
text.bind("<Control-a>", select_all)
root.bind("<Control-s>", lambda e: quick_save())
root.bind("<Control-f>", open_search_dialog)
root.bind("<Control-z>", lambda e: undo_action())
root.bind("<Control-y>", lambda e: redo_action())


# ---------- タブ2：サンプル一覧 ----------
samples_content = tk.Frame(tab_samples, padx=12, pady=12)
samples_content.pack(fill="both", expand=True)
tk.Label(samples_content, text="作りたいものを選んでください", font=("Meiryo UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
samples_body = tk.Frame(samples_content)
samples_body.pack(fill="both", expand=True)
samples_tree = ttk.Treeview(samples_body, show="tree", selectmode="browse")
samples_tree.column("#0", width=250, minwidth=200, stretch=False)
samples_tree.pack(side="left", fill="y")
samples_tree_scroll = ttk.Scrollbar(samples_body, orient="vertical", command=samples_tree.yview)
samples_tree_scroll.pack(side="left", fill="y")
samples_tree.configure(yscrollcommand=samples_tree_scroll.set)

samples_details = tk.Frame(samples_body, padx=14)
samples_details.pack(side="left", fill="both", expand=True)
samples_name_label = tk.Label(samples_details, text="作品を選択してください", anchor="w", font=("Meiryo UI", 13, "bold"))
samples_name_label.pack(fill="x", pady=(0, 6))
samples_description = tk.Label(samples_details, text="", anchor="nw", justify="left", wraplength=580)
samples_description.pack(fill="x", pady=(0, 8))
samples_preview = tk.Text(samples_details, wrap="word", height=18, font=("Consolas", 9), state="disabled")
samples_preview.pack(fill="both", expand=True)

samples_item_projects = {}
samples_category_items = {}
for project in PROJECT_EXAMPLES:
    category = project["category"]
    if category not in samples_category_items:
        samples_category_items[category] = samples_tree.insert("", "end", text=category, open=True)
    item = samples_tree.insert(samples_category_items[category], "end", text=project["name"])
    samples_item_projects[item] = project

samples_selected_project = {"value": None}
samples_buttons = tk.Frame(samples_content)
samples_buttons.pack(fill="x", pady=(10, 0))
samples_load_button = tk.Button(samples_buttons, text="コードをエディターに読み込む", state="disabled")
samples_load_button.pack(side="right", padx=(6, 0))
samples_designer_button = tk.Button(samples_buttons, text="フォーム作成を開く", state="disabled")
samples_designer_button.pack(side="right")

def samples_show_selection(event=None):
    selection = samples_tree.selection()
    project = samples_item_projects.get(selection[0]) if selection else None
    if project is None and selection:
        children = samples_tree.get_children(selection[0])
        if children:
            samples_tree.item(selection[0], open=True)
            samples_tree.selection_set(children[0])
            samples_tree.focus(children[0])
            project = samples_item_projects.get(children[0])
    samples_selected_project["value"] = project
    if project is None:
        return
    samples_name_label.config(text=project["name"])
    samples_description.config(text=project["description"])
    samples_preview.config(state="normal")
    samples_preview.delete("1.0", tk.END)
    samples_preview.insert("1.0", project["code"] or "この作品はフォーム作成タブを使います。")
    samples_preview.config(state="disabled")
    is_designer = project["kind"] == "designer"
    samples_load_button.config(state="disabled" if is_designer else "normal")
    samples_designer_button.config(state="normal" if is_designer else "disabled")

def samples_load_selected():
    project = samples_selected_project["value"]
    if project and load_project_code(project["code"]):
        if project["kind"] == "guide":
            messagebox.showinfo("セットアップ案内", "この作品は外部サービスの設定が必要です。コード内のコメントを確認してください。")

def samples_open_designer():
    top_notebook.select(tab_designer)

samples_load_button.config(command=samples_load_selected)
samples_designer_button.config(command=samples_open_designer)
samples_tree.bind("<<TreeviewSelect>>", samples_show_selection)
for category_item in samples_category_items.values():
    samples_tree.item(category_item, open=True)
first_project = next(iter(samples_item_projects), None)
if first_project:
    samples_tree.selection_set(first_project)
    samples_tree.focus(first_project)
    samples_show_selection()


# ---------- タブ3：ホットキー作成 ----------
hotkey_content = tk.Frame(tab_hotkey, padx=14, pady=12)
hotkey_content.pack(fill="both", expand=True)
tk.Label(hotkey_content, text="ホットキーとボタンの動作を登録", font=("Meiryo UI", 14, "bold")).pack(anchor="w")

hotkey_settings = tk.Frame(hotkey_content)
hotkey_settings.pack(fill="x", pady=(10, 8))
tk.Label(hotkey_settings, text="ウィンドウ名").pack(side="left")
hotkey_title_value = tk.StringVar(value="かんたんホットキー")
ttk.Entry(hotkey_settings, textvariable=hotkey_title_value, width=24).pack(side="left", padx=(6, 16))
tk.Label(hotkey_settings, text="幅").pack(side="left")
hotkey_width_value = tk.StringVar(value="240")
ttk.Entry(hotkey_settings, textvariable=hotkey_width_value, width=7).pack(side="left", padx=6)
tk.Label(hotkey_settings, text="高さ").pack(side="left")
hotkey_height_value = tk.StringVar(value="420")
ttk.Entry(hotkey_settings, textvariable=hotkey_height_value, width=7).pack(side="left", padx=6)
tk.Label(hotkey_settings, text="アイコン操作").pack(side="left", padx=(10, 4))
hotkey_tray_click_value = tk.StringVar(value="double")
ttk.Combobox(hotkey_settings, textvariable=hotkey_tray_click_value,
             values=("シングルクリックで終了", "ダブルクリックで終了"),
             state="readonly", width=22).pack(side="left")
if hotkey_tray_click_value.get() not in ("シングルクリックで終了", "ダブルクリックで終了"):
    hotkey_tray_click_value.set("ダブルクリックで終了")

hotkey_icon_settings = tk.Frame(hotkey_content)
hotkey_icon_settings.pack(fill="x", pady=(0, 8))
tk.Label(hotkey_icon_settings, text="トレイアイコン").pack(side="left")
hotkey_tray_icon_style_value = tk.StringVar(value="オリジナル（H）")
hotkey_icon_style_options = ("オリジナル（H）", "情報", "警告", "エラー", "ICOファイル")
if hotkey_tray_icon_style_value.get() not in hotkey_icon_style_options:
    hotkey_tray_icon_style_value.set(hotkey_icon_style_options[0])
ttk.Combobox(hotkey_icon_settings, textvariable=hotkey_tray_icon_style_value,
             values=hotkey_icon_style_options, state="readonly", width=17).pack(side="left", padx=6)
hotkey_tray_icon_path_value = tk.StringVar(value="")
ttk.Entry(hotkey_icon_settings, textvariable=hotkey_tray_icon_path_value, state="readonly").pack(
    side="left", fill="x", expand=True, padx=6
)

def hotkey_choose_tray_icon():
    selected_path = filedialog.askopenfilename(
        title="トレイアイコンを選択", filetypes=[("アイコンファイル", "*.ico")]
    )
    if selected_path:
        hotkey_tray_icon_path_value.set(selected_path)
        hotkey_tray_icon_style_value.set("ICOファイル")

ttk.Button(hotkey_icon_settings, text="ICOを選択...", command=hotkey_choose_tray_icon).pack(side="left")

hotkey_body = tk.Frame(hotkey_content)
hotkey_body.pack(fill="both", expand=True)
hotkey_columns = ("shortcut", "button", "kind", "target")
hotkey_table = ttk.Treeview(hotkey_body, columns=hotkey_columns, show="headings", height=9, selectmode="browse")
for column, label, width in (("shortcut", "ホットキー", 125), ("button", "ボタン名", 145), ("kind", "動作", 145), ("target", "内容", 400)):
    hotkey_table.heading(column, text=label)
    hotkey_table.column(column, width=width, minwidth=70, stretch=column == "target")
hotkey_table.pack(side="left", fill="both", expand=True)
hotkey_table_scroll = ttk.Scrollbar(hotkey_body, orient="vertical", command=hotkey_table.yview)
hotkey_table_scroll.pack(side="right", fill="y")
hotkey_table.configure(yscrollcommand=hotkey_table_scroll.set)

hotkey_form = tk.LabelFrame(hotkey_content, text="動作の追加・編集", padx=10, pady=8)
hotkey_form.pack(fill="x", pady=(10, 4))
hotkey_shortcut_value = tk.StringVar()
hotkey_button_value = tk.StringVar()
hotkey_kind_value = tk.StringVar(value="URLを開く")
hotkey_target_value = tk.StringVar()
hotkey_wait_value = tk.StringVar(value="0")
hotkey_followup_value = tk.StringVar()

tk.Label(hotkey_form, text="キー (例: Alt+a)").grid(row=0, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="ボタン名 (任意)").grid(row=0, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="動作").grid(row=1, column=0, sticky="w", padx=4, pady=3)
hotkey_kind_menu = ttk.Combobox(hotkey_form, textvariable=hotkey_kind_value, values=("URLを開く", "アプリ/ファイル起動", "キー送信", "コマンド実行"), state="readonly", width=18)
hotkey_kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="URL / パス / キー / コマンド").grid(row=1, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="実行後に待つ秒数").grid(row=2, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
tk.Label(hotkey_form, text="待機後に送るキー (任意)").grid(row=2, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_followup_value).grid(row=2, column=3, sticky="ew", padx=4, pady=3)
hotkey_form.columnconfigure(1, weight=1)
hotkey_form.columnconfigure(3, weight=2)
tk.Label(hotkey_content, text="キー送信の例: Ctrl+w、Alt+F4、Left。キー欄を空にするとボタンだけで実行します。", anchor="w").pack(fill="x", pady=(2, 4))

hotkey_actions = []

def hotkey_load_from_code():
    code = text.get("1.0", tk.END)
    if not code.strip():
        return False
    
    import re
    actions_match = re.search(r'ACTIONS\s*=\s*(\[.*?\])', code, re.DOTALL)
    if not actions_match:
        return False
    
    try:
        actions_data = json.loads(actions_match.group(1))
        if not isinstance(actions_data, list):
            return False
        
        global hotkey_actions
        hotkey_actions = []
        for item in actions_data:
            if not isinstance(item, dict):
                continue
            try:
                wait_seconds = float(item.get("wait", 0))
            except (TypeError, ValueError):
                continue
            if not 0 <= wait_seconds <= 3600:
                continue
            hotkey_actions.append({
                "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                "kind": str(item.get("kind", "URLを開く")), "target": str(item.get("target", "")),
                "wait": wait_seconds, "followup": str(item.get("followup", ""))
            })
        
        title_match = re.search(r'WINDOW_TITLE\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        if title_match:
            hotkey_title_value.set(title_match.group(1))
        
        width_match = re.search(r'WINDOW_WIDTH\s*=\s*(\d+)', code)
        if width_match:
            hotkey_width_value.set(width_match.group(1))
        
        height_match = re.search(r'WINDOW_HEIGHT\s*=\s*(\d+)', code)
        if height_match:
            hotkey_height_value.set(height_match.group(1))
        
        tray_exit_match = re.search(r'TRAY_EXIT_ON\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        if tray_exit_match:
            exit_value = tray_exit_match.group(1)
            if exit_value == "single":
                hotkey_tray_click_value.set("シングルクリックで終了")
            else:
                hotkey_tray_click_value.set("ダブルクリックで終了")
        
        tray_style_match = re.search(r'TRAY_ICON_STYLE\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        if tray_style_match:
            style = tray_style_match.group(1)
            if style in hotkey_icon_style_options:
                hotkey_tray_icon_style_value.set(style)
        
        tray_path_match = re.search(r'TRAY_ICON_PATH\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        if tray_path_match:
            hotkey_tray_icon_path_value.set(tray_path_match.group(1))
        
        return True
    except (json.JSONDecodeError, ValueError):
        return False

def hotkey_load_from_code_with_ui():
    if hotkey_load_from_code():
        hotkey_refresh_table()
        hotkey_clear_form()
        messagebox.showinfo("読み込み完了", f"{len(hotkey_actions)}件のホットキー設定を読み込みました。")
    else:
        messagebox.showerror("エラー", "コード内にACTIONS設定が見つかりませんでした。")

def hotkey_configuration_data():
    return {"title": hotkey_title_value.get(), "width": hotkey_width_value.get(),
            "height": hotkey_height_value.get(), "tray_click_exit": hotkey_tray_click_value.get(),
            "tray_icon_style": hotkey_tray_icon_style_value.get(),
            "tray_icon_path": hotkey_tray_icon_path_value.get(),
            "actions": hotkey_actions}

def hotkey_persist_configuration():
    path = get_settings_path(HOTKEY_BUILDER_SETTINGS_FILE)
    try:
        with open(path, "w", encoding="utf-8") as config_file:
            json.dump(hotkey_configuration_data(), config_file, ensure_ascii=False, indent=2)
    except OSError as error:
        messagebox.showerror("設定保存エラー", str(error))

def hotkey_save_configuration_as():
    path = filedialog.asksaveasfilename(
        title="ホットキー設定を保存", defaultextension=".json",
        filetypes=[("JSON設定", "*.json"), ("すべてのファイル", "*.*")]
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as config_file:
            json.dump(hotkey_configuration_data(), config_file, ensure_ascii=False, indent=2)
        hotkey_persist_configuration()
        messagebox.showinfo("設定保存", "設定を保存しました。")
    except OSError as error:
        messagebox.showerror("設定保存エラー", str(error))

def hotkey_load_configuration():
    path = filedialog.askopenfilename(
        title="ホットキー設定を読み込み", filetypes=[("JSON設定", "*.json"), ("すべてのファイル", "*.*")]
    )
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
        if not isinstance(loaded, dict) or not isinstance(loaded.get("actions"), list):
            raise ValueError("設定ファイルの形式が正しくありません。")
        loaded_actions = loaded["actions"]
        normalized_actions = []
        for item in loaded_actions:
            if not isinstance(item, dict):
                raise ValueError("動作一覧の形式が正しくありません。")
            wait_seconds = float(item.get("wait", 0))
            if not 0 <= wait_seconds <= 3600:
                raise ValueError("待ち時間は0から3600秒の範囲で指定してください。")
            normalized_actions.append({
                "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                "kind": str(item.get("kind", "URLを開く")), "target": str(item.get("target", "")),
                "wait": wait_seconds, "followup": str(item.get("followup", ""))
            })
        hotkey_actions[:] = normalized_actions
        hotkey_title_value.set(str(loaded.get("title", "かんたんホットキー")))
        hotkey_width_value.set(str(loaded.get("width", 240)))
        hotkey_height_value.set(str(loaded.get("height", 420)))
        hotkey_tray_click_value.set(loaded.get("tray_click_exit", "ダブルクリックで終了"))
        if hotkey_tray_click_value.get() not in ("シングルクリックで終了", "ダブルクリックで終了"):
            hotkey_tray_click_value.set("ダブルクリックで終了")
        hotkey_tray_icon_style_value.set(loaded.get("tray_icon_style", "オリジナル（H）"))
        if hotkey_tray_icon_style_value.get() not in hotkey_icon_style_options:
            hotkey_tray_icon_style_value.set(hotkey_icon_style_options[0])
        hotkey_tray_icon_path_value.set(str(loaded.get("tray_icon_path", "")))
        hotkey_refresh_table()
        hotkey_clear_form()
        hotkey_persist_configuration()
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        messagebox.showerror("設定読み込みエラー", str(error))

def hotkey_refresh_table(select_index=None):
    hotkey_table.delete(*hotkey_table.get_children())
    for index, item in enumerate(hotkey_actions):
        hotkey_table.insert("", "end", iid=str(index), values=(item["shortcut"], item["button"], item["kind"], item["target"]))
    if select_index is not None and 0 <= select_index < len(hotkey_actions):
        hotkey_table.selection_set(str(select_index))
        hotkey_table.focus(str(select_index))

def hotkey_clear_form():
    hotkey_table.selection_remove(hotkey_table.selection())
    hotkey_shortcut_value.set("")
    hotkey_button_value.set("")
    hotkey_kind_value.set("URLを開く")
    hotkey_target_value.set("")
    hotkey_wait_value.set("0")
    hotkey_followup_value.set("")

def hotkey_show_selected(event=None):
    selection = hotkey_table.selection()
    if not selection:
        return
    item = hotkey_actions[int(selection[0])]
    hotkey_shortcut_value.set(item["shortcut"])
    hotkey_button_value.set(item["button"])
    hotkey_kind_value.set(item["kind"])
    hotkey_target_value.set(item["target"])
    hotkey_wait_value.set(str(item["wait"]))
    hotkey_followup_value.set(item["followup"])

def hotkey_save_action():
    shortcut = hotkey_shortcut_value.get().strip()
    button = hotkey_button_value.get().strip()
    kind = hotkey_kind_value.get()
    target = hotkey_target_value.get().strip()
    if not shortcut and not button:
        messagebox.showerror("入力エラー", "ホットキーまたはボタン名を入力してください。")
        return
    if not target:
        messagebox.showerror("入力エラー", "動作の内容を入力してください。")
        return
    try:
        wait = float(hotkey_wait_value.get())
        if not 0 <= wait <= 3600:
            raise ValueError
    except ValueError:
        messagebox.showerror("入力エラー", "待ち時間は0から3600秒の数値で入力してください。")
        return
    item = {"shortcut": shortcut, "button": button, "kind": kind, "target": target,
            "wait": wait, "followup": hotkey_followup_value.get().strip()}
    selection = hotkey_table.selection()
    if selection:
        index = int(selection[0])
        hotkey_actions[index] = item
    else:
        index = len(hotkey_actions)
        hotkey_actions.append(item)
    hotkey_refresh_table(index)

def hotkey_delete_action():
    selection = hotkey_table.selection()
    if selection:
        del hotkey_actions[int(selection[0])]
        hotkey_refresh_table()
        hotkey_clear_form()

def hotkey_make_code():
    if not hotkey_actions:
        messagebox.showerror("入力エラー", "ホットキーまたはボタンを1つ以上登録してください。")
        return
    try:
        window_width = int(hotkey_width_value.get())
        window_height = int(hotkey_height_value.get())
        if not 120 <= window_width <= 3000 or not 120 <= window_height <= 3000:
            raise ValueError
    except ValueError:
        messagebox.showerror("入力エラー", "幅と高さは120から3000の整数で入力してください。")
        return
    seen_shortcuts = set()
    for item in hotkey_actions:
        key = item["shortcut"].lower().replace(" ", "")
        if key and key in seen_shortcuts:
            messagebox.showerror("入力エラー", f"ホットキーが重複しています: {item['shortcut']}")
            return
        seen_shortcuts.add(key)
    if hotkey_tray_icon_style_value.get() == "ICOファイル" and not os.path.isfile(hotkey_tray_icon_path_value.get()):
        messagebox.showerror("アイコンエラー", "選択したICOファイルが見つかりません。")
        return

    action_data = [{key: item[key] for key in ("shortcut", "button", "kind", "target", "wait", "followup")} for item in hotkey_actions]
    source = r'''import ctypes
from ctypes import wintypes
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser

WINDOW_TITLE = __TITLE__
WINDOW_WIDTH = __WIDTH__
WINDOW_HEIGHT = __HEIGHT__
TRAY_EXIT_ON = __TRAY_EXIT_ON__
TRAY_ICON_STYLE = __TRAY_ICON_STYLE__
TRAY_ICON_PATH = __TRAY_ICON_PATH__
ACTIONS = __ACTIONS__

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_GETICON = 0x007F
ICON_SMALL = 0
NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
HOTKEY_MODIFIERS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
                    "shift": MOD_SHIFT, "win": MOD_WIN, "windows": MOD_WIN}
SPECIAL_KEYS = {"backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
                "esc": 0x1B, "escape": 0x1B, "space": 0x20, "left": 0x25,
                "up": 0x026, "right": 0x027, "down": 0x028, "delete": 0x2E,
                "home": 0x024, "end": 0x023, "pageup": 0x021, "pagedown": 0x022}
for number in range(1, 13):
    SPECIAL_KEYS[f"f{number}"] = 0x70 + number - 1

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32
hotkey_events = queue.Queue()
hotkey_thread_id = 0
tray_added = False
previous_window_proc = None
tray_click_after_id = None
closing = False

class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

class TimeoutOrVersion(ctypes.Union):
    _fields_ = [("uTimeout", wintypes.UINT), ("uVersion", wintypes.UINT)]

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("timeout_or_version", TimeoutOrVersion),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                            wintypes.WPARAM, wintypes.LPARAM)
set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
set_window_long.restype = ctypes.c_void_p
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                  wintypes.WPARAM, wintypes.LPARAM]
user32.CallWindowProcW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL

def get_key_code(name):
    name = name.strip().lower()
    if name in SPECIAL_KEYS:
        return SPECIAL_KEYS[name]
    if len(name) == 1:
        result = user32.VkKeyScanW(ord(name))
        if result != -1:
            return result & 0xFF
    raise ValueError(f"未対応のキーです: {name}")

def parse_hotkey(shortcut):
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    modifiers = 0
    key = None
    for part in parts:
        if part in HOTKEY_MODIFIERS:
            modifiers |= HOTKEY_MODIFIERS[part]
        else:
            if key is not None:
                raise ValueError(f"キーは1つだけ指定してください: {shortcut}")
            key = get_key_code(part)
    if key is None:
        raise ValueError(f"キーが指定されていません: {shortcut}")
    return modifiers | MOD_NOREPEAT, key

def send_keys(sequence):
    names = [part.strip().lower() for part in sequence.split("+") if part.strip()]
    modifier_codes = {"ctrl": 0x11, "control": 0x11, "alt": 0x12,
                      "shift": 0x10, "win": 0x5B, "windows": 0x5B}
    codes = [modifier_codes[name] if name in modifier_codes else get_key_code(name) for name in names]
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        user32.keybd_event(code, 0, 0x0002, 0)

def run_action(index):
    action = ACTIONS[index]
    try:
        kind, target = action["kind"], action["target"]
        if kind == "URLを開く":
            webbrowser.open(target, new=2)
        elif kind == "アプリ/ファイル起動":
            os.startfile(target)
        elif kind == "コマンド実行":
            subprocess.Popen(target, shell=True)
        elif kind == "キー送信":
            send_keys(target)
        if action["wait"]:
            time.sleep(action["wait"])
        if action["followup"]:
            send_keys(action["followup"])
    except Exception as error:
        hotkey_events.put(("error", f"{action['button'] or action['shortcut']}: {error}"))

def hotkey_loop():
    global hotkey_thread_id
    hotkey_thread_id = kernel32.GetCurrentThreadId()
    registered = []
    try:
        for index, action in enumerate(ACTIONS):
            if not action["shortcut"]:
                continue
            try:
                modifiers, key = parse_hotkey(action["shortcut"])
                if not user32.RegisterHotKey(None, index + 1, modifiers, key):
                    raise OSError("このキーは登録できませんでした。別のアプリで使用中かもしれません。")
                registered.append(index + 1)
            except Exception as error:
                hotkey_events.put(("error", f"{action['shortcut']}: {error}"))
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                hotkey_events.put(("run", message.wParam - 1))
    finally:
        for hotkey_id in registered:
            user32.UnregisterHotKey(None, hotkey_id)

root = tk.Tk()
root.title(WINDOW_TITLE)
root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
tray_image = tk.PhotoImage(width=32, height=32)
tray_image.put("#1769aa", to=(0, 0, 32, 32))
tray_image.put("#ffffff", to=(6, 6, 10, 26))
tray_image.put("#ffffff", to=(22, 6, 26, 26))
tray_image.put("#ffffff", to=(10, 16, 22, 20))
tray_image.put("#f5c542", to=(13, 6, 19, 10))
root.iconphoto(True, tray_image)
for index, action in enumerate(ACTIONS):
    if action["button"]:
        tk.Button(root, text=action["button"], command=lambda i=index: threading.Thread(
            target=run_action, args=(i,), daemon=True).start()).pack(fill="x", padx=8, pady=4)

def process_events():
    while not hotkey_events.empty():
        kind, value = hotkey_events.get_nowait()
        if kind == "run":
            threading.Thread(target=run_action, args=(value,), daemon=True).start()
        else:
            messagebox.showerror("ホットキー", value, parent=root)
    root.after(50, process_events)

def restore_window():
    root.deiconify()
    root.state("normal")
    root.lift()
    root.focus_force()

def show_tray_menu():
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="ウィンドウを表示", command=restore_window)
    menu.add_separator()
    menu.add_command(label="終了", command=close_window)
    try:
        menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
    finally:
        menu.grab_release()

@WNDPROC
def tray_window_proc(hwnd, message, wparam, lparam):
    if message == WM_TRAYICON:
        event = lparam & 0xFFFF
        if event == WM_LBUTTONUP:
            if TRAY_EXIT_ON == "single":
                root.after(0, close_window)
            else:
                global tray_click_after_id
                if not closing:
                    tray_click_after_id = root.after(300, restore_window)
            return 0
        if event == WM_LBUTTONDBLCLK:
            if TRAY_EXIT_ON == "double":
                if tray_click_after_id is not None:
                    root.after_cancel(tray_click_after_id)
                    tray_click_after_id = None
                root.after(0, close_window)
            else:
                root.after(0, restore_window)
            return 0
        if event == WM_RBUTTONUP:
            root.after(0, show_tray_menu)
            return 0
    return user32.CallWindowProcW(previous_window_proc, hwnd, message, wparam, lparam)

def install_tray_icon():
    global previous_window_proc, tray_added
    root.update_idletasks()
    hwnd = wintypes.HWND(root.winfo_id())
    icon_handle = 0
    if TRAY_ICON_STYLE == "ICOファイル" and os.path.isfile(TRAY_ICON_PATH):
        user32.LoadImageW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.LoadImageW.restype = wintypes.HICON
        icon_handle = user32.LoadImageW(None, TRAY_ICON_PATH, 1, 0, 0, 0x0010)
    elif TRAY_ICON_STYLE in ("情報", "警告", "エラー"):
        user32.LoadIconW.restype = wintypes.HICON
        stock_icons = {"情報": 32516, "警告": 32515, "エラー": 32513}
        icon_handle = user32.LoadIconW(None, stock_icons[TRAY_ICON_STYLE])
    if not icon_handle:
        icon_handle = user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0)
    if not icon_handle:
        user32.LoadIconW.restype = wintypes.HICON
        icon_handle = user32.LoadIconW(None, 32512)
    icon_data = NOTIFYICONDATAW()
    icon_data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    icon_data.hWnd = hwnd
    icon_data.uID = 1
    icon_data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    icon_data.uCallbackMessage = WM_TRAYICON
    icon_data.hIcon = icon_handle
    icon_data.szTip = f"{WINDOW_TITLE} - 起動中"
    previous_window_proc = set_window_long(hwnd, -4, ctypes.cast(tray_window_proc, ctypes.c_void_p))
    tray_added = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(icon_data)))
    if tray_added:
        root.withdraw()
    else:
        root.deiconify()
        messagebox.showerror("タスクトレイ", "通知領域へアイコンを登録できませんでした。ウィンドウを表示します。", parent=root)

def close_window():
    global closing, tray_click_after_id
    if closing:
        return
    closing = True
    if tray_click_after_id is not None:
        try:
            root.after_cancel(tray_click_after_id)
        except tk.TclError:
            pass
        tray_click_after_id = None
    if tray_added:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(icon_data))
    if hotkey_thread_id:
        user32.PostThreadMessageW(hotkey_thread_id, WM_QUIT, 0, 0)
    root.destroy()

icon_data = NOTIFYICONDATAW()
icon_data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
icon_data.hWnd = wintypes.HWND(root.winfo_id())
icon_data.uID = 1
icon_data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
icon_data.uCallbackMessage = WM_TRAYICON
icon_data.hIcon = user32.SendMessageW(icon_data.hWnd, WM_GETICON, ICON_SMALL, 0)
icon_data.szTip = f"{WINDOW_TITLE} - 起動中"
root.protocol("WM_DELETE_WINDOW", close_window)
threading.Thread(target=hotkey_loop, daemon=True).start()
root.after(50, process_events)
root.withdraw()
root.after(100, install_tray_icon)
root.mainloop()
'''
    source = source.replace("__TITLE__", repr(hotkey_title_value.get().strip() or "かんたんホットキー"))
    source = source.replace("__WIDTH__", str(window_width)).replace("__HEIGHT__", str(window_height))
    source = source.replace("__TRAY_EXIT_ON__", repr(
        "single" if hotkey_tray_click_value.get() == "シングルクリックで終了" else "double"
    ))
    source = source.replace("__TRAY_ICON_STYLE__", repr(hotkey_tray_icon_style_value.get()))
    source = source.replace("__TRAY_ICON_PATH__", repr(hotkey_tray_icon_path_value.get()))
    source = source.replace("__ACTIONS__", json.dumps(action_data, ensure_ascii=False, indent=4))
    if load_project_code(source):
        messagebox.showinfo("生成完了", "ホットキーアプリのコードをエディターに転送しました！")

hotkey_row_buttons = tk.Frame(hotkey_content)
hotkey_row_buttons.pack(fill="x", pady=(4, 8))
ttk.Button(hotkey_row_buttons, text="新しい行", command=hotkey_clear_form).pack(side="left")
ttk.Button(hotkey_row_buttons, text="追加 / 更新", command=hotkey_save_action).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="選択行を削除", command=hotkey_delete_action).pack(side="left")
ttk.Button(hotkey_row_buttons, text="設定を読み込み", command=hotkey_load_configuration).pack(side="left", padx=(12, 0))
ttk.Button(hotkey_row_buttons, text="設定を保存", command=hotkey_save_configuration_as).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="コードから読み込み", command=hotkey_load_from_code_with_ui).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="コード生成", command=hotkey_make_code).pack(side="right")
hotkey_load_from_code()
hotkey_refresh_table()
hotkey_clear_form()
hotkey_table.bind("<<TreeviewSelect>>", hotkey_show_selected)

def on_hotkey_tab_selected(event):
    hotkey_load_from_code()
    hotkey_refresh_table()

top_notebook.bind("<<NotebookTabChanged>>", lambda e: on_hotkey_tab_selected(e) if top_notebook.select() == str(tab_hotkey) else None)

def hotkey_configuration_data():
    return {"title": hotkey_title_value.get(), "width": hotkey_width_value.get(),
            "height": hotkey_height_value.get(), "tray_click_exit": hotkey_tray_click_value.get(),
            "tray_icon_style": hotkey_tray_icon_style_value.get(),
            "tray_icon_path": hotkey_tray_icon_path_value.get(),
            "actions": hotkey_actions}

def hotkey_persist_configuration():
    path = get_settings_path(HOTKEY_BUILDER_SETTINGS_FILE)
    try:
        with open(path, "w", encoding="utf-8") as config_file:
            json.dump(hotkey_configuration_data(), config_file, ensure_ascii=False, indent=2)
    except OSError as error:
        messagebox.showerror("設定保存エラー", str(error))


# ---------- タブ4：ビジュアルフォーム作成 ----------
designer_components = []
selected_component = None

designer_toolbar = tk.Frame(tab_designer, bg="#2d2d2d", padx=8, pady=8)
designer_toolbar.pack(side="top", fill="x")

form_window_width = 600
form_window_height = 450
form_bg_color = "#f0f0f0"
form_fg_color = "#000000"
form_pos_x = 100
form_pos_y = 100
form_pos_mode = "manual"

canvas_container = tk.Frame(tab_designer, bg="#1e1e1e")
canvas_container.pack(side="top", fill="both", expand=True, padx=8, pady=8)

form_preview = tk.Frame(canvas_container, bg=form_bg_color, bd=2, relief="solid",
                        highlightbackground="#555555", highlightthickness=1)
form_preview.place(x=50, y=50, width=form_window_width, height=form_window_height)

form_resize_handle = tk.Label(form_preview, text="◢", bg="#0d6efd", fg="white",
                              font=("Meiryo UI", 10, "bold"), cursor="sizing")
form_resize_handle.place(relx=1.0, rely=1.0, x=-16, y=-16, width=16, height=16)

size_lbl = tk.Label(canvas_container,
                    text=f"📱 フォームサイズ: {form_window_width} x {form_window_height}  |  🖥 画面表示位置: X={form_pos_x}, Y={form_pos_y}",
                    bg="#1e1e1e", fg="#cccccc", font=("Meiryo UI", 9))
size_lbl.place(x=50, y=20)

def update_form_preview_size(w, h):
    global form_window_width, form_window_height
    form_window_width = max(200, w)
    form_window_height = max(75, h)
    form_preview.place(width=form_window_width, height=form_window_height)
    if "form_width_var" in globals():
        form_width_var.set(str(form_window_width))
        form_height_var.set(str(form_window_height))
    update_size_label()

def apply_form_size_inputs(event=None):
    try:
        width = int(form_width_var.get())
        height = int(form_height_var.get())
    except ValueError:
        form_width_var.set(str(form_window_width))
        form_height_var.set(str(form_window_height))
        return "break" if event else None
    update_form_preview_size(width, height)
    return "break" if event else None

size_control_frame = tk.Frame(designer_toolbar, bg="#2d2d2d")
size_control_frame.pack(side="right", padx=8)
tk.Label(size_control_frame, text="フォームサイズ", bg="#2d2d2d", fg="#eeeeee",
         font=("Meiryo UI", 9)).pack(side="left", padx=(0, 5))
form_width_var = tk.StringVar(value=str(form_window_width))
form_width_spin = ttk.Spinbox(size_control_frame, from_=200, to=100000, increment=1,
                              width=7, textvariable=form_width_var, command=apply_form_size_inputs)
form_width_spin.pack(side="left")
tk.Label(size_control_frame, text="×", bg="#2d2d2d", fg="#eeeeee").pack(side="left", padx=3)
form_height_var = tk.StringVar(value=str(form_window_height))
form_height_spin = ttk.Spinbox(size_control_frame, from_=75, to=100000, increment=1,
                               width=7, textvariable=form_height_var, command=apply_form_size_inputs)
form_height_spin.pack(side="left")
form_width_spin.bind("<Return>", apply_form_size_inputs)
form_height_spin.bind("<Return>", apply_form_size_inputs)
form_width_spin.bind("<FocusOut>", apply_form_size_inputs)
form_height_spin.bind("<FocusOut>", apply_form_size_inputs)

def update_size_label():
    pos_str = "画面中央に表示" if form_pos_mode == "center" else f"X={form_pos_x}, Y={form_pos_y}"
    size_lbl.config(text=f"📱 フォームサイズ: {form_window_width} x {form_window_height}  |  🖥 画面表示位置: {pos_str}")

def apply_form_colors():
    form_preview.configure(bg=form_bg_color)
    for comp in designer_components:
        try:
            if comp["type"] != "Button" and not comp.get("custom_background", False):
                comp["bg_color"] = form_bg_color
                comp["inner"].configure(bg=form_bg_color)
            if not comp.get("custom_foreground", False):
                comp["fg_color"] = form_fg_color
                comp["inner"].configure(fg=form_fg_color)
        except tk.TclError:
            pass
    form_bg_swatch.configure(bg=form_bg_color, activebackground=form_bg_color)
    form_fg_swatch.configure(bg=form_fg_color, activebackground=form_fg_color)

def choose_form_color(color_type):
    global form_bg_color, form_fg_color
    current_color = form_bg_color if color_type == "background" else form_fg_color
    selected_color = colorchooser.askcolor(
        color=current_color,
        title="フォーム背景色を選択" if color_type == "background" else "フォーム文字色を選択",
        parent=root,
    )[1]
    if selected_color:
        if color_type == "background":
            form_bg_color = selected_color
        else:
            form_fg_color = selected_color
        apply_form_colors()

form_color_controls = tk.Frame(designer_toolbar, bg="#2d2d2d")
form_color_controls.pack(side="right", padx=8)
tk.Label(form_color_controls, text="フォーム背景", bg="#2d2d2d", fg="#eeeeee",
         font=("Meiryo UI", 9)).pack(side="left", padx=(0, 3))
form_bg_swatch = tk.Button(form_color_controls, text="選択", width=5, bg=form_bg_color,
                           command=lambda: choose_form_color("background"), cursor="hand2")
form_bg_swatch.pack(side="left", padx=(0, 8))
tk.Label(form_color_controls, text="フォーム文字", bg="#2d2d2d", fg="#eeeeee",
         font=("Meiryo UI", 9)).pack(side="left", padx=(0, 3))
form_fg_swatch = tk.Button(form_color_controls, text="選択", width=5, bg=form_fg_color,
                           command=lambda: choose_form_color("foreground"), cursor="hand2")
form_fg_swatch.pack(side="left")

def on_form_resize_press(event):
    form_preview._w_start = form_preview.winfo_width()
    form_preview._h_start = form_preview.winfo_height()
    form_preview._x_start = event.x_root
    form_preview._y_start = event.y_root

def on_form_resize_drag(event):
    dx = event.x_root - form_preview._x_start
    dy = event.y_root - form_preview._y_start
    update_form_preview_size(form_preview._w_start + dx, form_preview._h_start + dy)

form_resize_handle.bind("<Button-1>", on_form_resize_press)
form_resize_handle.bind("<B1-Motion>", on_form_resize_drag)

def open_window_position_dialog():
    global form_pos_x, form_pos_y, form_pos_mode
    w_diag = tk.Toplevel(root)
    w_diag.title("ウィンドウの画面表示位置設定")
    w_diag.geometry("450x340")
    w_diag.resizable(False, False)
    w_diag.configure(bg="#f8f9fa")
    w_diag.transient(root)
    w_diag.grab_set()

    tk.Label(w_diag, text="🖥 アプリ起動時のデスクトップ画面上の位置",
             font=("Meiryo UI", 11, "bold"), bg="#0d6efd", fg="white",
             padx=10, pady=10).pack(side="top", fill="x")

    f_body = tk.Frame(w_diag, bg="#f8f9fa", padx=20, pady=15)
    f_body.pack(fill="both", expand=True)

    mode_var = tk.StringVar(value=form_pos_mode)
    tk.Radiobutton(f_body, text="画面の中央に自動で表示する", variable=mode_var, value="center",
                   bg="#f8f9fa", font=("Meiryo UI", 10)).pack(anchor="w", pady=5)
    tk.Radiobutton(f_body, text="デスクトップ上の指定座標 (X, Y) に表示する", variable=mode_var, value="manual",
                   bg="#f8f9fa", font=("Meiryo UI", 10)).pack(anchor="w", pady=(10, 5))

    coord_frame_diag = tk.Frame(f_body, bg="#f8f9fa", padx=20)
    coord_frame_diag.pack(anchor="w", pady=5)

    tk.Label(coord_frame_diag, text="X座標:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
    x_entry = tk.Entry(coord_frame_diag, width=12, font=("Consolas", 10))
    x_entry.grid(row=0, column=1, padx=10, pady=5)
    x_entry.insert(0, str(form_pos_x))

    tk.Label(coord_frame_diag, text="Y座標:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
    y_entry = tk.Entry(coord_frame_diag, width=12, font=("Consolas", 10))
    y_entry.grid(row=1, column=1, padx=10, pady=5)
    y_entry.insert(0, str(form_pos_y))

    def capture_mouse_pos_here(event=None):
        cx, cy = w_diag.winfo_pointerx(), w_diag.winfo_pointery()
        x_entry.delete(0, tk.END)
        x_entry.insert(0, str(cx))
        y_entry.delete(0, tk.END)
        y_entry.insert(0, str(cy))
        mode_var.set("manual")
        return "break"

    # 本体と入力欄の両方にバインド（クリックなしでHomeが効くように）
    w_diag.bind("<Home>", capture_mouse_pos_here)
    x_entry.bind("<Home>", capture_mouse_pos_here)
    y_entry.bind("<Home>", capture_mouse_pos_here)

    tk.Label(f_body, text="💡 [Home] キーで現在のマウス座標を自動入力",
             bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 9)).pack(anchor="w", pady=(10, 0))

    def save_pos():
        global form_pos_x, form_pos_y, form_pos_mode
        form_pos_mode = mode_var.get()
        if form_pos_mode == "manual":
            try:
                form_pos_x = int(x_entry.get().strip())
                form_pos_y = int(y_entry.get().strip())
            except ValueError:
                messagebox.showerror("エラー", "座標には有効な整数を入力してください。")
                return
        update_size_label()
        messagebox.showinfo("保存完了", "ウィンドウの画面表示位置を設定しました！")
        w_diag.destroy()

    tk.Button(w_diag, text="💾 設定を保存する", command=save_pos, bg="#198754", fg="white",
              font=("Meiryo UI", 10, "bold"), padx=10, pady=10, cursor="hand2").pack(side="bottom", fill="x", padx=20, pady=15)

    def center_position_dialog(event=None):
        w_diag.update_idletasks()
        dialog_width = w_diag.winfo_width()
        dialog_height = w_diag.winfo_height()
        screen_x = max(0, (w_diag.winfo_screenwidth() - dialog_width) // 2)
        screen_y = max(0, (w_diag.winfo_screenheight() - dialog_height) // 2)
        w_diag.geometry(f"450x340+{screen_x}+{screen_y}")

    w_diag.bind("<Map>", lambda event: w_diag.after_idle(center_position_dialog), add="+")
    center_position_dialog()
    w_diag.after(50, center_position_dialog)

    # 開いた瞬間にフォーカスを強制的に当てる
    w_diag.after(50, lambda: w_diag.focus_force())


def add_component(ctype):
    global selected_component
    wrapper = tk.Frame(form_preview, bg="#cccccc", bd=1, relief="raised")
    wrapper.place(x=40, y=40, width=150, height=36)

    default_bg = "#e8e8e8" if ctype == "Button" else form_bg_color
    default_fg = form_fg_color

    if ctype == "Button":
        inner = tk.Button(wrapper, text="ボタン", relief="flat", font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    elif ctype == "Label":
        inner = tk.Label(wrapper, text="テキストラベル", bg=default_bg, fg=default_fg, font=("Meiryo UI", 10))
    else:
        inner = tk.Entry(wrapper, font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    inner.pack(fill="both", expand=True)

    comp_resize_handle = tk.Label(wrapper, text="◢", bg="#0d6efd", fg="white", font=("Meiryo UI", 8), cursor="sizing")
    comp_resize_handle.place(relx=1.0, rely=1.0, x=-12, y=-12, width=12, height=12)

    comp_info = {
        "type": ctype, "wrapper": wrapper, "inner": inner,
        "text": "ボタン" if ctype == "Button" else ("テキストラベル" if ctype == "Label" else ""),
        "bg_color": default_bg, "fg_color": default_fg, "font_size": 10,
        "custom_background": False, "custom_foreground": False,
        "action": "none", "param": "", "close_after_action": True,
        "browser_choice": "既定のブラウザ", "browser_window_mode": "最大化"
    }
    designer_components.append(comp_info)

    def select(event=None):
        global selected_component
        if selected_component and selected_component != comp_info:
            selected_component["wrapper"].config(bd=1, bg="#cccccc")
        selected_component = comp_info
        wrapper.config(bd=2, bg="#0d6efd")
        if event:
            event.widget.focus_set()

    def on_press(event):
        select(event)
        wrapper._sx, wrapper._sy = event.x, event.y
        wrapper.lift()

    def on_drag(event):
        x = wrapper.winfo_x() + event.x - wrapper._sx
        y = wrapper.winfo_y() + event.y - wrapper._sy
        wrapper.place(x=max(0, x), y=max(0, y))

    def on_resize_press(event):
        select(event)
        wrapper._w_start = wrapper.winfo_width()
        wrapper._h_start = wrapper.winfo_height()
        wrapper._x_start = event.x_root
        wrapper._y_start = event.y_root

    def on_resize_drag(event):
        dx = event.x_root - wrapper._x_start
        dy = event.y_root - wrapper._y_start
        wrapper.place(width=max(40, wrapper._w_start + dx), height=max(24, wrapper._h_start + dy))

    for w in [wrapper, inner]:
        w.bind("<Button-1>", on_press)
        w.bind("<B1-Motion>", on_drag)
        w.bind("<Double-Button-1>", lambda e: (select(e), open_properties_dialog(comp_info)))

    comp_resize_handle.bind("<Button-1>", on_resize_press)
    comp_resize_handle.bind("<B1-Motion>", on_resize_drag)
    select()

def open_properties_dialog(comp):
    if not comp:
        messagebox.showwarning("注意", "部品を選択してください。")
        return
    diag = tk.Toplevel(root)
    diag.title("部品の詳細プロパティ設定")
    diag.geometry("640x620")
    diag.resizable(False, False)
    diag.configure(bg="#f8f9fa")
    diag.transient(root)

    tk.Label(diag, text="🎨 部品の見た目と動作の詳細設定",
             font=("Meiryo UI", 11, "bold"), bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    bottom_frame = tk.Frame(diag, bg="#e9ecef", padx=15, pady=12)
    bottom_frame.pack(side="bottom", fill="x")

    diag_notebook = ttk.Notebook(diag)
    diag_notebook.pack(fill="both", expand=True, padx=10, pady=10)

    tab_design = ttk.Frame(diag_notebook)
    tab_action = ttk.Frame(diag_notebook)
    diag_notebook.add(tab_design, text="① 文字・デザイン設定")
    diag_notebook.add(tab_action, text="② アクション設定")

    f_des = tk.Frame(tab_design, bg="#f8f9fa", padx=20, pady=20)
    f_des.pack(fill="both", expand=True)

    tk.Label(f_des, text="表示テキスト（内容）:", bg="#f8f9fa", font=("Meiryo UI", 10, "bold")).pack(anchor="w")
    txt_entry = tk.Entry(f_des, width=48, font=("Meiryo UI", 10))
    txt_entry.pack(anchor="w", pady=(2, 15))
    txt_entry.insert(0, comp["text"])

    style_frame = tk.LabelFrame(f_des, text=" デザイン（色・フォントサイズ） ", bg="#f8f9fa",
                                font=("Meiryo UI", 9, "bold"), padx=15, pady=12)
    style_frame.pack(fill="x", pady=5)

    tk.Label(style_frame, text="背景色:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
    bg_entry = tk.Entry(style_frame, width=18, font=("Consolas", 10))
    bg_entry.grid(row=0, column=1, sticky="w", padx=10, pady=5)
    bg_entry.insert(0, comp["bg_color"])

    def choose_component_color(entry, swatch, title):
        selected_color = colorchooser.askcolor(color=entry.get(), title=title, parent=diag)[1]
        if selected_color:
            entry.delete(0, tk.END)
            entry.insert(0, selected_color)
            swatch.configure(bg=selected_color, activebackground=selected_color)

    bg_swatch = tk.Button(style_frame, text="  ", width=3, bg=comp["bg_color"],
                          command=lambda: choose_component_color(bg_entry, bg_swatch, "部品の背景色を選択"),
                          cursor="hand2")
    bg_swatch.grid(row=0, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="文字色:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
    fg_entry = tk.Entry(style_frame, width=18, font=("Consolas", 10))
    fg_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)
    fg_entry.insert(0, comp["fg_color"])
    fg_swatch = tk.Button(style_frame, text="  ", width=3, bg=comp["fg_color"],
                          command=lambda: choose_component_color(fg_entry, fg_swatch, "部品の文字色を選択"),
                          cursor="hand2")
    fg_swatch.grid(row=1, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="文字サイズ:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=2, column=0, sticky="w", pady=5)
    size_spin = ttk.Spinbox(style_frame, from_=8, to=36, width=16)
    size_spin.grid(row=2, column=1, sticky="w", padx=10, pady=5)
    size_spin.set(comp["font_size"])

    if comp["type"] == "Button":
        act_container = tk.Frame(tab_action, bg="#f8f9fa")
        act_container.pack(fill="both", expand=True)
        act_canvas = tk.Canvas(act_container, bg="#f8f9fa", highlightthickness=0)
        act_scrollbar = ttk.Scrollbar(act_container, orient="vertical", command=act_canvas.yview)
        f_act = tk.Frame(act_canvas, bg="#f8f9fa", padx=15, pady=10)
        f_act.bind("<Configure>", lambda e: act_canvas.configure(scrollregion=act_canvas.bbox("all")))
        act_canvas.create_window((0, 0), window=f_act, anchor="nw")
        act_canvas.configure(yscrollcommand=act_scrollbar.set)
        act_canvas.pack(side="left", fill="both", expand=True)
        act_scrollbar.pack(side="right", fill="y")

        tk.Label(f_act, text="実行するアクションを選択（初心者向けを多数追加）:", bg="#f8f9fa",
                 font=("Meiryo UI", 10, "bold")).pack(anchor="w", pady=(0, 5))

        action_categories = [
            ("--- 基本 ---", [
                ("何もしない", "none"),
                ("🚪 アプリを終了する", "close_app"),
            ]),
            ("📁 ファイル・フォルダ操作（超おすすめ）", [
                ("📄 ファイルをコピーする", "copy_file"),
                ("📂 フォルダをコピーする", "copy_folder"),
                ("✂ ファイルを移動する", "move_file"),
                ("🗑 ファイルを削除する（確認あり）", "delete_file"),
                ("📂 フォルダを開く", "open_folder"),
                ("📄 ファイルを開く（関連付けアプリ）", "open_file_default"),
                ("📁 新規フォルダを作成", "create_folder"),
                ("📝 テキストファイルを作成", "create_text_file"),
            ]),
            ("🖥 よく使うフォルダを開く", [
                ("🖥 デスクトップを開く", "open_desktop"),
                ("📄 ドキュメントを開く", "open_documents"),
                ("⬇ ダウンロードを開く", "open_downloads"),
                ("📂 エクスプローラーを開く", "open_explorer"),
            ]),
            ("🌐 Web・検索", [
                ("指定のURLを開く", "open_url"),
                ("Xを開く", "open_x"),
                ("ABEMA TVを開く", "open_abema"),
                ("Google検索", "google_search"),
                ("YouTube検索", "youtube_search"),
                ("Google翻訳", "google_translate"),
                ("Googleマップ", "google_maps"),
            ]),
            ("💬 メッセージ・便利機能", [
                ("メッセージボックスを表示", "show_msg"),
                ("確認ダイアログ", "ask_yesno"),
                ("文字をクリップボードにコピー", "copy_clipboard"),
                ("現在時刻をクリップボードにコピー", "copy_time"),
                ("現在の時刻を表示", "show_time"),
            ]),
            ("🖥 システム・ツール", [
                ("メモ帳を開く", "open_notepad"),
                ("電卓を開く", "open_calc"),
                ("コマンドプロンプト／ターミナルを開く", "open_terminal"),
                ("ビープ音を鳴らす", "beep"),
            ]),
            ("🎲 お楽しみ", [
                ("1〜100くじ引き", "random_num"),
                ("サイコロを振る", "dice_roll"),
                ("おみくじ", "omikuji"),
                ("パスワード生成", "gen_password"),
            ]),
        ]

        act_var = tk.StringVar(value=comp["action"])
        for cat_name, acts in action_categories:
            tk.Label(f_act, text=cat_name, bg="#f8f9fa", fg="#0d6efd",
                     font=("Meiryo UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
            for text_lbl, val in acts:
                tk.Radiobutton(f_act, text=text_lbl, variable=act_var, value=val,
                               bg="#f8f9fa", font=("Meiryo UI", 9), anchor="w").pack(anchor="w", padx=12, pady=1)

        tk.Label(f_act, text="アクションパラメータ（URLやメッセージ内容など）:", bg="#f8f9fa",
                 font=("Meiryo UI", 9, "bold")).pack(anchor="w", pady=(14, 2))
        param_entry = tk.Entry(f_act, width=50, font=("Meiryo UI", 10))
        param_entry.pack(anchor="w")
        param_entry.insert(0, comp["param"])
        close_after_var = tk.BooleanVar(value=comp.get("close_after_action", True))
        tk.Checkbutton(
            f_act,
            text="アクション実行後にこのアプリを終了する",
            variable=close_after_var,
            bg="#f8f9fa",
            font=("Meiryo UI", 9),
            anchor="w",
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(f_act, text="ブラウザを開くアクションの使用ブラウザ:", bg="#f8f9fa",
                 font=("Meiryo UI", 9)).pack(anchor="w", pady=(8, 2))
        browser_var = tk.StringVar(value=comp.get("browser_choice", "既定のブラウザ"))
        browser_combo = ttk.Combobox(
            f_act,
            textvariable=browser_var,
            values=("既定のブラウザ", "Microsoft Edge", "Google Chrome", "Mozilla Firefox", "Brave"),
            state="readonly",
            width=24,
        )
        browser_combo.pack(anchor="w")
        tk.Label(f_act, text="ブラウザの表示方法:", bg="#f8f9fa",
                 font=("Meiryo UI", 9)).pack(anchor="w", pady=(6, 2))
        browser_window_mode_var = tk.StringVar(value=comp.get("browser_window_mode", "最大化"))
        browser_window_mode_combo = ttk.Combobox(
            f_act,
            textvariable=browser_window_mode_var,
            values=("最大化", "左半分", "右半分"),
            state="readonly",
            width=12,
        )
        browser_window_mode_combo.pack(anchor="w")
        tk.Label(f_act, text="※ コピー操作では下の詳細設定で送信元・送信先を指定してください。",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).pack(anchor="w", pady=(4, 0))

        path_frame = tk.LabelFrame(f_act, text="コピー元・コピー先の設定",
                                   bg="#f8f9fa", font=("Meiryo UI", 9, "bold"), padx=8, pady=6)
        path_frame.pack(fill="x", pady=(12, 0))
        tk.Label(path_frame, text="コピー操作では必須です。設定した場所をボタン実行時に使います。",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).grid(
                     row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        tk.Label(path_frame, text="コピー元:", bg="#f8f9fa").grid(row=1, column=0, sticky="w", pady=3)
        source_entry = tk.Entry(path_frame, width=38, font=("Consolas", 9))
        source_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        source_entry.insert(0, comp.get("source_path", ""))

        tk.Label(path_frame, text="コピー先フォルダ:", bg="#f8f9fa").grid(row=2, column=0, sticky="w", pady=3)
        destination_entry = tk.Entry(path_frame, width=38, font=("Consolas", 9))
        destination_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        destination_entry.insert(0, comp.get("destination_path", ""))
        path_frame.grid_columnconfigure(1, weight=1)

        def browse_source_path():
            if act_var.get() == "copy_folder":
                path = filedialog.askdirectory(parent=diag, title="コピー元フォルダを選択")
            else:
                path = filedialog.askopenfilename(parent=diag, title="コピー元ファイルを選択")
            if path:
                source_entry.delete(0, tk.END)
                source_entry.insert(0, path)

        def browse_destination_path():
            path = filedialog.askdirectory(parent=diag, title="コピー先フォルダを選択")
            if path:
                destination_entry.delete(0, tk.END)
                destination_entry.insert(0, path)

        tk.Button(path_frame, text="参照...", command=browse_source_path).grid(row=1, column=2, padx=4)
        tk.Button(path_frame, text="参照...", command=browse_destination_path).grid(row=2, column=2, padx=4)

        def scroll_action_list(event):
            if getattr(event, "num", None) == 4:
                units = -3
            elif getattr(event, "num", None) == 5:
                units = 3
            else:
                delta = getattr(event, "delta", 0)
                if not delta:
                    return "break"
                units = -int(delta / 120)
                if units == 0:
                    units = -1 if delta > 0 else 1
            act_canvas.yview_scroll(units, "units")
            return "break"

        def bind_action_scroll(widget):
            widget.bind("<MouseWheel>", scroll_action_list)
            widget.bind("<Button-4>", scroll_action_list)
            widget.bind("<Button-5>", scroll_action_list)
            for child in widget.winfo_children():
                bind_action_scroll(child)

        bind_action_scroll(f_act)
    else:
        act_var = tk.StringVar(value="none")
        param_entry = None
        source_entry = None
        destination_entry = None
        close_after_var = None
        browser_var = None
        browser_window_mode_var = None
        tk.Label(tab_action, text="ラベルや入力欄にはアクションを設定できません。",
                 bg="#f8f9fa", fg="#6c757d", font=("Meiryo UI", 10)).pack(padx=20, pady=20)

    def save_config():
        if bg_entry.get().strip().lower() != comp["bg_color"].lower():
            comp["custom_background"] = True
        if fg_entry.get().strip().lower() != comp["fg_color"].lower():
            comp["custom_foreground"] = True
        selected_action = act_var.get()
        if selected_action in ("copy_file", "copy_folder"):
            source_path = source_entry.get().strip()
            destination_path = destination_entry.get().strip()
            if not source_path or not destination_path:
                messagebox.showwarning(
                    "コピー設定が必要です",
                    "コピー元とコピー先フォルダを設定してください。",
                    parent=diag,
                )
                return
            if selected_action == "copy_file" and not os.path.isfile(source_path):
                messagebox.showerror("設定エラー", "コピー元ファイルが見つかりません。", parent=diag)
                return
            if selected_action == "copy_folder" and not os.path.isdir(source_path):
                messagebox.showerror("設定エラー", "コピー元フォルダが見つかりません。", parent=diag)
                return
            if not os.path.isdir(destination_path):
                messagebox.showerror("設定エラー", "コピー先フォルダが見つかりません。", parent=diag)
                return

        comp["text"] = txt_entry.get().strip()
        comp["bg_color"] = bg_entry.get().strip() or "#e8e8e8"
        comp["fg_color"] = fg_entry.get().strip() or "#000000"
        try:
            comp["font_size"] = int(size_spin.get())
        except Exception:
            comp["font_size"] = 10
        comp["action"] = act_var.get()
        if param_entry:
            comp["param"] = param_entry.get().strip()
        if close_after_var:
            comp["close_after_action"] = bool(close_after_var.get())
        if browser_var:
            comp["browser_choice"] = browser_var.get()
        if browser_window_mode_var:
            comp["browser_window_mode"] = browser_window_mode_var.get()
        if source_entry:
            comp["source_path"] = source_entry.get().strip()
            comp["destination_path"] = destination_entry.get().strip()
        try:
            if comp["type"] == "Entry":
                comp["inner"].config(bg=comp["bg_color"], fg=comp["fg_color"], font=("Meiryo UI", comp["font_size"]))
            else:
                comp["inner"].config(text=comp["text"], bg=comp["bg_color"], fg=comp["fg_color"],
                                     font=("Meiryo UI", comp["font_size"]))
        except Exception:
            pass
        messagebox.showinfo("保存完了", "部品の設定を更新しました！")
        diag.destroy()

    tk.Button(bottom_frame, text="💾 設定を保存して決定する", command=save_config,
              bg="#198754", fg="white", font=("Meiryo UI", 11, "bold"),
              padx=15, pady=8, cursor="hand2").pack(fill="x")

    def center_properties_dialog(event=None):
        diag.update_idletasks()
        dialog_width = diag.winfo_width()
        dialog_height = diag.winfo_height()
        screen_x = max(0, (diag.winfo_screenwidth() - dialog_width) // 2)
        screen_y = max(0, (diag.winfo_screenheight() - dialog_height) // 2)
        diag.geometry(f"640x620+{screen_x}+{screen_y}")

    diag.bind("<Map>", lambda event: diag.after_idle(center_properties_dialog), add="+")
    center_properties_dialog()
    diag.after(50, center_properties_dialog)
    diag.after(50, diag.lift)

def delete_component():
    global selected_component
    if selected_component:
        selected_component["wrapper"].destroy()
        designer_components.remove(selected_component)
        selected_component = None
    else:
        messagebox.showwarning("注意", "削除する部品を選択してください。")

def clear_designer():
    global selected_component
    if not designer_components:
        return
    if not messagebox.askyesno("フォームを全消去", "配置した部品をすべて削除しますか？"):
        return
    for comp in designer_components:
        comp["wrapper"].destroy()
    designer_components.clear()
    selected_component = None

def generate_code_from_designer():
    missing_copy_settings = [
        comp for comp in designer_components
        if comp["type"] == "Button"
        and comp["action"] in ("copy_file", "copy_folder")
        and (not comp.get("source_path", "").strip() or not comp.get("destination_path", "").strip())
    ]
    if missing_copy_settings:
        messagebox.showwarning(
            "コピー設定が必要です",
            "コピー操作のボタンは、詳細設定でコピー元とコピー先フォルダを設定してください。",
        )
        top_notebook.select(tab_designer)
        return

    if form_pos_mode == "center":
        geometry_code = (
            f"root.geometry('{form_window_width}x{form_window_height}')\n"
            f"root.update_idletasks()\n"
            f"sw = root.winfo_screenwidth()\n"
            f"sh = root.winfo_screenheight()\n"
            f"x = (sw - {form_window_width}) // 2\n"
            f"y = (sh - {form_window_height}) // 2\n"
            f"root.geometry(f'{form_window_width}x{form_window_height}+{{x}}+{{y}}')"
        )
    else:
        geometry_code = f"root.geometry('{form_window_width}x{form_window_height}+{form_pos_x}+{form_pos_y}')"

    actions = {
        comp["action"] for comp in designer_components
        if comp["type"] == "Button"
    }
    browser_actions = {
        "open_url", "open_x", "open_abema", "google_search",
        "youtube_search", "google_translate", "google_maps",
    }
    needs_browser = bool(actions & browser_actions)
    browser_configs = {
        (comp.get("browser_choice", "既定のブラウザ"), comp.get("browser_window_mode", "最大化"))
        for comp in designer_components
        if comp["type"] == "Button" and comp["action"] in browser_actions
    }
    simple_browser = browser_configs == {("既定のブラウザ", "最大化")}
    imports = ["import tkinter as tk"]
    if actions & {
        "copy_file", "copy_folder", "move_file", "delete_file",
        "create_folder", "create_text_file", "open_folder",
        "open_file_default", "open_desktop", "open_documents",
        "open_downloads", "open_explorer", "open_notepad", "open_calc",
        "open_terminal",
    } or needs_browser:
        imports.append("import os")
    if actions & {
        "copy_file", "copy_folder", "move_file", "delete_file",
        "create_folder", "create_text_file", "show_msg", "ask_yesno",
        "copy_clipboard", "copy_time", "show_time", "random_num",
        "dice_roll", "omikuji", "gen_password",
    } or needs_browser:
        imports.append("from tkinter import messagebox")
    if actions & {
        "move_file", "delete_file", "create_folder", "create_text_file",
        "open_folder", "open_file_default",
    }:
        imports.append("from tkinter import filedialog")
    if actions & {"copy_file", "copy_folder", "move_file"} or (needs_browser and not simple_browser):
        imports.append("import shutil")
    if actions & {
        "open_folder", "open_file_default", "open_explorer", "open_notepad",
        "open_calc", "open_terminal",
    } or (needs_browser and not simple_browser):
        imports.append("import subprocess")
    if needs_browser:
        imports.append("import webbrowser")
        if not simple_browser:
            imports.append("import time")
    if actions & {"google_search", "youtube_search", "google_translate", "google_maps"}:
        imports.append("import urllib.parse")
    if actions & {"copy_time", "show_time"}:
        imports.append("import datetime")
    if actions & {"random_num", "dice_roll", "omikuji", "gen_password"}:
        imports.append("import random")
    if "beep" in actions:
        imports.extend([
            "try:",
            "    import winsound",
            "except ImportError:",
            "    winsound = None",
        ])

    code = [
        *imports,
        "",
        "root = tk.Tk()",
        "root.title('作成したフォームアプリ')",
        f"root.configure(bg={form_bg_color!r})",
        f"root.option_add('*Foreground', {form_fg_color!r})",
        geometry_code,
        "",
        "def open_browser(url, browser_choice, browser_window_mode):",
        "    browser_programs = {",
        "        'Microsoft Edge': ('msedge.exe', 'Microsoft/Edge/Application/msedge.exe'),",
        "        'Google Chrome': ('chrome.exe', 'Google/Chrome/Application/chrome.exe'),",
        "        'Mozilla Firefox': ('firefox.exe', 'Mozilla Firefox/firefox.exe'),",
        "        'Brave': ('brave.exe', 'BraveSoftware/Brave-Browser/Application/brave.exe'),",
        "    }",
        "    browser_executables = {",
        "        '既定のブラウザ': {'msedge.exe', 'chrome.exe', 'firefox.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe'},",
        "        'Microsoft Edge': {'msedge.exe'},",
        "        'Google Chrome': {'chrome.exe'},",
        "        'Mozilla Firefox': {'firefox.exe'},",
        "        'Brave': {'brave.exe'},",
        "    }",
        "    try:",
        "        if os.name == 'nt':",
        "            import ctypes",
        "            from ctypes import wintypes",
        "            user32 = ctypes.windll.user32",
        "            kernel32 = ctypes.windll.kernel32",
        "            user32.AllowSetForegroundWindow(-1)",
        "        root.iconify()",
        "        root.update_idletasks()",
        "        if browser_choice == '既定のブラウザ':",
        "            opened = webbrowser.open(url, new=2)",
        "        elif os.name == 'nt':",
        "            executable, relative_path = browser_programs[browser_choice]",
        "            browser_path = shutil.which(executable)",
        "            if not browser_path:",
        "                for install_root in (os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('LOCALAPPDATA')):",
        "                    if install_root:",
        "                        candidate = os.path.join(install_root, *relative_path.split('/'))",
        "                        if os.path.isfile(candidate):",
        "                            browser_path = candidate",
        "                            break",
        "            if not browser_path:",
        "                raise FileNotFoundError(f'{browser_choice}が見つかりません。')",
        "            subprocess.Popen([browser_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
        "            opened = True",
        "        else:",
        "            browser_aliases = {'Microsoft Edge': 'edge', 'Google Chrome': 'chrome', 'Mozilla Firefox': 'firefox', 'Brave': 'chrome'}",
        "            opened = webbrowser.get(browser_aliases[browser_choice]).open(url, new=2)",
        "        if not opened:",
        "            raise RuntimeError('ブラウザを起動できませんでした。')",
        "        if os.name == 'nt':",
        "            expected_names = browser_executables.get(browser_choice, browser_executables['既定のブラウザ'])",
        "            enum_callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)",
        "            user32.IsWindowVisible.argtypes = [wintypes.HWND]",
        "            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]",
        "            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]",
        "            kernel32.OpenProcess.restype = wintypes.HANDLE",
        "            kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]",
        "            kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL",
        "            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]",
        "            user32.EnumWindows.argtypes = [enum_callback_type, wintypes.LPARAM]",
        "            user32.EnumWindows.restype = wintypes.BOOL",
        "            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]",
        "            user32.BringWindowToTop.argtypes = [wintypes.HWND]",
        "            user32.SetForegroundWindow.argtypes = [wintypes.HWND]",
        "            user32.GetForegroundWindow.restype = wintypes.HWND",
        "            class WorkArea(ctypes.Structure):",
        "                _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]",
        "            user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.POINTER(WorkArea), wintypes.UINT]",
        "            user32.SystemParametersInfoW.restype = wintypes.BOOL",
        "            user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]",
        "            user32.GetSystemMetrics.argtypes = [ctypes.c_int]",
        "            user32.GetSystemMetrics.restype = ctypes.c_int",
        "            for _ in range(50):",
        "                browser_windows = []",
        "                def collect_browser_windows(hwnd, _lparam):",
        "                    if not user32.IsWindowVisible(hwnd):",
        "                        return True",
        "                    process_id = wintypes.DWORD()",
        "                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))",
        "                    process_handle = kernel32.OpenProcess(0x1000, False, process_id.value)",
        "                    if process_handle:",
        "                        try:",
        "                            executable_path = ctypes.create_unicode_buffer(1024)",
        "                            path_length = wintypes.DWORD(len(executable_path))",
        "                            if kernel32.QueryFullProcessImageNameW(process_handle, 0, executable_path, ctypes.byref(path_length)):",
        "                                if os.path.basename(executable_path.value).lower() in expected_names:",
        "                                    browser_windows.append(hwnd)",
        "                        finally:",
        "                            kernel32.CloseHandle(process_handle)",
        "                    return True",
        "                callback = enum_callback_type(collect_browser_windows)",
        "                user32.EnumWindows(callback, 0)",
        "                for browser_window in browser_windows:",
        "                    if browser_window_mode == '最大化':",
        "                        user32.ShowWindow(browser_window, 3)",
        "                    else:",
        "                        user32.ShowWindow(browser_window, 9)",
        "                        work_area = WorkArea()",
        "                        if user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0):",
        "                            area_left, area_top = work_area.left, work_area.top",
        "                            area_width, area_height = work_area.right - work_area.left, work_area.bottom - work_area.top",
        "                        else:",
        "                            area_left, area_top = 0, 0",
        "                            area_width, area_height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)",
        "                        half_width = area_width // 2",
        "                        if browser_window_mode == '左半分':",
        "                            window_x, window_width = area_left, half_width",
        "                        else:",
        "                            window_x, window_width = area_left + half_width, area_width - half_width",
        "                        user32.MoveWindow(browser_window, window_x, area_top, window_width, area_height, True)",
        "                    user32.BringWindowToTop(browser_window)",
        "                    user32.SetForegroundWindow(browser_window)",
        "                    if user32.GetForegroundWindow() == browser_window:",
        "                        return True",
        "                time.sleep(0.1)",
        "            raise RuntimeError(f'{browser_choice}を最前面に表示できませんでした。')",
        "        return True",
        "    except Exception as e:",
        "        error = str(e)",
        "    root.deiconify()",
        "    root.lift()",
        "    root.focus_force()",
        "    messagebox.showerror('ブラウザ起動エラー', error, parent=root)",
        "    return False",
        ""
    ]

    browser_start = code.index("def open_browser(url, browser_choice, browser_window_mode):")
    browser_end = code.index("", browser_start)
    if not needs_browser:
        del code[browser_start:browser_end + 1]
    elif simple_browser:
        code[browser_start:browser_end + 1] = [
            "def open_browser(url):",
            "    try:",
            "        root.iconify()",
            "        if os.name == 'nt':",
            "            import ctypes",
            "            shell_execute = ctypes.windll.shell32.ShellExecuteW",
            "            shell_execute.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]",
            "            shell_execute.restype = ctypes.c_void_p",
            "            result = shell_execute(None, 'open', url, None, None, 3)",
            "            if not result or result <= 32:",
            "                raise OSError('ブラウザを起動できませんでした。')",
            "        elif not webbrowser.open(url, new=2):",
            "            raise RuntimeError('ブラウザを起動できませんでした。')",
            "        return True",
            "    except Exception as e:",
            "        root.deiconify()",
            "        root.lift()",
            "        root.focus_force()",
            "        messagebox.showerror('ブラウザ起動エラー', str(e), parent=root)",
            "        return False",
            "",
        ]

    for i, comp in enumerate(designer_components):
        w = comp["wrapper"]
        x, y = w.winfo_x(), w.winfo_y()
        width, height = w.winfo_width(), w.winfo_height()
        ctype, act, param, label_text = comp["type"], comp["action"], comp["param"], comp["text"]
        source_path = comp.get("source_path", "").strip()
        destination_path = comp.get("destination_path", "").strip()
        browser_choice = comp.get("browser_choice", "既定のブラウザ")
        browser_window_mode = comp.get("browser_window_mode", "最大化")
        browser_call_args = "" if simple_browser else f", {browser_choice!r}, {browser_window_mode!r}"
        bg, fg, f_size = comp["bg_color"], comp["fg_color"], comp["font_size"]
        font_str = f"('Meiryo UI', {f_size})"

        if ctype == "Button":
            if act != "none":
                code.append(f"def on_btn_{i}_click():")
                if act == "close_app":
                    code.append("    root.destroy()")
                elif act == "copy_file":
                    code.append(f"    src = {source_path!r}")
                    code.append("    if not src: return")
                    code.append(f"    dest = {destination_path!r}")
                    code.append("    if not dest: return")
                    code.append("    try:")
                    code.append("        shutil.copy2(src, dest)")
                    code.append("        messagebox.showinfo('完了', f'ファイルをコピーしました\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('エラー', str(e))")
                    code.append("        return")
                elif act == "copy_folder":
                    code.append(f"    src = {source_path!r}")
                    code.append("    if not src: return")
                    code.append(f"    dest_parent = {destination_path!r}")
                    code.append("    if not dest_parent: return")
                    code.append("    dest = os.path.join(dest_parent, os.path.basename(src))")
                    code.append("    try:")
                    code.append("        source_real = os.path.normcase(os.path.realpath(src))")
                    code.append("        destination_real = os.path.normcase(os.path.realpath(dest))")
                    code.append("        try:")
                    code.append("            copies_into_source = os.path.commonpath([source_real, destination_real]) == source_real")
                    code.append("        except ValueError:")
                    code.append("            copies_into_source = False")
                    code.append("        if copies_into_source:")
                    code.append("            raise ValueError('コピー先をコピー元フォルダ自身または内部には設定できません。')")
                    code.append("        if os.path.exists(dest):")
                    code.append("            if not messagebox.askyesno('確認', '同じ名前のフォルダがあります。中身を上書き・統合しますか？', parent=root): return")
                    code.append("        shutil.copytree(src, dest, dirs_exist_ok=True)")
                    code.append("        messagebox.showinfo('完了', f'フォルダをコピーしました\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('エラー', str(e))")
                    code.append("        return")
                elif act == "move_file":
                    code.append("    src = filedialog.askopenfilename(parent=root, title='移動するファイルを選択', initialdir=os.getcwd())")
                    code.append("    if not src: return")
                    code.append("    dest = filedialog.askdirectory(parent=root, title='移動先フォルダを選択', initialdir=os.path.dirname(src))")
                    code.append("    if not dest: return")
                    code.append("    try:")
                    code.append("        shutil.move(src, dest)")
                    code.append("        messagebox.showinfo('完了', f'ファイルを移動しました\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('エラー', str(e))")
                elif act == "delete_file":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='削除するファイルを選択', initialdir=os.getcwd())")
                    code.append("    if not path: return")
                    code.append("    if messagebox.askyesno('確認', f'本当に削除しますか？\\n{os.path.basename(path)}', parent=root):")
                    code.append("        try:")
                    code.append("            os.remove(path)")
                    code.append("            messagebox.showinfo('完了', 'ファイルを削除しました')")
                    code.append("        except Exception as e:")
                    code.append("            messagebox.showerror('エラー', str(e))")
                elif act == "open_folder":
                    code.append("    path = filedialog.askdirectory(parent=root, title='開くフォルダを選択', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "open_file_default":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='開くファイルを選択', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "create_folder":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='作成する場所を選択', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    new_name = '新しいフォルダ'")
                    code.append("    path = os.path.join(parent, new_name)")
                    code.append("    try:")
                    code.append("        os.makedirs(path, exist_ok=True)")
                    code.append("        messagebox.showinfo('完了', f'フォルダを作成しました\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('エラー', str(e))")
                elif act == "create_text_file":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='作成する場所を選択', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    path = os.path.join(parent, '新しいテキスト.txt')")
                    code.append("    try:")
                    code.append("        with open(path, 'w', encoding='utf-8') as f:")
                    code.append("            f.write('')")
                    code.append("        messagebox.showinfo('完了', f'テキストファイルを作成しました\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('エラー', str(e))")
                elif act == "open_desktop":
                    code.append("    path = os.path.join(os.path.expanduser('~'), 'Desktop')")
                    code.append("    if not os.path.exists(path): path = os.path.expanduser('~')")
                    code.append("    os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "open_documents":
                    code.append("    path = os.path.join(os.path.expanduser('~'), 'Documents')")
                    code.append("    if not os.path.exists(path): path = os.path.expanduser('~')")
                    code.append("    os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "open_downloads":
                    code.append("    path = os.path.join(os.path.expanduser('~'), 'Downloads')")
                    code.append("    if not os.path.exists(path): path = os.path.expanduser('~')")
                    code.append("    os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "open_explorer":
                    code.append("    if os.name == 'nt':")
                    code.append("        subprocess.Popen('explorer')")
                    code.append("    else:")
                    code.append("        subprocess.Popen(['xdg-open', os.path.expanduser('~')])")
                elif act == "open_url":
                    code.append(f"    if not open_browser({(param or 'https://www.google.com')!r}{browser_call_args}): return")
                elif act == "open_x":
                    code.append(f"    if not open_browser('https://x.com/'{browser_call_args}): return")
                elif act == "open_abema":
                    code.append(f"    if not open_browser('https://abema.tv/'{browser_call_args}): return")
                elif act == "google_search":
                    code.append(f"    if not open_browser('https://www.google.com/search?q=' + urllib.parse.quote({param!r}){browser_call_args}): return")
                elif act == "youtube_search":
                    code.append(f"    if not open_browser('https://www.youtube.com/results?search_query=' + urllib.parse.quote({param!r}){browser_call_args}): return")
                elif act == "google_translate":
                    code.append(f"    if not open_browser('https://translate.google.co.jp/?hl=ja&sl=auto&tl=ja&text=' + urllib.parse.quote({param!r}){browser_call_args}): return")
                elif act == "google_maps":
                    code.append(f"    if not open_browser('https://www.google.com/maps/search/' + urllib.parse.quote({param!r}){browser_call_args}): return")
                elif act == "show_msg":
                    code.append(f"    messagebox.showinfo('通知', {(param or 'こんにちは！')!r})")
                elif act == "ask_yesno":
                    code.append(f"    res = messagebox.askyesno('確認', {(param or '実行しますか？')!r})")
                    code.append("    messagebox.showinfo('結果', f'選択結果: {res}')")
                elif act == "copy_clipboard":
                    code.append("    root.clipboard_clear()")
                    code.append(f"    root.clipboard_append({param!r})")
                    code.append("    messagebox.showinfo('コピー', 'クリップボードにコピーしました')")
                elif act == "copy_time":
                    code.append("    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')")
                    code.append("    root.clipboard_clear()")
                    code.append("    root.clipboard_append(now)")
                    code.append("    messagebox.showinfo('コピー', f'現在時刻をコピーしました\\n{now}')")
                elif act == "show_time":
                    code.append("    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')")
                    code.append("    messagebox.showinfo('現在時刻', f'いまの時間: {now}')")
                elif act == "open_notepad":
                    code.append("    if os.name == 'nt':")
                    code.append("        subprocess.Popen('notepad.exe')")
                    code.append("    else:")
                    code.append("        subprocess.Popen(['gedit'])")
                elif act == "open_calc":
                    code.append("    if os.name == 'nt':")
                    code.append("        subprocess.Popen('calc.exe')")
                    code.append("    else:")
                    code.append("        subprocess.Popen(['gnome-calculator'])")
                elif act == "open_terminal":
                    code.append("    if os.name == 'nt':")
                    code.append("        subprocess.Popen('cmd.exe')")
                    code.append("    else:")
                    code.append("        subprocess.Popen(['x-terminal-emulator'])")
                elif act == "beep":
                    code.append("    if winsound:")
                    code.append("        winsound.Beep(1000, 300)")
                    code.append("    else:")
                    code.append("        print('\\a')")
                elif act == "random_num":
                    code.append("    n = random.randint(1, 100)")
                    code.append("    messagebox.showinfo('くじ引き', f'出た数字: {n}')")
                elif act == "dice_roll":
                    code.append("    d = random.randint(1, 6)")
                    code.append("    messagebox.showinfo('サイコロ', f'出た目: 🎲 {d}')")
                elif act == "omikuji":
                    code.append("    omi = random.choice(['大吉 ✨', '中吉 🌟', '小吉 👍', '吉 😊', '凶 💦'])")
                    code.append("    messagebox.showinfo('おみくじ', f'今日の運勢: {omi}')")
                elif act == "gen_password":
                    code.append("    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$*'")
                    code.append("    pwd = ''.join(random.choices(chars, k=12))")
                    code.append("    messagebox.showinfo('パスワード生成', f'生成されたパスワード:\\n{pwd}')")
                if comp.get("close_after_action", True) and act != "close_app":
                    code.append("    root.destroy()")
                code.append("")
                cmd_str = f", command=on_btn_{i}_click"
            else:
                cmd_str = ""

            code.append(f"btn_{i} = tk.Button(root, text={label_text!r}, bg={bg!r}, fg={fg!r}, font={font_str}{cmd_str})")
            code.append(f"btn_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Label":
            code.append(f"lbl_{i} = tk.Label(root, text={label_text!r}, bg={bg!r}, fg={fg!r}, font={font_str})")
            code.append(f"lbl_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Entry":
            code.append(f"ent_{i} = tk.Entry(root, bg={bg!r}, fg={fg!r}, font={font_str})")
            code.append(f"ent_{i}.place(x={x}, y={y}, width={width}, height={height})")

    code.extend(["", "root.mainloop()"])
    if text.get("1.0", tk.END).strip():
        if not messagebox.askyesno("上書き確認", "エディターの内容を生成コードで置き換えますか？"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", "\n".join(code) + "\n")
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    messagebox.showinfo("生成完了", "フォームのコードでエディター内容を置き換えました！\nファイル操作系は実行時に選択画面が出ます。")

# ツールバーボタン
def add_designer_toolbar_button(label, command, bg, fg="white", active_bg=None):
    options = {
        "text": label, "command": command, "bg": bg, "fg": fg,
        "relief": "flat", "font": ("Meiryo UI", 9, "bold"),
        "width": 12, "height": 2, "wraplength": 100,
        "padx": 6, "pady": 5, "cursor": "hand2",
    }
    if active_bg:
        options["activebackground"] = active_bg
        options["activeforeground"] = fg
    tk.Button(designer_toolbar, **options).pack(side="left", padx=3)

add_designer_toolbar_button("＋ ボタン", lambda: add_component("Button"), "#1769aa", active_bg="#12558a")
add_designer_toolbar_button("＋ ラベル", lambda: add_component("Label"), "#0f766e", active_bg="#0b5c56")
add_designer_toolbar_button("＋ 入力欄", lambda: add_component("Entry"), "#3a7d44", active_bg="#2d6335")
add_designer_toolbar_button("⚙ ウィンドウ位置", open_window_position_dialog, "#6610f2")
add_designer_toolbar_button("⚙ 詳細設定", lambda: open_properties_dialog(selected_component) if selected_component else messagebox.showwarning("注意", "部品を選んでください"), "#ffc107", fg="#000")
add_designer_toolbar_button("🗑 削除", delete_component, "#dc3545")
add_designer_toolbar_button("🧹 全消去", clear_designer, "#6c757d")
add_designer_toolbar_button("📝 コード生成して転送", generate_code_from_designer, "#0d6efd")


# ---------- タブ4：ツール ----------
tools_frame = tk.Frame(tab_tools, bg=THEMES[current_theme]['bg'], padx=20, pady=20)
tools_frame.pack(expand=True, fill="both")
tk.Label(tools_frame, text="🛠 開発環境およびツール管理",
         font=("Meiryo UI", 12, "bold"), bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=(0, 10))
tk.Label(tools_frame, text=f"Python 実行パス: {sys.executable}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
virtualenv_path_display = tk.StringVar(value=f"モジュール用仮想環境: {get_virtualenv_path()}")
tk.Label(tools_frame, textvariable=virtualenv_path_display, font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"設定保存フォルダ: {SETTINGS_FOLDER}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"OS: {platform.system()} {platform.release()}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)

mod_frame = tk.LabelFrame(tools_frame, text=" 📦 外部モジュールのインストール ",
                          bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                          font=("Meiryo UI", 10, "bold"), padx=15, pady=12)
mod_frame.pack(anchor="w", fill="x", pady=15)
tk.Label(mod_frame, text="モジュール名 (例: requests):", bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 9)).pack(side="left", padx=(0, 10))
mod_entry = tk.Entry(mod_frame, width=20, font=("Consolas", 10))
mod_entry.pack(side="left", padx=5)

def install_custom_module():
    mname = mod_entry.get().strip()
    if not mname:
        messagebox.showwarning("注意", "インストールするモジュール名を入力してください。")
        return
    try:
        python_executable = get_virtualenv_python()
        res = subprocess.run([python_executable, "-m", "pip", "install", mname],
                             capture_output=True, text=True, timeout=90)
        if res.returncode == 0:
            messagebox.showinfo("インストール成功", f"モジュール '{mname}' のインストールが完了しました！")
        else:
            messagebox.showerror("エラー", f"インストールに失敗しました:\n{res.stderr[:500]}")
    except Exception as e:
        messagebox.showerror("エラー", f"エラーが発生しました:\n{e}")

tk.Button(mod_frame, text="pip install 実行", command=install_custom_module,
          bg="#198754", fg="white", relief="flat", font=("Meiryo UI", 9, "bold"),
          padx=10, pady=4).pack(side="left", padx=15)

def open_settings_dialog():
    dialog = tk.Toplevel(root)
    dialog.title("設定")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    timeout_value = tk.StringVar(value=str(test_timeout_seconds))
    virtualenv_path_value = tk.StringVar(value=get_virtualenv_path())
    content = tk.Frame(dialog, padx=20, pady=18)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="テストランのタイムアウト", font=("Meiryo UI", 10, "bold")).grid(
        row=0, column=0, sticky="w", padx=(0, 12), pady=6
    )
    ttk.Spinbox(content, from_=1, to=3600, increment=1, textvariable=timeout_value,
                width=8).grid(row=0, column=1, sticky="w", pady=6)
    tk.Label(content, text="秒（1〜3600秒）").grid(row=0, column=2, sticky="w", padx=(6, 0))

    tk.Label(content, text="仮想環境の保存先", font=("Meiryo UI", 10, "bold")).grid(
        row=1, column=0, sticky="w", padx=(0, 12), pady=6
    )
    ttk.Entry(content, textvariable=virtualenv_path_value, width=52).grid(
        row=1, column=1, columnspan=2, sticky="ew", pady=6
    )

    def browse_virtualenv_path():
        current_path = virtualenv_path_value.get()
        initial_directory = current_path if os.path.isdir(current_path) else os.path.dirname(current_path)
        if not os.path.isdir(initial_directory):
            initial_directory = get_desktop_path()
        selected_path = filedialog.askdirectory(
            parent=dialog,
            title="仮想環境の保存先を選択",
            initialdir=initial_directory,
            mustexist=False
        )
        if selected_path:
            virtualenv_path_value.set(selected_path)

    ttk.Button(content, text="参照...", command=browse_virtualenv_path).grid(
        row=1, column=3, padx=(8, 0), pady=6
    )

    def save_settings_dialog():
        global test_timeout_seconds, VIRTUALENV_PATH
        try:
            timeout = int(timeout_value.get())
        except ValueError:
            messagebox.showerror("入力エラー", "タイムアウトは整数で入力してください。", parent=dialog)
            return
        if not 1 <= timeout <= 3600:
            messagebox.showerror("入力エラー", "1〜3600秒の範囲で入力してください。", parent=dialog)
            return
        selected_path = virtualenv_path_value.get().strip()
        if not selected_path:
            messagebox.showerror("入力エラー", "仮想環境の保存先を指定してください。", parent=dialog)
            return
        test_timeout_seconds = timeout
        VIRTUALENV_PATH = os.path.abspath(os.path.expanduser(selected_path))
        save_settings()
        virtualenv_path_display.set(f"モジュール用仮想環境: {get_virtualenv_path()}")
        dialog.destroy()
        messagebox.showinfo("設定", "設定を保存しました。", parent=root)

    buttons = tk.Frame(content)
    buttons.grid(row=2, column=0, columnspan=4, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="キャンセル", command=dialog.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(buttons, text="保存", command=save_settings_dialog).pack(side="right")
    dialog.bind("<Return>", lambda event: save_settings_dialog())


# メニューバー
menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="新規作成", command=new_file)
file_menu.add_command(label="ファイルを開く", command=open_file)
file_menu.add_separator()
file_menu.add_command(label="上書き保存 (Ctrl+S)", command=quick_save)
file_menu.add_command(label="名前を付けて保存", command=save_as_file)
file_menu.add_separator()
file_menu.add_command(label="終了", command=safe_exit)
menubar.add_cascade(label="ファイル", menu=file_menu)

edit_menu = tk.Menu(menubar, tearoff=0)
edit_menu.add_command(label="元に戻す (Ctrl+Z)", command=undo_action)
edit_menu.add_command(label="やり直し (Ctrl+Y)", command=redo_action)
edit_menu.add_separator()
edit_menu.add_command(label="検索 (Ctrl+F)", command=open_search_dialog)
edit_menu.add_command(label="全選択 (Ctrl+A)", command=select_all)
menubar.add_cascade(label="編集", menu=edit_menu)

settings_menu = tk.Menu(menubar, tearoff=0)
settings_menu.add_command(label="設定...", command=open_settings_dialog)
menubar.add_cascade(label="設定", menu=settings_menu)

root.config(menu=menubar)

apply_theme(current_theme)
update_line_numbers()
update_status_bar()
root.protocol("WM_DELETE_WINDOW", safe_exit)
root.mainloop()

