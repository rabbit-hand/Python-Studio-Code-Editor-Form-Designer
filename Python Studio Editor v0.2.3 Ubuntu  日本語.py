#!/usr/bin/env python3

import sys
try:
    import tkinter as tk
    from tkinter import messagebox, filedialog, colorchooser, ttk
except ModuleNotFoundError as error:
    if error.name not in {"tkinter", "_tkinter"}:
        raise
    print(
        "Tkinterが見つかりません。Ubuntu系Linuxでは "
        "「sudo apt install python3-tk python3-venv」を実行してください。",
        file=sys.stderr,
    )
    raise SystemExit(1) from error
import subprocess
import re
from threading import Thread
import tempfile
import os
import json
import platform
import shutil

# Version
APP_VERSION = "0.2.3"

# 設定
SETTINGS_FOLDER = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")),
    "python-studio-editor",
)
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
def get_desktop_path():
    try:
        result = subprocess.run(
            ["xdg-user-dir", "DESKTOP"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        desktop_path = os.path.expanduser(result.stdout.strip())
        if desktop_path and os.path.isabs(desktop_path):
            return desktop_path
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")

VIRTUALENV_PATH = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")),
    "python-studio-editor",
    "project-venv",
)

def build_hotkey_runtime_source(actions):
    return [
        f"HOTKEY_ACTIONS = {actions!r}",
        "",
        "def normalize_hotkey(shortcut):",
        "    aliases = {'control': 'ctrl', 'windows': 'cmd', 'win': 'cmd', 'super': 'cmd', 'return': 'enter', 'escape': 'esc'}",
        "    parts = [part.strip().lower() for part in shortcut.split('+') if part.strip()]",
        "    if not parts:",
        "        raise ValueError('ホットキーが空です。')",
        "    return '+'.join(f'<{aliases.get(part, part)}>' if len(part) > 1 else part for part in parts)",
        "",
        "def send_hotkey_keys(sequence):",
        "    aliases = {'control': 'ctrl', 'windows': 'cmd', 'win': 'cmd', 'super': 'cmd', 'return': 'enter', 'escape': 'esc'}",
        "    names = [aliases.get(part.strip().lower(), part.strip().lower()) for part in sequence.split('+') if part.strip()]",
        "    if not names:",
        "        raise ValueError('送信するキーが空です。')",
        "    special = {'ctrl': pynput_keyboard.Key.ctrl, 'alt': pynput_keyboard.Key.alt, 'shift': pynput_keyboard.Key.shift, 'cmd': pynput_keyboard.Key.cmd}",
        "    keys = []",
        "    for name in names:",
        "        key = special.get(name) or getattr(pynput_keyboard.Key, name, None)",
        "        if key is None and len(name) == 1:",
        "            key = name",
        "        if key is None:",
        "            raise ValueError(f'未対応のキーです: {name}')",
        "        keys.append(key)",
        "    controller = pynput_keyboard.Controller()",
        "    try:",
        "        for key in keys:",
        "            controller.press(key)",
        "    finally:",
        "        for key in reversed(keys):",
        "            controller.release(key)",
        "",
        "def run_hotkey_action(index):",
        "    action = HOTKEY_ACTIONS[index]",
        "    try:",
        "        kind, target = action['kind'], action['target']",
        "        if kind == 'Open URL':",
        "            import webbrowser",
        "            webbrowser.open(target, new=0)",
        "        elif kind == 'Launch app/file':",
        "            executable = shutil.which(target)",
        "            if executable:",
        "                subprocess.Popen([executable], start_new_session=True)",
        "            else:",
        "                subprocess.Popen(['xdg-open', target], start_new_session=True)",
        "        elif kind == 'Run command':",
        "            command = shlex.split(target)",
        "            if not command:",
        "                raise ValueError('実行するコマンドが空です。')",
        "            subprocess.Popen(command, start_new_session=True)",
        "        elif kind == 'Send keys':",
        "            send_hotkey_keys(target)",
        "        elif kind == 'Hide window':",
        "            root.after(0, root.iconify if 'icon' not in globals() else root.withdraw)",
        "        if action['wait']:",
        "            time.sleep(action['wait'])",
        "        if action['followup']:",
        "            send_hotkey_keys(action['followup'])",
        "    except Exception as error:",
        "        root.after(0, lambda error=error: messagebox.showerror('ホットキー', f\"{action['button'] or action['shortcut']}: {error}\", parent=root))",
        "",
        "def start_hotkey_listener():",
        "    shortcuts = {}",
        "    last_triggered = {}",
        "    trigger_lock = threading.Lock()",
        "    def make_callback(index, shortcut):",
        "        def trigger():",
        "            now = time.monotonic()",
        "            with trigger_lock:",
        "                if now - last_triggered.get(shortcut, 0.0) < 1.0:",
        "                    return",
        "                last_triggered[shortcut] = now",
        "            threading.Thread(target=run_hotkey_action, args=(index,), daemon=True).start()",
        "        return trigger",
        "    for index, action in enumerate(HOTKEY_ACTIONS):",
        "        if action['shortcut']:",
        "            shortcut = normalize_hotkey(action['shortcut'])",
        "            shortcuts[shortcut] = make_callback(index, shortcut)",
        "    if not shortcuts:",
        "        return None",
        "    if pynput_keyboard is None:",
        "        messagebox.showwarning('ホットキーを登録できません', 'pynputがインストールされていません。ボタン操作は引き続き使用できます。', parent=root)",
        "        return None",
        "    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland' or os.environ.get('WAYLAND_DISPLAY'):",
        "        messagebox.showwarning('ホットキーの制限', 'Waylandではアプリから全体ホットキーを登録できません。ボタン操作は使用できます。必要な場合はデスクトップ環境のショートカット設定から登録してください。', parent=root)",
        "        return None",
        "    try:",
        "        hotkeys = [pynput_keyboard.HotKey(pynput_keyboard.HotKey.parse(shortcut), callback) for shortcut, callback in shortcuts.items()]",
        "        pending_releases = {}",
        "        release_lock = threading.Lock()",
        "        listener = None",
        "",
        "        def on_press(key, injected):",
        "            if injected:",
        "                return",
        "            canonical_key = listener.canonical(key)",
        "            with release_lock:",
        "                repeat_timer = pending_releases.pop(canonical_key, None)",
        "                if repeat_timer is not None:",
        "                    repeat_timer.cancel()",
        "                    return",
        "                for hotkey in hotkeys:",
        "                    hotkey.press(canonical_key)",
        "",
        "        def on_release(key, injected):",
        "            if injected:",
        "                return",
        "            canonical_key = listener.canonical(key)",
        "",
        "            def release_after_repeat_window():",
        "                with release_lock:",
        "                    if pending_releases.get(canonical_key) is timer:",
        "                        del pending_releases[canonical_key]",
        "                        for hotkey in hotkeys:",
        "                            hotkey.release(canonical_key)",
        "",
        "            timer = threading.Timer(0.1, release_after_repeat_window)",
        "            timer.daemon = True",
        "            with release_lock:",
        "                previous_timer = pending_releases.get(canonical_key)",
        "                if previous_timer is not None:",
        "                    previous_timer.cancel()",
        "                pending_releases[canonical_key] = timer",
        "            timer.start()",
        "",
        "        listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)",
        "        listener.start()",
        "        return listener",
        "    except (ImportError, OSError, RuntimeError) as error:",
        "        messagebox.showwarning('ホットキーを登録できません', f'{error}\\nボタン操作は引き続き使用できます。', parent=root)",
        "        return None",
        "",
        "def shutdown_app():",
        "    if hotkey_listener is not None:",
        "        hotkey_listener.stop()",
        "    if 'icon' in globals() and icon is not None:",
        "        icon.stop()",
        "    root.destroy()",
        "",
        "def close_combined_window():",
        "    if 'icon' in globals() and icon is not None:",
        "        root.withdraw()",
        "    else:",
        "        shutdown_app()",
        "",
        "root.protocol('WM_DELETE_WINDOW', close_combined_window)",
    ]

def build_hotkey_instance_lock_source():
    return [
        "INSTANCE_LOCK_FILES = []",
        "",
        "def acquire_hotkey_locks():",
        "    if not sys.platform.startswith('linux'):",
        "        return True",
        "    import fcntl",
        "    shortcuts = sorted({normalize_hotkey(action['shortcut']) for action in HOTKEY_ACTIONS if action['shortcut']})",
        "    if not shortcuts:",
        "        return True",
        "    runtime_dir = os.environ.get('XDG_RUNTIME_DIR')",
        "    if not runtime_dir:",
        "        runtime_dir = os.path.join(os.path.expanduser('~'), '.cache', 'python-studio-editor', 'instances')",
        "    os.makedirs(runtime_dir, mode=0o700, exist_ok=True)",
        "    for shortcut in shortcuts:",
        "        lock_name = hashlib.sha256(shortcut.encode('utf-8')).hexdigest()",
        "        lock_file = open(os.path.join(runtime_dir, f'python-studio-hotkey-{lock_name}.lock'), 'a+', encoding='utf-8')",
        "        try:",
        "            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)",
        "        except BlockingIOError:",
        "            lock_file.close()",
        "            for held_lock in reversed(INSTANCE_LOCK_FILES):",
        "                fcntl.flock(held_lock.fileno(), fcntl.LOCK_UN)",
        "                held_lock.close()",
        "            INSTANCE_LOCK_FILES.clear()",
        "            return False",
        "        INSTANCE_LOCK_FILES.append(lock_file)",
        "    return True",
    ]

def add_python_shebang(source):
    source = source.lstrip("\ufeff")
    if source.startswith("#!/usr/bin/env python3"):
        return source
    return "#!/usr/bin/env python3\n" + source

def build_hotkey_app_source(actions, title, width, height):
    source = [
        "import os",
        "import hashlib",
        "import queue",
        "import shlex",
        "import shutil",
        "import subprocess",
        "import sys",
        "import threading",
        "import time",
        "import tkinter as tk",
        "from tkinter import messagebox",
        "",
        "try:",
        "    from pynput import keyboard as pynput_keyboard",
        "except ImportError:",
        "    pynput_keyboard = None",
        "",
        "if sys.platform.startswith('linux') and os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY') and any(name in os.environ.get('XDG_CURRENT_DESKTOP', '').lower() for name in ('cinnamon', 'mate', 'xfce', 'lxde', 'lxqt')):",
        "    os.environ.setdefault('PYSTRAY_BACKEND', 'xorg')",
        "",
        "try:",
        "    import pystray",
        "    from PIL import Image, ImageDraw, ImageFont",
        "    PYSTRAY_AVAILABLE = True",
        "except ImportError:",
        "    PYSTRAY_AVAILABLE = False",
        "",
        f"WINDOW_TITLE = {title!r}",
        f"WINDOW_WIDTH = {width}",
        f"WINDOW_HEIGHT = {height}",
        "",
        "root = tk.Tk()",
        "root.title(WINDOW_TITLE)",
        "root.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}')",
        "icon = None",
        "TRAY_ACTION_QUEUE = queue.SimpleQueue()",
        "",
    ]
    source.extend(build_hotkey_runtime_source(actions))
    source.extend(build_hotkey_instance_lock_source())
    source.extend([
        "",
        "if not acquire_hotkey_locks():",
        "    messagebox.showwarning('ホットキーは起動済みです', '同じホットキーを登録したアプリがすでに起動しています。重複実行を防ぐため終了します。', parent=root)",
        "    root.destroy()",
        "    raise SystemExit(0)",
        "",
        "hotkey_listener = start_hotkey_listener()",
        "",
        "",
        "def restore_window():",
        "    root.deiconify()",
        "    root.lift()",
        "    root.focus_force()",
        "",
        "def on_tray_action(icon, item):",
        "    TRAY_ACTION_QUEUE.put(getattr(item, 'text', ''))",
        "",
        "def process_tray_actions():",
        "    root.after(100, process_tray_actions)",
        "    while not TRAY_ACTION_QUEUE.empty():",
        "        item_text = TRAY_ACTION_QUEUE.get()",
        "        if item_text == 'メニュー':",
        "            show_tray_menu()",
        "        elif item_text == '終了':",
        "            shutdown_app()",
        "        else:",
        "            restore_window()",
        "",
        "def show_tray_menu():",
        "    tray_menu = tk.Menu(root, tearoff=0)",
        "    tray_menu.add_command(label='表示', command=restore_window)",
        "    tray_menu.add_separator()",
        "    tray_menu.add_command(label='終了', command=shutdown_app)",
        "    try:",
        "        tray_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())",
        "    finally:",
        "        tray_menu.grab_release()",
        "",
        "def close_window():",
        "    if icon is not None:",
        "        root.withdraw()",
        "    else:",
        "        shutdown_app()",
        "",
        "for index, action in enumerate(HOTKEY_ACTIONS):",
        "    if action['button']:",
        "        tk.Button(root, text=action['button'], command=lambda i=index: threading.Thread(target=run_hotkey_action, args=(i,), daemon=True).start()).pack(fill='x', padx=8, pady=4)",
        "",
        "root.protocol('WM_DELETE_WINDOW', close_window)",
        "if PYSTRAY_AVAILABLE:",
        "    try:",
        "        tray_image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))",
        "        tray_draw = ImageDraw.Draw(tray_image)",
        "        tray_draw.rectangle((2, 2, 62, 62), fill=(23, 105, 170, 255))",
        "        try:",
        "            tray_font = ImageFont.truetype('DejaVuSans-Bold.ttf', 24)",
        "        except OSError:",
        "            tray_font = ImageFont.load_default()",
        "        tray_bounds = tray_draw.textbbox((0, 0), 'PY', font=tray_font)",
        "        tray_x = (64 - (tray_bounds[2] - tray_bounds[0])) // 2 - tray_bounds[0]",
        "        tray_y = (64 - (tray_bounds[3] - tray_bounds[1])) // 2 - tray_bounds[1]",
        "        tray_draw.text((tray_x, tray_y), 'PY', fill='white', font=tray_font)",
        "        tray_menu = (",
        "            pystray.Menu(pystray.MenuItem('メニュー', on_tray_action, default=True))",
        "            if pystray.Icon.__module__ == 'pystray._xorg'",
        "            else pystray.Menu(",
        "                pystray.MenuItem('表示', on_tray_action, default=True),",
        "                pystray.MenuItem('終了', on_tray_action),",
        "            )",
        "        )",
        "        icon = pystray.Icon('PythonStudio', tray_image, 'Python Studio', menu=tray_menu)",
        "        icon.run_detached()",
        "        root.withdraw()",
        "    except Exception as error:",
        "        messagebox.showwarning('タスクトレイを使用できません', str(error), parent=root)",
        "        icon = None",
        "        root.deiconify()",
        "else:",
        "    messagebox.showwarning('タスクトレイを使用できません', 'タスクトレイ機能には pystray と Pillow が必要です。', parent=root)",
        "",
        "root.after(100, process_tray_actions)",
        "root.mainloop()",
    ])
    return add_python_shebang("\n".join(source) + "\n")

def get_virtualenv_path():
    return VIRTUALENV_PATH

def get_virtualenv_python():
    venv_path = get_virtualenv_path()
    python_path = os.path.join(venv_path, "bin", "python")
    if not os.path.isfile(python_path):
        os.makedirs(os.path.dirname(venv_path), exist_ok=True)
        try:
            subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", venv_path], check=True,
                           capture_output=True, text=True, timeout=120)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e.stderr.strip() or str(e)) from e
    if not os.path.isfile(python_path):
        raise RuntimeError("仮想環境のPythonを作成できませんでした。")
    return python_path

