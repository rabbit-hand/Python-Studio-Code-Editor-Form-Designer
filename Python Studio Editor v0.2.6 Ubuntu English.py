#!/usr/bin/env python3

import sys
try:
    import tkinter as tk
    from tkinter import messagebox, filedialog, colorchooser, ttk
except ModuleNotFoundError as error:
    if error.name not in {"tkinter", "_tkinter"}:
        raise
    print(
        "Tkinter not found. On Ubuntu-based Linux, please run "
        "\"sudo apt install python3-tk python3-venv\".",
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
APP_VERSION = "0.2.6"

# Settings
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
        "        raise ValueError('Hotkey is empty.')",
        "    return '+'.join(f'<{aliases.get(part, part)}>' if len(part) > 1 else part for part in parts)",
        "",
        "def send_hotkey_keys(sequence):",
        "    aliases = {'control': 'ctrl', 'windows': 'cmd', 'win': 'cmd', 'super': 'cmd', 'return': 'enter', 'escape': 'esc'}",
        "    names = [aliases.get(part.strip().lower(), part.strip().lower()) for part in sequence.split('+') if part.strip()]",
        "    if not names:",
        "        raise ValueError('Keys to send are empty.')",
        "    special = {'ctrl': pynput_keyboard.Key.ctrl, 'alt': pynput_keyboard.Key.alt, 'shift': pynput_keyboard.Key.shift, 'cmd': pynput_keyboard.Key.cmd}",
        "    keys = []",
        "    for name in names:",
        "        key = special.get(name) or getattr(pynput_keyboard.Key, name, None)",
        "        if key is None and len(name) == 1:",
        "            key = name",
        "        if key is None:",
        "            raise ValueError(f'Unsupported key: {name}')",
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
        "                raise ValueError('Command to execute is empty.')",
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
        "        root.after(0, lambda error=error: messagebox.showerror('Hotkey', f\"{action['button'] or action['shortcut']}: {error}\", parent=root))",
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
        "        messagebox.showwarning('Cannot register hotkey', 'pynput is not installed. Button operations can still be used.', parent=root)",
        "        return None",
        "    if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland' or os.environ.get('WAYLAND_DISPLAY'):",
        "        messagebox.showwarning('Hotkey limitation', 'Apps cannot register global hotkeys on Wayland. Button operations can be used. If needed, register via desktop environment shortcut settings.', parent=root)",
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
        "        messagebox.showwarning('Cannot register hotkey', f'{error}\\nButton operations can still be used.', parent=root)",
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
        "    messagebox.showwarning('Hotkey already running', 'An app with the same hotkey is already running. Exiting to prevent duplicate execution.', parent=root)",
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
        "        if item_text == 'Menu':",
        "            show_tray_menu()",
        "        elif item_text == 'Exit':",
        "            shutdown_app()",
        "        else:",
        "            restore_window()",
        "",
        "def show_tray_menu():",
        "    tray_menu = tk.Menu(root, tearoff=0)",
        "    tray_menu.add_command(label='View', command=restore_window)",
        "    tray_menu.add_separator()",
        "    tray_menu.add_command(label='Exit', command=shutdown_app)",
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
        "            pystray.Menu(pystray.MenuItem('Menu', on_tray_action, default=True))",
        "            if pystray.Icon.__module__ == 'pystray._xorg'",
        "            else pystray.Menu(",
        "                pystray.MenuItem('View', on_tray_action, default=True),",
        "                pystray.MenuItem('Exit', on_tray_action),",
        "            )",
        "        )",
        "        icon = pystray.Icon('PythonStudio', tray_image, 'Python Studio', menu=tray_menu)",
        "        icon.run_detached()",
        "        root.withdraw()",
        "    except Exception as error:",
        "        messagebox.showwarning('Cannot use System Tray', str(error), parent=root)",
        "        icon = None",
        "        root.deiconify()",
        "else:",
        "    messagebox.showwarning('Cannot use System Tray', 'System Tray feature requires pystray and Pillow.', parent=root)",
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
        raise RuntimeError("Could not create Python in Virtual Environment.")
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
        res = messagebox.askyesnocancel("Confirm", "Changes not saved. Save?")
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
            messagebox.showinfo("Save Complete", f"File overwritten and saved:\n{os.path.basename(quick_save.current_file_path)}")
            return True
        except OSError as e:
            messagebox.showerror("Error", f"Save Failed: {e}")
            return False
    else:
        return save_as_file()

def save_as_file():
    global last_saved_content, text_modified
    content = text.get("1.0", tk.END).strip()
    selected_filetype = tk.StringVar(root)
    path = filedialog.asksaveasfilename(
        filetypes=[
            ("Python Files (*.py)", "*.py")
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
            messagebox.showinfo("Save Complete", f"File saved:\n{os.path.basename(path)}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Save Failed: {e}")
    return False

def open_file():
    global last_saved_content, text_modified
    path = filedialog.askopenfilename(
        filetypes=[("Python Files", "*.py")]
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
            messagebox.showerror("Error", f"Load Failed: {e}")

def new_file():
    global text_modified, last_saved_content
    if text_modified and not messagebox.askyesno("Confirm", "Discard current content and create new?"):
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
        "category": "Practice Mini Apps", "name": "Calculator", "kind": "code",
        "description": "Select two numbers and calculation method to view result. Simple GUI calculator.",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Simple Calculator")
root.geometry("320x220")
first = tk.Entry(root)
first.pack(padx=12, pady=(16, 6), fill="x")
operation = tk.StringVar(value="+")
tk.OptionMenu(root, operation, "+", "-", "*", "/").pack()
second = tk.Entry(root)
second.pack(padx=12, pady=6, fill="x")
result = tk.Label(root, text="Answer: ")
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
        result.config(text=f"Answer: {answer:g}")
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a number in both fields.")
    except ZeroDivisionError:
        messagebox.showerror("Calculation Error", "Cannot divide by zero.")

tk.Button(root, text="Calculate", command=calculate).pack(pady=4)
root.mainloop()
'''
    },
    {
        "category": "Practice Mini Apps", "name": "Rock Paper Scissors Game", "kind": "code",
        "description": "Press button to play against computer. Win/loss count also displayed.",
        "code": '''import random
import tkinter as tk

root = tk.Tk()
root.title("Rock Paper Scissors")
root.geometry("340x220")
score = {"Win": 0, "Lose": 0, "Draw": 0}
result = tk.Label(root, text="Please choose your hand", font=("Meiryo UI", 14))
result.pack(pady=20)
score_label = tk.Label(root, text="Win 0  Lose 0  Draw 0")
score_label.pack(pady=8)

def play(player):
    computer = random.choice(["Rock", "Scissors", "Paper"])
    if player == computer:
        outcome = "Draw"
    elif (player, computer) in [("Rock", "Scissors"), ("Scissors", "Paper"), ("Paper", "Rock")]:
        outcome = "Win"
    else:
        outcome = "Lose"
    score[outcome] += 1
    result.config(text=f"You: {player} / Opponent: {computer}  → {outcome}")
    score_label.config(text=f"Win {score['Win']}  Lose {score['Lose']}  Draw {score['Draw']}")

for hand in ("Rock", "Scissors", "Paper"):
    tk.Button(root, text=hand, command=lambda value=hand: play(value)).pack(side="left", expand=True, padx=8)
root.mainloop()
'''
    },
    {
        "category": "Practice Mini Apps", "name": "Number Guessing Game", "kind": "code",
        "description": "Guess a number from 1 to 100. Enter number in input field to check.",
        "code": '''import random
import tkinter as tk

root = tk.Tk()
root.title("Number Guessing Game")
root.geometry("340x220")
answer = random.randint(1, 100)
tries = 0
message = tk.Label(root, text="Guess a number from 1 to 100")
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
        message.config(text="Please enter an integer from 1 to 100")
        return
    tries += 1
    if number == answer:
        message.config(text=f"Correct! {tries}attempts to guess correctly")
    elif number < answer:
        message.config(text="Number is higher")
    else:
        message.config(text="Number is lower")

tk.Button(root, text="Check", command=check_guess).pack(pady=8)
root.mainloop()
'''
    },
    {
        "category": "Practice Mini Apps", "name": "Timer", "kind": "code",
        "description": "Timer that counts down from specified seconds.",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Timer")
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
        messagebox.showinfo("Timer", "Time is up!")
        return
    seconds_left -= 1
    root.after(1000, tick)

def start():
    global seconds_left, running
    try:
        seconds_left = int(seconds_input.get())
        if seconds_left <= 0: raise ValueError
    except ValueError:
        messagebox.showerror("Input Error", "Please enter 1 or more seconds.")
        return
    running = True
    tick()

tk.Button(root, text="Start", command=start).pack(pady=10)
root.mainloop()
'''
    },
    {
        "category": "Daily Useful Tools", "name": "ToDoList", "kind": "code",
        "description": "Can add tasks and delete completed items.",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("ToDoList")
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
        messagebox.showinfo("Confirm", "Please select a task to delete.")

buttons = tk.Frame(root)
buttons.pack(pady=10)
tk.Button(buttons, text="Add", command=add_task).pack(side="left", padx=5)
tk.Button(buttons, text="Delete Selected Item", command=remove_task).pack(side="left", padx=5)
root.mainloop()
'''
    },
    {
        "category": "Daily Useful Tools", "name": "Notepad", "kind": "code",
        "description": "Edit text and open/save as text file.",
        "code": '''import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("Simple Notepad")
root.geometry("640x440")
editor = tk.Text(root, wrap="word", undo=True)
editor.pack(fill="both", expand=True, padx=8, pady=8)

def open_note():
    path = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
    if path:
        try:
            with open(path, encoding="utf-8") as file:
                editor.delete("1.0", tk.END)
                editor.insert("1.0", file.read())
        except OSError as error:
            messagebox.showerror("LoadError", str(error))

def save_note():
    path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
    if path:
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(editor.get("1.0", "end-1c"))
            messagebox.showinfo("Save", "Memo saved.")
        except OSError as error:
            messagebox.showerror("SaveError", str(error))

toolbar = tk.Frame(root)
toolbar.pack(fill="x")
tk.Button(toolbar, text="Open", command=open_note).pack(side="left", padx=6, pady=4)
tk.Button(toolbar, text="Save As", command=save_note).pack(side="left", padx=6, pady=4)
root.mainloop()
'''
    },
    {
        "category": "Daily Useful Tools", "name": "Password Generator", "kind": "code",
        "description": "Create random password of specified length.",
        "code": '''import secrets
import string
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Password Generator")
root.geometry("380x190")
tk.Label(root, text="Character count (8-128)").pack(pady=(18, 4))
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
        messagebox.showerror("Input Error", "Please enter an integer from 8 to 128.")
        return
    alphabet = string.ascii_letters + string.digits + "!@#$%&*+-_"
    result.delete(0, tk.END)
    result.insert(0, "".join(secrets.choice(alphabet) for _ in range(size)))

tk.Button(root, text="Generate", command=generate).pack()
root.mainloop()
'''
    },
    {
        "category": "Daily Useful Tools", "name": "Bulk Rename Files", "kind": "code",
        "description": "Add prefix to file names in selected folder. Confirms before changes.",
        "code": '''import os
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("Bulk Rename Files")
root.geometry("430x210")
folder = tk.StringVar()
prefix = tk.StringVar(value="Organized_")

def choose_folder():
    selected = filedialog.askdirectory()
    if selected:
        folder.set(selected)

tk.Label(root, text="Target Folder").pack(anchor="w", padx=12, pady=(12, 2))
tk.Entry(root, textvariable=folder).pack(fill="x", padx=12)
tk.Button(root, text="Select Folder", command=choose_folder).pack(anchor="e", padx=12, pady=4)
tk.Label(root, text="Prefix character to add to file names").pack(anchor="w", padx=12, pady=(6, 2))
tk.Entry(root, textvariable=prefix).pack(fill="x", padx=12)

def rename_files():
    path, start = folder.get(), prefix.get()
    if not path or not start:
        messagebox.showerror("Input Error", "Please specify folder and prefix.")
        return
    files = [name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name)) and not name.startswith(start)]
    if not files:
        messagebox.showinfo("Confirm", "No files to change.")
        return
    if not messagebox.askyesno("Confirm Changes", f"{len(files)}file names will be changed. Continue?"):
        return
    renamed = 0
    for name in files:
        old = os.path.join(path, name)
        new = os.path.join(path, start + name)
        if not os.path.exists(new):
            os.rename(old, new)
            renamed += 1
    messagebox.showinfo("Complete", f"{renamed}file names changed.")

tk.Button(root, text="Bulk Rename", command=rename_files).pack(pady=10)
root.mainloop()
'''
    },
    {
        "category": "Daily Useful Tools", "name": "CSV Organization & Summary", "kind": "code",
        "description": "Open CSV file and view count and sum of values for each column.",
        "code": '''import csv
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("CSV Simple Summary")
root.geometry("900x620")
root.minsize(720, 500)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

toolbar = tk.Frame(root, padx=16, pady=14)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Label(toolbar, text="Summarize CSV File", font=("Meiryo UI", 15, "bold")).pack(side="left")
output_frame = tk.Frame(root, padx=16, pady=12)
output_frame.grid(row=1, column=0, sticky="nsew")
output_frame.grid_columnconfigure(0, weight=1)
output_frame.grid_rowconfigure(0, weight=1)
output = tk.Text(output_frame, wrap="none", font=("Meiryo UI", 11), padx=10, pady=8)
output.grid(row=0, column=0, sticky="nsew")
scrollbar = tk.Scrollbar(output_frame, orient="vertical", command=output.yview)
scrollbar.grid(row=0, column=1, sticky="ns")
output.config(yscrollcommand=scrollbar.set)
status = tk.Label(root, text="Select CSV file to view count and sum for each column.",
              anchor="w", font=("Meiryo UI", 10), padx=16)
status.grid(row=2, column=0, sticky="ew", pady=(0, 6))

def summarize():
    path = filedialog.askopenfilename(filetypes=[("CSVFile", "*.csv"), ("All", "*.*")])
    if not path:
        return
    try:
        with open(path, newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
        if not rows:
            messagebox.showinfo("Confirm", "CSV has no data rows.")
            return
        lines = [f"Data rows: {len(rows)}"]
        for column in rows[0]:
            values = [row.get(column, "").strip() for row in rows]
            numbers = []
            for value in values:
                try:
                    numbers.append(float(value.replace(",", "")))
                except ValueError:
                    pass
            lines.append(f"{column}: Input {sum(bool(v) for v in values)}items")
            if numbers:
                lines.append(f"  Numeric sum: {sum(numbers):g}")
        output.delete("1.0", tk.END)
        output.insert("1.0", "\\n".join(lines))
        status.config(text=f"Summary Complete: {len(rows)}rows")
    except (OSError, csv.Error) as error:
        messagebox.showerror("LoadError", str(error))

tk.Button(toolbar, text="Select CSV and Summarize", command=summarize,
          font=("Meiryo UI", 12, "bold"), padx=28, pady=12).pack(side="right")
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "Get Web Page Title", "kind": "code",
        "description": "Enter URL to get web page title using standard library.",
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
root.title("Get Web Page Title")
root.geometry("480x180")
url = tk.Entry(root)
url.insert(0, "https://example.com")
url.pack(fill="x", padx=12, pady=16)
result = tk.Label(root, text="Results will be displayed here", wraplength=440)
result.pack(pady=8)

def fetch_title():
    address = url.get().strip()
    if not address.startswith(("https://", "http://")):
        messagebox.showerror("URL Error", "Please enter a URL starting with http:// or https://")
        return
    try:
        request = Request(address, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=10) as response:
            parser = TitleParser()
            parser.feed(response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace"))
        result.config(text=parser.title.strip() or "Title not found.")
    except Exception as error:
        messagebox.showerror("Fetch Error", str(error))

tk.Button(root, text="Get Title", command=fetch_title).pack()
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "Weather App", "kind": "code",
        "description": "Get weather by city name. Uses Open-Meteo free API, no API key needed.",
        "code": '''import json
from urllib.parse import urlencode
from urllib.request import urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Simple Weather")
root.geometry("360x210")
city = tk.Entry(root, justify="center")
city.insert(0, "Tokyo")
city.pack(fill="x", padx=18, pady=(20, 8))
result = tk.Label(root, text="Please enter a city name", font=("Meiryo UI", 12), wraplength=320)
result.pack(pady=12)

def get_weather():
    name = city.get().strip()
    if not name:
        messagebox.showerror("Input Error", "Please enter a city name.")
        return
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({"name": name, "count": 1, "language": "ja", "format": "json"})
        with urlopen(geo_url, timeout=10) as response:
            places = json.load(response).get("results", [])
        if not places:
            result.config(text="City not found")
            return
        place = places[0]
        query = urlencode({"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,relative_humidity_2m,weather_code"})
        with urlopen("https://api.open-meteo.com/v1/forecast?" + query, timeout=10) as response:
            current = json.load(response)["current"]
        result.config(text=f"{place['name']}\\nTemperature {current['temperature_2m']}℃ / Humidity {current['relative_humidity_2m']}%\\nWeather code {current['weather_code']}")
    except Exception as error:
        messagebox.showerror("Fetch Error", str(error))

tk.Button(root, text="Get Weather", command=get_weather).pack()
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "Discord Webhook Send", "kind": "code",
        "description": "Enter Webhook URL and message to send to Discord. No additional libraries or bot tokens needed. Treat Webhook URL as secret.",
        "code": '''import json
from urllib.error import HTTPError, URL Error
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Discord Webhook Send")
root.geometry("640x440")
root.minsize(560, 390)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(3, weight=1)

tk.Label(root, text="Discord Webhook URL", font=("Meiryo UI", 11, "bold")).grid(
    row=0, column=0, sticky="w", padx=18, pady=(18, 4)
)
webhook_input = tk.Entry(root, font=("Consolas", 10))
webhook_input.grid(row=1, column=0, sticky="ew", padx=18)
tk.Label(root, text="Message to send", font=("Meiryo UI", 11, "bold")).grid(
    row=2, column=0, sticky="w", padx=18, pady=(14, 4)
)
message_input = tk.Text(root, height=7, wrap="word", font=("Meiryo UI", 11))
message_input.grid(row=3, column=0, sticky="nsew", padx=18)
status = tk.Label(root, text="Please enter Webhook URL and message.", anchor="w")
status.grid(row=4, column=0, sticky="ew", padx=18, pady=8)

def send_message():
    webhook = webhook_input.get().strip()
    content = message_input.get("1.0", "end-1c").strip()
    parsed = urlparse(webhook)
    if parsed.scheme != "https" or parsed.netloc not in ("discord.com", "discordapp.com") or not parsed.path.startswith("/api/webhooks/"):
        messagebox.showerror("URL Error", "Please enter Discord Webhook URL.")
        return
    if not content:
        messagebox.showerror("Input Error", "Please enter message to send.")
        return
    if len(content) > 2000:
        messagebox.showerror("Input Error", "Message must be 2000 characters or less.")
        return
    request = Request(webhook, data=json.dumps({"content": content}).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Unexpected response from Discord: {response.status}")
        status.config(text="Sent.")
    except HTTPError as error:
        messagebox.showerror("Discord Error", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}")
    except (URL Error, TimeoutError, RuntimeError) as error:
        messagebox.showerror("Send Error", str(error))

tk.Button(root, text="Send to Discord", command=send_message,
          font=("Meiryo UI", 12, "bold"), padx=24, pady=10).grid(
              row=5, column=0, sticky="e", padx=18, pady=(0, 16)
          )
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "LINE Notification (Official Messaging API)", "kind": "code",
        "description": "GUI to send messages via LINE official API. Requires channel access token and recipient ID. Webhook URL alone cannot send to official LINE.",
        "code": '''import json
from urllib.error import HTTPError, URL Error
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("LINE Message Send")
root.geometry("620x520")
root.minsize(540, 470)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(7, weight=1)

tk.Label(root, text="Send message via LINE Messaging API", font=("Meiryo UI", 14, "bold")).grid(
    row=0, column=0, sticky="w", padx=18, pady=(18, 4)
)
tk.Label(root, text="Use channel access token and recipient ID instead of Webhook URL.",
         wraplength=570, justify="left").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 10))
tk.Label(root, text="Channel Access Token", font=("Meiryo UI", 10, "bold")).grid(
    row=2, column=0, sticky="w", padx=18, pady=(4, 3)
)
token_input = tk.Entry(root, show="*", font=("Consolas", 10))
token_input.grid(row=3, column=0, sticky="ew", padx=18)
tk.Label(root, text="Recipient User ID or Group ID", font=("Meiryo UI", 10, "bold")).grid(
    row=4, column=0, sticky="w", padx=18, pady=(10, 3)
)
recipient_input = tk.Entry(root, font=("Consolas", 10))
recipient_input.grid(row=5, column=0, sticky="ew", padx=18)
tk.Label(root, text="Message", font=("Meiryo UI", 10, "bold")).grid(
    row=6, column=0, sticky="w", padx=18, pady=(8, 3)
)
message_input = tk.Text(root, height=5, wrap="word", font=("Meiryo UI", 11))
message_input.grid(row=7, column=0, sticky="nsew", padx=18)
status = tk.Label(root, text="Entered tokens are not saved.", anchor="w")
status.grid(row=8, column=0, sticky="ew", padx=18, pady=8)

def send_message():
    token = token_input.get().strip()
    recipient = recipient_input.get().strip()
    content = message_input.get("1.0", "end-1c").strip()
    if not token or not recipient or not content:
        messagebox.showerror("Input Error", "Please enter token, recipient ID, and message.")
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
                raise RuntimeError(f"Unexpected response from LINE: {response.status}")
        status.config(text="Sent to LINE.")
    except HTTPError as error:
        messagebox.showerror("LINE API Error", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}")
    except (URL Error, TimeoutError, RuntimeError) as error:
        messagebox.showerror("Send Error", str(error))

tk.Button(root, text="Send to LINE", command=send_message,
          font=("Meiryo UI", 12, "bold"), padx=24, pady=10).grid(
              row=9, column=0, sticky="e", padx=18, pady=(0, 16)
          )
root.mainloop()
'''
    },
    {
        "category": "Module Examples - File System", "name": "File Manager", "kind": "code",
        "description": "Browse and manipulate files and folders. Uses os, pathlib, shutil modules.",
        "code": '''import os
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

root = tk.Tk()
root.title("File Manager")
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
            size = f"{item.stat().st_size:,} bytes" if item.is_file() else ""
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
    name = tk.simpledialog.askstring("New Folder", "Enter folder name:", parent=root)
    if name:
        try:
            (Path(current_path.get()) / name).mkdir()
            refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

def delete_selected():
    selection = tree.selection()
    if not selection:
        return
    item = tree.item(selection[0])
    name = item["values"][1]
    target = Path(current_path.get()) / name
    if messagebox.askyesno("Confirm", f"{name}Delete"):
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            refresh_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

toolbar = tk.Frame(root, padx=10, pady=8)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Button(toolbar, text="⬆ Up", command=go_up).pack(side="left", padx=2)
tk.Button(toolbar, text="⬇ Open", command=go_down).pack(side="left", padx=2)
tk.Button(toolbar, text="📁 New Folder", command=create_folder).pack(side="left", padx=2)
tk.Button(toolbar, text="🗑 Delete", command=delete_selected).pack(side="left", padx=2)
path_entry = tk.Entry(toolbar, textvariable=current_path, width=50)
path_entry.pack(side="left", padx=10)
tk.Button(toolbar, text="Move", command=refresh_list).pack(side="left")

columns = ("icon", "name", "size")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("icon", text="")
tree.heading("name", text="Name")
tree.heading("size", text="Size")
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
        "category": "Module Examples - File System", "name": "Text File Search", "kind": "code",
        "description": "Search for text in files within a folder. Uses os, re, glob modules.",
        "code": '''import os
import re
import glob
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

root = tk.Tk()
root.title("Text File Search")
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
        messagebox.showerror("Error", "Invalid folder")
        return
    results = []
    files = glob.glob(os.path.join(folder, "**", pattern), recursive=True)
    try:
        regex = re.compile(text, re.IGNORECASE) if text else None
    except re.error:
        messagebox.showerror("Error", "Invalid regular expression")
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
tk.Label(control_frame, text="Folder:").grid(row=0, column=0, sticky="w")
tk.Entry(control_frame, textvariable=search_folder, width=50).grid(row=0, column=1, padx=5)
tk.Button(control_frame, text="Browse", command=lambda: search_folder.set(filedialog.askdirectory())).grid(row=0, column=2)
tk.Label(control_frame, text="File pattern (e.g. *.txt):").grid(row=1, column=0, sticky="w", pady=5)
tk.Entry(control_frame, textvariable=search_pattern, width=30).grid(row=1, column=1, padx=5, pady=5)
tk.Label(control_frame, text="Search text (regex):").grid(row=2, column=0, sticky="w", pady=5)
tk.Entry(control_frame, textvariable=search_text, width=30).grid(row=2, column=1, padx=5, pady=5)
tk.Button(control_frame, text="Search", command=do_search, bg="#0d6efd", fg="white").grid(row=3, column=0, columnspan=3, pady=10, sticky="ew")

columns = ("file", "line", "preview", "path")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("file", text="File")
tree.heading("line", text="rows")
tree.heading("preview", text="Preview")
tree.heading("path", text="Full Path")
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
        "category": "Module Examples - System", "name": "View System Information", "kind": "code",
        "description": "View system information. Uses platform, os, sys modules.",
        "code": '''import platform
import os
import sys
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("SystemInformation")
root.geometry("700x600")
root.minsize(600, 400)

info_text = tk.Text(root, wrap="word", font=("Consolas", 10), padx=10, pady=10)
info_text.pack(fill="both", expand=True)

def get_system_info():
    info = []
    info.append("=" * 50)
    info.append("SystemInformation")
    info.append("=" * 50)
    info.append(f"Platform: {platform.platform()}")
    info.append(f"System: {platform.system()}")
    info.append(f"Node name: {platform.node()}")
    info.append(f"Release: {platform.release()}")
    info.append(f"Version: {platform.version()}")
    info.append(f"Machine: {platform.machine()}")
    info.append(f"Processor: {platform.processor()}")
    info.append("")
    info.append("=" * 50)
    info.append("PythonInformation")
    info.append("=" * 50)
    info.append(f"PythonVersion: {sys.version}")
    info.append(f"PythonExecuteFile: {sys.executable}")
    info.append(f"PythonPath: {sys.path[0]}")
    info.append("")
    info.append("=" * 50)
    info.append("Environment")
    info.append("=" * 50)
    info.append(f"Current directory: {os.getcwd()}")
    info.append(f"Home directory: {os.path.expanduser('~')}")
    info.append(f"User: {os.getenv('USERNAME', 'Unknown')}")
    info.append("")
    info.append("=" * 50)
    info.append("CPU and Memory")
    info.append("=" * 50)
    info.append(f"CPU count: {os.cpu_count()}")
    info.append(f"Boot time: {platform.boot_time()}")
    return "\\n".join(info)

info_text.insert("1.0", get_system_info())
info_text.config(state="disabled")

root.mainloop()
'''
    },
    {
        "category": "Module Examples - Data", "name": "JSON Editor", "kind": "code",
        "description": "View and edit JSON files. Uses json module.",
        "code": '''import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("JSON Editor")
root.geometry("800x600")
root.minsize(600, 400)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)

current_file = tk.StringVar()

def load_json():
    path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            editor.delete("1.0", tk.END)
            editor.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
            current_file.set(path)
            status.config(text=f"Load: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load JSON: {e}")

def save_json():
    path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
    if path:
        try:
            content = editor.get("1.0", tk.END)
            data = json.loads(content)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            current_file.set(path)
            status.config(text=f"Save: {os.path.basename(path)}")
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

def format_json():
    try:
        content = editor.get("1.0", tk.END)
        data = json.loads(content)
        editor.delete("1.0", tk.END)
        editor.insert("1.0", json.dumps(data, indent=2, ensure_ascii=False))
    except json.JSONDecodeError as e:
        messagebox.showerror("Error", f"Invalid JSON: {e}")

toolbar = tk.Frame(root, padx=10, pady=8)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Button(toolbar, text="Open JSON", command=load_json).pack(side="left", padx=2)
tk.Button(toolbar, text="Save JSON", command=save_json).pack(side="left", padx=2)
tk.Button(toolbar, text="Format", command=format_json).pack(side="left", padx=2)

editor = tk.Text(root, wrap="none", font=("Consolas", 11))
editor.grid(row=1, column=0, sticky="nsew")

y_scroll = tk.Scrollbar(root, orient="vertical", command=editor.yview)
y_scroll.grid(row=1, column=1, sticky="ns")
x_scroll = tk.Scrollbar(root, orient="horizontal", command=editor.xview)
x_scroll.grid(row=2, column=0, sticky="ew")
editor.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

status = tk.Label(root, text="No file loaded", anchor="w")
status.grid(row=3, column=0, sticky="ew", padx=10, pady=5)

root.mainloop()
'''
    },
    {
        "category": "Module Examples - Database", "name": "SQLite Database Management", "kind": "code",
        "description": "Manage SQLite database with CRUD operations. Uses sqlite3 module.",
        "code": '''import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("SQLite Database Management")
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
tk.Label(input_frame, text="Name:").grid(row=0, column=0, padx=5)
name_entry = tk.Entry(input_frame, width=30)
name_entry.grid(row=0, column=1, padx=5)
tk.Label(input_frame, text="Email:").grid(row=0, column=2, padx=5)
email_entry = tk.Entry(input_frame, width=30)
email_entry.grid(row=0, column=3, padx=5)
tk.Button(input_frame, text="Add", command=add_user).grid(row=0, column=4, padx=10)
tk.Button(input_frame, text="Delete Selected", command=delete_user).grid(row=0, column=5, padx=5)

columns = ("id", "name", "email")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("id", text="ID")
tree.heading("name", text="Name")
tree.heading("email", text="Email")
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
        "category": "Module Examples - Network", "name": "HTTP Request Tool", "kind": "code",
        "description": "Send HTTP request and view response. Uses http.client and urllib modules.",
        "code": '''import http.client
import urllib.parse
import json
import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("HTTP Request Tool")
root.geometry("900x700")
root.minsize(800, 500)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(3, weight=1)

method = tk.StringVar(value="GET")
url = tk.StringVar(value="https://httpbin.org/get")

def send_request():
    target_url = url.get().strip()
    if not target_url:
        messagebox.showerror("Error", "Please enter URL")
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
        result_text.insert("1.0", f"Status: {status}\\n\\nHeaders:\\n{headers}\\n\\nBody:\\n{body}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

control_frame = tk.Frame(root, padx=10, pady=10)
control_frame.grid(row=0, column=0, sticky="ew")
tk.Label(control_frame, text="Method:").pack(side="left")
ttk.Combobox(control_frame, textvariable=method, values=("GET", "POST", "PUT", "DELETE"), state="readonly", width=10).pack(side="left", padx=5)
tk.Label(control_frame, text="URL:").pack(side="left", padx=5)
tk.Entry(control_frame, textvariable=url, width=60).pack(side="left", padx=5)
tk.Button(control_frame, text="Send Request", command=send_request, bg="#0d6efd", fg="white").pack(side="left", padx=10)

result_text = tk.Text(root, wrap="word", font=("Consolas", 10), padx=10, pady=10)
result_text.grid(row=3, column=0, sticky="nsew")

y_scroll = ttk.Scrollbar(root, orient="vertical", command=result_text.yview)
y_scroll.grid(row=3, column=1, sticky="ns")
result_text.configure(yscrollcommand=y_scroll.set)

root.mainloop()
'''
    },
    {
        "category": "Module Examples - Utilities", "name": "Calendar App", "kind": "code",
        "description": "View calendar and navigate months. Uses calendar module.",
        "code": '''import calendar
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Calendar App")
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
        
        days = ["Month", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
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
tk.Button(nav_frame, text="◀ Previous Month", command=prev_month).pack(side="left", padx=5)
tk.Entry(nav_frame, textvariable=current_year, width=6).pack(side="left", padx=2)
tk.Entry(nav_frame, textvariable=current_month, width=4).pack(side="left", padx=2)
tk.Button(nav_frame, text="Next Month ▶", command=next_month).pack(side="left", padx=5)
tk.Button(nav_frame, text="Today", command=lambda: (current_year.set(str(calendar.datetime.datetime.now().year)), current_month.set(str(calendar.datetime.datetime.now().month)), update_calendar())).pack(side="left", padx=10)

header = tk.Label(root, text="", font=("Arial", 16, "bold"), pady=10)
header.pack()

calendar_frame = tk.Frame(root, padx=10, pady=10)
calendar_frame.pack()

update_calendar()
root.mainloop()
'''
    },
    {
        "category": "Module Examples - Advanced Features", "name": "Process Management", "kind": "code",
        "description": "List and manage running processes. Uses subprocess and os modules.",
        "code": '''import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("Process Management")
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
        messagebox.showerror("Error", str(e))
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
        if messagebox.askyesno("Confirm", f"Send termination request to process {pid}?"):
            try:
                subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                refresh_list()
            except Exception as e:
                messagebox.showerror("Error", str(e))

toolbar = tk.Frame(root, padx=10, pady=8)
toolbar.grid(row=0, column=0, sticky="ew")
tk.Button(toolbar, text="🔄 Update", command=refresh_list).pack(side="left", padx=2)
tk.Button(toolbar, text="🔴 Terminate processExit", command=kill_process, bg="#dc3545", fg="white").pack(side="left", padx=2)

columns = ("name", "pid")
tree = ttk.Treeview(root, columns=columns, show="headings", selectmode="browse")
tree.heading("name", text="Process name")
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
        "category": "Advanced Projects", "name": "GUI Form (Designer)", "kind": "designer",
        "description": "Place buttons, labels, and input fields to create GUI. Moves to form creation tab.",
        "code": ""
    },
    {
        "category": "Advanced Projects", "name": "System Tray App", "kind": "code",
        "description": "Clicking the tray icon opens a menu with Show and Exit options. (pystray required)",
        "code": '''import tkinter as tk
import os
import sys
import queue
import threading
import time

# Note: To run this code, install pystray with the following command:
# pip install pystray

if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY") and any(name in os.environ.get("XDG_CURRENT_DESKTOP", "").lower() for name in ("cinnamon", "mate", "xfce", "lxde", "lxqt")):
    os.environ.setdefault("PYSTRAY_BACKEND", "xorg")

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("Warning: pystray is not installed. Install with 'pip install pystray'.")

# Window Management
root = tk.Tk()
root.title("System Tray App")
root.geometry("300x200")
icon = None
TRAY_ACTION_QUEUE = queue.SimpleQueue()
# ButtonWindow
button_window = tk.Toplevel(root)
button_window.title("Button")
button_window.geometry("200x200")

# Button frame
button_frame = tk.Frame(button_window)
button_frame.pack(pady=20)

# Action button
action_button = tk.Button(button_frame, text="Click!", font=("Arial", 12), width=15, command=lambda: hide_window())
action_button.pack(pady=5)

# Minimize to Tray button
minimize_button = tk.Button(button_frame, text="Minimize to Tray", font=("Arial", 10), width=15, command=lambda: hide_window())
minimize_button.pack(pady=5)

def show_window():
    """Show Button Window"""
    button_window.deiconify()
    button_window.lift()

def hide_window():
    """Hide Button Window"""
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
        if item_text == "Menu":
            show_tray_menu()
        elif item_text == "Exit":
            shutdown_app()
        else:
            show_window()

def show_tray_menu():
    tray_menu = tk.Menu(root, tearoff=0)
    tray_menu.add_command(label="View", command=show_window)
    tray_menu.add_separator()
    tray_menu.add_command(label="Exit", command=shutdown_app)
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
                pystray.Menu(pystray.MenuItem("Menu", on_tray_action, default=True))
                if pystray.Icon.__module__ == "pystray._xorg"
                else pystray.Menu(
                    pystray.MenuItem("View", on_tray_action, default=True),
                    pystray.MenuItem("Exit", on_tray_action),
                )
            )
        )
        icon.run_detached()
        root.withdraw()
        button_window.withdraw()
    except Exception as error:
        print(f"Warning: Cannot launch system tray: {error}")
        icon = None
        show_window()

# Main loop
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
        answer = messagebox.askyesnocancel("Unsaved Changes", "Save current code before loading project?")
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
            messagebox.showinfo("Auto Install", f"Automatically installed modules: {', '.join(installed)}")
    
    return True

def open_hotkey_builder():
    win = tk.Toplevel(root)
    win.title("Hotkey & Button Creator")
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
                "kind": str(item.get("kind", "Open URL")), "target": str(item.get("target", "")),
                "wait": wait_seconds, "followup": str(item.get("followup", ""))
            })
    content = tk.Frame(win, padx=14, pady=12)
    content.pack(fill="both", expand=True)
    tk.Label(
        content,
        text="Register hotkey and button actions (global hotkeys available on X11 sessions)",
        font=("Meiryo UI", 14, "bold"),
    ).pack(anchor="w")

    settings = tk.Frame(content)
    settings.pack(fill="x", pady=(10, 8))
    tk.Label(settings, text="Window name").pack(side="left")
    title_value = tk.StringVar(value=str(builder_config.get("title", "Simple Hotkey")))
    ttk.Entry(settings, textvariable=title_value, width=24).pack(side="left", padx=(6, 16))
    tk.Label(settings, text="Width").pack(side="left")
    width_value = tk.StringVar(value=str(builder_config.get("width", 240)))
    ttk.Entry(settings, textvariable=width_value, width=7).pack(side="left", padx=6)
    tk.Label(settings, text="Height").pack(side="left")
    height_value = tk.StringVar(value=str(builder_config.get("height", 420)))
    ttk.Entry(settings, textvariable=height_value, width=7).pack(side="left", padx=6)
    body = tk.Frame(content)
    body.pack(fill="both", expand=True)
    columns = ("shortcut", "button", "kind", "target")
    table = ttk.Treeview(body, columns=columns, show="headings", height=9, selectmode="browse")
    for column, label, width in (("shortcut", "Hotkey", 125), ("button", "Button name", 145), ("kind", "Action", 145), ("target", "Content", 400)):
        table.heading(column, text=label)
        table.column(column, width=width, minwidth=70, stretch=column == "target")
    table.pack(side="left", fill="both", expand=True)
    table_scroll = ttk.Scrollbar(body, orient="vertical", command=table.yview)
    table_scroll.pack(side="right", fill="y")
    table.configure(yscrollcommand=table_scroll.set)

    form = tk.LabelFrame(content, text="Add/Edit Action", padx=10, pady=8)
    form.pack(fill="x", pady=(10, 4))
    shortcut_value = tk.StringVar()
    button_value = tk.StringVar()
    kind_value = tk.StringVar(value="Open URL")
    target_value = tk.StringVar()
    wait_value = tk.StringVar(value="0")
    followup_value = tk.StringVar()

    tk.Label(form, text="Key (e.g. Alt+a)", font=("Meiryo UI", 11)).grid(row=0, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="Button name (optional)", font=("Meiryo UI", 11)).grid(row=0, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="Action", font=("Meiryo UI", 11)).grid(row=1, column=0, sticky="w", padx=4, pady=3)
    kind_menu = ttk.Combobox(form, textvariable=kind_value, values=("Open URL", "Launch app/file", "Send keys", "Run command", "Hide window"), state="readonly", width=18, font=("Meiryo UI", 11))
    kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="URL / Path / Key / Command", font=("Meiryo UI", 11)).grid(row=1, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="Seconds to wait after execution", font=("Meiryo UI", 11)).grid(row=2, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
    tk.Label(form, text="Key to send after wait (optional)", font=("Meiryo UI", 11)).grid(row=2, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=followup_value).grid(row=2, column=3, sticky="ew", padx=4, pady=3)
    form.columnconfigure(1, weight=1)
    form.columnconfigure(3, weight=2)
    tk.Label(content, text="Key send examples: Ctrl+w, Alt+F4, Left. Leave key field empty to execute with button only.", anchor="w").pack(fill="x", pady=(2, 4))

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
            messagebox.showerror("Settings SaveError", str(error), parent=win)

    def save_configuration_as():
        path = filedialog.asksaveasfilename(
            parent=win, title="Save Hotkey Settings", defaultextension=".json",
            filetypes=[("JSON Settings", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as config_file:
                json.dump(configuration_data(), config_file, ensure_ascii=False, indent=2)
            persist_configuration()
            messagebox.showinfo("Settings Save", "Settings saved.", parent=win)
        except OSError as error:
            messagebox.showerror("Settings SaveError", str(error), parent=win)

    def load_configuration():
        path = filedialog.askopenfilename(
            parent=win, title="Load Hotkey Settings", filetypes=[("JSON Settings", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as config_file:
                loaded = json.load(config_file)
            if not isinstance(loaded, dict) or not isinstance(loaded.get("actions"), list):
                raise ValueError("Settings file format is incorrect.")
            loaded_actions = loaded["actions"]
            normalized_actions = []
            for item in loaded_actions:
                if not isinstance(item, dict):
                    raise ValueError("Action list format is incorrect.")
                wait_seconds = float(item.get("wait", 0))
                if not 0 <= wait_seconds <= 3600:
                    raise ValueError("Please specify wait time in range 0-3600 seconds.")
                normalized_actions.append({
                    "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                    "kind": str(item.get("kind", "Open URL")), "target": str(item.get("target", "")),
                    "wait": wait_seconds, "followup": str(item.get("followup", ""))
                })
            actions[:] = normalized_actions
            title_value.set(str(loaded.get("title", "Simple Hotkey")))
            width_value.set(str(loaded.get("width", 240)))
            height_value.set(str(loaded.get("height", 420)))
            refresh_table()
            clear_form()
            persist_configuration()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showerror("SettingsLoadError", str(error), parent=win)

    def clear_form():
        table.selection_remove(table.selection())
        shortcut_value.set("")
        button_value.set("")
        kind_value.set("Open URL")
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
            messagebox.showerror("Input Error", "Please enter hotkey or button name.", parent=win)
            return
        if not target and kind != "Hide window":
            messagebox.showerror("Input Error", "Please enter action content.", parent=win)
            return
        try:
            wait = float(wait_value.get())
            if not 0 <= wait <= 3600:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input Error", "Please enter wait time as a number in range 0-3600 seconds.", parent=win)
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
            messagebox.showerror("Input Error", "Please register at least one hotkey or button.", parent=win)
            return
        try:
            window_width = int(width_value.get())
            window_height = int(height_value.get())
            if not 120 <= window_width <= 3000 or not 120 <= window_height <= 3000:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input Error", "Please enter width and height as integers in range 120-3000.", parent=win)
            return
        seen_shortcuts = set()
        for item in actions:
            key = item["shortcut"].lower().replace(" ", "")
            if key and key in seen_shortcuts:
                messagebox.showerror("Input Error", f"Hotkey is duplicated: {item['shortcut']}", parent=win)
                return
            seen_shortcuts.add(key)
        action_data = [{key: item[key] for key in ("shortcut", "button", "kind", "target", "wait", "followup")} for item in actions]
        persist_configuration()

        # Convert Japanese action names to English
        kind_map = {
            "Open URL": "Open URL",
            "Launch app/file": "Launch app/file",
            "Send keys": "Send keys",
            "Run command": "Run command",
            "Hide window": "Hide window"
        }
        for action in action_data:
            if action["kind"] in kind_map:
                action["kind"] = kind_map[action["kind"]]
        
        source = build_hotkey_app_source(
            action_data,
            title_value.get().strip() or "Simple Hotkey",
            window_width,
            window_height,
        )

        if load_project_code(source):
            win.destroy()

    row_buttons = tk.Frame(content)
    row_buttons.pack(fill="x", pady=(4, 8))
    ttk.Button(row_buttons, text="New Row", command=clear_form).pack(side="left")
    ttk.Button(row_buttons, text="Add / Update", command=save_action).pack(side="left", padx=6)
    ttk.Button(row_buttons, text="Delete Selected Row", command=delete_action).pack(side="left")
    ttk.Button(row_buttons, text="Load Settings", command=load_configuration).pack(side="left", padx=(12, 0))
    ttk.Button(row_buttons, text="Save Settings", command=save_configuration_as).pack(side="left", padx=6)
    ttk.Button(row_buttons, text="Generate Code", command=make_code).pack(side="right")
    ttk.Button(row_buttons, text="Close", command=close_builder).pack(side="right", padx=6)
    refresh_table()
    table.bind("<<TreeviewSelect>>", show_selected)
    win.protocol("WM_DELETE_WINDOW", close_builder)


def open_project_catalog():
    win = tk.Toplevel(root)
    win.title("Beginner Project List")
    win.geometry("930x600")
    win.minsize(760, 480)
    win.transient(root)

    main = tk.Frame(win, padx=12, pady=12)
    main.pack(fill="both", expand=True)
    tk.Label(main, text="Select what you want to create", font=("Meiryo UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
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
    name_label = tk.Label(details, text="Please select a project", anchor="w", font=("Meiryo UI", 13, "bold"))
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
    load_button = tk.Button(buttons, text="Load Code into Editor", state="disabled")
    load_button.pack(side="right", padx=(6, 0))
    designer_button = tk.Button(buttons, text="Open Form Creator", state="disabled")
    designer_button.pack(side="right")
    tk.Button(buttons, text="Close", command=win.destroy).pack(side="left")

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
        preview.insert("1.0", project["code"] or "This project uses the form creation tab.")
        preview.config(state="disabled")
        is_designer = project["kind"] == "designer"
        load_button.config(state="disabled" if is_designer else "normal")
        designer_button.config(state="normal" if is_designer else "disabled")

    def load_selected():
        project = selected_project["value"]
        if project and load_project_code(project["code"]):
            win.destroy()
            if project["kind"] == "guide":
                messagebox.showinfo("Setup Guide", "This project requires external service configuration. Check comments in the code.")

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
    fname = os.path.basename(quick_save.current_file_path) if hasattr(quick_save, 'current_file_path') and quick_save.current_file_path else "Untitled File"
    mod = " ●" if text_modified else ""
    status_label.config(text=f" 📂 {fname}{mod}   |   rows: {line}  Column: {col}  Character count: {char_count} ")
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
    search_window.title("Search and Replace")
    search_window.geometry("420x180")
    search_window.resizable(False, False)
    th = THEMES[current_theme]
    search_window.configure(bg=th['bg'])

    tk.Label(search_window, text="Search:", bg=th['bg'], fg=th['text_fg']).place(x=20, y=20)
    q_entry = tk.Entry(search_window, width=32, font=("Consolas", 10))
    q_entry.place(x=90, y=20)
    q_entry.focus_set()

    tk.Label(search_window, text="Replace:", bg=th['bg'], fg=th['text_fg']).place(x=20, y=60)
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
            messagebox.showinfo("Search", "Not found.")

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
            messagebox.showinfo("Replace Complete", "Replaced all.")
        else:
            messagebox.showinfo("Replace", "No matches found.")

    tk.Button(search_window, text="Find Next", command=do_find, width=12).place(x=90, y=110)
    tk.Button(search_window, text="Replace", command=do_replace, width=10).place(x=200, y=110)
    tk.Button(search_window, text="AllReplace", command=do_replace_all, width=12).place(x=290, y=110)
    return 'break'

def format_code():
    code = text.get("1.0", tk.END).strip()
    if not code:
        return
    try:
        venv_python = get_virtualenv_python()
    except Exception as e:
        messagebox.showerror("Error", f"Could not prepare virtual environment:\n{e}")
        return
    try:
        availability = subprocess.run([venv_python, "-m", "autopep8", "--version"],
                                      capture_output=True, text=True, timeout=15)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to confirm autopep8:\n{e}")
        return
    if availability.returncode != 0:
        if messagebox.askyesno("Confirm", "autopep8 is not installed.\nInstall it?"):
            try:
                subprocess.run([venv_python, "-m", "pip", "install", "autopep8"],
                               check=True, capture_output=True, text=True, timeout=60)
            except Exception as e:
                messagebox.showerror("Error", f"Install failed:\n{e}")
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
        messagebox.showinfo("Format Complete", "Code auto-formatted to PEP8 compliance.")
    except Exception as e:
        messagebox.showerror("Error", f"Formatting failed:\n{e}")
    finally:
        if 'tpath' in locals() and os.path.exists(tpath):
            try:
                os.unlink(tpath)
            except Exception:
                pass

def test_python_code():
    global text_modified
    if text_modified:
        if messagebox.askyesno("Confirm", "There are unsaved changes. Save before test run?"):
            if not quick_save():
                return
    code = text.get("1.0", tk.END).strip()
    if not code:
        return
    try:
        python_executable = get_virtualenv_python()
    except Exception as e:
        messagebox.showerror("Error", f"Could not prepare virtual environment:\n{e}")
        return
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(code)
        tpath = tf.name

    def run():
        try:
            res = subprocess.run([python_executable, tpath], capture_output=True, text=True, timeout=test_timeout_seconds)
            error_output = res.stderr.strip() or res.stdout.strip() or f"Exit code: {res.returncode}"
            out = res.stdout if res.returncode == 0 else f"[Error]\n{error_output}"
            if res.returncode == 0 and not out.strip():
                out = "Test execution completed successfully.\nNo standard output."
            if res.returncode == 0:
                root.after(0, lambda: messagebox.showinfo("Test Run Result", out[:1500] + ("\n...(truncated)" if len(out) > 1500 else "")))
            else:
                root.after(0, lambda: messagebox.showerror("Test Run Error", out))
        except subprocess.TimeoutExpired:
            root.after(0, lambda: messagebox.showerror("Timeout", f"Execution exceeded configured time limit ({test_timeout_seconds} seconds)."))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("ExecuteError", str(e)))
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
            messagebox.showwarning("Caution", "No code in editor.")
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
            messagebox.showinfo("Confirm", "No external modules requiring installation found!")
        return []
    try:
        python_executable = get_virtualenv_python()
        check_script = "import importlib.util, json, sys; names=json.loads(sys.argv[1]); print(json.dumps([name for name in names if importlib.util.find_spec(name) is None]))"
        result = subprocess.run([python_executable, "-c", check_script, json.dumps(candidate_modules)],
                                check=True, capture_output=True, text=True, timeout=30)
        target_modules = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as e:
        messagebox.showerror("Error", f"Failed to confirm virtual environment modules:\n{e}")
        return []
    if not target_modules:
        if not auto_install:
            messagebox.showinfo("Confirm", "No external modules requiring installation found!")
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
            messagebox.showerror("Module installation failed", "\n".join(fail_list))
        return success_list
    
    # Manual install mode with dialog
    win = tk.Toplevel(root)
    win.title("moduleAuto Install")
    win.geometry("450x320")
    win.resizable(False, False)
    win.configure(bg="#f8f9fa")
    tk.Label(win, text="📦 Uninstalled external modules found", font=("Meiryo UI", 11, "bold"),
             bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    tk.Label(win, text="Install the following modules with pip?", font=("Meiryo UI", 9), bg="#f8f9fa").pack(anchor="w", padx=15, pady=(10, 5))
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
            messagebox.showwarning("Caution", "Please select a module.")
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
        msg = f"Installation complete: {', '.join(success_list) if success_list else 'None'}"
        if fail_list:
            msg += f"\nFailed: {', '.join(fail_list)}"
        messagebox.showinfo("Installation Result", msg)
        win.destroy()
    tk.Button(win, text="🚀 Install Selected Modules", command=do_install,
              bg="#198754", fg="white", font=("Meiryo UI", 10, "bold"), padx=10, pady=8, cursor="hand2").pack(side="bottom", fill="x", padx=15, pady=15)


# ==================== Main UI ====================
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
        display_text = error_text[:1500] + "\n...(truncated. Full text copied to clipboard)"
    else:
        display_text = error_text + "\n\nError content copied to clipboard."
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
top_notebook.add(tab_editor, text="📝 Code Editor")

tab_samples = ttk.Frame(top_notebook)
top_notebook.add(tab_samples, text="🧩 Sample List")

tab_hotkey = ttk.Frame(top_notebook)
top_notebook.add(tab_hotkey, text="⌨ Hotkey Creator")

tab_designer = ttk.Frame(top_notebook)
top_notebook.add(tab_designer, text="🎨 Form Creator")

tab_docked = ttk.Frame(top_notebook)
top_notebook.add(tab_docked, text="🔗 Hotkey & Form Integration")
docked_toolbar = ttk.Frame(tab_docked)
docked_toolbar.pack(fill="x", padx=8, pady=(8, 0))
ttk.Button(
    docked_toolbar,
    text="⚡ Generate hotkey + form as single program",
    command=lambda: generate_code_from_designer(include_hotkeys=True),
).pack(side="left")
docked_notebook = ttk.Notebook(tab_docked)
docked_notebook.pack(fill="both", expand=True, padx=4, pady=(4, 4))
docked_hotkey_tab = ttk.Frame(docked_notebook)
docked_notebook.add(docked_hotkey_tab, text="⌨ Hotkey")
docked_form_tab = ttk.Frame(docked_notebook)
docked_notebook.add(docked_form_tab, text="🎨 Form")

tab_robot = ttk.Frame(top_notebook)
top_notebook.add(tab_robot, text="🚁 Drone & Robot Control")

tab_tools = ttk.Frame(top_notebook)
top_notebook.add(tab_tools, text="🛠 Tools & Environment Info")


# ---------- Tab 1: Code Editor ----------
top_btn_frame = tk.Frame(tab_editor, bg=THEMES[current_theme]['bg'])
top_btn_frame.pack(fill="x", pady=6, padx=6)

def add_btn(parent, text, cmd, bg="#333333", fg="white"):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat",
                  padx=10, pady=5, font=("Meiryo UI", 9, "bold"), cursor="hand2")
    b.pack(side="left", padx=3)
    return b

add_btn(top_btn_frame, "📄 New", new_file, "#495057")
add_btn(top_btn_frame, "📂 Open", open_file, "#495057")
add_btn(top_btn_frame, "💾 Save", quick_save, "#0d6efd")
add_btn(top_btn_frame, "✨ Auto Format", format_code, "#6c757d")
add_btn(top_btn_frame, "▶ Test Run", test_python_code, "#198754")
add_btn(top_btn_frame, "📦 Auto Install Modules", lambda: parse_and_install_code_modules(auto_install=True), "#6610f2")
add_btn(top_btn_frame, "🔍 Search", open_search_dialog, "#6c757d")
add_btn(top_btn_frame, "🌓 Toggle Theme", toggle_theme, "#ffc107", "#000")
# Code load button added later

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
status_label = tk.Label(status_bar, text=" 📂 Untitled File   |   rows: 1  Column: 0  Character count: 0 ",
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


# ---------- Tab 2: Sample List ----------
samples_content = tk.Frame(tab_samples, padx=12, pady=12, bg=THEMES[current_theme]['bg'])
samples_content.pack(fill="both", expand=True)
tk.Label(samples_content, text="Select what you want to create", font=("Meiryo UI", 15, "bold"),
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
samples_name_label = tk.Label(samples_details, text="Please select a project", anchor="w", font=("Meiryo UI", 13, "bold"),
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
samples_load_button = tk.Button(samples_buttons, text="Load Code into Editor", state="disabled")
samples_load_button.pack(side="right", padx=(6, 0))
samples_designer_button = tk.Button(samples_buttons, text="Open Form Creator", state="disabled")
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
    samples_preview.insert("1.0", project["code"] or "This project uses the form creation tab.")
    samples_preview.config(state="disabled")
    is_designer = project["kind"] == "designer"
    samples_load_button.config(state="disabled" if is_designer else "normal")
    samples_designer_button.config(state="normal" if is_designer else "disabled")

def samples_load_selected():
    project = samples_selected_project["value"]
    if project and load_project_code(project["code"]):
        if project["kind"] == "guide":
            messagebox.showinfo("Setup Guide", "This project requires external service configuration. Check comments in the code.")

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


# ---------- Tab 3: Hotkey Creator ----------
hotkey_content = tk.Frame(root, padx=14, pady=12, bg=THEMES[current_theme]['bg'])
hotkey_content.pack(in_=tab_hotkey, fill="both", expand=True)
tk.Label(hotkey_content, text="Register hotkey and button actions", font=("Meiryo UI", 14, "bold"),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w")
tk.Label(
    hotkey_content,
    text="Global hotkeys available on X11 sessions. On Wayland, use desktop shortcut settings.",
    bg=THEMES[current_theme]['bg'],
    fg=THEMES[current_theme]['text_fg'],
    anchor="w",
).pack(fill="x", pady=(2, 4))

hotkey_settings = tk.Frame(hotkey_content, bg=THEMES[current_theme]['bg'])
hotkey_settings.pack(fill="x", pady=(10, 8))
tk.Label(hotkey_settings, text="Window name", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left")
hotkey_title_value = tk.StringVar(value="Simple Hotkey")
ttk.Entry(hotkey_settings, textvariable=hotkey_title_value, width=24).pack(side="left", padx=(6, 16))
tk.Label(hotkey_settings, text="Width", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left")
hotkey_width_value = tk.StringVar(value="240")
ttk.Entry(hotkey_settings, textvariable=hotkey_width_value, width=7).pack(side="left", padx=6)
tk.Label(hotkey_settings, text="Height", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left")
hotkey_height_value = tk.StringVar(value="420")
ttk.Entry(hotkey_settings, textvariable=hotkey_height_value, width=7).pack(side="left", padx=6)
hotkey_body = tk.Frame(hotkey_content, bg=THEMES[current_theme]['bg'])
hotkey_body.pack(fill="both", expand=True)
hotkey_columns = ("shortcut", "button", "kind", "target")
hotkey_table = ttk.Treeview(hotkey_body, columns=hotkey_columns, show="headings", height=9, selectmode="browse")
for column, label, width in (("shortcut", "Hotkey", 125), ("button", "Button name", 145), ("kind", "Action", 145), ("target", "Content", 400)):
    hotkey_table.heading(column, text=label)
    hotkey_table.column(column, width=width, minwidth=70, stretch=column == "target")
hotkey_table.pack(side="left", fill="both", expand=True)
hotkey_table_scroll = ttk.Scrollbar(hotkey_body, orient="vertical", command=hotkey_table.yview)
hotkey_table_scroll.pack(side="right", fill="y")
hotkey_table.configure(yscrollcommand=hotkey_table_scroll.set)

hotkey_form = tk.LabelFrame(hotkey_content, text="Add/Edit Action", padx=10, pady=8,
                          bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'])
hotkey_form.pack(fill="x", pady=(10, 4))
hotkey_shortcut_value = tk.StringVar()
hotkey_button_value = tk.StringVar()
hotkey_kind_value = tk.StringVar(value="Open URL")
hotkey_target_value = tk.StringVar()
hotkey_wait_value = tk.StringVar(value="0")
hotkey_followup_value = tk.StringVar()

tk.Label(hotkey_form, text="Key (e.g. Alt+a)", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=0, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="Button name (optional)", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=0, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="Action", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=1, column=0, sticky="w", padx=4, pady=3)
hotkey_kind_menu = ttk.Combobox(hotkey_form, textvariable=hotkey_kind_value, values=("Open URL", "Launch app/file", "Send keys", "Run command", "Hide window"), state="readonly", width=18, font=("Meiryo UI", 11))
hotkey_kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="URL / Path / Key / Command", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=1, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="Seconds to wait after execution", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=2, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
tk.Label(hotkey_form, text="Key to send after wait (optional)", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 11)).grid(row=2, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_followup_value).grid(row=2, column=3, sticky="ew", padx=4, pady=3)
hotkey_form.columnconfigure(1, weight=1)
hotkey_form.columnconfigure(3, weight=2)
tk.Label(hotkey_content, text="Key send examples: Ctrl+w, Alt+F4, Left. Leave key field empty to execute with button only.",
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
                "kind": str(item.get("kind", "Open URL")), "target": str(item.get("target", "")),
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
        messagebox.showinfo("LoadComplete", f"{len(hotkey_actions)}hotkey settings loaded.")
    else:
        messagebox.showerror("Error", "ACTION settings not found in code.")

def hotkey_configuration_data():
    return {"title": hotkey_title_value.get(), "width": hotkey_width_value.get(),
            "height": hotkey_height_value.get(), "actions": hotkey_actions}

def hotkey_persist_configuration():
    path = get_settings_path(HOTKEY_BUILDER_SETTINGS_FILE)
    try:
        with open(path, "w", encoding="utf-8") as config_file:
            json.dump(hotkey_configuration_data(), config_file, ensure_ascii=False, indent=2)
    except OSError as error:
        messagebox.showerror("Settings SaveError", str(error))

def hotkey_save_configuration_as():
    path = filedialog.asksaveasfilename(
        title="Save Hotkey Settings", defaultextension=".json",
        filetypes=[("JSON Settings", "*.json"), ("All Files", "*.*")]
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as config_file:
            json.dump(hotkey_configuration_data(), config_file, ensure_ascii=False, indent=2)
        hotkey_persist_configuration()
        messagebox.showinfo("Settings Save", "Settings saved.")
    except OSError as error:
        messagebox.showerror("Settings SaveError", str(error))

def hotkey_load_configuration():
    path = filedialog.askopenfilename(
        title="Load Hotkey Settings", filetypes=[("JSON Settings", "*.json"), ("All Files", "*.*")]
    )
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
        if not isinstance(loaded, dict) or not isinstance(loaded.get("actions"), list):
            raise ValueError("Settings file format is incorrect.")
        loaded_actions = loaded["actions"]
        normalized_actions = []
        for item in loaded_actions:
            if not isinstance(item, dict):
                raise ValueError("Action list format is incorrect.")
            wait_seconds = float(item.get("wait", 0))
            if not 0 <= wait_seconds <= 3600:
                raise ValueError("Please specify wait time in range 0-3600 seconds.")
            normalized_actions.append({
                "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                "kind": str(item.get("kind", "Open URL")), "target": str(item.get("target", "")),
                "wait": wait_seconds, "followup": str(item.get("followup", ""))
            })
        hotkey_actions[:] = normalized_actions
        hotkey_title_value.set(str(loaded.get("title", "Simple Hotkey")))
        hotkey_width_value.set(str(loaded.get("width", 240)))
        hotkey_height_value.set(str(loaded.get("height", 420)))
        hotkey_refresh_table()
        hotkey_clear_form()
        hotkey_persist_configuration()
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        messagebox.showerror("SettingsLoadError", str(error))

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
    hotkey_kind_value.set("Open URL")
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
        messagebox.showerror("Input Error", "Please enter hotkey or button name.")
        return
    if not target and kind != "Hide window":
        messagebox.showerror("Input Error", "Please enter action content.")
        return
    try:
        wait = float(hotkey_wait_value.get())
        if not 0 <= wait <= 3600:
            raise ValueError
    except ValueError:
        messagebox.showerror("Input Error", "Please enter wait time as a number in range 0-3600 seconds.")
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
        messagebox.showerror("Input Error", "Please register at least one hotkey or button.")
        return
    try:
        window_width = int(hotkey_width_value.get())
        window_height = int(hotkey_height_value.get())
        if not 120 <= window_width <= 3000 or not 120 <= window_height <= 3000:
            raise ValueError
    except ValueError:
        messagebox.showerror("Input Error", "Please enter width and height as integers in range 120-3000.")
        return
    seen_shortcuts = set()
    for item in hotkey_actions:
        key = item["shortcut"].lower().replace(" ", "")
        if key and key in seen_shortcuts:
            messagebox.showerror("Input Error", f"Hotkey is duplicated: {item['shortcut']}")
            return
        seen_shortcuts.add(key)
    action_data = [{key: item[key] for key in ("shortcut", "button", "kind", "target", "wait", "followup")} for item in hotkey_actions]

    # Convert Japanese action names to English
    kind_map = {
        "Open URL": "Open URL",
        "Launch app/file": "Launch app/file",
        "Send keys": "Send keys",
        "Run command": "Run command",
        "Hide window": "Hide window"
    }
    for action in action_data:
        if action["kind"] in kind_map:
            action["kind"] = kind_map[action["kind"]]

    source = build_hotkey_app_source(
        action_data,
        hotkey_title_value.get().strip() or "Simple Hotkey",
        window_width,
        window_height,
    )
    if load_project_code(source):
        messagebox.showinfo("GenerateComplete", "Hotkey app code transferred to editor!")

hotkey_row_buttons = tk.Frame(hotkey_content)
hotkey_row_buttons.pack(fill="x", pady=(4, 8))
ttk.Button(hotkey_row_buttons, text="New Row", command=hotkey_clear_form).pack(side="left")
ttk.Button(hotkey_row_buttons, text="Add / Update", command=hotkey_save_action).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="Delete Selected Row", command=hotkey_delete_action).pack(side="left")
ttk.Button(hotkey_row_buttons, text="Load Settings", command=hotkey_load_configuration).pack(side="left", padx=(12, 0))
ttk.Button(hotkey_row_buttons, text="Save Settings", command=hotkey_save_configuration_as).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="Load from Code", command=hotkey_load_from_code_with_ui).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="Generate Code", command=hotkey_make_code).pack(side="right")
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
        messagebox.showerror("Settings SaveError", str(error))


# ---------- Tab 4: Visual Form Creator ----------
designer_components = []
selected_component = None

designer_toolbar = tk.Frame(root, bg="#2d2d2d", padx=8, pady=8)
designer_toolbar.pack(in_=tab_designer, side="top", fill="x")

form_window_width = 692
form_window_height = 477
form_bg_color = "#f0f0f0"
form_fg_color = "#000000"
form_pos_x = 100
form_pos_y = 100
form_pos_mode = "manual"
form_use_tray = False
form_width_var = None
form_height_var = None

# Form Designer Save Settings/Load
DESIGNER_SETTINGS_FILE = 'designer_settings.json'

def load_designer_settings():
    global form_use_tray, form_window_width, form_window_height, form_bg_color, form_fg_color, form_pos_x, form_pos_y, form_pos_mode
    # Disable settings file load (fix initial size)
    form_use_tray = False
    form_window_width = 692
    form_window_height = 477
    form_bg_color = '#f0f0f0'
    form_fg_color = '#000000'
    form_pos_x = 100
    form_pos_y = 100
    form_pos_mode = 'manual'

def save_designer_settings():
    # Disable settings file save (fix initial size)
    return

# Load settings
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
                    text=f"📱 FormSize: {form_window_width} x {form_window_height}  |  🖥 ScreenViewPosition: X={form_pos_x}, Y={form_pos_y}",
                    bg="#1e1e1e", fg="#cccccc", font=("Meiryo UI", 9))
size_lbl.place(x=50, y=20)

def update_form_preview_size(w, h):
    global form_window_width, form_window_height
    form_window_width = max(0, w)
    form_window_height = max(0, h)
    form_preview.place(width=form_window_width, height=form_window_height)
    if form_width_var is not None and form_height_var is not None:
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

# Code load button
def load_form_from_code():
    global designer_components, form_window_width, form_window_height, form_bg_color, form_fg_color
    
    # Show file selection dialog
    path = filedialog.askopenfilename(
        filetypes=[("Python Files", "*.py")]
    )
    if not path:
        return
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        messagebox.showerror("Error", f"FileLoad Failed: {e}")
        return
    
    parse_and_load_code(code, path)

def load_form_from_editor():
    global designer_components, form_window_width, form_window_height, form_bg_color, form_fg_color
    
    code = text.get("1.0", tk.END).strip()
    if not code:
        messagebox.showwarning("Warning", "No code in editor")
        return
    
    parse_and_load_code(code, quick_save.current_file_path if hasattr(quick_save, 'current_file_path') else None)

def parse_and_load_code(code, file_path=None):
    global designer_components, form_window_width, form_window_height, form_bg_color, form_fg_color
    
    # Also load into editor if file path exists
    if file_path:
        text.delete("1.0", tk.END)
        text.insert("1.0", code)
        quick_save.current_file_path = file_path
        last_saved_content = code + "\n"
        text_modified = False
        update_status_bar()
    
    # Clear current components
    for comp in designer_components:
        try:
            comp["wrapper"].destroy()
        except:
            pass
    designer_components.clear()
    
    # Extract size from geometry
    width_match = re.search(r'geometry\s*=\s*[\'"](\d+)x(\d+)', code)
    if width_match:
        form_window_width = int(width_match.group(1))
        form_window_height = int(width_match.group(2))
        update_form_preview_size(form_window_width, form_window_height)
    
    # Extract place() pattern (2-line format)
    button_pattern = r'btn_(\d+)\s*=\s*tk\.Button.*'
    button_place_pattern = r'btn_(\d+)\.place\s*\(\s*x=(\d+),\s*y=(\d+),\s*width=(\d+),\s*height=(\d+)\s*\)'
    label_pattern = r'lbl_(\d+)\s*=\s*tk\.Label.*'
    label_place_pattern = r'lbl_(\d+)\.place\s*\(\s*x=(\d+),\s*y=(\d+),\s*width=(\d+),\s*height=(\d+)\s*\)'
    entry_pattern = r'ent_(\d+)\s*=\s*tk\.Entry.*'
    entry_place_pattern = r'ent_(\d+)\.place\s*\(\s*x=(\d+),\s*y=(\d+),\s*width=(\d+),\s*height=(\d+)\s*\)'
    
    # Extract designer setting comments
    config_pattern = r'# DESIGNER_CONFIG_(\d+):\s*(\{.*?\})'
    component_configs = {}
    for match in re.finditer(config_pattern, code):
        idx, config_json = match.groups()
        try:
            component_configs[idx] = json.loads(config_json)
        except:
            pass
    
    # Parse button action functions (old code support)
    def extract_button_action(btn_idx):
        # Search for on_btn_N_click function
        action_pattern = rf'def on_btn_{btn_idx}_click\(\):\s*(.*?)(?=\ndef|\Z)'
        action_match = re.search(action_pattern, code, re.DOTALL)
        if action_match:
            action_body = action_match.group(1)
            # Search for open_browser
            browser_match = re.search(r"open_browser\(['\"]([^'\"]+)['\"'],\s*['\"]([^'\"]+)['\"]\)", action_body)
            if browser_match:
                url, browser = browser_match.groups()
                return {'action': 'open_url', 'param': url, 'browser_choice': browser}
        return None
    
    # Helper function to extract properties
    def extract_properties(line):
        props = {}
        # Extract text
        text_match = re.search(r'text=([\'"])(.*?)\1', line)
        if text_match:
            props['text'] = text_match.group(2)
        # Extract bg
        bg_match = re.search(r'bg=([\'"])(.*?)\1', line)
        if bg_match:
            props['bg'] = bg_match.group(2)
        # Extract fg
        fg_match = re.search(r'fg=([\'"])(.*?)\1', line)
        if fg_match:
            props['fg'] = fg_match.group(2)
        return props
    
    # Parse buttons
    button_def_lines = {}
    for match in re.finditer(button_pattern, code):
        idx = match.group(1)
        button_def_lines[idx] = match.group(0)
    
    for match in re.finditer(button_place_pattern, code):
        idx, x, y, w, h = match.groups()
        comp = add_component("Button", int(x), int(y), int(w), int(h), idx)
        if idx in button_def_lines:
            props = extract_properties(button_def_lines[idx])
            if 'text' in props:
                comp['text'] = props['text']
                comp['inner'].config(text=props['text'])
            if 'bg' in props:
                comp['bg_color'] = props['bg']
                comp['inner'].config(bg=props['bg'])
            if 'fg' in props:
                comp['fg_color'] = props['fg']
                comp['inner'].config(fg=props['fg'])
        # Restore designer settings
        if idx in component_configs:
            config = component_configs[idx]
            comp['action'] = config.get('action', 'none')
            comp['param'] = config.get('param', '')
            comp['font_size'] = config.get('font_size', 10)
            comp['close_after_action'] = config.get('close_after_action', False)
            comp['browser_choice'] = config.get('browser_choice', 'Default browser')
            comp['source_path'] = config.get('source_path', '')
            comp['destination_path'] = config.get('destination_path', '')
            comp['source_filetype'] = config.get('source_filetype', 'All Files')
        else:
            # Old code support: Parse action functions
            action_info = extract_button_action(idx)
            if action_info:
                comp['action'] = action_info.get('action', 'none')
                comp['param'] = action_info.get('param', '')
                comp['browser_choice'] = action_info.get('browser_choice', 'Default browser')
    
    # Parse labels
    label_def_lines = {}
    for match in re.finditer(label_pattern, code):
        idx = match.group(1)
        label_def_lines[idx] = match.group(0)
    
    for match in re.finditer(label_place_pattern, code):
        idx, x, y, w, h = match.groups()
        comp = add_component("Label", int(x), int(y), int(w), int(h), idx)
        if idx in label_def_lines:
            props = extract_properties(label_def_lines[idx])
            if 'text' in props:
                comp['text'] = props['text']
                comp['inner'].config(text=props['text'])
            if 'bg' in props:
                comp['bg_color'] = props['bg']
                comp['inner'].config(bg=props['bg'])
            if 'fg' in props:
                comp['fg_color'] = props['fg']
                comp['inner'].config(fg=props['fg'])
        # Restore designer settings
        if idx in component_configs:
            config = component_configs[idx]
            comp['action'] = config.get('action', 'none')
            comp['param'] = config.get('param', '')
            comp['font_size'] = config.get('font_size', 10)
    
    # Parse entries
    entry_def_lines = {}
    for match in re.finditer(entry_pattern, code):
        idx = match.group(1)
        entry_def_lines[idx] = match.group(0)
    
    for match in re.finditer(entry_place_pattern, code):
        idx, x, y, w, h = match.groups()
        comp = add_component("Entry", int(x), int(y), int(w), int(h), idx)
        if idx in entry_def_lines:
            props = extract_properties(entry_def_lines[idx])
            if 'bg' in props:
                comp['bg_color'] = props['bg']
                comp['inner'].config(bg=props['bg'])
            if 'fg' in props:
                comp['fg_color'] = props['fg']
                comp['inner'].config(fg=props['fg'])
        # Restore designer settings
        if idx in component_configs:
            config = component_configs[idx]
            comp['action'] = config.get('action', 'none')
            comp['param'] = config.get('param', '')
            comp['font_size'] = config.get('font_size', 10)
    
    if designer_components:
        messagebox.showinfo("LoadComplete", f"{len(designer_components)}components loaded")
    else:
        messagebox.showwarning("Warning", "Components not found")

# Add code load button (execute after function definition)
add_btn(top_btn_frame, "📥 Load Code", load_form_from_editor, "#0d6efd")



def update_size_label():
    pos_str = "Display in Screen Center" if form_pos_mode == "center" else f"X={form_pos_x}, Y={form_pos_y}"
    size_lbl.config(text=f"📱 FormSize: {form_window_width} x {form_window_height}  |  🖥 ScreenViewPosition: {pos_str}")

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
        title="Select Form Background Color" if color_type == "background" else "Select Form Text Color",
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
tk.Label(form_color_controls, text="Form Background", bg="#2d2d2d", fg="#eeeeee",
         font=("Meiryo UI", 9)).pack(side="left", padx=(0, 3))
form_bg_swatch = tk.Button(form_color_controls, text="Select", width=5, bg=form_bg_color,
                           command=lambda: choose_form_color("background"), cursor="hand2")
form_bg_swatch.pack(side="left", padx=(0, 8))
tk.Label(form_color_controls, text="Form Text", bg="#2d2d2d", fg="#eeeeee",
         font=("Meiryo UI", 9)).pack(side="left", padx=(0, 3))
form_fg_swatch = tk.Button(form_color_controls, text="Select", width=5, bg=form_fg_color,
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
    w_diag.title("Window Screen Position Settings")
    w_diag.geometry("450x390")
    w_diag.resizable(False, False)
    w_diag.configure(bg="#f8f9fa")
    w_diag.transient(root)
    w_diag.grab_set()

    tk.Label(w_diag, text="🖥 Position on desktop screen at app launch",
             font=("Meiryo UI", 11, "bold"), bg="#0d6efd", fg="white",
             padx=10, pady=10).pack(side="top", fill="x")

    f_body = tk.Frame(w_diag, bg="#f8f9fa", padx=20, pady=15)
    f_body.pack(fill="both", expand=True)

    mode_var = tk.StringVar(value=form_pos_mode)
    tk.Radiobutton(f_body, text="Automatically display in center of screen", variable=mode_var, value="center",
                   bg="#f8f9fa", font=("Meiryo UI", 10)).pack(anchor="w", pady=5)
    tk.Radiobutton(f_body, text="Display at specified coordinates (X, Y) on desktop", variable=mode_var, value="manual",
                   bg="#f8f9fa", font=("Meiryo UI", 10)).pack(anchor="w", pady=(10, 5))

    tray_start_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        f_body,
        text="Minimize to system tray at program execution",
        variable=tray_start_var,
        bg="#f8f9fa",
        font=("Meiryo UI", 10),
    ).pack(anchor="w", pady=(10, 5))

    coord_frame_diag = tk.Frame(f_body, bg="#f8f9fa", padx=20)
    coord_frame_diag.pack(anchor="w", pady=5)

    tk.Label(coord_frame_diag, text="X Coordinate:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
    x_entry = tk.Entry(coord_frame_diag, width=12, font=("Consolas", 10))
    x_entry.grid(row=0, column=1, padx=10, pady=5)
    x_entry.insert(0, str(form_pos_x))

    tk.Label(coord_frame_diag, text="Y Coordinate:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
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

    # Bind to both main body and input field (so Home works even when click is None)
    w_diag.bind("<Home>", capture_mouse_pos_here)
    x_entry.bind("<Home>", capture_mouse_pos_here)
    y_entry.bind("<Home>", capture_mouse_pos_here)

    tk.Label(f_body, text="💡 Press [Home] key to auto-enter current mouse coordinates",
             bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 9)).pack(anchor="w", pady=(10, 0))

    def save_pos():
        global form_pos_x, form_pos_y, form_pos_mode, form_use_tray
        form_pos_mode = mode_var.get()
        if form_pos_mode == "manual":
            try:
                form_pos_x = int(x_entry.get().strip())
                form_pos_y = int(y_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Please enter valid integers for coordinates.")
                return
        form_use_tray = tray_start_var.get()
        update_size_label()
        save_designer_settings()
        messagebox.showinfo("Save Complete", "Window screen position has been set!")
        w_diag.destroy()

    tk.Button(w_diag, text="💾 Save Settings", command=save_pos, bg="#198754", fg="white",
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

    # Force focus immediately after opening
    w_diag.after(50, lambda: w_diag.focus_force())


def add_component(ctype, x=None, y=None, width=None, height=None, button_index=None):
    global selected_component
    wrapper = tk.Frame(form_preview, bg="#cccccc", bd=1, relief="raised")
    
    # Use specified position and size if provided
    if x is not None and y is not None and width is not None and height is not None:
        wrapper.place(x=x, y=y, width=width, height=height)
    else:
        wrapper.place(x=40, y=40, width=150, height=36)

    default_bg = "#e8e8e8" if ctype == "Button" else form_bg_color
    default_fg = form_fg_color

    if button_index is None:
        button_number = max(
            (
                existing.get("button_index", -1)
                for existing in designer_components
                if existing["type"] == "Button"
            ),
            default=-1,
        ) + 1
    else:
        button_number = int(button_index)
    
    if ctype == "Button":
        inner = tk.Button(wrapper, text=f"{button_number}. Button", relief="flat", font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    elif ctype == "Label":
        inner = tk.Label(wrapper, text="TextLabel", bg=default_bg, fg=default_fg, font=("Meiryo UI", 10))
    else:
        inner = tk.Entry(wrapper, font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    inner.pack(fill="both", expand=True)

    comp_resize_handle = tk.Label(wrapper, text="◢", bg="#0d6efd", fg="white", font=("Meiryo UI", 8), cursor="sizing")
    comp_resize_handle.place(relx=1.0, rely=1.0, x=-12, y=-12, width=12, height=12)

    comp_info = {
        "type": ctype, "wrapper": wrapper, "inner": inner,
        "text": f"{button_number}. Button" if ctype == "Button" else ("TextLabel" if ctype == "Label" else ""),
        "bg_color": default_bg, "fg_color": default_fg, "font_size": 10,
        "custom_background": False, "custom_foreground": False,
        "action": "none", "param": "", "close_after_action": False,
        "button_index": button_number,
        "browser_choice": "Default browser"
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
    
    return comp_info

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
    
    return comp_info

def open_properties_dialog(comp):
    if not comp:
        messagebox.showwarning("Caution", "Please select a component.")
        return

    diag = tk.Toplevel(root)
    diag.title("Component Details Properties Settings")
    diag.geometry("640x620")
    diag.resizable(False, False)
    diag.configure(bg="#f8f9fa")
    diag.transient(root)

    tk.Label(diag, text="🎨 Component Appearance and Action Details Settings",
             font=("Meiryo UI", 11, "bold"), bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    bottom_frame = tk.Frame(diag, bg="#e9ecef", padx=15, pady=12)
    bottom_frame.pack(side="bottom", fill="x")

    diag_notebook = ttk.Notebook(diag)
    diag_notebook.pack(fill="both", expand=True, padx=10, pady=10)

    tab_design = ttk.Frame(diag_notebook)
    tab_action = ttk.Frame(diag_notebook)
    diag_notebook.add(tab_design, text="① Text / Design Settings")
    diag_notebook.add(tab_action, text="② Action Settings")

    f_des = tk.Frame(tab_design, bg="#f8f9fa", padx=20, pady=20)
    f_des.pack(fill="both", expand=True)

    tk.Label(f_des, text="View Text (Content):", bg="#f8f9fa", font=("Meiryo UI", 10, "bold")).pack(anchor="w")
    txt_entry = tk.Entry(f_des, width=48, font=("Meiryo UI", 10))
    txt_entry.pack(anchor="w", pady=(2, 15))
    txt_entry.insert(0, comp["text"])

    style_frame = tk.LabelFrame(f_des, text=" Design (Colors / Font Size) ", bg="#f8f9fa",
                                font=("Meiryo UI", 9, "bold"), padx=15, pady=12)
    style_frame.pack(fill="x", pady=5)

    tk.Label(style_frame, text="Background color:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
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
                          command=lambda: choose_component_color(bg_entry, bg_swatch, "Select component background color"),
                          cursor="hand2")
    bg_swatch.grid(row=0, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="Text color:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
    fg_entry = tk.Entry(style_frame, width=18, font=("Consolas", 10))
    fg_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)
    fg_entry.insert(0, comp["fg_color"])
    fg_swatch = tk.Button(style_frame, text="  ", width=3, bg=comp["fg_color"],
                          command=lambda: choose_component_color(fg_entry, fg_swatch, "Select component text color"),
                          cursor="hand2")
    fg_swatch.grid(row=1, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="Font size:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=2, column=0, sticky="w", pady=5)
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

        tk.Label(f_act, text="Select the action to execute (many beginner-friendly options):", bg="#f8f9fa",
                 font=("Meiryo UI", 11, "bold")).pack(anchor="w", pady=(0, 5))

        action_categories = [
            ("--- Basic ---", [
                ("Do nothing", "none"),
                ("🚪 Exit app", "close_app"),
            ]),
            ("📁 File/Folder Operations (Highly Recommended)", [
                ("📄 Copy file", "copy_file"),
                ("📂 Copy folder", "copy_folder"),
                ("✂ Move file", "move_file"),
                ("🗑 Delete file (with confirmation)", "delete_file"),
                ("📂 Open folder", "open_folder"),
                ("📄 Open file (associated app)", "open_file_default"),
                ("📁 Create new folder", "create_folder"),
                ("📝 Create text file", "create_text_file"),
            ]),
            ("🖥 Open frequently used folders", [
                ("🖥 Open Desktop", "open_desktop"),
                ("Open Documents", "open_documents"),
                ("⬇ Open Downloads", "open_downloads"),
                ("📂 Open File Manager", "open_explorer"),
            ]),
            ("🌐 Web & Search", [
                ("Open specified URL", "open_url"),
                ("Open X", "open_x"),
                ("Open ABEMA TV", "open_abema"),
                ("GoogleSearch", "google_search"),
                ("YouTubeSearch", "youtube_search"),
                ("Google Translate", "google_translate"),
                ("GoogleMap", "google_maps"),
            ]),
            ("💬 Message / Utilities", [
                ("Show message box", "show_msg"),
                ("Confirmation dialog", "ask_yesno"),
                ("Copy text to clipboard", "copy_clipboard"),
                ("Copy current time to clipboard", "copy_time"),
                ("Show current time", "show_time"),
            ]),
            ("🖥 System & Tools", [
                ("Open text editor", "open_notepad"),
                ("Open calculator", "open_calc"),
                ("Open command prompt / terminal", "open_terminal"),
                ("Play beep sound", "beep"),
            ]),
            ("🎲 Fun", [
                ("1-100 lottery", "random_num"),
                ("Roll dice", "dice_roll"),
                ("Fortune slip", "omikuji"),
                ("Generate password", "gen_password"),
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

        tk.Label(f_act, text="Action parameters (URL, message content, etc.):", bg="#f8f9fa",
                 font=("Meiryo UI", 11, "bold")).pack(anchor="w", pady=(14, 2))
        param_entry = tk.Entry(f_act, width=50, font=("Meiryo UI", 11))
        param_entry.pack(anchor="w")
        param_entry.insert(0, comp["param"])
        close_after_var = tk.BooleanVar(value=comp.get("close_after_action", True), name="prop_close_after_var")
        tk.Checkbutton(
            f_act,
            text="Close this app after the action is executed",
            variable=close_after_var,
            bg="#f8f9fa",
            font=("Meiryo UI", 11),
            anchor="w",
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(f_act, text="Browser used for open-URL actions:", bg="#f8f9fa",
                 font=("Meiryo UI", 11)).pack(anchor="w", pady=(8, 2))
        browser_var = tk.StringVar(value=comp.get("browser_choice", "Default browser"), name="prop_browser_var")
        browser_combo = ttk.Combobox(
            f_act,
            textvariable=browser_var,
            values=("Default browser", "Microsoft Edge", "Google Chrome", "Mozilla Firefox", "Brave"),
            state="readonly",
            width=24,
            font=("Meiryo UI", 11),
        )
        browser_combo.pack(anchor="w")
        tk.Label(f_act, text="* For copy actions, specify the source and destination below.",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).pack(anchor="w", pady=(4, 0))

        path_frame = tk.LabelFrame(f_act, text="Source / Destination Settings",
                                   bg="#f8f9fa", font=("Meiryo UI", 9, "bold"), padx=8, pady=6)
        path_frame.pack(fill="x", pady=(12, 0))
        tk.Label(path_frame, text="Required for copy actions. These locations are used when the button runs.",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).grid(
                     row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        tk.Label(path_frame, text="Source:", bg="#f8f9fa").grid(row=1, column=0, sticky="w", pady=3)
        source_entry = tk.Entry(path_frame, width=38, font=("Consolas", 9))
        source_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        source_entry.insert(0, comp.get("source_path", ""))

        tk.Label(path_frame, text="Destination folder:", bg="#f8f9fa").grid(row=2, column=0, sticky="w", pady=3)
        destination_entry = tk.Entry(path_frame, width=38, font=("Consolas", 9))
        destination_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        destination_entry.insert(0, comp.get("destination_path", ""))
        path_frame.grid_columnconfigure(1, weight=1)

        filetype_options = [
            ("All Files", "*.*"),
            ("Python Files (*.py)", "*.py *.pyw"),
            ("TextFile (*.txt)", "*.txt"),
            ("CSV Files (*.csv)", "*.csv"),
            ("JSON Files (*.json)", "*.json"),
            ("ImageFile", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg"),
            ("PDF Files (*.pdf)", "*.pdf"),
            ("Excel Files (*.xlsx *.xls)", "*.xlsx *.xls"),
            ("Word Files (*.docx *.doc)", "*.docx *.doc"),
            ("Compressed files (*.zip *.7z)", "*.zip *.tar *.gz *.tgz *.bz2 *.7z *.rar"),
            ("VideoFile", "*.mp4 *.mkv *.avi *.mov *.wmv *.webm *.flv"),
            ("AudioFile", "*.mp3 *.wav *.ogg *.flac *.aac *.m4a"),
            ("ExecuteFile (*.sh *.exe)", "*.sh *.AppImage *.run *.exe *.bat"),
        ]
        filetype_labels = [label for label, _ in filetype_options]
        filetype_map = dict(filetype_options)
        saved_filetype = comp.get("source_filetype", "")
        filetype_var = tk.StringVar(
            value=saved_filetype if saved_filetype in filetype_map else "All Files"
        )

        tk.Label(path_frame, text="File type filter:", bg="#f8f9fa").grid(row=3, column=0, sticky="w", pady=3)
        filetype_combo = ttk.Combobox(
            path_frame,
            textvariable=filetype_var,
            values=filetype_labels,
            state="readonly",
            width=30,
            font=("Meiryo UI", 9),
        )
        filetype_combo.grid(row=3, column=1, sticky="ew", padx=5, pady=3)
        tk.Label(path_frame, text="(Used to filter the file picker; disabled for folder selection)",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).grid(
                     row=4, column=0, columnspan=3, sticky="w", pady=(0, 2))

        def update_filetype_state(*_):
            filetype_combo.configure(
                state="disabled" if act_var.get() == "copy_folder" else "readonly"
            )

        act_var.trace_add("write", update_filetype_state)
        update_filetype_state()

        def browse_source_path():
            if act_var.get() == "copy_folder":
                path = filedialog.askdirectory(parent=diag, title="Select source folder")
            else:
                pattern = filetype_map.get(filetype_var.get(), "*.*")
                path = filedialog.askopenfilename(
                    parent=diag,
                    title="Select source file",
                    filetypes=[(filetype_var.get(), pattern), ("All Files", "*.*")],
                )
            if path:
                source_entry.delete(0, tk.END)
                source_entry.insert(0, path)

        def browse_destination_path():
            path = filedialog.askdirectory(parent=diag, title="Select destination folder")
            if path:
                destination_entry.delete(0, tk.END)
                destination_entry.insert(0, path)

        tk.Button(path_frame, text="Browse...", command=browse_source_path).grid(row=1, column=2, padx=4)
        tk.Button(path_frame, text="Browse...", command=browse_destination_path).grid(row=2, column=2, padx=4)

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
        filetype_var = None
        close_after_var = None
        browser_var = None
        tk.Label(tab_action, text="Actions cannot be assigned to labels or input fields.",
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
                    "Copy settings required",
                    "For copy actions, set the source and destination folders in Details Settings.",
                    parent=diag,
                )
                return
            if selected_action == "copy_file" and not os.path.isfile(source_path):
                messagebox.showerror("Settings error", "Source file not found.", parent=diag)
                return
            if selected_action == "copy_folder" and not os.path.isdir(source_path):
                messagebox.showerror("Settings error", "Source folder not found.", parent=diag)
                return
            if not os.path.isdir(destination_path):
                messagebox.showerror("Settings error", "Destination folder not found.", parent=diag)
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
            if filetype_var:
                comp["source_filetype"] = filetype_var.get()
        try:
            if comp["type"] == "Entry":
                comp["inner"].config(bg=comp["bg_color"], fg=comp["fg_color"], font=("Meiryo UI", comp["font_size"]))
            else:
                comp["inner"].config(text=comp["text"], bg=comp["bg_color"], fg=comp["fg_color"],
                                     font=("Meiryo UI", comp["font_size"]))
        except Exception:
            pass
        messagebox.showinfo("Save complete", "Component settings updated.")
        diag.destroy()

    tk.Button(bottom_frame, text="💾 Save settings and confirm", command=save_config,
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
        messagebox.showwarning("Caution", "Please select a component to delete.")

def clear_designer():
    global selected_component
    if not designer_components:
        return
    if not messagebox.askyesno("Clear Form", "Delete all placed components?"):
        return
    for comp in designer_components:
        comp["wrapper"].destroy()
    designer_components.clear()
    selected_component = None

def generate_code_from_designer(include_hotkeys=False):
    combined_hotkey_actions = []
    if include_hotkeys:
        if not hotkey_actions:
            messagebox.showerror("Input error", "Register at least one hotkey action for the combined program.")
            top_notebook.select(tab_docked)
            docked_notebook.select(docked_hotkey_tab)
            return
        seen_shortcuts = set()
        for item in hotkey_actions:
            shortcut = item["shortcut"].lower().replace(" ", "")
            if shortcut and shortcut in seen_shortcuts:
                messagebox.showerror("Input Error", f"Hotkey is duplicated: {item['shortcut']}")
                top_notebook.select(tab_docked)
                docked_notebook.select(docked_hotkey_tab)
                return
            seen_shortcuts.add(shortcut)
        kind_map = {
            "Open URL": "Open URL",
            "Launch app/file": "Launch app/file",
            "Send keys": "Send keys",
            "Run command": "Run command",
            "Hide window": "Hide window",
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
            "Copy settings required",
            "For copy-action buttons, set the source and destination folders in Details Settings.",
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
        "root.title('Created Form App')",
        f"root.configure(bg={form_bg_color!r})",
        f"root.option_add('*Foreground', {form_fg_color!r})",
        geometry_code,
        "icon = None",
        "",
        "def open_browser(url, browser_choice='Default browser'):",
        "    try:",
        "        root.iconify()",
        "        if browser_choice == 'Default browser':",
        "            opened = webbrowser.open(url, new=0)",
        "            if not opened:",
        "                raise RuntimeError('Could not launch the default browser.')",
        "        else:",
        "            browser_commands = {",
        "                'Microsoft Edge': ('microsoft-edge', 'microsoft-edge-stable', 'msedge'),",
        "                'Google Chrome': ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'),",
        "                'Mozilla Firefox': ('firefox',),",
        "                'Brave': ('brave-browser',),",
        "            }",
        "            executable = next((shutil.which(name) for name in browser_commands[browser_choice] if shutil.which(name)), None)",
        "            if not executable:",
        "                raise FileNotFoundError(f'{browser_choice}not found.')",
        "            subprocess.Popen([executable, url], start_new_session=True)",
        "        return True",
        "    except Exception as error:",
        "        root.deiconify()",
        "        root.lift()",
        "        root.focus_force()",
        "        messagebox.showerror('Browser Launch Error', str(error), parent=root)",
        "        return False",
        "",

    ]

    if not needs_browser:
        browser_start = code.index("def open_browser(url, browser_choice='Default browser'):")
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
        browser_choice = comp.get("browser_choice", "Default browser")
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
                    code.append("        messagebox.showinfo('Complete', f'File copied\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
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
                    code.append("            raise ValueError('The destination cannot be the source folder itself or inside it.')")
                    code.append("        if os.path.exists(dest):")
                    code.append("            if not messagebox.askyesno('Confirm', 'A folder with the same name exists. Overwrite and merge its contents?', parent=root): return")
                    code.append("        shutil.copytree(src, dest, dirs_exist_ok=True)")
                    code.append("        messagebox.showinfo('Complete', f'Folder copied\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                    code.append("        return")
                elif act == "move_file":
                    code.append("    src = filedialog.askopenfilename(parent=root, title='Select file to move', initialdir=os.getcwd())")
                    code.append("    if not src: return")
                    code.append("    dest = filedialog.askdirectory(parent=root, title='Select destination folder', initialdir=os.path.dirname(src))")
                    code.append("    if not dest: return")
                    code.append("    try:")
                    code.append("        shutil.move(src, dest)")
                    code.append("        messagebox.showinfo('Complete', f'File moved\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                elif act == "delete_file":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='Select file to delete', initialdir=os.getcwd())")
                    code.append("    if not path: return")
                    code.append("    if messagebox.askyesno('Confirm', f'Really delete?\\n{os.path.basename(path)}', parent=root):")
                    code.append("        try:")
                    code.append("            os.remove(path)")
                    code.append("            messagebox.showinfo('Complete', 'File deleted')")
                    code.append("        except Exception as e:")
                    code.append("            messagebox.showerror('Error', str(e))")
                elif act == "open_folder":
                    code.append("    path = filedialog.askdirectory(parent=root, title='Select folder to open', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        subprocess.Popen(['xdg-open', path], start_new_session=True)")
                elif act == "open_file_default":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='Select file to open', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        subprocess.Popen(['xdg-open', path], start_new_session=True)")
                elif act == "create_folder":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='Select location to create', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    new_name = 'New folder'")
                    code.append("    path = os.path.join(parent, new_name)")
                    code.append("    try:")
                    code.append("        os.makedirs(path, exist_ok=True)")
                    code.append("        messagebox.showinfo('Complete', f'Folder created\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                elif act == "create_text_file":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='Select location to create', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    path = os.path.join(parent, 'New text.txt')")
                    code.append("    try:")
                    code.append("        with open(path, 'w', encoding='utf-8') as f:")
                    code.append("            f.write('')")
                    code.append("        messagebox.showinfo('Complete', f'Text file created\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
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
                    code.append(f"    messagebox.showinfo('Notification', {(param or 'Hello!')!r})")
                elif act == "ask_yesno":
                    code.append(f"    res = messagebox.askyesno('Confirm', {(param or 'Proceed?')!r})")
                    code.append("    messagebox.showinfo('Result', f'Selected: {res}')")
                elif act == "copy_clipboard":
                    code.append("    root.clipboard_clear()")
                    code.append(f"    root.clipboard_append({param!r})")
                    code.append("    messagebox.showinfo('Copy', 'Copied to clipboard')")
                elif act == "copy_time":
                    code.append("    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')")
                    code.append("    root.clipboard_clear()")
                    code.append("    root.clipboard_append(now)")
                    code.append("    messagebox.showinfo('Copy', f'Current time copied\\n{now}')")
                elif act == "show_time":
                    code.append("    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')")
                    code.append("    messagebox.showinfo('Current Time', f'Current time: {now}')")
                elif act == "open_notepad":
                    code.append("    editor = next((shutil.which(name) for name in ('xed', 'gnome-text-editor', 'gedit', 'mousepad', 'pluma') if shutil.which(name)), None)")
                    code.append("    if editor: subprocess.Popen([editor], start_new_session=True)")
                    code.append("    else: messagebox.showerror('Launch Error', 'Text editor not found.')")
                elif act == "open_calc":
                    code.append("    calculator = next((shutil.which(name) for name in ('gnome-calculator', 'mate-calc', 'galculator', 'kcalc') if shutil.which(name)), None)")
                    code.append("    if calculator: subprocess.Popen([calculator], start_new_session=True)")
                    code.append("    else: messagebox.showerror('LaunchError', 'CalculatorAppsnot found.')")
                elif act == "open_terminal":
                    terminal = next((shutil.which(name) for name in ('x-terminal-emulator', 'gnome-terminal', 'mate-terminal', 'xfce4-terminal', 'xterm') if shutil.which(name)), None)
                    if terminal:
                        code.append(f"    subprocess.Popen([{terminal!r}], start_new_session=True)")
                    else:
                        code.append("    messagebox.showerror('Launch Error', 'Terminal app not found.')")
                elif act == "beep":
                    code.append("    root.bell()")
                elif act == "random_num":
                    code.append("    n = random.randint(1, 100)")
                    code.append("    messagebox.showinfo('Lottery', f'Number drawn: {n}')")
                elif act == "dice_roll":
                    code.append("    d = random.randint(1, 6)")
                    code.append("    messagebox.showinfo('Dice', f'Roll result: 🎲 {d}')")
                elif act == "omikuji":
                    code.append("    omi = random.choice(['Great fortune ✨', 'Good fortune 🌟', 'Small fortune 👍', 'Fortune 😊', 'Bad fortune 💦'])")
                    code.append("    messagebox.showinfo('Fortune slip', f'Today\'s fortune: {omi}')")
                elif act == "gen_password":
                    code.append("    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$*'")
                    code.append("    pwd = ''.join(random.choices(chars, k=12))")
                    code.append("    messagebox.showinfo('Password Generator', f'Generated password:\\n{pwd}')")
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
            # Embed designer settings as a comment
            config = {
                "action": comp.get("action", "none"),
                "param": comp.get("param", ""),
                "font_size": comp.get("font_size", 10),
                "close_after_action": comp.get("close_after_action", False),
                "browser_choice": comp.get("browser_choice", "Default browser"),
                "source_path": comp.get("source_path", ""),
                "destination_path": comp.get("destination_path", ""),
                "source_filetype": comp.get("source_filetype", "All Files")
            }
            code.append(f"# DESIGNER_CONFIG_{i}: {json.dumps(config, ensure_ascii=False)}")
            code.append(f"btn_{i} = tk.Button({component_parent}, text={label_text!r}, bg={bg!r}, fg={fg!r}, font={font_str}{cmd_str})")
            code.append(f"btn_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Label":
            component_parent = "root"
            config = {
                "action": comp.get("action", "none"),
                "param": comp.get("param", ""),
                "font_size": comp.get("font_size", 10)
            }
            code.append(f"# DESIGNER_CONFIG_{i}: {json.dumps(config, ensure_ascii=False)}")
            code.append(f"lbl_{i} = tk.Label({component_parent}, text={label_text!r}, bg={bg!r}, fg={fg!r}, font={font_str})")
            code.append(f"lbl_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Entry":
            component_parent = "root"
            config = {
                "action": comp.get("action", "none"),
                "param": comp.get("param", ""),
                "font_size": comp.get("font_size", 10)
            }
            code.append(f"# DESIGNER_CONFIG_{i}: {json.dumps(config, ensure_ascii=False)}")
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
            "# Create system tray icon",
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
            "        if item_text == 'Menu':",
            "            show_tray_menu()",
            "        elif item_text in ('Exit', 'Exit'):",
            "            exit_from_tray(icon)",
            "        else:",
            "            restore_window()",
            "",
            "def show_tray_menu():",
            "    tray_menu = tk.Menu(root, tearoff=0)",
            "    tray_menu.add_command(label='View', command=restore_window)",
            "    tray_menu.add_separator()",
            "    tray_menu.add_command(label='Exit', command=lambda: exit_from_tray(icon))",
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
            "                pystray.Menu(pystray.MenuItem('Menu', on_tray_clicked, default=True))",
            "                if pystray.Icon.__module__ == 'pystray._xorg'",
            "                else pystray.Menu(",
            "                    pystray.MenuItem('View', on_tray_clicked, default=True),",
            "                    pystray.MenuItem('Exit', on_tray_clicked)",
            "                )",
            "            )",
            "        )",
            "        tray_thread = threading.Thread(target=icon.run, daemon=True)",
            "        tray_thread.start()",
            "        root.withdraw()",
            "    except Exception as error:",
            "        messagebox.showwarning('Cannot use System Tray', str(error), parent=root)",
            "        icon = None",
            "        root.deiconify()",
            "else:",
            "    messagebox.showwarning('Cannot use System Tray', 'The system tray feature requires pystray and Pillow. Install them with: pip install pystray Pillow')",
            ""
        ])

    if include_hotkeys:
        code.extend([""])
        code.extend(build_hotkey_runtime_source(combined_hotkey_actions))
        code.extend(build_hotkey_instance_lock_source())
        code.extend([
            "",
            "if not acquire_hotkey_locks():",
            "    messagebox.showwarning('Hotkey Already Running', 'An app registered with the same hotkey is already running. Exiting to prevent duplicate execution.', parent=root)",
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
        if not messagebox.askyesno("Confirm Overwrite", "Replace the editor content with the generated code?"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", generated_code)
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    if include_hotkeys:
        messagebox.showinfo("Generation Complete", "Generated a program combining hotkeys and the form.")
    else:
        messagebox.showinfo("Generation Complete", "Replaced the editor content with the form code!\nFile actions show a selection dialog when executed.")

# Toolbar buttons
designer_toolbar_buttons = []
designer_toolbar_columns = 0
designer_buttons_frame = tk.Frame(designer_toolbar, bg="#2d2d2d")

def add_designer_toolbar_button(label, command, bg, fg="white", active_bg=None):
    options = {
        "text": label, "command": command, "bg": bg, "fg": fg,
        "relief": "flat", "font": ("Meiryo UI", 10, "bold"),
        "padx": 2, "pady": 6, "cursor": "hand2",
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

add_designer_toolbar_button("+ Button", lambda: add_component("Button"), "#1769aa", active_bg="#12558a")
add_designer_toolbar_button("+ Label", lambda: add_component("Label"), "#0f766e", active_bg="#0b5c56")
add_designer_toolbar_button("+ Entry", lambda: add_component("Entry"), "#3a7d44", active_bg="#2d6335")
add_designer_toolbar_button("⚙ WindowPosition", open_window_position_dialog, "#6610f2")
add_designer_toolbar_button("⚙ ButtonDetailsSettings", lambda: open_properties_dialog(selected_component) if selected_component else messagebox.showwarning("Caution", "Please select a component"), "#ffc107", fg="#000")
add_designer_toolbar_button("📥 Load Code", load_form_from_code, "#0d6efd")
add_designer_toolbar_button("🗑 Delete", delete_component, "#dc3545")
add_designer_toolbar_button("🧹 Clear All", clear_designer, "#6c757d")
add_designer_toolbar_button("📝 Generate Code", generate_code_from_designer, "#198754")
designer_buttons_frame.pack_forget()
designer_options_frame.pack_forget()
designer_options_frame.pack(side="right", anchor="n", padx=(8, 0), pady=2)
designer_buttons_frame.pack(side="left", fill="x", expand=True)
top_notebook.bind(
    "<<NotebookTabChanged>>",
    lambda event: designer_buttons_frame.after_idle(arrange_designer_toolbar),
    add="+",
)


# ---------- Tab 5: Drone & Robot Control ----------
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
        messagebox.showwarning("Limit", "Blocks are limited to 90 maximum")
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
    
    # Get actual canvas width
    robot_canvas.update_idletasks()
    canvas_width = robot_canvas.winfo_width()
    canvas_height = robot_canvas.winfo_height()
    
    # Default values (for first display)
    if canvas_width < 100:
        canvas_width = 900
    if canvas_height < 100:
        canvas_height = 400

    block_width = 110     # Block width
    block_height = 35      # Block height
    block_gap = 3          # Gap between blocks
    padding = 10           # Padding

    # Calculate how many blocks can fit in a row
    items_per_row = max(1, int((canvas_width - padding * 2) / (block_width + block_gap)))
    max_rows = 15          # Maximum rows

    # Calculate blocks per row
    rows_info = []
    for i in range(len(robot_blocks)):
        row = i // items_per_row
        if row >= max_rows:
            row = max_rows - 1
        if row >= len(rows_info):
            rows_info.append(0)
        rows_info[row] += 1

    for i, block in enumerate(robot_blocks):
        # Calculate row and column (horizontal layout)
        row = i // items_per_row
        column = i % items_per_row

        # Ensure not exceeding max rows
        if row >= max_rows:
            row = max_rows - 1
            column = i  # Overflow blocks go to same row horizontally

        # Get blocks in this row
        blocks_in_row = rows_info[row] if row < len(rows_info) else 1

        # Total width of blocks in this row
        total_row_width = blocks_in_row * block_width + (blocks_in_row - 1) * block_gap

        # Start position for centered alignment
        x_start = (canvas_width - total_row_width) / 2

        x_pos = x_start + (column * (block_width + block_gap))
        y_pos = padding + (row * (block_height + block_gap))

        block_frame = robot_create_block_ui()
        block_frame.place(x=x_pos, y=y_pos, width=block_width, height=block_height)
        
        block_text = robot_get_block_text(block)
        tk.Label(block_frame, text=f"{i+1}. {block_text}",
                bg=THEMES[current_theme]['button_bg'], fg=THEMES[current_theme]['text_fg'],
                font=("Meiryo UI", 9), wraplength=150).pack(fill="both", expand=True, padx=2, pady=1)
    
    # Update canvas size
    max_height = padding + (max_rows * (block_height + block_gap))
    robot_canvas.configure(height=max_height)

def robot_get_block_text(block):
    block_type = block["type"]
    params = block["params"]
    
    if block_type == "takeoff":
        return f"Takeoff ({params.get('height', 5)} meters)"
    elif block_type == "land":
        return "Land"
    elif block_type == "forward":
        return f"Forward ({params.get('distance', 5)} meters)"
    elif block_type == "backward":
        return f"Backward ({params.get('distance', 5)} meters)"
    elif block_type == "left":
        return f"Left ({params.get('distance', 5)} meters)"
    elif block_type == "right":
        return f"Right ({params.get('distance', 5)} meters)"
    elif block_type == "up":
        return f"Ascend ({params.get('height', 5)} meters)"
    elif block_type == "down":
        return f"Descend ({params.get('height', 5)} meters)"
    elif block_type == "rotate_left":
        return f"Rotate Left ({params.get('angle', 90)} degrees)"
    elif block_type == "rotate_right":
        return f"Rotate Right ({params.get('angle', 90)} degrees)"
    elif block_type == "rotate_180":
        return "Reverse (180 degrees)"
    elif block_type == "wait":
        return f"Wait ({params.get('seconds', 1)} seconds)"
    elif block_type == "return_home":
        return "⚠️ Return on Signal Loss"
    elif block_type == "face_direction":
        direction = params.get('direction', 'North')
        return f"Face {direction}"
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
            # DJI Tello control code
            code_lines.extend([
                "# DJI Tello Drone Control Program",
                "# Required installation: pip install djitellopy",
                "",
                "from djitellopy import Tello",
                "import time",
                "",
                "# Connect to drone",
                "drone = Tello()",
                "drone.connect()",
                "",
                "# Battery check",
                "print(f'Battery: {drone.get_battery()}%')",
                "",
                "# Takeoff",
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
                    dist = params.get('distance', 5) * 100  # convert to cm
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
                    code_lines.append("# The Tello automatically lands if the signal is lost")
                    code_lines.append("drone.land()")
            
            code_lines.extend([
                "",
                "# Close connection",
                "drone.end()",
                "",
                "# Preparation before use:",
                "# 1. Turn on Tello drone power",
                "# 2. Connect PC/phone WiFi to Tello network",
                "# 3. Run this program"
            ])
        else:
            # Simulation
            code_lines.extend([
                "import tkinter as tk",
                "from tkinter import messagebox",
                "",
                "# Drone Control Program (Simulation)",
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
                "            messagebox.showwarning('Warning', 'Already taken off')",
                "            return",
                "        self.start_x = self.x",
                "        self.start_y = self.y",
                "        self.start_z = self.z",
                "        self.z += height",
                "        self.launched = True",
                "        print(f'{height} meters ascended and took off')",
                "",
                "    def land(self):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.z = 0",
                "        self.launched = False",
                "        print('Landed')",
                "",
                "    def forward(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.x += distance",
                "        print(f'Moved {distance} meters forward')",
                "",
                "    def backward(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.x -= distance",
                "        print(f'Moved {distance} meters backward')",
                "",
                "    def left(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.y -= distance",
                "        print(f'Moved {distance} meters left')",
                "",
                "    def right(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.y += distance",
                "        print(f'Moved {distance} meters right')",
                "",
                "    def up(self, height):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.z += height",
                "        print(f'Ascended {height} meters')",
                "",
                "    def down(self, height):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        self.z -= height",
                "        if self.z < 0:",
                "            self.z = 0",
                "            self.launched = False",
                "            print('Landed')",
                "        else:",
                "            print(f'Descended {height} meters')",
                "",
                "    def rotate_left(self, angle):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        print(f'Rotated {angle} degrees left')",
                "",
                "    def rotate_right(self, angle):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not taken off')",
                "            return",
                "        print(f'Rotated {angle} degrees right')",
                "",
                "    def wait(self, seconds):",
                "        import time",
                "        time.sleep(seconds)",
                "",
                "    def return_home(self):",
                "        if not self.launched:",
                "            print('No need to return as not taken off')",
                "            return",
                "        print('⚠️ Signal lost! Starting auto return')",
                "        self.z = 0",
                "        self.x = self.start_x",
                "        self.y = self.start_y",
                "        self.launched = False",
                "        print('✅ Returned to original position')",
                "",
                "    def show_status(self):",
                "        print(f'Current position: X={self.x}, Y={self.y}, Z={self.z}')",
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
                "# Caution: This is a simulation.",
                "# To control actual drone, select hardware option."
            ])
    
    else:  # robot mode
        if hardware == "rpi":
            # Raspberry Pi control code
            code_lines.extend([
                "# Raspberry Pi Robot Control Program",
                "# Required library: pip install gpiozero",
                "",
                "from gpiozero import Robot",
                "from time import sleep",
                "",
                "# Motor pin settings (adjust to match your wiring)",
                "# Left motor: GPIO pins 17, 18",
                "# Right motor: GPIO pins 22, 23",
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
                    code_lines.append("# Return: Reverse and move forward")
                    code_lines.append("robot.left()")
                    code_lines.append("sleep(1.0)")
                    code_lines.append("robot.stop()")
            
            code_lines.extend([
                "",
                "# Preparation before use:",
                "# 1. Install gpiozero on Raspberry Pi: pip install gpiozero",
                "# 2. Connect motor driver (L298N, etc.)",
                "# 3. Wire GPIO pins correctly",
                "# 4. Change pin numbers to match actual wiring"
            ])
        else:
            # Simulation
            code_lines.extend([
                "import tkinter as tk",
                "from tkinter import messagebox",
                "",
                "# Self-driving Robot Control Program (Simulation)",
                "",
                "class RobotController:",
                "    def __init__(self):",
                "        self.x = 0",
                "        self.y = 0",
                "        self.direction = 0  # 0=North, 1=East, 2=South, 3=West",
                "        self.start_x = 0",
                "        self.start_y = 0",
                "        self.start_direction = 0",
                "        self.directions = ['North', 'East', 'South', 'West']",
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
                "        print(f'Moved {distance} meters forward (direction: {self.directions[self.direction]})')",
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
                "        print(f'Moved {distance} meters backward (direction: {self.directions[self.direction]})')",
                "",
                "    def rotate_left(self):",
                "        self.direction = (self.direction + 3) % 4",
                "        print(f'Rotated left 90 degrees (current direction: {self.directions[self.direction]})')",
                "",
                "    def rotate_right(self):",
                "        self.direction = (self.direction + 1) % 4",
                "        print(f'Rotated right 90 degrees (current direction: {self.directions[self.direction]})')",
                "",
                "    def rotate_180(self):",
                "        self.direction = (self.direction + 2) % 4",
                "        print(f'Reversed 180 degrees (current direction: {self.directions[self.direction]})')",
                "",
                "    def face_direction(self, direction):",
                "        direction_map = {'North': 0, 'East': 1, 'South': 2, 'West': 3}",
                "        if direction in direction_map:",
                "            self.direction = direction_map[direction]",
                "            print(f'Now facing {direction}')",
                "",
                "    def wait(self, seconds):",
                "        import time",
                "        time.sleep(seconds)",
                "",
                "    def return_home(self):",
                "        print('⚠️ Signal lost! Starting auto return')",
                "        self.x = self.start_x",
                "        self.y = self.start_y",
                "        self.direction = self.start_direction",
                "        print('✅ Returned to original position')",
                "",
                "    def show_status(self):",
                "        print(f'Current position: X={self.x}, Y={self.y}, direction={self.directions[self.direction]}')",
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
                    code_lines.append(f"robot.face_direction('{params.get('direction', 'North')}')")
                elif block_type == "wait":
                    code_lines.append(f"robot.wait({params.get('seconds', 1)})")
                elif block_type == "return_home":
                    code_lines.append("robot.return_home()")
            
            code_lines.extend([
                "",
                "robot.show_status()",
                "",
                "# Caution: This is a simulation.",
                "# To control actual robot, select hardware option."
            ])
    
    generated_code = add_python_shebang("\n".join(code_lines))
    robot_code_output.set(generated_code)
    
    # Transfer to editor
    if text.get("1.0", tk.END).strip():
        if not messagebox.askyesno("Overwrite Confirm", "Replace editor content with generated code?"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", generated_code + "\n")
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    
    # Hardware-specific message
    if hardware == "tello":
        messagebox.showinfo("Generation Complete", "DJI Tello code generated!\n\nPreparation before use:\n1. pip install djitellopy\n2. Turn on Tello power\n3. Connect to Tello via WiFi\n4. Run program")
    elif hardware == "rpi":
        messagebox.showinfo("Generation Complete", "Raspberry Pi code generated!\n\nPreparation before use:\n1. pip install gpiozero\n2. Connect motor driver\n3. Wire GPIO pins\n4. Verify and change pin numbers")
    else:
        messagebox.showinfo("Generation Complete", "Simulation code transferred to editor!")

def center_dialog(dialog):
    dialog.update_idletasks()
    width = dialog.winfo_width()
    height = dialog.winfo_height()
    x = (dialog.winfo_screenwidth() // 2) - (width // 2)
    y = (dialog.winfo_screenheight() // 2) - (height // 2)
    dialog.geometry(f'+{x}+{y}')

def robot_add_takeoff():
    dialog = tk.Toplevel(root)
    dialog.title("Takeoff Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Ascend meters:", font=("Meiryo UI", 12)).pack(pady=15)
    height_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=height_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            height = float(height_var.get())
            robot_add_block("takeoff", {"height": height})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_land():
    robot_add_block("land")

def robot_add_forward():
    dialog = tk.Toplevel(root)
    dialog.title("Forward Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Move meters:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("forward", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_backward():
    dialog = tk.Toplevel(root)
    dialog.title("Backward Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Move meters:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("backward", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_left():
    dialog = tk.Toplevel(root)
    dialog.title("Left Move Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Move meters:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("left", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_right():
    dialog = tk.Toplevel(root)
    dialog.title("Right Move Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Move meters:", font=("Meiryo UI", 12)).pack(pady=15)
    dist_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=dist_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            dist = float(dist_var.get())
            robot_add_block("right", {"distance": dist})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_up():
    dialog = tk.Toplevel(root)
    dialog.title("Ascend Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Ascend meters:", font=("Meiryo UI", 12)).pack(pady=15)
    height_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=height_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            height = float(height_var.get())
            robot_add_block("up", {"height": height})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_down():
    dialog = tk.Toplevel(root)
    dialog.title("Descend Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Descend meters:", font=("Meiryo UI", 12)).pack(pady=15)
    height_var = tk.StringVar(value="5")
    tk.Entry(dialog, textvariable=height_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            height = float(height_var.get())
            robot_add_block("down", {"height": height})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_rotate_left():
    dialog = tk.Toplevel(root)
    dialog.title("Rotate Left Angle Settings")
    dialog.geometry("300x180")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="Rotation angle (degrees):", font=("Meiryo UI", 12)).pack(pady=15)
    angle_var = tk.StringVar(value="90")
    tk.Entry(dialog, textvariable=angle_var, font=("Meiryo UI", 12), justify="center").pack(pady=5)

    def confirm():
        try:
            angle = float(angle_var.get())
            robot_add_block("rotate_left", {"angle": angle})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)

    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white",
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_rotate_right():
    dialog = tk.Toplevel(root)
    dialog.title("Rotate Right Angle Settings")
    dialog.geometry("300x180")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(dialog, text="Rotation angle (degrees):", font=("Meiryo UI", 12)).pack(pady=15)
    angle_var = tk.StringVar(value="90")
    tk.Entry(dialog, textvariable=angle_var, font=("Meiryo UI", 12), justify="center").pack(pady=5)

    def confirm():
        try:
            angle = float(angle_var.get())
            robot_add_block("rotate_right", {"angle": angle})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)

    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white",
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_rotate_180():
    robot_add_block("rotate_180")

def robot_add_face_direction():
    dialog = tk.Toplevel(root)
    dialog.title("Direction Settings")
    dialog.geometry("350x200")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Select direction:", font=("Meiryo UI", 12)).pack(pady=15)
    dir_var = tk.StringVar(value="North")
    directions = ["North", "East", "South", "West"]
    ttk.Combobox(dialog, textvariable=dir_var, values=directions, state="readonly", 
                 width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        robot_add_block("face_direction", {"direction": dir_var.get()})
        dialog.destroy()
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_wait():
    dialog = tk.Toplevel(root)
    dialog.title("Wait Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Wait seconds:", font=("Meiryo UI", 12)).pack(pady=15)
    sec_var = tk.StringVar(value="1")
    tk.Entry(dialog, textvariable=sec_var, width=18, font=("Meiryo UI", 11)).pack(pady=8)
    
    def confirm():
        try:
            sec = float(sec_var.get())
            robot_add_block("wait", {"seconds": sec})
            dialog.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter a number", parent=dialog)
    
    tk.Button(dialog, text="Add", command=confirm, bg="#0d6efd", fg="white", 
              font=("Meiryo UI", 11, "bold"), width=12, height=2).pack(pady=15)
    center_dialog(dialog)

def robot_add_return_home():
    robot_add_block("return_home")

# Drone & Robot Control tab UI
robot_main_frame = tk.Frame(tab_robot, bg=THEMES[current_theme]['bg'])
robot_main_frame.pack(expand=True, fill="both", padx=15, pady=15)

# Mode selection
robot_mode_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_mode_frame.pack(fill="x", pady=(0, 15))
tk.Label(robot_mode_frame, text="Control mode:", font=("Meiryo UI", 13, "bold"), 
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left", padx=(0, 15))
mode_drone_btn = tk.Radiobutton(robot_mode_frame, text="🚁 Drone", variable=robot_control_mode, 
                                value="drone", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                font=("Meiryo UI", 12), selectcolor=THEMES[current_theme]['button_bg'])
mode_drone_btn.pack(side="left", padx=8)
mode_robot_btn = tk.Radiobutton(robot_mode_frame, text="🤖 Self-driving Robot", variable=robot_control_mode, 
                                value="robot", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                font=("Meiryo UI", 12), selectcolor=THEMES[current_theme]['button_bg'])
mode_robot_btn.pack(side="left", padx=8)

# Hardware selection and operation buttons
robot_hardware_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_hardware_frame.pack(fill="x", pady=(0, 15))
tk.Label(robot_hardware_frame, text="Hardware:", font=("Meiryo UI", 13, "bold"),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left", padx=(0, 15))
robot_hardware_var = tk.StringVar(value="simulation")
hardware_drone_sim = tk.Radiobutton(robot_hardware_frame, text="Simulation", variable=robot_hardware_var,
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

# Add operation buttons to hardware selection column
tk.Frame(robot_hardware_frame, width=30, bg=THEMES[current_theme]['bg']).pack(side="left")  # Spacer
tk.Button(robot_hardware_frame, text="🗑️ Delete Last Block", command=robot_delete_last_block,
          bg="#dc3545", fg="white", font=("Meiryo UI", 10, "bold"), width=18, height=1).pack(side="left", padx=3)
tk.Button(robot_hardware_frame, text="🧹 Clear All Blocks", command=robot_clear_blocks,
          bg="#6c757d", fg="white", font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(side="left", padx=3)
tk.Button(robot_hardware_frame, text="📝 Generate Code", command=robot_generate_code,
          bg="#0d6efd", fg="white", font=("Meiryo UI", 10, "bold"), width=18, height=1).pack(side="left", padx=3)

# Main content area (split left/right)
robot_content_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_content_frame.pack(expand=True, fill="both", pady=(0, 15))

# Left: Button area
robot_buttons_frame = tk.LabelFrame(robot_content_frame, text=" Add Blocks ", 
                                   bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                   font=("Meiryo UI", 12, "bold"), padx=12, pady=12)
robot_buttons_frame.pack(side="left", fill="y", padx=(0, 10))

# Drone buttons (vertical layout)
drone_btns = tk.Frame(robot_buttons_frame, bg=THEMES[current_theme]['bg'])
drone_btns.pack(fill="x")
tk.Button(drone_btns, text="🚀 Takeoff", command=robot_add_takeoff, bg="#198754", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🛬 Land", command=robot_add_land, bg="#dc3545", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⬆️ Forward", command=robot_add_forward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⬇️ Backward", command=robot_add_backward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⬅️ Left", command=robot_add_left, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="➡️ Right", command=robot_add_right, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🔼 Ascend", command=robot_add_up, bg="#17a2b8", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🔼 Descend", command=robot_add_down, bg="#17a2b8", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="↪️ Rotate Left", command=robot_add_rotate_left, bg="#6c757d", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="↩️ Rotate Right", command=robot_add_rotate_right, bg="#6c757d", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⏱️ Wait", command=robot_add_wait, bg="#fd7e14", fg="white",
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🏠 Return on Signal Loss", command=robot_add_return_home, bg="#ffc107", fg="#000", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)

# Robot buttons (vertical layout, initially hidden)
robot_btns = tk.Frame(robot_buttons_frame, bg=THEMES[current_theme]['bg'])
robot_btns.pack_forget()  # Initially hidden
tk.Button(robot_btns, text="⬆️ Forward", command=robot_add_forward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="⬇️ Backward", command=robot_add_backward, bg="#0d6efd", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="↪️ Rotate Left", command=robot_add_rotate_left, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="↩️ Rotate Right", command=robot_add_rotate_right, bg="#6c757d", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🔄 Reverse", command=robot_add_rotate_180, bg="#6610f2", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🧭 Face Direction", command=robot_add_face_direction, bg="#20c997", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="⏱️ Wait", command=robot_add_wait, bg="#fd7e14", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🏠 Return on Signal Loss", command=robot_add_return_home, bg="#ffc107", fg="#000", 
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

# Right: Program area
robot_program_frame = tk.LabelFrame(robot_content_frame, text=" Program ", 
                                   bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                   font=("Meiryo UI", 12, "bold"), padx=12, pady=12)
robot_program_frame.pack(side="left", expand=True, fill="both")

robot_canvas_frame = tk.Frame(robot_program_frame, bg=THEMES[current_theme]['bg'])
robot_canvas_frame.pack(expand=True, fill="both")
robot_canvas = tk.Canvas(robot_canvas_frame, bg=THEMES[current_theme]['text_bg'], 
                        highlightthickness=0)
robot_canvas.pack(side="left", expand=True, fill="both")

# Reposition blocks on canvas size change
robot_canvas.bind("<Configure>", lambda e: robot_refresh_blocks_display())


# ---------- Tab 6: Tools ----------
tools_frame = tk.Frame(tab_tools, bg=THEMES[current_theme]['bg'], padx=20, pady=20)
tools_frame.pack(expand=True, fill="both")
tk.Label(tools_frame, text="🛠 Development Environment & Tools Management",
         font=("Meiryo UI", 12, "bold"), bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=(0, 10))
tk.Label(tools_frame, text=f"Python ExecutePath: {sys.executable}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
virtualenv_path_display = tk.StringVar(value=f"Virtual Environment for Modules: {get_virtualenv_path()}")
tk.Label(tools_frame, textvariable=virtualenv_path_display, font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"Settings Folder: {SETTINGS_FOLDER}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"OS: {platform.system()} {platform.release()}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)

mod_frame = tk.LabelFrame(tools_frame, text=" 📦 Install External Modules ",
                          bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                          font=("Meiryo UI", 10, "bold"), padx=15, pady=12)
mod_frame.pack(anchor="w", fill="x", pady=15)
tk.Label(mod_frame, text="Module name (e.g. requests):", bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 9)).pack(side="left", padx=(0, 10))
mod_entry = tk.Entry(mod_frame, width=20, font=("Consolas", 10))
mod_entry.pack(side="left", padx=5)

def install_custom_module():
    mname = mod_entry.get().strip()
    if not mname:
        messagebox.showwarning("Caution", "Please enter module name to install.")
        return
    try:
        python_executable = get_virtualenv_python()
        res = subprocess.run([python_executable, "-m", "pip", "install", mname],
                             capture_output=True, text=True, timeout=90)
        if res.returncode == 0:
            messagebox.showinfo("Install Success", f"Module '{mname}' installed successfully!")
        else:
            messagebox.showerror("Error", f"Installation failed:\n{res.stderr[:500]}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")

tk.Button(mod_frame, text="Run pip install", command=install_custom_module,
          bg="#198754", fg="white", relief="flat", font=("Meiryo UI", 9, "bold"),
          padx=10, pady=4).pack(side="left", padx=15)

def open_settings_dialog():
    dialog = tk.Toplevel(root)
    dialog.title("Settings")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    timeout_value = tk.StringVar(value=str(test_timeout_seconds))
    virtualenv_path_value = tk.StringVar(value=get_virtualenv_path())
    content = tk.Frame(dialog, padx=20, pady=18)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="Test run timeout", font=("Meiryo UI", 10, "bold")).grid(
        row=0, column=0, sticky="w", padx=(0, 12), pady=6
    )
    ttk.Spinbox(content, from_=1, to=3600, increment=1, textvariable=timeout_value,
                width=8).grid(row=0, column=1, sticky="w", pady=6)
    tk.Label(content, text="seconds (1-3600 seconds)").grid(row=0, column=2, sticky="w", padx=(6, 0))

    tk.Label(content, text="Virtual Environment Path", font=("Meiryo UI", 10, "bold")).grid(
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
            title="Select Virtual Environment Path",
            initialdir=initial_directory,
            mustexist=False
        )
        if selected_path:
            virtualenv_path_value.set(selected_path)

    ttk.Button(content, text="Browse...", command=browse_virtualenv_path).grid(
        row=1, column=3, padx=(8, 0), pady=6
    )

    def save_settings_dialog():
        global test_timeout_seconds, VIRTUALENV_PATH
        try:
            timeout = int(timeout_value.get())
        except ValueError:
            messagebox.showerror("Input Error", "Please enter timeout as an integer.", parent=dialog)
            return
        if not 1 <= timeout <= 3600:
            messagebox.showerror("Input Error", "Please enter a value between 1 and 3600 seconds.", parent=dialog)
            return
        selected_path = virtualenv_path_value.get().strip()
        if not selected_path:
            messagebox.showerror("Input Error", "Please specify Virtual Environment path.", parent=dialog)
            return
        test_timeout_seconds = timeout
        VIRTUALENV_PATH = os.path.abspath(os.path.expanduser(selected_path))
        save_settings()
        virtualenv_path_display.set(f"Virtual Environment for Modules: {get_virtualenv_path()}")
        dialog.destroy()
        messagebox.showinfo("Settings", "Settings saved.", parent=root)

    buttons = tk.Frame(content)
    buttons.grid(row=2, column=0, columnspan=4, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(buttons, text="Save", command=save_settings_dialog).pack(side="right")
    dialog.bind("<Return>", lambda event: save_settings_dialog())


# Menu bar
menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="New", command=new_file)
file_menu.add_command(label="Open File", command=open_file)
file_menu.add_separator()
file_menu.add_command(label="Save As (Ctrl+S)", command=quick_save)
file_menu.add_command(label="Save As", command=save_as_file)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=safe_exit)
menubar.add_cascade(label="File", menu=file_menu)

edit_menu = tk.Menu(menubar, tearoff=0)
edit_menu.add_command(label="Undo (Ctrl+Z)", command=undo_action)
edit_menu.add_command(label="Redo (Ctrl+Y)", command=redo_action)
edit_menu.add_separator()
edit_menu.add_command(label="Search (Ctrl+F)", command=open_search_dialog)
edit_menu.add_command(label="Select All (Ctrl+A)", command=select_all)
menubar.add_cascade(label="Edit", menu=edit_menu)

settings_menu = tk.Menu(menubar, tearoff=0)
settings_menu.add_command(label="Settings...", command=open_settings_dialog)
menubar.add_cascade(label="Settings", menu=settings_menu)

root.config(menu=menubar)

apply_theme(current_theme)
update_line_numbers()
update_status_bar()
root.protocol("WM_DELETE_WINDOW", safe_exit)
root.mainloop()