def get_settings_path(filename):
    os.makedirs(SETTINGS_FOLDER, exist_ok=True)
    path = os.path.join(SETTINGS_FOLDER, filename)
    legacy_path = os.path.join(os.path.expanduser("~"), "UltimatePythonIDE_Settings", filename)
    if not os.path.exists(path) and os.path.isfile(legacy_path):
        shutil.copy2(legacy_path, path)
    return path

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
                saved_virtualenv_path = os.path.expanduser(
                    data.get('virtualenv_path') or VIRTUALENV_PATH
                )
                if os.path.isabs(saved_virtualenv_path):
                    VIRTUALENV_PATH = os.path.abspath(saved_virtualenv_path)
                else:
                    VIRTUALENV_PATH = os.path.join(
                        os.environ.get(
                            "XDG_DATA_HOME",
                            os.path.join(os.path.expanduser("~"), ".local", "share"),
                        ),
                        "python-studio-editor",
                        "project-venv",
                    )
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
        except OSError as e:
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
        "category": "モジュール活用例 - ファイルシステム", "name": "ファイルマネージャー", "kind": "code",
        "description": "ファイルとフォルダーを閲覧・操作します。os, pathlib, shutilモジュールを使用。",
        "code": '''import os
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

root = tk.Tk()
root.title("ファイルマネージャー")
root.geometry("900x650")
root.minsize(800, 500)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

current_path = tk.StringVar(value=os.path.expanduser("~"))

def refresh_list():
    path = Path(current_path.get())
    if not path.exists():
        return
    for item in tree.get_children():
        tree.delete(item)
    try:
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for item in items:
            icon = "📁" if item.is_dir() else "📄"
            size = f"{item.stat().st_size:,} バイト" if item.is_file() else ""
            tree.insert("", "end", values=(icon, item.name, size))
    except PermissionError:
        pass

def go_up():
    parent = Path(current_path.get()).parent
    if str(parent) != current_path.get():
        current_path.set(str(parent))
        refresh_list()

def go_down():
    selection = tree.selection()
    if selection:
        item = tree.item(selection[0])
        name = item["values"][1]
        new_path = Path(current_path.get()) / name
        if new_path.is_dir():
            current_path.set(str(new_path))
            refresh_list()

def create_folder():
    name = tk.simpledialog.askstring("新規フォルダー", "フォルダー名を入力:", parent=root)
    if name:
        try:
            (Path(current_path.get()) / name).mkdir()
            refresh_list()
        except Exception as e:
            messagebox.showerror("エラー", str(e))

def delete_selected():
    selection = tree.selection()
    if not selection:
        return
    item = tree.item(selection[0])
    name = item["values"][1]
    target = Path(current_path.get()) / name
    if messagebox.askyesno("確認", f"{name}を削除しますか？"):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            refresh_list()
        except Exception as e:
            messagebox.showerror("エラー", str(e))

toolbar = tk.Frame(root, padx=10, pady=8)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Button(toolbar, text="⬆ 上へ", command=go_up).pack(side="left", padx=2)
tk.Button(toolbar, text="⬇ 開く", command=go_down).pack(side="left", padx=2)
tk.Button(toolbar, text="📁 新規フォルダー", command=create_folder).pack(side="left", padx=2)
tk.Button(toolbar, text="🗑 削除", command=delete_selected).pack(side="left", padx=2)
path_entry = tk.Entry(toolbar, textvariable=current_path, width=50)
path_entry.pack(side="left", padx=10)
tk.Button(toolbar, text="移動", command=refresh_list).pack(side="left")

columns = ("icon", "name", "size")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("icon", text="")
tree.heading("name", text="名前")
tree.heading("size", text="サイズ")
tree.column("icon", width=40)
tree.column("name", width=300)
tree.column("size", width=150)
tree.grid(row=1, column=0, sticky="nsew")
tree.bind("<Double-1>", lambda e: go_down())

scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
scrollbar.grid(row=1, column=1, sticky="ns")
tree.configure(yscrollcommand=scrollbar.set)

refresh_list()
root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - ファイルシステム", "name": "テキストファイル検索", "kind": "code",
        "description": "フォルダー内のファイルでテキストを検索します。os, re, globモジュールを使用。",
        "code": '''import os
import re
import glob
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

root = tk.Tk()
root.title("テキストファイル検索")
root.geometry("800x600")
root.minsize(700, 450)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(2, weight=1)

search_folder = tk.StringVar(value=os.path.expanduser("~"))
search_pattern = tk.StringVar()
search_text = tk.StringVar()
results = []

def do_search():
    global results
    pattern = search_pattern.get()
    text = search_text.get()
    folder = search_folder.get()
    if not folder or not os.path.isdir(folder):
        messagebox.showerror("エラー", "無効なフォルダーです")
        return
    results = []
    files = glob.glob(os.path.join(folder, "**", pattern), recursive=True)
    try:
        regex = re.compile(text, re.IGNORECASE) if text else None
    except re.error:
        messagebox.showerror("エラー", "無効な正規表現です")
        return
    for filepath in files:
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if regex:
                        matches = list(regex.finditer(content))
                        if matches:
                            for m in matches:
                                line_num = content[:m.start()].count("\\n") + 1
                                line_content = content.split("\\n")[line_num - 1].strip()
                                results.append((filepath, line_num, line_content))
                    else:
                        results.append((filepath, "", ""))
            except Exception:
                pass
    display_results()

def display_results():
    for item in tree.get_children():
        tree.delete(item)
    for filepath, line_num, line_content in results:
        tree.insert("", "end", values=(os.path.basename(filepath), line_num, line_content[:60], filepath))

control_frame = tk.Frame(root, padx=10, pady=10)
control_frame.grid(row=0, column=0, sticky="ew")
tk.Label(control_frame, text="フォルダー:").grid(row=0, column=0, sticky="w")
tk.Entry(control_frame, textvariable=search_folder, width=50).grid(row=0, column=1, padx=5)
tk.Button(control_frame, text="参照", command=lambda: search_folder.set(filedialog.askdirectory())).grid(row=0, column=2)
tk.Label(control_frame, text="ファイルパターン（例: *.txt）:").grid(row=1, column=0, sticky="w", pady=5)
tk.Entry(control_frame, textvariable=search_pattern, width=30).grid(row=1, column=1, padx=5, pady=5)
tk.Label(control_frame, text="検索テキスト（正規表現）:").grid(row=2, column=0, sticky="w", pady=5)
tk.Entry(control_frame, textvariable=search_text, width=30).grid(row=2, column=1, padx=5, pady=5)
tk.Button(control_frame, text="検索", command=do_search, bg="#0d6efd", fg="white").grid(row=3, column=0, columnspan=3, pady=10, sticky="ew")

columns = ("file", "line", "preview", "path")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("file", text="ファイル")
tree.heading("line", text="行")
tree.heading("preview", text="プレビュー")
tree.heading("path", text="フルパス")
tree.column("file", width=150)
tree.column("line", width=50)
tree.column("preview", width=300)
tree.column("path", width=200)
tree.grid(row=2, column=0, sticky="nsew")

scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
scrollbar.grid(row=2, column=1, sticky="ns")
tree.configure(yscrollcommand=scrollbar.set)

root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - システム", "name": "システム情報表示", "kind": "code",
        "description": "システム情報を表示します。platform, os, sysモジュールを使用。",
        "code": '''import platform
import os
import sys
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("システム情報")
root.geometry("700x600")
root.minsize(600, 400)

info_text = tk.Text(root, wrap="word", font=("Consolas", 10), padx=10, pady=10)
info_text.pack(fill="both", expand=True)

def get_system_info():
    info = []
    info.append("=" * 50)
    info.append("システム情報")
    info.append("=" * 50)
    info.append(f"プラットフォーム: {platform.platform()}")
    info.append(f"システム: {platform.system()}")
    info.append(f"ノード名: {platform.node()}")
    info.append(f"リリース: {platform.release()}")
    info.append(f"バージョン: {platform.version()}")
    info.append(f"マシン: {platform.machine()}")
    info.append(f"プロセッサ: {platform.processor()}")
    info.append("")
    info.append("=" * 50)
    info.append("Python情報")
    info.append("=" * 50)
    info.append(f"Pythonバージョン: {sys.version}")
    info.append(f"Python実行ファイル: {sys.executable}")
    info.append(f"Pythonパス: {sys.path[0]}")
    info.append("")
    info.append("=" * 50)
    info.append("環境")
    info.append("=" * 50)
    info.append(f"カレントディレクトリ: {os.getcwd()}")
    info.append(f"ホームディレクトリ: {os.path.expanduser('~')}")
    info.append(f"ユーザー: {os.getenv('USERNAME', '不明')}")
    info.append("")
    info.append("=" * 50)
    info.append("CPUとメモリ")
    info.append("=" * 50)
    info.append(f"CPU数: {os.cpu_count()}")
    info.append(f"起動時刻: {platform.boot_time()}")
    return "\\n".join(info)

info_text.insert("1.0", get_system_info())
info_text.config(state="disabled")

root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - データ", "name": "JSONエディター", "kind": "code",
        "description": "JSONファイルを表示・編集します。jsonモジュールを使用。",
        "code": '''import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("JSONエディター")
root.geometry("800x600")
root.minsize(600, 400)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

current_file = tk.StringVar()

def load_json():
    path = filedialog.askopenfilename(filetypes=[("JSONファイル", "*.json"), ("すべてのファイル", "*.*")])
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            editor.delete("1.0", tk.END)
            editor.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
            current_file.set(path)
            status.config(text=f"読み込み: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("エラー", f"JSONの読み込みに失敗: {e}")

def save_json():
    path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSONファイル", "*.json")])
    if path:
        try:
            content = editor.get("1.0", tk.END)
            data = json.loads(content)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            current_file.set(path)
            status.config(text=f"保存: {os.path.basename(path)}")
        except json.JSONDecodeError as e:
            messagebox.showerror("エラー", f"無効なJSON: {e}")
        except Exception as e:
            messagebox.showerror("エラー", f"保存に失敗: {e}")

def format_json():
    try:
        content = editor.get("1.0", tk.END)
        data = json.loads(content)
        editor.delete("1.0", tk.END)
        editor.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
    except json.JSONDecodeError as e:
        messagebox.showerror("エラー", f"無効なJSON: {e}")

toolbar = tk.Frame(root, padx=10, pady=8)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Button(toolbar, text="JSONを開く", command=load_json).pack(side="left", padx=2)
tk.Button(toolbar, text="JSONを保存", command=save_json).pack(side="left", padx=2)
tk.Button(toolbar, text="整形", command=format_json).pack(side="left", padx=2)

editor = tk.Text(root, wrap="none", font=("Consolas", 11))
editor.grid(row=1, column=0, sticky="nsew")

y_scroll = tk.Scrollbar(root, orient="vertical", command=editor.yview)
y_scroll.grid(row=1, column=1, sticky="ns")
x_scroll = tk.Scrollbar(root, orient="horizontal", command=editor.xview)
x_scroll.grid(row=2, column=0, sticky="ew")
editor.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

status = tk.Label(root, text="ファイルが読み込まれていません", anchor="w")
status.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - データベース", "name": "SQLiteデータベース管理", "kind": "code",
        "description": "SQLiteデータベースをCRUD操作で管理します。sqlite3モジュールを使用。",
        "code": '''import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("SQLiteデータベース管理")
root.geometry("900x650")
root.minsize(800, 500)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

conn = sqlite3.connect(":memory:")
cursor = conn.cursor()
cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
conn.commit()

def refresh_table():
    for item in tree.get_children():
        tree.delete(item)
    cursor.execute("SELECT * FROM users")
    for row in cursor.fetchall():
        tree.insert("", "end", values=row)

def add_user():
    name = name_entry.get().strip()
    email = email_entry.get().strip()
    if name and email:
        cursor.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        conn.commit()
        refresh_table()
        name_entry.delete(0, tk.END)
        email_entry.delete(0, tk.END)

def delete_user():
    selection = tree.selection()
    if selection:
        user_id = tree.item(selection[0])["values"][0]
        cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        refresh_table()

input_frame = tk.Frame(root, padx=10, pady=10)
input_frame.grid(row=0, column=0, sticky="ew")
tk.Label(input_frame, text="名前:").grid(row=0, column=0, padx=5)
name_entry = tk.Entry(input_frame, width=30)
name_entry.grid(row=0, column=1, padx=5)
tk.Label(input_frame, text="メール:").grid(row=0, column=2, padx=5)
email_entry = tk.Entry(input_frame, width=30)
email_entry.grid(row=0, column=3, padx=5)
tk.Button(input_frame, text="追加", command=add_user).grid(row=0, column=4, padx=10)
tk.Button(input_frame, text="選択を削除", command=delete_user).grid(row=0, column=5, padx=5)

columns = ("id", "name", "email")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("id", text="ID")
tree.heading("name", text="名前")
tree.heading("email", text="メール")
tree.column("id", width=50)
tree.column("name", width=200)
tree.column("email", width=300)
tree.grid(row=1, column=0, sticky="nsew")

scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
scrollbar.grid(row=1, column=1, sticky="ns")
tree.configure(yscrollcommand=scrollbar.set)

refresh_table()
root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - ネットワーク", "name": "HTTPリクエストツール", "kind": "code",
        "description": "HTTPリクエストを送信し、レスポンスを表示します。http.clientとurllibモジュールを使用。",
        "code": '''import http.client
import urllib.parse
import json
import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("HTTPリクエストツール")
root.geometry("900x700")
root.minsize(800, 500)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(3, weight=1)

method = tk.StringVar(value="GET")
url = tk.StringVar(value="https://httpbin.org/get")

def send_request():
    target_url = url.get().strip()
    if not target_url:
        messagebox.showerror("エラー", "URLを入力してください")
        return
    try:
        parsed = urllib.parse.urlparse(target_url)
        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(parsed.netloc, timeout=10)
        else:
            conn = http.client.HTTPConnection(parsed.netloc, timeout=10)
        
        m = method.get()
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        
        conn.request(m, path)
        response = conn.getresponse()
        status = f"{response.status} {response.reason}"
        headers = "\\n".join([f"{k}: {v}" for k, v in response.getheaders()])
        body = response.read().decode("utf-8", errors="ignore")
        conn.close()
        
        result_text.delete("1.0", tk.END)
        result_text.insert("1.0", f"ステータス: {status}\\n\\nヘッダー:\\n{headers}\\n\\n本文:\\n{body}")
    except Exception as e:
        messagebox.showerror("エラー", str(e))

control_frame = tk.Frame(root, padx=10, pady=10)
control_frame.grid(row=0, column=0, sticky="ew")
tk.Label(control_frame, text="メソッド:").pack(side="left")
ttk.Combobox(control_frame, textvariable=method, values=("GET", "POST", "PUT", "DELETE"), state="readonly", width=10).pack(side="left", padx=5)
tk.Label(control_frame, text="URL:").pack(side="left", padx=5)
tk.Entry(control_frame, textvariable=url, width=60).pack(side="left", padx=5)
tk.Button(control_frame, text="リクエスト送信", command=send_request, bg="#0d6efd", fg="white").pack(side="left", padx=10)

result_text = tk.Text(root, wrap="word", font=("Consolas", 10), padx=10, pady=10)
result_text.grid(row=3, column=0, sticky="nsew")

y_scroll = ttk.Scrollbar(root, orient="vertical", command=result_text.yview)
y_scroll.grid(row=3, column=1, sticky="ns")
result_text.configure(yscrollcommand=y_scroll.set)

root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - ユーティリティ", "name": "カレンダーアプリ", "kind": "code",
        "description": "カレンダーを表示し、月を移動します。calendarモジュールを使用。",
        "code": '''import calendar
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("カレンダーアプリ")
root.geometry("400x450")

current_year = tk.StringVar(value=str(calendar.datetime.datetime.now().year))
current_month = tk.StringVar(value=str(calendar.datetime.datetime.now().month))

def update_calendar():
    try:
        year = int(current_year.get())
        month = int(current_month.get())
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        header.config(text=f"{month_name} {year}")
        
        for widget in calendar_frame.winfo_children():
            widget.destroy()
        
        days = ["月", "火", "水", "木", "金", "土", "日"]
        for i, day in enumerate(days):
            tk.Label(calendar_frame, text=day, font=("Arial", 10, "bold"), width=5).grid(row=0, column=i, padx=2, pady=2)
        
        for week_num, week in enumerate(cal, start=1):
            for day_num, day in enumerate(week):
                cell_text = str(day) if day != 0 else ""
                bg = "#e3f2fd" if day == calendar.datetime.datetime.now().day and month == calendar.datetime.datetime.now().month and year == calendar.datetime.datetime.now().year else "white"
                tk.Label(calendar_frame, text=cell_text, width=5, height=2, relief="solid", bg=bg).grid(row=week_num, column=day_num, padx=1, pady=1)
    except ValueError:
        pass

def prev_month():
    year = int(current_year.get())
    month = int(current_month.get())
    month -= 1
    if month == 0:
        month = 12
        year -= 1
    current_year.set(str(year))
    current_month.set(str(month))
    update_calendar()

def next_month():
    year = int(current_year.get())
    month = int(current_month.get())
    month += 1
    if month == 13:
        month = 1
        year += 1
    current_year.set(str(year))
    current_month.set(str(month))
    update_calendar()

nav_frame = tk.Frame(root, pady=10)
nav_frame.pack()
tk.Button(nav_frame, text="◀ 前月", command=prev_month).pack(side="left", padx=5)
tk.Entry(nav_frame, textvariable=current_year, width=6).pack(side="left", padx=2)
tk.Entry(nav_frame, textvariable=current_month, width=4).pack(side="left", padx=2)
tk.Button(nav_frame, text="翌月 ▶", command=next_month).pack(side="left", padx=5)
tk.Button(nav_frame, text="今日", command=lambda: (current_year.set(str(calendar.datetime.datetime.now().year)), current_month.set(str(calendar.datetime.datetime.now().month)), update_calendar())).pack(side="left", padx=10)

header = tk.Label(root, text="", font=("Arial", 16, "bold"), pady=10)
header.pack()

calendar_frame = tk.Frame(root, padx=10, pady=10)
calendar_frame.pack()

update_calendar()
root.mainloop()
'''
    },
    {
        "category": "モジュール活用例 - 高度な機能", "name": "プロセス管理", "kind": "code",
        "description": "実行中のプロセスを一覧・管理します。subprocessとosモジュールを使用。",
        "code": '''import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("プロセス管理")
root.geometry("900x600")
root.minsize(800, 450)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

def get_processes():
    try:
        result = subprocess.run(
            ["ps", "-eo", "comm=,pid="],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [
            (parts[0], parts[1])
            for line in result.stdout.splitlines()
            if len(parts := line.split(None, 1)) == 2
        ]
    except Exception as e:
        messagebox.showerror("エラー", str(e))
        return []

def refresh_list():
    for item in tree.get_children():
        tree.delete(item)
    processes = get_processes()
    for name, pid in processes:
        tree.insert("", "end", values=(name, pid))

def kill_process():
    selection = tree.selection()
    if selection:
        item = tree.item(selection[0])
        pid = item["values"][1]
        if messagebox.askyesno("確認", f"プロセス {pid} に終了要求を送信しますか？"):
            try:
                subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                refresh_list()
            except Exception as e:
                messagebox.showerror("エラー", str(e))

toolbar = tk.Frame(root, padx=10, pady=8)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Button(toolbar, text="🔄 更新", command=refresh_list).pack(side="left", padx=2)
tk.Button(toolbar, text="🔴 プロセス終了", command=kill_process, bg="#dc3545", fg="white").pack(side="left", padx=2)

columns = ("name", "pid")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("name", text="プロセス名")
tree.heading("pid", text="PID")
tree.column("name", width=400)
tree.column("pid", width=100)
tree.grid(row=1, column=0, sticky="nsew")

scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
scrollbar.grid(row=1, column=1, sticky="ns")
tree.configure(yscrollcommand=scrollbar.set)

refresh_list()
root.mainloop()
'''
    },
    {
        "category": "少し背伸びした作品", "name": "GUIフォーム（デザイナー）", "kind": "designer",
        "description": "ボタン・ラベル・入力欄を配置してGUIを作ります。フォーム作成タブへ移動します。",
        "code": ""
    },
    {
        "category": "少し背伸びした作品", "name": "タスクトレイアプリ", "kind": "code",
        "description": "タスクトレイのアイコンをクリックすると、表示と終了のメニューが開きます。（pystrayが必要）",
        "code": '''import tkinter as tk
import os
import sys
import queue
import threading
import time

# 注意: このコードを実行するには、以下のコマンドでpystrayをインストールしてください:
# pip install pystray

if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY") and any(name in os.environ.get("XDG_CURRENT_DESKTOP", "").lower() for name in ("cinnamon", "mate", "xfce", "lxde", "lxqt")):
    os.environ.setdefault("PYSTRAY_BACKEND", "xorg")

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("警告: pystrayがインストールされていません。'pip install pystray' でインストールしてください。")

# ウィンドウ管理
root = tk.Tk()
root.title("タスクトレイアプリ")
root.geometry("300x200")
icon = None
TRAY_ACTION_QUEUE = queue.SimpleQueue()
# ボタンウィンドウ
button_window = tk.Toplevel(root)
button_window.title("ボタン")
button_window.geometry("200x200")

# ボタンフレーム
button_frame = tk.Frame(button_window)
button_frame.pack(pady=20)

# アクションボタン
action_button = tk.Button(button_frame, text="クリック！", font=("Arial", 12), width=15, command=lambda: hide_window())
action_button.pack(pady=5)

# タスクトレイに格納ボタン
minimize_button = tk.Button(button_frame, text="タスクトレイに格納", font=("Arial", 10), width=15, command=lambda: hide_window())
minimize_button.pack(pady=5)

def show_window():
    """ボタンウィンドウを表示"""
    button_window.deiconify()
    button_window.lift()

def hide_window():
    """ボタンウィンドウを隠す"""
    if icon is not None:
        button_window.withdraw()
    else:
        button_window.iconify()

def on_tray_action(icon, item):
    TRAY_ACTION_QUEUE.put(getattr(item, "text", ""))

def process_tray_actions():
    root.after(100, process_tray_actions)
    while not TRAY_ACTION_QUEUE.empty():
        item_text = TRAY_ACTION_QUEUE.get()
        if item_text == "メニュー":
            show_tray_menu()
        elif item_text == "終了":
            shutdown_app()
        else:
            show_window()

def show_tray_menu():
    tray_menu = tk.Menu(root, tearoff=0)
    tray_menu.add_command(label="表示", command=show_window)
    tray_menu.add_separator()
    tray_menu.add_command(label="終了", command=shutdown_app)
    try:
        tray_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())
    finally:
        tray_menu.grab_release()

def shutdown_app():
    if icon is not None:
        icon.stop()
    root.destroy()

def close_window():
    if icon is not None:
        button_window.withdraw()
    else:
        root.destroy()

if PYSTRAY_AVAILABLE:
    try:
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((2, 2, 62, 62), fill=(23, 105, 170, 255))
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
        except OSError:
            font = ImageFont.load_default()
        bounds = draw.textbbox((0, 0), "PY", font=font)
        x = (64 - (bounds[2] - bounds[0])) // 2 - bounds[0]
        y = (64 - (bounds[3] - bounds[1])) // 2 - bounds[1]
        draw.text((x, y), "PY", fill="white", font=font)

        icon = pystray.Icon(
            "PythonTrayApp",
            image,
            "Python Tray App",
            menu=(
                pystray.Menu(pystray.MenuItem("メニュー", on_tray_action, default=True))
                if pystray.Icon.__module__ == "pystray._xorg"
                else pystray.Menu(
                    pystray.MenuItem("表示", on_tray_action, default=True),
                    pystray.MenuItem("終了", on_tray_action),
                )
            )
        )
        icon.run_detached()
        root.withdraw()
        button_window.withdraw()
    except Exception as error:
        print(f"警告: タスクトレイを起動できません: {error}")
        icon = None
        show_window()

# メインループ
root.protocol("WM_DELETE_WINDOW", close_window)
if not PYSTRAY_AVAILABLE:
    show_window()
root.after(100, process_tray_actions)
root.mainloop()
'''
    },
]

def load_project_code(code, auto_install_modules=True):
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
    
    # Auto install modules if enabled
    if auto_install_modules:
        installed = parse_and_install_code_modules(code, auto_install=True)
        if installed:
            messagebox.showinfo("自動インストール", f"自動的にモジュールをインストールしました: {', '.join(installed)}")
    
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
    tk.Label(
        content,
        text="ホットキーとボタンの動作を登録（全体ホットキーはX11セッションで利用できます）",
        font=("Meiryo UI", 14, "bold"),
    ).pack(anchor="w")

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

    tk.Label(form, text="キー (例: Alt+a)", font=("Meiryo UI", 11)).grid(row=0, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="ボタン名 (任意)", font=("Meiryo UI", 11)).grid(row=0, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="動作", font=("Meiryo UI", 11)).grid(row=1, column=0, sticky="w", padx=4, pady=3)
    kind_menu = ttk.Combobox(form, textvariable=kind_value, values=("URLを開く", "アプリ/ファイル起動", "キー送信", "コマンド実行", "ウィンドウを隠す"), state="readonly", width=18, font=("Meiryo UI", 11))
    kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="URL / パス / キー / コマンド", font=("Meiryo UI", 11)).grid(row=1, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="実行後に待つ秒数", font=("Meiryo UI", 11)).grid(row=2, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
    tk.Label(form, text="待機後に送るキー (任意)", font=("Meiryo UI", 11)).grid(row=2, column=2, sticky="w", padx=4, pady=3)
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
                "height": height_value.get(), "actions": actions}

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
        if not target and kind != "ウィンドウを隠す":
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
        action_data = [{key: item[key] for key in ("shortcut", "button", "kind", "target", "wait", "followup")} for item in actions]
        persist_configuration()

        # 日本語アクション名を英語に変換
        kind_map = {
            "URLを開く": "Open URL",
            "アプリ/ファイル起動": "Launch app/file",
            "キー送信": "Send keys",
            "コマンド実行": "Run command",
            "ウィンドウを隠す": "Hide window"
        }
        for action in action_data:
            if action["kind"] in kind_map:
                action["kind"] = kind_map[action["kind"]]
        
        source = build_hotkey_app_source(
            action_data,
            title_value.get().strip() or "かんたんホットキー",
            window_width,
            window_height,
        )

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

def parse_and_install_code_modules(code_text=None, auto_install=False):
    if code_text is None:
        code_text = text.get("1.0", tk.END)
    if not code_text.strip():
        if not auto_install:
            messagebox.showwarning("注意", "エディターにコードがありません。")
        return []
    import_matches = re.findall(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', code_text, re.MULTILINE)
    modules = list(set(import_matches))
    stdlib_set = set(getattr(sys, "stdlib_module_names", ())) | {
        'os', 'sys', 're', 'math', 'time', 'datetime', 'json', 'random', 'subprocess',
        'threading', 'tempfile', 'tkinter', 'webbrowser', 'urllib', 'pathlib',
        'collections', 'itertools', 'functools', 'io', 'shutil', 'glob', 'sqlite3', 'csv',
        'hashlib', 'hmac', 'uuid', 'smtplib', 'imaplib', 'http', 'socket', 'asyncio', 'logging',
        'platform', 'typing', 'dataclasses', 'enum', 'abc', 'copy', 'pprint', 'argparse',
        'queue', 'shlex', 'html', 'calendar', 'string', 'traceback', 'inspect',
        'statistics', 'decimal', 'fractions', 'array', 'struct', 'pickle', 'shelve',
        'configparser', 'xml', 'email', 'unittest', 'doctest', 'contextlib',
        'contextvars', 'concurrent', 'multiprocessing', 'signal', 'select',
        'selectors', 'ssl', 'ftplib',
    }
    candidate_modules = [m for m in modules if m not in stdlib_set]
    package_names = {"PIL": "Pillow"}
    if not candidate_modules:
        if not auto_install:
            messagebox.showinfo("確認", "追加でインストールが必要な未導入の外部モジュールは見つかりませんでした！")
        return []
    try:
        python_executable = get_virtualenv_python()
        check_script = "import importlib.util, json, sys; names=json.loads(sys.argv[1]); print(json.dumps([name for name in names if importlib.util.find_spec(name) is None]))"
        result = subprocess.run([python_executable, "-c", check_script, json.dumps(candidate_modules)],
                                check=True, capture_output=True, text=True, timeout=30)
        target_modules = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as e:
        messagebox.showerror("エラー", f"仮想環境のモジュール確認に失敗しました:\n{e}")
        return []
    if not target_modules:
        if not auto_install:
            messagebox.showinfo("確認", "追加でインストールが必要な未導入の外部モジュールは見つかりませんでした！")
        return []
    
    # Auto install mode
    if auto_install:
        success_list, fail_list = [], []
        for mname in target_modules:
            try:
                package_name = package_names.get(mname, mname)
                res = subprocess.run([python_executable, "-m", "pip", "install", package_name],
                                     capture_output=True, text=True, timeout=90)
                if res.returncode == 0:
                    success_list.append(package_name)
                else:
                    fail_list.append(f"{package_name}: {res.stderr.strip() or res.stdout.strip()}")
            except (OSError, subprocess.SubprocessError) as error:
                fail_list.append(f"{package_name}: {error}")
        if fail_list:
            messagebox.showerror("モジュールのインストール失敗", "\n".join(fail_list))
        return success_list
    
    # Manual install mode with dialog
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
            package_name = package_names.get(mname, mname)
            try:
                res = subprocess.run([python_executable, "-m", "pip", "install", package_name],
                                     capture_output=True, text=True, timeout=90)
                if res.returncode == 0:
                    success_list.append(package_name)
                else:
                    fail_list.append(f"{package_name}: {res.stderr.strip() or res.stdout.strip()}")
            except (OSError, subprocess.SubprocessError) as error:
                fail_list.append(f"{package_name}: {error}")
        msg = f"インストール完了: {', '.join(success_list) if success_list else 'なし'}"
        if fail_list:
            msg += f"\n失敗: {', '.join(fail_list)}"
        messagebox.showinfo("インストール結果", msg)
        win.destroy()
    tk.Button(win, text="🚀 選択したモジュールをインストール実行", command=do_install,
              bg="#198754", fg="white", font=("Meiryo UI", 10, "bold"), padx=10, pady=8, cursor="hand2").pack(side="bottom", fill="x", padx=15, pady=15)


# ==================== メインUI ====================
root = tk.Tk()
root.title(f"Python Studio - Code & Form Designer v{APP_VERSION}")

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

try:
    root.attributes("-zoomed", True)
except tk.TclError:
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{min(1400, screen_width)}x{min(900, screen_height - 100)}")

root.update_idletasks()
root.minsize(
    min(1200, max(320, root.winfo_screenwidth() - 80)),
    min(800, max(240, root.winfo_screenheight() - 140)),
)

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

tab_docked = ttk.Frame(top_notebook)
top_notebook.add(tab_docked, text="🔗 ホットキー・フォーム統合")
docked_toolbar = ttk.Frame(tab_docked)
docked_toolbar.pack(fill="x", padx=8, pady=(8, 0))
ttk.Button(
    docked_toolbar,
    text="⚡ ホットキー＋フォームを一つのプログラムとして生成",
    command=lambda: generate_code_from_designer(include_hotkeys=True),
).pack(side="left")
docked_notebook = ttk.Notebook(tab_docked)
docked_notebook.pack(fill="both", expand=True, padx=4, pady=(4, 4))
docked_hotkey_tab = ttk.Frame(docked_notebook)
docked_notebook.add(docked_hotkey_tab, text="⌨ ホットキー")
docked_form_tab = ttk.Frame(docked_notebook)
docked_notebook.add(docked_form_tab, text="🎨 フォーム")

tab_robot = ttk.Frame(top_notebook)
top_notebook.add(tab_robot, text="🚁 ドローン・ロボット制御")

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
add_btn(top_btn_frame, "📦 モジュール自動インストール", lambda: parse_and_install_code_modules(auto_install=True), "#6610f2")
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
samples_content = tk.Frame(tab_samples, padx=12, pady=12, bg=THEMES[current_theme]['bg'])
samples_content.pack(fill="both", expand=True)
tk.Label(samples_content, text="作りたいものを選んでください", font=("Meiryo UI", 15, "bold"),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=(0, 10))
samples_body = tk.Frame(samples_content, bg=THEMES[current_theme]['bg'])
samples_body.pack(fill="both", expand=True)
samples_tree = ttk.Treeview(samples_body, show="tree", selectmode="browse")
samples_tree.column("#0", width=250, minwidth=200, stretch=False)
samples_tree.pack(side="left", fill="y")
samples_tree_scroll = ttk.Scrollbar(samples_body, orient="vertical", command=samples_tree.yview)
samples_tree_scroll.pack(side="left", fill="y")
samples_tree.configure(yscrollcommand=samples_tree_scroll.set)

samples_details = tk.Frame(samples_body, padx=14, bg=THEMES[current_theme]['bg'])
samples_details.pack(side="left", fill="both", expand=True)
samples_name_label = tk.Label(samples_details, text="作品を選択してください", anchor="w", font=("Meiryo UI", 13, "bold"),
                            bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'])
samples_name_label.pack(fill="x", pady=(0, 6))
samples_description = tk.Label(samples_details, text="", anchor="nw", justify="left", wraplength=580,
                               bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'])
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
samples_buttons = tk.Frame(samples_content, bg=THEMES[current_theme]['bg'])
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
hotkey_content = tk.Frame(root, padx=14, pady=12, bg=THEMES[current_theme]['bg'])
hotkey_content.pack(in_=tab_hotkey, fill="both", expand=True)
tk.Label(hotkey_content, text="ホットキーとボタンの動作を登録", font=("Meiryo UI", 14, "bold"),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w")
tk.Label(
    hotkey_content,
    text="全体ホットキーはX11セッションで利用できます。Waylandではデスクトップのショートカット設定を使用してください。",
    bg=THEMES[current_theme]['bg'],
    fg=THEMES[current_theme]['text_fg'],
    anchor="w",
).pack(fill="x", pady=(2, 4))

hotkey_settings = tk.Frame(hotkey_content, bg=THEMES[current_theme]['bg'])
hotkey_settings.pack(fill="x", pady=(10, 8))
tk.Label(hotkey_settings, text="ウィンドウ名", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left")
hotkey_title_value = tk.StringVar(value="かんたんホットキー")
ttk.Entry(hotkey_settings, textvariable=hotkey_title_value, width=24).pack(side="left", padx=(6, 16))
tk.Label(hotkey_settings, text="幅", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left")
hotkey_width_value = tk.StringVar(value="240")
ttk.Entry(hotkey_settings, textvariable=hotkey_width_value, width=7).pack(side="left", padx=6)
tk.Label(hotkey_settings, text="高さ", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left")
hotkey_height_value = tk.StringVar(value="420")
ttk.Entry(hotkey_settings, textvariable=hotkey_height_value, width=7).pack(side="left", padx=6)
hotkey_body = tk.Frame(hotkey_content, bg=THEMES[current_theme]['bg'])
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

hotkey_form = tk.LabelFrame(hotkey_content, text="動作の追加・編集", padx=10, pady=8,
                          bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'])
hotkey_form.pack(fill="x", pady=(10, 4))
hotkey_shortcut_value = tk.StringVar()
hotkey_button_value = tk.StringVar()
hotkey_kind_value = tk.StringVar(value="URLを開く")
hotkey_target_value = tk.StringVar()
hotkey_wait_value = tk.StringVar(value="0")
hotkey_followup_value = tk.StringVar()

tk.Label(hotkey_form, text="キー (例: Alt+a)", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=0, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="ボタン名 (任意)", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=0, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="動作", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=1, column=0, sticky="w", padx=4, pady=3)
hotkey_kind_menu = ttk.Combobox(hotkey_form, textvariable=hotkey_kind_value, values=("URLを開く", "アプリ/ファイル起動", "キー送信", "コマンド実行", "ウィンドウを隠す"), state="readonly", width=18, font=("Meiryo UI", 11))
hotkey_kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="URL / パス / キー / コマンド", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=1, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="実行後に待つ秒数", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=2, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
tk.Label(hotkey_form, text="待機後に送るキー (任意)", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=2, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_followup_value).grid(row=2, column=3, sticky="ew", padx=4, pady=3)
hotkey_form.columnconfigure(1, weight=1)
hotkey_form.columnconfigure(3, weight=2)
tk.Label(hotkey_content, text="キー送信の例: Ctrl+w、Alt+F4、Left。キー欄を空にするとボタンだけで実行します。",
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], anchor="w").pack(fill="x", pady=(2, 4))

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
            "height": hotkey_height_value.get(), "actions": hotkey_actions}

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
    if not target and kind != "ウィンドウを隠す":
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
    action_data = [{key: item[key] for key in ("shortcut", "button", "kind", "target", "wait", "followup")} for item in hotkey_actions]

    # 日本語アクション名を英語に変換
    kind_map = {
        "URLを開く": "Open URL",
        "アプリ/ファイル起動": "Launch app/file",
        "キー送信": "Send keys",
        "コマンド実行": "Run command",
        "ウィンドウを隠す": "Hide window"
    }
    for action in action_data:
        if action["kind"] in kind_map:
            action["kind"] = kind_map[action["kind"]]

    source = build_hotkey_app_source(
        action_data,
        hotkey_title_value.get().strip() or "かんたんホットキー",
        window_width,
        window_height,
    )
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
            "height": hotkey_height_value.get(), "actions": hotkey_actions}

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

designer_toolbar = tk.Frame(root, bg="#2d2d2d", padx=8, pady=8)
designer_toolbar.pack(in_=tab_designer, side="top", fill="x")

form_window_width = 600
form_window_height = 450
form_bg_color = "#f0f0f0"
form_fg_color = "#000000"
form_pos_x = 100
form_pos_y = 100
form_pos_mode = "manual"
form_use_tray = False

# フォームデザイナーの設定を保存/読み込み
DESIGNER_SETTINGS_FILE = 'designer_settings.json'

def load_designer_settings():
    global form_use_tray, form_window_width, form_window_height, form_bg_color, form_fg_color, form_pos_x, form_pos_y, form_pos_mode
    path = get_settings_path(DESIGNER_SETTINGS_FILE)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                form_use_tray = data.get('start_in_tray', False)
                form_window_width = data.get('window_width', 600)
                form_window_height = data.get('window_height', 450)
                form_bg_color = data.get('bg_color', '#f0f0f0')
                form_fg_color = data.get('fg_color', '#000000')
                form_pos_x = data.get('pos_x', 100)
                form_pos_y = data.get('pos_y', 100)
                form_pos_mode = data.get('pos_mode', 'manual')
        except Exception:
            pass

def save_designer_settings():
    path = get_settings_path(DESIGNER_SETTINGS_FILE)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'start_in_tray': form_use_tray,
                'window_width': form_window_width,
                'window_height': form_window_height,
                'bg_color': form_bg_color,
                'fg_color': form_fg_color,
                'pos_x': form_pos_x,
                'pos_y': form_pos_y,
                'pos_mode': form_pos_mode
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 設定を読み込む
load_designer_settings()

canvas_container = tk.Frame(root, bg="#1e1e1e")
canvas_container.pack(in_=tab_designer, side="top", fill="both", expand=True, padx=8, pady=8)

def dock_pack(widget, parent, **options):
    if widget.winfo_manager() == "pack" and widget.pack_info().get("in") == parent:
        return
    widget.pack_forget()
    widget.pack(in_=parent, **options)

def move_docked_feature_widgets(event=None):
    if top_notebook.select() == str(tab_docked):
        if docked_notebook.select() == str(docked_hotkey_tab):
            hotkey_parent, form_parent = docked_hotkey_tab, tab_designer
        else:
            hotkey_parent, form_parent = tab_hotkey, docked_form_tab
    else:
        hotkey_parent, form_parent = tab_hotkey, tab_designer

    dock_pack(hotkey_content, hotkey_parent, fill="both", expand=True)
    dock_pack(designer_toolbar, form_parent, side="top", fill="x")
    dock_pack(canvas_container, form_parent, side="top", fill="both", expand=True, padx=8, pady=8)

def on_docked_tab_changed(event=None):
    move_docked_feature_widgets()
    if (top_notebook.select() == str(tab_docked)
            and docked_notebook.select() == str(docked_hotkey_tab)):
        on_hotkey_tab_selected(None)

docked_notebook.bind("<<NotebookTabChanged>>", on_docked_tab_changed, add="+")
top_notebook.bind("<<NotebookTabChanged>>", move_docked_feature_widgets, add="+")

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
    form_window_width = max(0, w)
    form_window_height = max(0, h)
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

designer_options_frame = tk.Frame(designer_toolbar, bg="#2d2d2d")
designer_options_frame.pack(side="bottom", fill="x")

size_control_frame = tk.Frame(designer_options_frame, bg="#2d2d2d")
size_control_frame.pack(side="right", padx=8)
tk.Label(size_control_frame, text="フォームサイズ", bg="#2d2d2d", fg="#eeeeee",
         font=("Meiryo UI", 9)).pack(side="left", padx=(0, 5))
form_width_var = tk.StringVar(value=str(form_window_width))
form_width_spin = ttk.Spinbox(size_control_frame, from_=0, to=100000, increment=1,
                              width=7, textvariable=form_width_var, command=apply_form_size_inputs)
form_width_spin.pack(side="left")
tk.Label(size_control_frame, text="×", bg="#2d2d2d", fg="#eeeeee").pack(side="left", padx=3)
form_height_var = tk.StringVar(value=str(form_window_height))
form_height_spin = ttk.Spinbox(size_control_frame, from_=0, to=100000, increment=1,
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

form_color_controls = tk.Frame(designer_options_frame, bg="#2d2d2d")
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
    global form_pos_x, form_pos_y, form_pos_mode, form_use_tray
    w_diag = tk.Toplevel(root)
    w_diag.title("ウィンドウの画面表示位置設定")
    w_diag.geometry("450x390")
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

    tray_start_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        f_body,
        text="プログラム実行時にタスクトレイへ格納する",
        variable=tray_start_var,
        bg="#f8f9fa",
        font=("Meiryo UI", 10),
    ).pack(anchor="w", pady=(10, 5))

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
        global form_pos_x, form_pos_y, form_pos_mode, form_use_tray
        form_pos_mode = mode_var.get()
        if form_pos_mode == "manual":
            try:
                form_pos_x = int(x_entry.get().strip())
                form_pos_y = int(y_entry.get().strip())
            except ValueError:
                messagebox.showerror("エラー", "座標には有効な整数を入力してください。")
                return
        form_use_tray = tray_start_var.get()
        update_size_label()
        save_designer_settings()
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
        w_diag.geometry(f"450x390+{screen_x}+{screen_y}")

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

    button_number = max(
        (
            existing.get("button_index", -1)
            for existing in designer_components
            if existing["type"] == "Button"
        ),
        default=-1,
    ) + 1
    if ctype == "Button":
        inner = tk.Button(wrapper, text=f"{button_number}. ボタン", relief="flat", font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    elif ctype == "Label":
        inner = tk.Label(wrapper, text="テキストラベル", bg=default_bg, fg=default_fg, font=("Meiryo UI", 10))
    else:
        inner = tk.Entry(wrapper, font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    inner.pack(fill="both", expand=True)

    comp_resize_handle = tk.Label(wrapper, text="◢", bg="#0d6efd", fg="white", font=("Meiryo UI", 8), cursor="sizing")
    comp_resize_handle.place(relx=1.0, rely=1.0, x=-12, y=-12, width=12, height=12)

    comp_info = {
        "type": ctype, "wrapper": wrapper, "inner": inner,
        "text": f"{button_number}. ボタン" if ctype == "Button" else ("テキストラベル" if ctype == "Label" else ""),
        "bg_color": default_bg, "fg_color": default_fg, "font_size": 10,
        "custom_background": False, "custom_foreground": False,
        "action": "none", "param": "", "close_after_action": False,
        "button_index": button_number,
        "browser_choice": "既定のブラウザ"
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
                 font=("Meiryo UI", 11, "bold")).pack(anchor="w", pady=(0, 5))

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
                ("📂 ファイルマネージャーを開く", "open_explorer"),
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
                ("テキストエディターを開く", "open_notepad"),
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

        initial_action = comp["action"]
        if initial_action == "hide_window":
            initial_action = "none"
        act_var = tk.StringVar(value=initial_action)
        for cat_name, acts in action_categories:
            tk.Label(f_act, text=cat_name, bg="#f8f9fa", fg="#0d6efd",
                     font=("Meiryo UI", 11, "bold")).pack(anchor="w", pady=(10, 2))
            for text_lbl, val in acts:
                tk.Radiobutton(f_act, text=text_lbl, variable=act_var, value=val,
                               bg="#f8f9fa", font=("Meiryo UI", 11), anchor="w").pack(anchor="w", padx=12, pady=1)

        tk.Label(f_act, text="アクションパラメータ（URLやメッセージ内容など）:", bg="#f8f9fa",
                 font=("Meiryo UI", 11, "bold")).pack(anchor="w", pady=(14, 2))
        param_entry = tk.Entry(f_act, width=50, font=("Meiryo UI", 11))
        param_entry.pack(anchor="w")
        param_entry.insert(0, comp["param"])
        close_after_var = tk.BooleanVar(value=comp.get("close_after_action", True), name="prop_close_after_var")
        tk.Checkbutton(
            f_act,
            text="アクション実行後にこのアプリを終了する",
            variable=close_after_var,
            bg="#f8f9fa",
            font=("Meiryo UI", 11),
            anchor="w",
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(f_act, text="ブラウザを開くアクションの使用ブラウザ:", bg="#f8f9fa",
                 font=("Meiryo UI", 11)).pack(anchor="w", pady=(8, 2))
        browser_var = tk.StringVar(value=comp.get("browser_choice", "既定のブラウザ"), name="prop_browser_var")
        browser_combo = ttk.Combobox(
            f_act,
            textvariable=browser_var,
            values=("既定のブラウザ", "Microsoft Edge", "Google Chrome", "Mozilla Firefox", "Brave"),
            state="readonly",
            width=24,
            font=("Meiryo UI", 11),
        )
        browser_combo.pack(anchor="w")
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

    def on_dialog_close():
        diag.destroy()

    diag.protocol("WM_DELETE_WINDOW", on_dialog_close)

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

def generate_code_from_designer(include_hotkeys=False):
    combined_hotkey_actions = []
    if include_hotkeys:
        if not hotkey_actions:
            messagebox.showerror("入力エラー", "統合プログラムにはホットキー動作を1つ以上登録してください。")
            top_notebook.select(tab_docked)
            docked_notebook.select(docked_hotkey_tab)
            return
        seen_shortcuts = set()
        for item in hotkey_actions:
            shortcut = item["shortcut"].lower().replace(" ", "")
            if shortcut and shortcut in seen_shortcuts:
                messagebox.showerror("入力エラー", f"ホットキーが重複しています: {item['shortcut']}")
                top_notebook.select(tab_docked)
                docked_notebook.select(docked_hotkey_tab)
                return
            seen_shortcuts.add(shortcut)
        kind_map = {
            "URLを開く": "Open URL",
            "アプリ/ファイル起動": "Launch app/file",
            "キー送信": "Send keys",
            "コマンド実行": "Run command",
            "ウィンドウを隠す": "Hide window",
        }
        combined_hotkey_actions = []
        for item in hotkey_actions:
            action = {
                key: item[key]
                for key in ("shortcut", "button", "kind", "target", "wait", "followup")
            }
            action["kind"] = kind_map.get(action["kind"], action["kind"])
            combined_hotkey_actions.append(action)
    hotkey_button_actions = [
        (index, action)
        for index, action in enumerate(combined_hotkey_actions)
        if action["button"]
    ]
    combined_window_height = form_window_height
    hotkey_button_start_y = form_window_height
    hotkey_button_columns = max(1, form_window_width // 180)
    if include_hotkeys and hotkey_button_actions:
        component_bottom = max(
            (
                comp["wrapper"].winfo_y() + comp["wrapper"].winfo_height()
                for comp in designer_components
            ),
            default=form_window_height,
        )
        hotkey_button_start_y = max(form_window_height, component_bottom) + 8
        hotkey_button_rows = (
            len(hotkey_button_actions) + hotkey_button_columns - 1
        ) // hotkey_button_columns
        combined_window_height = hotkey_button_start_y + hotkey_button_rows * 42 + 8

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
        top_notebook.select(tab_docked if include_hotkeys else tab_designer)
        if include_hotkeys:
            docked_notebook.select(docked_form_tab)
        return

    if form_pos_mode == "center":
        geometry_code = (
            f"root.geometry('{form_window_width}x{combined_window_height}')\n"
            f"root.update_idletasks()\n"
            f"sw = root.winfo_screenwidth()\n"
            f"sh = root.winfo_screenheight()\n"
            f"x = (sw - {form_window_width}) // 2\n"
            f"y = (sh - {combined_window_height}) // 2\n"
            f"root.geometry(f'{form_window_width}x{combined_window_height}+{{x}}+{{y}}')"
        )
    else:
        geometry_code = f"root.geometry('{form_window_width}x{combined_window_height}+{form_pos_x}+{form_pos_y}')"

    actions = {
        comp["action"] for comp in designer_components
        if comp["type"] == "Button"
    }
    browser_actions = {
        "open_url", "open_x", "open_abema", "google_search",
        "youtube_search", "google_translate", "google_maps",
    }
    needs_browser = bool(actions & browser_actions)
    imports = ["import tkinter as tk"]
    if actions & {
        "copy_file", "copy_folder", "move_file", "delete_file",
        "create_folder", "create_text_file", "open_folder",
        "open_file_default", "open_desktop", "open_documents",
        "open_downloads", "open_explorer", "open_notepad", "open_calc",
        "open_terminal", "maximize_window",
    } or needs_browser:
        imports.append("import os")
    if actions & {
        "copy_file", "copy_folder", "move_file", "delete_file",
        "create_folder", "create_text_file", "show_msg", "ask_yesno",
        "copy_clipboard", "copy_time", "show_time", "random_num",
        "dice_roll", "omikuji", "gen_password", "open_notepad",
        "open_calc", "open_terminal",
    } or needs_browser:
        imports.append("from tkinter import messagebox")
    if actions & {
        "move_file", "delete_file", "create_folder", "create_text_file",
        "open_folder", "open_file_default",
    }:
        imports.append("from tkinter import filedialog")
    if actions & {
        "copy_file", "copy_folder", "move_file", "open_notepad",
        "open_calc", "open_terminal",
    } or needs_browser:
        imports.append("import shutil")
    if actions & {
        "open_folder", "open_file_default", "open_explorer", "open_notepad",
        "open_calc", "open_terminal",
    } or needs_browser:
        imports.append("import subprocess")
    if needs_browser:
        imports.append("import webbrowser")
    if actions & {"google_search", "youtube_search", "google_translate", "google_maps"}:
        imports.append("import urllib.parse")
    if actions & {"copy_time", "show_time"}:
        imports.append("import datetime")
    if actions & {"random_num", "dice_roll", "omikuji", "gen_password"}:
        imports.append("import random")
    needs_tray = form_use_tray
    if include_hotkeys:
        for statement in (
            "import os",
            "import hashlib",
            "import sys",
            "import shutil",
            "import shlex",
            "import subprocess",
            "import threading",
            "import time",
            "try:",
            "    from pynput import keyboard as pynput_keyboard",
            "except ImportError:",
            "    pynput_keyboard = None",
        ):
            if statement not in imports:
                imports.append(statement)
    if needs_tray:
        if "from tkinter import messagebox" not in imports:
            imports.append("from tkinter import messagebox")
        imports.extend([
            "import threading",
            "import queue",
            "try:",
            "    import pystray",
            "    from PIL import Image, ImageDraw, ImageFont",
            "    PYSTRAY_AVAILABLE = True",
            "except ImportError:",
            "    PYSTRAY_AVAILABLE = False",
        ])

    code = [
        *imports,
        "",
        *(["TRAY_ACTION_QUEUE = queue.SimpleQueue()", ""] if needs_tray else []),
        "root = tk.Tk()",
        "root.title('作成したフォームアプリ')",
        f"root.configure(bg={form_bg_color!r})",
        f"root.option_add('*Foreground', {form_fg_color!r})",
        geometry_code,
        "icon = None",
        "",
        "def open_browser(url, browser_choice='既定のブラウザ'):",
        "    try:",
        "        root.iconify()",
        "        if browser_choice == '既定のブラウザ':",
        "            opened = webbrowser.open(url, new=0)",
        "            if not opened:",
        "                raise RuntimeError('既定のブラウザーを起動できませんでした。')",
        "        else:",
        "            browser_commands = {",
        "                'Microsoft Edge': ('microsoft-edge', 'microsoft-edge-stable', 'msedge'),",
        "                'Google Chrome': ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'),",
        "                'Mozilla Firefox': ('firefox',),",
        "                'Brave': ('brave-browser',),",
        "            }",
        "            executable = next((shutil.which(name) for name in browser_commands[browser_choice] if shutil.which(name)), None)",
        "            if not executable:",
        "                raise FileNotFoundError(f'{browser_choice}が見つかりません。')",
        "            subprocess.Popen([executable, url], start_new_session=True)",
        "        return True",
        "    except Exception as error:",
        "        root.deiconify()",
        "        root.lift()",
        "        root.focus_force()",
        "        messagebox.showerror('ブラウザ起動エラー', str(error), parent=root)",
        "        return False",
        "",

    ]

    if not needs_browser:
        browser_start = code.index("def open_browser(url, browser_choice='既定のブラウザ'):")
        browser_end = code.index("", browser_start)
        del code[browser_start:browser_end + 1]

    for i, comp in enumerate(designer_components):
        w = comp["wrapper"]
        x, y = w.winfo_x(), w.winfo_y()
        width, height = w.winfo_width(), w.winfo_height()
        ctype, act, param, label_text = comp["type"], comp["action"], comp["param"], comp["text"]
        if act == "hide_window":
            act = "none"
        source_path = comp.get("source_path", "").strip()
        destination_path = comp.get("destination_path", "").strip()
        browser_choice = comp.get("browser_choice", "既定のブラウザ")
        browser_call_args = f", {browser_choice!r}"
        bg, fg, f_size = comp["bg_color"], comp["fg_color"], comp["font_size"]
        font_str = f"('Meiryo UI', {f_size})"

        if ctype == "Button":
            if act != "none":
                code.append(f"def on_btn_{i}_click():")
                if act == "close_app":
                    code.append("    shutdown_app()" if include_hotkeys else "    root.destroy()")
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
                    code.append("        subprocess.Popen(['xdg-open', path], start_new_session=True)")
                elif act == "open_file_default":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='開くファイルを選択', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        subprocess.Popen(['xdg-open', path], start_new_session=True)")
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
                    code.append("    path = subprocess.run(['xdg-user-dir', 'DESKTOP'], check=True, capture_output=True, text=True, timeout=5).stdout.strip()")
                    code.append("    if not os.path.isdir(path): path = os.path.expanduser('~')")
                    code.append("    subprocess.Popen(['xdg-open', path], start_new_session=True)")
                elif act == "open_documents":
                    code.append("    path = subprocess.run(['xdg-user-dir', 'DOCUMENTS'], check=True, capture_output=True, text=True, timeout=5).stdout.strip()")
                    code.append("    if not os.path.isdir(path): path = os.path.expanduser('~')")
                    code.append("    subprocess.Popen(['xdg-open', path], start_new_session=True)")
                elif act == "open_downloads":
                    code.append("    path = subprocess.run(['xdg-user-dir', 'DOWNLOAD'], check=True, capture_output=True, text=True, timeout=5).stdout.strip()")
                    code.append("    if not os.path.isdir(path): path = os.path.expanduser('~')")
                    code.append("    subprocess.Popen(['xdg-open', path], start_new_session=True)")
                elif act == "open_explorer":
                    code.append("    subprocess.Popen(['xdg-open', os.path.expanduser('~')], start_new_session=True)")
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
                    code.append("    editor = next((shutil.which(name) for name in ('xed', 'gnome-text-editor', 'gedit', 'mousepad', 'pluma') if shutil.which(name)), None)")
                    code.append("    if editor: subprocess.Popen([editor], start_new_session=True)")
                    code.append("    else: messagebox.showerror('起動エラー', 'テキストエディターが見つかりません。')")
                elif act == "open_calc":
                    code.append("    calculator = next((shutil.which(name) for name in ('gnome-calculator', 'mate-calc', 'galculator', 'kcalc') if shutil.which(name)), None)")
                    code.append("    if calculator: subprocess.Popen([calculator], start_new_session=True)")
                    code.append("    else: messagebox.showerror('起動エラー', '電卓アプリが見つかりません。')")
                elif act == "open_terminal":
                    terminal = next((shutil.which(name) for name in ('x-terminal-emulator', 'gnome-terminal', 'mate-terminal', 'xfce4-terminal', 'xterm') if shutil.which(name)), None)
                    if terminal:
                        code.append(f"    subprocess.Popen([{terminal!r}], start_new_session=True)")
                    else:
                        code.append("    messagebox.showerror('起動エラー', 'ターミナルアプリが見つかりません。')")
                elif act == "beep":
                    code.append("    root.bell()")
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
                elif act == "show_window":
                    code.append("    root.deiconify()")
                    code.append("    root.lift()")
                    code.append("    root.focus_force()")
                elif act == "minimize_window":
                    code.append("    root.iconify()")
                elif act == "maximize_window":
                    code.append("    root.attributes('-zoomed', True)")
                if needs_tray and act != "close_app" and act not in ("hide_window", "show_window"):
                    code.append("    root.withdraw()")
                elif comp.get("close_after_action", False) and act != "close_app" and act not in ("hide_window", "show_window", "minimize_window", "maximize_window"):
                    code.append("    shutdown_app()" if include_hotkeys else "    root.destroy()")
                code.append("")
                cmd_str = f", command=on_btn_{i}_click"
            else:
                cmd_str = ""

            component_parent = "root"
            code.append(f"btn_{i} = tk.Button({component_parent}, text={label_text!r}, bg={bg!r}, fg={fg!r}, font={font_str}{cmd_str})")
            code.append(f"btn_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Label":
            component_parent = "root"
            code.append(f"lbl_{i} = tk.Label({component_parent}, text={label_text!r}, bg={bg!r}, fg={fg!r}, font={font_str})")
            code.append(f"lbl_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Entry":
            component_parent = "root"
            code.append(f"ent_{i} = tk.Entry({component_parent}, bg={bg!r}, fg={fg!r}, font={font_str})")
            code.append(f"ent_{i}.place(x={x}, y={y}, width={width}, height={height})")

    if include_hotkeys and hotkey_button_actions:
        code.extend(["", "# Hotkey action buttons"])
        for button_index, (action_index, action) in enumerate(hotkey_button_actions):
            column = button_index % hotkey_button_columns
            row = button_index // hotkey_button_columns
            cell_width = form_window_width // hotkey_button_columns
            button_x = column * cell_width + 3
            button_y = hotkey_button_start_y + row * 42
            button_width = max(1, cell_width - 6)
            code.extend([
                f"hotkey_button_{button_index} = tk.Button(root, text={action['button']!r}, command=lambda: threading.Thread(target=run_hotkey_action, args=({action_index},), daemon=True).start())",
                f"hotkey_button_{button_index}.place(x={button_x}, y={button_y}, width={button_width}, height=36)",
            ])

    if needs_tray:
        code.extend([
            "",
            "# タスクトレイアイコンの作成",
            "def create_tray_icon():",
            "    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))",
            "    draw = ImageDraw.Draw(image)",
            "    try:",
            "        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 24)",
            "    except OSError:",
            "        font = ImageFont.load_default()",
            "    draw.rectangle((2, 2, 62, 62), fill=(23, 105, 170, 255))",
            "    bounds = draw.textbbox((0, 0), 'PY', font=font)",
            "    x = (64 - (bounds[2] - bounds[0])) // 2 - bounds[0]",
            "    y = (64 - (bounds[3] - bounds[1])) // 2 - bounds[1]",
            "    draw.text((x, y), 'PY', fill='white', font=font)",
            "    return image",
            "",
            "def restore_window():",
            "    root.deiconify()",
            "    root.update_idletasks()",
            f"    x = max(0, (root.winfo_screenwidth() - {form_window_width}) // 2)",
            f"    y = max(0, (root.winfo_screenheight() - {form_window_height}) // 2)",
            f"    root.geometry(f'{form_window_width}x{form_window_height}+{{x}}+{{y}}')",
            "    root.lift()",
            "    root.focus_force()",
            "",
            "def exit_from_tray(icon):",
            "    shutdown_app()" if include_hotkeys else "    icon.stop()",
            "    root.destroy()" if not include_hotkeys else "",
            "",
            "def on_tray_clicked(icon, item):",
            "    TRAY_ACTION_QUEUE.put(getattr(item, 'text', item))",
            "",
            "def process_tray_actions():",
            "    root.after(100, process_tray_actions)",
            "    while not TRAY_ACTION_QUEUE.empty():",
            "        item_text = TRAY_ACTION_QUEUE.get()",
            "        if item_text == 'メニュー':",
            "            show_tray_menu()",
            "        elif item_text in ('Exit', '終了'):",
            "            exit_from_tray(icon)",
            "        else:",
            "            restore_window()",
            "",
            "def show_tray_menu():",
            "    tray_menu = tk.Menu(root, tearoff=0)",
            "    tray_menu.add_command(label='表示', command=restore_window)",
            "    tray_menu.add_separator()",
            "    tray_menu.add_command(label='終了', command=lambda: exit_from_tray(icon))",
            "    try:",
            "        tray_menu.tk_popup(root.winfo_pointerx(), root.winfo_pointery())",
            "    finally:",
            "        tray_menu.grab_release()",
            "",
            "def close_window():",
            "    if icon is not None:",
            "        root.iconify()",
            "        root.withdraw()",
            "    else:",
            "        root.destroy()",
            "",
            "root.protocol('WM_DELETE_WINDOW', close_window)",
            "if PYSTRAY_AVAILABLE:",
            "    try:",
            "        icon = pystray.Icon(",
            "            'PythonFormApp',",
            "            create_tray_icon(),",
            "            'Python Form App',",
            "            menu=(",
            "                pystray.Menu(pystray.MenuItem('メニュー', on_tray_clicked, default=True))",
            "                if pystray.Icon.__module__ == 'pystray._xorg'",
            "                else pystray.Menu(",
            "                    pystray.MenuItem('表示', on_tray_clicked, default=True),",
            "                    pystray.MenuItem('終了', on_tray_clicked)",
            "                )",
            "            )",
            "        )",
            "        tray_thread = threading.Thread(target=icon.run, daemon=True)",
            "        tray_thread.start()",
            "        root.withdraw()",
            "    except Exception as error:",
            "        messagebox.showwarning('タスクトレイを使用できません', str(error), parent=root)",
            "        icon = None",
            "        root.deiconify()",
            "else:",
            "    messagebox.showwarning('タスクトレイを使用できません', 'タスクトレイ機能には pystray と Pillow が必要です。pip install pystray Pillow でインストールしてください。')",
            ""
        ])

    if include_hotkeys:
        code.extend([""])
        code.extend(build_hotkey_runtime_source(combined_hotkey_actions))
        code.extend(build_hotkey_instance_lock_source())
        code.extend([
            "",
            "if not acquire_hotkey_locks():",
            "    messagebox.showwarning('ホットキーは起動済みです', '同じホットキーを登録したアプリがすでに起動しています。重複実行を防ぐため終了します。', parent=root)",
            "    root.destroy()",
            "    raise SystemExit(0)",
            "",
            "hotkey_listener = start_hotkey_listener()",
        ])

    if needs_tray:
        code.extend(["", "root.after(100, process_tray_actions)"])
    code.extend(["", "root.mainloop()"])
    generated_code = add_python_shebang("\n".join(code) + "\n")
    if text.get("1.0", tk.END).strip():
        if not messagebox.askyesno("上書き確認", "エディターの内容を生成コードで置き換えますか？"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", generated_code)
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    if include_hotkeys:
        messagebox.showinfo("生成完了", "ホットキーとフォームを統合したプログラムを生成しました。")
    else:
        messagebox.showinfo("生成完了", "フォームのコードでエディター内容を置き換えました！\nファイル操作系は実行時に選択画面が出ます。")

# ツールバーボタン
designer_toolbar_buttons = []
designer_toolbar_columns = 0
designer_buttons_frame = tk.Frame(designer_toolbar, bg="#2d2d2d")

def add_designer_toolbar_button(label, command, bg, fg="white", active_bg=None):
    options = {
        "text": label, "command": command, "bg": bg, "fg": fg,
        "relief": "flat", "font": ("Meiryo UI", 8, "bold"),
        "padx": 2, "pady": 3, "cursor": "hand2",
    }
    if active_bg:
        options["activebackground"] = active_bg
        options["activeforeground"] = fg
    designer_toolbar_buttons.append(tk.Button(designer_buttons_frame, **options))

def arrange_designer_toolbar(event=None):
    global designer_toolbar_columns
    toolbar_width = event.width if event else designer_buttons_frame.winfo_width()
    if toolbar_width < 100 or not designer_buttons_frame.winfo_ismapped():
        return
    available_width = toolbar_width - 6
    button_widths = []
    for button in designer_toolbar_buttons:
        button.configure(wraplength=0)
        button_width = button.winfo_reqwidth()
        if button_width > available_width:
            button.configure(wraplength=max(1, available_width - 12))
            button_width = min(button.winfo_reqwidth(), available_width)
        button_widths.append(button_width)

    column_widths = None
    for columns in range(len(designer_toolbar_buttons), 0, -1):
        widths = [
            max(button_widths[index::columns])
            for index in range(columns)
        ]
        if sum(widths) + 6 * (columns - 1) <= available_width:
            column_widths = widths
            designer_toolbar_columns = columns
            break
    if column_widths is None:
        return

    for column in range(len(designer_toolbar_buttons)):
        designer_buttons_frame.grid_columnconfigure(column, weight=0, minsize=0)
    for column, width in enumerate(column_widths):
        designer_buttons_frame.grid_columnconfigure(
            column,
            weight=1,
            minsize=width,
        )

    for button in designer_toolbar_buttons:
        button.grid_forget()
    for index, button in enumerate(designer_toolbar_buttons):
        button.grid(
            row=index // designer_toolbar_columns,
            column=index % designer_toolbar_columns,
            padx=3,
            pady=2,
            sticky="ew",
        )

designer_buttons_frame.bind(
    "<Configure>",
    lambda event: designer_buttons_frame.after_idle(arrange_designer_toolbar),
)
designer_toolbar.bind(
    "<Configure>",
    lambda event: designer_buttons_frame.after_idle(arrange_designer_toolbar),
    add="+",
)
designer_buttons_frame.bind(
    "<Map>",
    lambda event: designer_buttons_frame.after_idle(arrange_designer_toolbar),
    add="+",
)

add_designer_toolbar_button("＋ ボタン", lambda: add_component("Button"), "#1769aa", active_bg="#12558a")
add_designer_toolbar_button("＋ ラベル", lambda: add_component("Label"), "#0f766e", active_bg="#0b5c56")
add_designer_toolbar_button("＋ 入力欄", lambda: add_component("Entry"), "#3a7d44", active_bg="#2d6335")
add_designer_toolbar_button("⚙ ウィンドウ位置", open_window_position_dialog, "#6610f2")
add_designer_toolbar_button("⚙ ボタン詳細設定", lambda: open_properties_dialog(selected_component) if selected_component else messagebox.showwarning("注意", "部品を選んでください"), "#ffc107", fg="#000")
add_designer_toolbar_button("🗑 削除", delete_component, "#dc3545")
add_designer_toolbar_button("🧹 全消去", clear_designer, "#6c757d")
add_designer_toolbar_button("📝 コード生成して転送", generate_code_from_designer, "#0d6efd")
designer_buttons_frame.pack_forget()
designer_options_frame.pack_forget()
designer_options_frame.pack(side="right", anchor="n", padx=(8, 0), pady=2)
designer_buttons_frame.pack(side="left", fill="x", expand=True)
top_notebook.bind(
    "<<NotebookTabChanged>>",
    lambda event: designer_buttons_frame.after_idle(arrange_designer_toolbar),
    add="+",
)


# ---------- タブ5：ドローン・ロボット制御 ----------
robot_control_mode = tk.StringVar(value="drone")
robot_blocks = []
robot_code_output = tk.StringVar()

def robot_create_block_ui():
    block_frame = tk.Frame(robot_canvas, bg=THEMES[current_theme]['bg'], relief="raised", bd=2)
    return block_frame

def robot_add_block(block_type, params=None):
    if params is None:
        params = {}
    
    if len(robot_blocks) >= 90:
        messagebox.showwarning("制限", "ブロックは最大90個までです")
        return
    
    block = {
        "type": block_type,
        "params": params,
        "id": len(robot_blocks)
    }
    robot_blocks.append(block)
    robot_refresh_blocks_display()

def robot_refresh_blocks_display():
    for widget in robot_canvas.winfo_children():
        widget.destroy()
    
    # Canvasの実際の幅を取得
    robot_canvas.update_idletasks()
    canvas_width = robot_canvas.winfo_width()
    canvas_height = robot_canvas.winfo_height()
    
    # デフォルト値（初回表示時）
    if canvas_width < 100:
        canvas_width = 900
    if canvas_height < 100:
        canvas_height = 400

    block_width = 110     # ブロックの幅
    block_height = 35      # ブロックの高さ
    block_gap = 3          # ブロック間の隙間
    padding = 10           # 余白

    # 横に並べられるブロック数を計算
    items_per_row = max(1, int((canvas_width - padding * 2) / (block_width + block_gap)))
    max_rows = 15          # 最大行数

    # 各行のブロック数を計算
    rows_info = []
    for i in range(len(robot_blocks)):
        row = i // items_per_row
        if row >= max_rows:
            row = max_rows - 1
        if row >= len(rows_info):
            rows_info.append(0)
        rows_info[row] += 1

    for i, block in enumerate(robot_blocks):
        # 行と列を計算（横並び）
        row = i // items_per_row
        column = i % items_per_row

        # 最大行数を超えないように
        if row >= max_rows:
            row = max_rows - 1
            column = i  # 超えた分は同じ行に横に並べる

        # その行のブロック数を取得
        blocks_in_row = rows_info[row] if row < len(rows_info) else 1

        # その行のブロック全体の幅
        total_row_width = blocks_in_row * block_width + (blocks_in_row - 1) * block_gap

        # 中央揃えの開始位置
        x_start = (canvas_width - total_row_width) / 2

        x_pos = x_start + (column * (block_width + block_gap))
        y_pos = padding + (row * (block_height + block_gap))

        block_frame = robot_create_block_ui()
        block_frame.place(x=x_pos, y=y_pos, width=block_width, height=block_height)
        
        block_text = robot_get_block_text(block)
        tk.Label(block_frame, text=f"{i+1}. {block_text}",
                bg=THEMES[current_theme]['button_bg'], fg=THEMES[current_theme]['text_fg'],
                font=("Meiryo UI", 9), wraplength=150).pack(fill="both", expand=True, padx=2, pady=1)
    
    # Canvasサイズを更新
    max_height = padding + (max_rows * (block_height + block_gap))
    robot_canvas.configure(height=max_height)

def robot_get_block_text(block):
    block_type = block["type"]
    params = block["params"]
    
    if block_type == "takeoff":
        return f"離陸（{params.get('height', 5)}メートル）"
    elif block_type == "land":
        return "着陸"
    elif block_type == "forward":
        return f"前進（{params.get('distance', 5)}メートル）"
    elif block_type == "backward":
        return f"後退（{params.get('distance', 5)}メートル）"
    elif block_type == "left":
        return f"左移動（{params.get('distance', 5)}メートル）"
    elif block_type == "right":
        return f"右移動（{params.get('distance', 5)}メートル）"
    elif block_type == "up":
        return f"上昇（{params.get('height', 5)}メートル）"
    elif block_type == "down":
        return f"下降（{params.get('height', 5)}メートル）"
    elif block_type == "rotate_left":
        return f"左回転（{params.get('angle', 90)}度）"
    elif block_type == "rotate_right":
        return f"右回転（{params.get('angle', 90)}度）"
    elif block_type == "rotate_180":
        return "反転（180度）"
    elif block_type == "wait":
        return f"待機（{params.get('seconds', 1)}秒）"
    elif block_type == "return_home":
        return "⚠️ 電波途脱時帰還"
    elif block_type == "face_direction":
        direction = params.get('direction', '北')
        return f"{direction}を向く"
    else:
        return block_type

def robot_clear_blocks():
    robot_blocks.clear()
    robot_refresh_blocks_display()

def robot_delete_last_block():
    if robot_blocks:
        robot_blocks.pop()
        robot_refresh_blocks_display()

def robot_generate_code():
    mode = robot_control_mode.get()
    hardware = robot_hardware_var.get()
    code_lines = []
    
    if mode == "drone":
        if hardware == "tello":
            # DJI Tello用コード
            code_lines.extend([
                "# DJI Telloドローン制御プログラム",
                "# インストールが必要: pip install djitellopy",
                "",
                "from djitellopy import Tello",
                "import time",
                "",
                "# ドローンに接続",
                "drone = Tello()",
                "drone.connect()",
                "",
                "# バッテリー確認",
                "print(f'バッテリー: {drone.get_battery()}%')",
                "",
                "# 離陸",
                "drone.takeoff()",
                "time.sleep(2)",
                ""
            ])
            
            for block in robot_blocks:
                block_type = block["type"]
                params = block["params"]
                
                if block_type == "takeoff":
                    code_lines.append("drone.takeoff()")
                    code_lines.append("time.sleep(2)")
                elif block_type == "land":
                    code_lines.append("drone.land()")
                elif block_type == "forward":
                    dist = params.get('distance', 5) * 100  # cmに変換
                    code_lines.append(f"drone.move_forward({dist})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "backward":
                    dist = params.get('distance', 5) * 100
                    code_lines.append(f"drone.move_back({dist})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "left":
                    dist = params.get('distance', 5) * 100
                    code_lines.append(f"drone.move_left({dist})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "right":
                    dist = params.get('distance', 5) * 100
                    code_lines.append(f"drone.move_right({dist})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "up":
                    height = params.get('height', 5) * 100
                    code_lines.append(f"drone.move_up({height})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "down":
                    height = params.get('height', 5) * 100
                    code_lines.append(f"drone.move_down({height})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "rotate_left":
                    angle = params.get('angle', 90)
                    code_lines.append(f"drone.rotate_counter_clockwise({angle})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "rotate_right":
                    angle = params.get('angle', 90)
                    code_lines.append(f"drone.rotate_clockwise({angle})")
                    code_lines.append("time.sleep(1)")
                elif block_type == "wait":
                    code_lines.append(f"time.sleep({params.get('seconds', 1)})")
                elif block_type == "return_home":
                    code_lines.append("# 電波途脱時はTelloが自動的に着陸します")
                    code_lines.append("drone.land()")
            
            code_lines.extend([
                "",
                "# 接続を閉じる",
                "drone.end()",
                "",
                "# 使用前の準備:",
                "# 1. Telloドローンの電源を入れる",
                "# 2. PC/スマホのWiFiでTelloのネットワークに接続",
                "# 3. このプログラムを実行"
            ])
        else:
            # シミュレーション
            code_lines.extend([
                "import tkinter as tk",
                "from tkinter import messagebox",
                "",
                "# ドローン制御プログラム（シミュレーション）",
                "",
                "class DroneController:",
                "    def __init__(self):",
                "        self.launched = False",
                "        self.x = 0",
                "        self.y = 0",
                "        self.z = 0",
                "        self.start_x = 0",
                "        self.start_y = 0",
                "        self.start_z = 0",
                "        self.signal_lost = False",
                "",
                "    def takeoff(self, height):",
                "        if self.launched:",
                "            messagebox.showwarning('警告', 'すでに離陸しています')",
                "            return",
                "        self.start_x = self.x",
                "        self.start_y = self.y",
                "        self.start_z = self.z",
                "        self.z += height",
                "        self.launched = True",
                "        print(f'{height}メートル上昇して離陸しました')",
                "",
                "    def land(self):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.z = 0",
                "        self.launched = False",
                "        print('着陸しました')",
                "",
                "    def forward(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.x += distance",
                "        print(f'{distance}メートル前進しました')",
                "",
                "    def backward(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.x -= distance",
                "        print(f'{distance}メートル後退しました')",
                "",
                "    def left(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.y -= distance",
                "        print(f'{distance}メートル左に移動しました')",
                "",
                "    def right(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.y += distance",
                "        print(f'{distance}メートル右に移動しました')",
                "",
                "    def up(self, height):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.z += height",
                "        print(f'{height}メートル上昇しました')",
                "",
                "    def down(self, height):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        self.z -= height",
                "        if self.z < 0:",
                "            self.z = 0",
                "            self.launched = False",
                "            print('着陸しました')",
                "        else:",
                "            print(f'{height}メートル下降しました')",
                "",
                "    def rotate_left(self, angle):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        print(f'左に{angle}度回転しました')",
                "",
                "    def rotate_right(self, angle):",
                "        if not self.launched:",
                "            messagebox.showwarning('警告', '離陸していません')",
                "            return",
                "        print(f'右に{angle}度回転しました')",
                "",
                "    def wait(self, seconds):",
                "        import time",
                "        time.sleep(seconds)",
                "",
                "    def return_home(self):",
                "        if not self.launched:",
                "            print('離陸していないため帰還不要です')",
                "            return",
                "        print('⚠️ 電波が途絶しました！自動帰還を開始します')",
                "        self.z = 0",
                "        self.x = self.start_x",
                "        self.y = self.start_y",
                "        self.launched = False",
                "        print('✅ 元の位置に帰還完了しました')",
                "",
                "    def show_status(self):",
                "        print(f'現在位置: X={self.x}, Y={self.y}, Z={self.z}')",
                "",
                "",
                "drone = DroneController()",
                ""
            ])
            
            for block in robot_blocks:
                block_type = block["type"]
                params = block["params"]
                
                if block_type == "takeoff":
                    code_lines.append(f"drone.takeoff({params.get('height', 5)})")
                elif block_type == "land":
                    code_lines.append("drone.land()")
                elif block_type == "forward":
                    code_lines.append(f"drone.forward({params.get('distance', 5)})")
                elif block_type == "backward":
                    code_lines.append(f"drone.backward({params.get('distance', 5)})")
                elif block_type == "left":
                    code_lines.append(f"drone.left({params.get('distance', 5)})")
                elif block_type == "right":
                    code_lines.append(f"drone.right({params.get('distance', 5)})")
                elif block_type == "rotate_left":
                    code_lines.append(f"drone.rotate_left({params.get('angle', 90)})")
                elif block_type == "rotate_right":
                    code_lines.append(f"drone.rotate_right({params.get('angle', 90)})")
                elif block_type == "up":
                    code_lines.append(f"drone.up({params.get('height', 5)})")
                elif block_type == "down":
                    code_lines.append(f"drone.down({params.get('height', 5)})")
                elif block_type == "wait":
                    code_lines.append(f"drone.wait({params.get('seconds', 1)})")
                elif block_type == "return_home":
                    code_lines.append("drone.return_home()")
            
            code_lines.extend([
                "",
                "drone.show_status()",
                "",
                "# 注意: これはシミュレーションです。",
                "# 実際のドローンを制御するにはハードウェアを選択してください。"
            ])
    
    else:  # robot mode
        if hardware == "rpi":
            # Raspberry Pi用コード
            code_lines.extend([
                "# Raspberry Pi ロボット制御プログラム",
                "# 必要なライブラリ: pip install gpiozero",
                "",
                "from gpiozero import Robot",
                "from time import sleep",
                "",
                "# モーターのピン設定（使用するピンに合わせて変更）",
                "# 左モーター: GPIOピン17, 18",
                "# 右モーター: GPIOピン22, 23",
                "robot = Robot(left=(17, 18), right=(22, 23))",
                ""
            ])
            
            for block in robot_blocks:
                block_type = block["type"]
                params = block["params"]
                
                if block_type == "forward":
                    dist = params.get('distance', 5)
                    code_lines.append(f"robot.forward()")
                    code_lines.append(f"sleep({dist})")
                    code_lines.append("robot.stop()")
                elif block_type == "backward":
                    dist = params.get('distance', 5)
                    code_lines.append(f"robot.backward()")
                    code_lines.append(f"sleep({dist})")
                    code_lines.append("robot.stop()")
                elif block_type == "rotate_left":
                    code_lines.append("robot.left()")
                    code_lines.append("sleep(0.5)")
                    code_lines.append("robot.stop()")
                elif block_type == "rotate_right":
                    code_lines.append("robot.right()")
                    code_lines.append("sleep(0.5)")
                    code_lines.append("robot.stop()")
                elif block_type == "rotate_180":
                    code_lines.append("robot.left()")
                    code_lines.append("sleep(1.0)")
                    code_lines.append("robot.stop()")
                elif block_type == "wait":
                    code_lines.append(f"sleep({params.get('seconds', 1)})")
                elif block_type == "return_home":
                    code_lines.append("# 帰還: 反転して前進")
                    code_lines.append("robot.left()")
                    code_lines.append("sleep(1.0)")
                    code_lines.append("robot.stop()")
            
            code_lines.extend([
                "",
                "# 使用前の準備:",
                "# 1. Raspberry Piにgpiozeroをインストール: pip install gpiozero",
                "# 2. モータードライバ（L298N等）を接続",
                "# 3. GPIOピンを正しく配線",
                "# 4. ピン番号を実際の配線に合わせて変更"
            ])
        else:
            # シミュレーション
            code_lines.extend([
                "import tkinter as tk",
                "from tkinter import messagebox",
                "",
                "# 自走式ロボット制御プログラム（シミュレーション）",
                "",
                "class RobotController:",
                "    def __init__(self):",
                "        self.x = 0",
                "        self.y = 0",
                "        self.direction = 0  # 0=北, 1=東, 2=南, 3=西",
                "        self.start_x = 0",
                "        self.start_y = 0",
                "        self.start_direction = 0",
                "        self.directions = ['北', '東', '南', '西']",
                "",
                "    def forward(self, distance):",
                "        if self.direction == 0:",
                "            self.y += distance",
                "        elif self.direction == 1:",
                "            self.x += distance",
                "        elif self.direction == 2:",
                "            self.y -= distance",
                "        else:",
                "            self.x -= distance",
                "        print(f'{distance}メートル前進しました（向き: {self.directions[self.direction]}）')",
                "",
                "    def backward(self, distance):",
                "        if self.direction == 0:",
                "            self.y -= distance",
                "        elif self.direction == 1:",
                "            self.x -= distance",
                "        elif self.direction == 2:",
                "            self.y += distance",
                "        else:",
                "            self.x += distance",
                "        print(f'{distance}メートル後退しました（向き: {self.directions[self.direction]}）')",
                "",
                "    def rotate_left(self):",
                "        self.direction = (self.direction + 3) % 4",
                "        print(f'左に90度回転しました（現在の向き: {self.directions[self.direction]}）')",
                "",
                "    def rotate_right(self):",
                "        self.direction = (self.direction + 1) % 4",
                "        print(f'右に90度回転しました（現在の向き: {self.directions[self.direction]}）')",
                "",
                "    def rotate_180(self):",
                "        self.direction = (self.direction + 2) % 4",
                "        print(f'180度反転しました（現在の向き: {self.directions[self.direction]}）')",
                "",
                "    def face_direction(self, direction):",
                "        direction_map = {'北': 0, '東': 1, '南': 2, '西': 3}",
                "        if direction in direction_map:",
                "            self.direction = direction_map[direction]",
                "            print(f'{direction}を向きました')",
                "",
                "    def wait(self, seconds):",
                "        import time",
                "        time.sleep(seconds)",
                "",
                "    def return_home(self):",
                "        print('⚠️ 電波が途絶しました！自動帰還を開始します')",
                "        self.x = self.start_x",
                "        self.y = self.start_y",
                "        self.direction = self.start_direction",
                "        print('✅ 元の位置に帰還完了しました')",
                "",
                "    def show_status(self):",
                "        print(f'現在位置: X={self.x}, Y={self.y}, 向き={self.directions[self.direction]}')",
                "",
                "",
                "robot = RobotController()",
                ""
            ])
            
            for block in robot_blocks:
                block_type = block["type"]
                params = block["params"]
                
                if block_type == "forward":
                    code_lines.append(f"robot.forward({params.get('distance', 5)})")
                elif block_type == "backward":
                    code_lines.append(f"robot.backward({params.get('distance', 5)})")
                elif block_type == "rotate_left":
                    code_lines.append("robot.rotate_left()")
                elif block_type == "rotate_right":
                    code_lines.append("robot.rotate_right()")
                elif block_type == "rotate_180":
                    code_lines.append("robot.rotate_180()")
                elif block_type == "face_direction":
                    code_lines.append(f"robot.face_direction('{params.get('direction', '北')}')")
                elif block_type == "wait":
                    code_lines.append(f"robot.wait({params.get('seconds', 1)})")
                elif block_type == "return_home":
                    code_lines.append("robot.return_home()")
            
            code_lines.extend([
                "",
                "robot.show_status()",
                "",
                "# 注意: これはシミュレーションです。",
                "# 実際のロボットを制御するにはハードウェアを選択してください。"
            ])
    
    generated_code = add_python_shebang("\n".join(code_lines))
    robot_code_output.set(generated_code)
    
    # エディターに転送
    if text.get("1.0", tk.END).strip():
        if not messagebox.askyesno("上書き確認", "エディターの内容を生成コードで置き換えますか？"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", generated_code + "\n")
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    
    # ハードウェアに応じたメッセージ
    if hardware == "tello":
        messagebox.showinfo("生成完了", "DJI Tello用コードを生成しました！\n\n使用前の準備:\n1. pip install djitellopy\n2. Telloの電源を入れる\n3. WiFiでTelloに接続\n4. プログラムを実行")
    elif hardware == "rpi":
        messagebox.showinfo("生成完了", "Raspberry Pi用コードを生成しました！\n\n使用前の準備:\n1. pip install gpiozero\n2. モータードライバを接続\n3. GPIOピンを配線\n4. ピン番号を確認・変更")
    else:
        messagebox.showinfo("生成完了", "シミュレーションコードをエディターに転送しました！")

def center_dialog(dialog):
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'+{x}+{y}')

def robot_add_takeoff():
    dialog = tk.Toplevel(root)
    dialog.title("離陸設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="上昇メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    height_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=height_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            height = float(height_var.get())
            robot_add_block("takeoff", {"height": height})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_land():
    robot_add_block("land")

def robot_add_forward():
    dialog = tk.Toplevel(root)
    dialog.title("前進設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="移動メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("forward", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_backward():
    dialog = tk.Toplevel(root)
    dialog.title("後退設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="移動メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("backward", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_left():
    dialog = tk.Toplevel(root)
    dialog.title("左移動設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="移動メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("left", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_right():
    dialog = tk.Toplevel(root)
    dialog.title("右移動設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="移動メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("right", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_up():
    dialog = tk.Toplevel(root)
    dialog.title("上昇設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="上昇メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    height_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=height_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            height = float(height_var.get())
            robot_add_block("up", {"height": height})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_down():
    dialog = tk.Toplevel(root)
    dialog.title("下降設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="下降メートル数:", font=("Meiryo UI", 12)).pack(pady=15)
    height_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=height_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            height = float(height_var.get())
            robot_add_block("down", {"height": height})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_rotate_left():
    dialog = tk.Toplevel(root)
    dialog.title("左回転角度設定")
    dialog.geometry("300x180")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="回転角度（度）:", font=("Meiryo UI", 12)).pack(pady=15)
    angle_var = tk.StringVar(value="90")
    tk.Entry(dialog, textvariable=angle_var, font=("Meiryo UI", 12), justify="center").pack(pady=5)

    def confirm():
        try:
            angle = float(angle_var.get())
            robot_add_block("rotate_left", {"angle": angle})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)

    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white",
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_rotate_right():
    dialog = tk.Toplevel(root)
    dialog.title("右回転角度設定")
    dialog.geometry("300x180")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="回転角度（度）:", font=("Meiryo UI", 12)).pack(pady=15)
    angle_var = tk.StringVar(value="90")
    tk.Entry(dialog, textvariable=angle_var, font=("Meiryo UI", 12), justify="center").pack(pady=5)

    def confirm():
        try:
            angle = float(angle_var.get())
            robot_add_block("rotate_right", {"angle": angle})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)

    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white",
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_rotate_180():
    robot_add_block("rotate_180")

def robot_add_face_direction():
    dialog = tk.Toplevel(root)
    dialog.title("方向設定")
    dialog.geometry("350x200")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="向きを選択:", font=("Meiryo UI", 12)).pack(pady=15)
    dir_var = tk.StringVar(value="北")
    directions = ["北", "東", "南", "西"]
    ttk.Combobox(dialog, textvariable=dir_var, values=directions, state="readonly", 
                 width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        robot_add_block("face_direction", {"direction": dir_var.get()})
        dialog.destroy()
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_wait():
    dialog = tk.Toplevel(root)
    dialog.title("待機設定")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="待機秒数:", font=("Meiryo UI", 12)).pack(pady=15)
    sec_var = tk.StringVar(value="1")
    tk.Entry(dialog, textvariable=sec_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            sec = float(sec_var.get())
            robot_add_block("wait", {"seconds": sec})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("エラー", "数字を入力してください", parent=dialog)
    
    tk.Button(dialog, text="追加", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_return_home():
    robot_add_block("return_home")

# ドローン・ロボット制御タブのUI
robot_main_frame = tk.Frame(tab_robot, bg=THEMES[current_theme]['bg'])
robot_main_frame.pack(expand=True, fill="both", padx=15, pady=15)

# モード選択
robot_mode_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_mode_frame.pack(fill="x", pady=(0, 15))
tk.Label(robot_mode_frame, text="制御モード:", font=("Meiryo UI", 13, "bold"), 
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left", padx=(0, 15))
mode_drone_btn = tk.Radiobutton(robot_mode_frame, text="🚁 ドローン", variable=robot_control_mode, 
                                value="drone", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                font=("Meiryo UI", 12), selectcolor=THEMES[current_theme]['button_bg'])
mode_drone_btn.pack(side="left", padx=8)
mode_robot_btn = tk.Radiobutton(robot_mode_frame, text="🤖 自走ロボット", variable=robot_control_mode, 
                                value="robot", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                font=("Meiryo UI", 12), selectcolor=THEMES[current_theme]['button_bg'])
mode_robot_btn.pack(side="left", padx=8)

# ハードウェア選択と操作ボタン
robot_hardware_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_hardware_frame.pack(fill="x", pady=(0, 15))
tk.Label(robot_hardware_frame, text="ハードウェア:", font=("Meiryo UI", 13, "bold"),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left", padx=(0, 15))
robot_hardware_var = tk.StringVar(value="simulation")
hardware_drone_sim = tk.Radiobutton(robot_hardware_frame, text="シミュレーション", variable=robot_hardware_var,
                                     value="simulation", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                     font=("Meiryo UI", 11), selectcolor=THEMES[current_theme]['button_bg'])
hardware_drone_sim.pack(side="left", padx=5)
hardware_drone_tello = tk.Radiobutton(robot_hardware_frame, text="DJI Tello", variable=robot_hardware_var,
                                       value="tello", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                       font=("Meiryo UI", 11), selectcolor=THEMES[current_theme]['button_bg'])
hardware_drone_tello.pack(side="left", padx=5)
hardware_robot_rpi = tk.Radiobutton(robot_hardware_frame, text="Raspberry Pi", variable=robot_hardware_var,
                                      value="rpi", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                      font=("Meiryo UI", 11), selectcolor=THEMES[current_theme]['button_bg'])
hardware_robot_rpi.pack(side="left", padx=5)

# 操作ボタンをハードウェア選択の列に追加
tk.Frame(robot_hardware_frame, width=30, bg=THEMES[current_theme]['bg']).pack(side="left")  # スペーサー
tk.Button(robot_hardware_frame, text="🗑️ 最後のブロックを削除", command=robot_delete_last_block,
          bg="#dc3545", fg="white", font=("Meiryo UI", 10, "bold"), width=18, height=1).pack(side="left", padx=3)
tk.Button(robot_hardware_frame, text="🧹 全ブロックを消去", command=robot_clear_blocks,
          bg="#6c757d", fg="white", font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(side="left", padx=3)
tk.Button(robot_hardware_frame, text="📝 コード生成して転送", command=robot_generate_code,
          bg="#0d6efd", fg="white", font=("Meiryo UI", 10, "bold"), width=18, height=1).pack(side="left", padx=3)

# メインコンテンツエリア（左右分割）
robot_content_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_content_frame.pack(expand=True, fill="both", pady=(0, 15))

# 左側：ボタンエリア
robot_buttons_frame = tk.LabelFrame(robot_content_frame, text=" ブロックを追加 ", 
                                   bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                   font=("Meiryo UI", 12, "bold"), padx=12, pady=12)
robot_buttons_frame.pack(side="left", fill="y", padx=(0, 10))

# ドローン用ボタン（縦並び）
drone_btns = tk.Frame(robot_buttons_frame, bg=THEMES[current_theme]['bg'])
drone_btns.pack(fill="x")
tk.Button(drone_btns, text="🚀 離陸", command=robot_add_takeoff, bg="#198754", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🛬 着陸", command=robot_add_land, bg="#dc3545", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⬆️ 前進", command=robot_add_forward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⬇️ 後退", command=robot_add_backward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⬅️ 左移動", command=robot_add_left, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="➡️ 右移動", command=robot_add_right, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🔼 上昇", command=robot_add_up, bg="#17a2b8", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🔽 下降", command=robot_add_down, bg="#17a2b8", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="↪️ 左回転", command=robot_add_rotate_left, bg="#6c757d", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="↩️ 右回転", command=robot_add_rotate_right, bg="#6c757d", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⏱️ 待機", command=robot_add_wait, bg="#fd7e14", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🏠 電波途脱時帰還", command=robot_add_return_home, bg="#ffc107", fg="#000", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)

# ロボット用ボタン（縦並び、初期は非表示）
robot_btns = tk.Frame(robot_buttons_frame, bg=THEMES[current_theme]['bg'])
robot_btns.pack_forget()  # 初期は非表示
tk.Button(robot_btns, text="⬆️ 前進", command=robot_add_forward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="⬇️ 後退", command=robot_add_backward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="↪️ 左回転", command=robot_add_rotate_left, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="↩️ 右回転", command=robot_add_rotate_right, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🔄 反転", command=robot_add_rotate_180, bg="#6610f2", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🧭 方向を向く", command=robot_add_face_direction, bg="#20c997", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="⏱️ 待機", command=robot_add_wait, bg="#fd7e14", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🏠 電波途脱時帰還", command=robot_add_return_home, bg="#ffc107", fg="#000", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)

def update_robot_buttons():
    mode = robot_control_mode.get()
    if mode == "drone":
        drone_btns.pack(fill="x")
        robot_btns.pack_forget()
    else:
        drone_btns.pack_forget()
        robot_btns.pack(fill="x")

robot_control_mode.trace_add("write", lambda *args: update_robot_buttons())

# 右側：プログラム表示エリア
robot_program_frame = tk.LabelFrame(robot_content_frame, text=" プログラム ", 
                                   bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                   font=("Meiryo UI", 12, "bold"), padx=12, pady=12)
robot_program_frame.pack(side="left", expand=True, fill="both")

robot_canvas_frame = tk.Frame(robot_program_frame, bg=THEMES[current_theme]['bg'])
robot_canvas_frame.pack(expand=True, fill="both")
robot_canvas = tk.Canvas(robot_canvas_frame, bg=THEMES[current_theme]['text_bg'], 
                        highlightthickness=0)
robot_canvas.pack(side="left", expand=True, fill="both")

# Canvasサイズ変更時にブロックを再配置
robot_canvas.bind("<Configure>", lambda e: robot_refresh_blocks_display())


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
