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

# Windows only
try:
    import winsound
except ImportError:
    winsound = None

# Settings
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
VENV_FOLDER_NAME = "Python_Editor_Virtual_Environment"

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
        raise RuntimeError("Could not create virtual environment Python.")
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
        res = messagebox.askyesnocancel("Confirm", "Changes have not been saved. Do you want to save?")
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
            messagebox.showinfo("Save Complete", f"File overwritten:\n{os.path.basename(quick_save.current_file_path)}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
            return False
    else:
        return save_as_file()

def save_as_file():
    global last_saved_content, text_modified
    content = text.get("1.0", tk.END).strip()
    selected_filetype = tk.StringVar(root)
    path = filedialog.asksaveasfilename(
        filetypes=[
            ("Python Windowless (*.pyw)", "*.pyw"),
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
            messagebox.showinfo("Save Complete", f"File saved:\n{os.path.basename(path)}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
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
            messagebox.showerror("Error", f"Load failed: {e}")

def new_file():
    global text_modified, last_saved_content
    if text_modified and not messagebox.askyesno("Confirm", "Discard current content and create new file?"):
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
        "description": "A simple GUI calculator that selects two numbers and calculation method to display the result.",
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
        messagebox.showerror("Input Error", "Please enter numbers in both fields.")
    except ZeroDivisionError:
        messagebox.showerror("Calculation Error", "Cannot divide by zero.")

tk.Button(root, text="Calculate", command=calculate).pack(pady=4)
root.mainloop()
'''
    },
    {
        "category": "Practice Mini Apps", "name": "Rock Paper Scissors", "kind": "code",
        "description": "Press a button to play against the computer. Also displays win/loss counts.",
        "code": '''import random
import tkinter as tk

root = tk.Tk()
root.title("Rock Paper Scissors")
root.geometry("340x220")
score = {"Win": 0, "Lose": 0, "Draw": 0}
result = tk.Label(root, text="Choose your hand", font=("Meiryo UI", 14))
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
    result.config(text=f"You: {player} / Opponent: {computer}  -> {outcome}")
    score_label.config(text=f"Win {score['Win']}  Lose {score['Lose']}  Draw {score['Draw']}")

for hand in ("Rock", "Scissors", "Paper"):
    tk.Button(root, text=hand, command=lambda value=hand: play(value)).pack(side="left", expand=True, padx=8)
root.mainloop()
'''
    },
    {
        "category": "Practice Mini Apps", "name": "Number Guessing Game", "kind": "code",
        "description": "Guess a number from 1 to 100. Enter a number in the input field to check.",
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
        message.config(text=f"Correct! You guessed it in {tries} tries")
    elif number < answer:
        message.config(text="Try a larger number")
    else:
        message.config(text="Try a smaller number")

tk.Button(root, text="Check", command=check_guess).pack(pady=8)
root.mainloop()
'''
    },
    {
        "category": "Practice Mini Apps", "name": "Timer", "kind": "code",
        "description": "A timer that counts down for a specified number of seconds.",
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
        messagebox.showinfo("Timer", "Time's up!")
        return
    seconds_left -= 1
    root.after(1000, tick)

def start():
    global seconds_left, running
    try:
        seconds_left = int(seconds_input.get())
        if seconds_left <= 0: raise ValueError
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a positive number of seconds.")
        return
    running = True
    tick()

tk.Button(root, text="Start", command=start).pack(pady=10)
root.mainloop()
'''
    },
    {
        "category": "Daily Utilities", "name": "ToDo List", "kind": "code",
        "description": "Add tasks and delete completed items.",
        "code": '''import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("ToDo List")
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
tk.Button(buttons, text="Delete Selected", command=remove_task).pack(side="left", padx=5)
root.mainloop()
'''
    },
    {
        "category": "Daily Utilities", "name": "Notepad", "kind": "code",
        "description": "Edit text and open/save as text files.",
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
            messagebox.showerror("Load Error", str(error))

def save_note():
    path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
    if path:
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(editor.get("1.0", "end-1c"))
            messagebox.showinfo("Save", "Memo saved.")
        except OSError as error:
            messagebox.showerror("Save Error", str(error))

toolbar = tk.Frame(root)
toolbar.pack(fill="x")
tk.Button(toolbar, text="Open", command=open_note).pack(side="left", padx=6, pady=4)
tk.Button(toolbar, text="Save As", command=save_note).pack(side="left", padx=6, pady=4)
root.mainloop()
'''
    },
    {
        "category": "Daily Utilities", "name": "Password Generator", "kind": "code",
        "description": "Generate a random password of specified length.",
        "code": '''import secrets
import string
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Password Generator")
root.geometry("380x190")
tk.Label(root, text="Length (8-128)").pack(pady=(18, 4))
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
        "category": "Daily Utilities", "name": "Batch Rename Files", "kind": "code",
        "description": "Add a prefix to file names in a selected folder. Confirms before changes.",
        "code": '''import os
import tkinter as tk
from tkinter import filedialog, messagebox

root = tk.Tk()
root.title("Batch Rename Files")
root.geometry("430x210")
folder = tk.StringVar()
prefix = tk.StringVar(value="Sorted_")

def choose_folder():
    selected = filedialog.askdirectory()
    if selected:
        folder.set(selected)

tk.Label(root, text="Target Folder").pack(anchor="w", padx=12, pady=(12, 2))
tk.Entry(root, textvariable=folder).pack(fill="x", padx=12)
tk.Button(root, text="Choose Folder", command=choose_folder).pack(anchor="e", padx=12, pady=4)
tk.Label(root, text="Prefix to add to file names").pack(anchor="w", padx=12, pady=(6, 2))
tk.Entry(root, textvariable=prefix).pack(fill="x", padx=12)

def rename_files():
    path, start = folder.get(), prefix.get()
    if not path or not start:
        messagebox.showerror("Input Error", "Please specify folder and prefix.")
        return
    files = [name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name)) and not name.startswith(start)]
    if not files:
        messagebox.showinfo("Confirm", "No files to rename.")
        return
    if not messagebox.askyesno("Confirm Changes", f"Rename {len(files)} files. Continue?"):
        return
    renamed = 0
    for name in files:
        old = os.path.join(path, name)
        new = os.path.join(path, start + name)
        if not os.path.exists(new):
            os.rename(old, new)
            renamed += 1
    messagebox.showinfo("Complete", f"Renamed {renamed} files.")

tk.Button(root, text="Batch Rename", command=rename_files).pack(pady=10)
root.mainloop()
'''
    },
    {
        "category": "Daily Utilities", "name": "CSV Summary", "kind": "code",
        "description": "Open a CSV file and display counts and numeric totals for each column.",
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
tk.Label(toolbar, text="CSV File Summary", font=("Meiryo UI", 15, "bold")).pack(side="left")
output_frame = tk.Frame(root, padx=16, pady=12)
output_frame.grid(row=1, column=0, sticky="nsew")
output_frame.grid_columnconfigure(0, weight=1)
output_frame.grid_rowconfigure(0, weight=1)
output = tk.Text(output_frame, wrap="none", font=("Meiryo UI", 11), padx=10, pady=8)
output.grid(row=0, column=0, sticky="nsew")
scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=output.yview)
scrollbar.grid(row=0, column=1, sticky="ns")
output.config(yscrollcommand=scrollbar.set)
status = tk.Label(root, text="Select a CSV file to display counts and numeric totals by column.",
              anchor="w", font=("Meiryo UI", 10), padx=16)
status.grid(row=2, column=0, sticky="ew", pady=(0, 6))

def summarize():
    path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
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
            lines.append(f"{column}: Input {sum(bool(v) for v in values)} items")
            if numbers:
                lines.append(f"  Numeric total: {sum(numbers):g}")
        output.delete("1.0", tk.END)
        output.insert("1.0", "\\n".join(lines))
        status.config(text=f"Summary complete: {len(rows)} rows")
    except (OSError, csv.Error) as error:
        messagebox.showerror("Load Error", str(error))

tk.Button(toolbar, text="Select CSV and Summarize", command=summarize,
          font=("Meiryo UI", 12, "bold"), padx=28, pady=12).pack(side="right")
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "Get Web Page Title", "kind": "code",
        "description": "Enter a URL to get the web page title using standard library.",
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
result = tk.Label(root, text="Result will be displayed here", wraplength=440)
result.pack(pady=8)

def fetch_title():
    address = url.get().strip()
    if not address.startswith(("https://", "http://")):
        messagebox.showerror("URL Error", "Please enter a URL starting with http:// or https://.")
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
        "description": "Get weather from city name. Uses Open-Meteo free API, no API key required.",
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
result = tk.Label(root, text="Enter city name", font=("Meiryo UI", 12), wraplength=320)
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
        result.config(text=f"{place['name']}\\nTemp {current['temperature_2m']}℃ / Humidity {current['relative_humidity_2m']}%\\nWeather code {current['weather_code']}")
    except Exception as error:
        messagebox.showerror("Fetch Error", str(error))

tk.Button(root, text="Get Weather", command=get_weather).pack()
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "Discord Webhook Sender", "kind": "code",
        "description": "Enter Webhook URL and message to send to Discord. No additional libraries or bot tokens needed. Treat Webhook URL as secret information.",
        "code": '''import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Discord Webhook Sender")
root.geometry("640x440")
root.minsize(560, 390)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(3, weight=1)

tk.Label(root, text="Discord Webhook URL", font=("Meiryo UI", 11, "bold")).grid(
    row=0, column=0, sticky="w", padx=18, pady=(18, 4)
)
webhook_input = tk.Entry(root, font=("Consolas", 10))
webhook_input.grid(row=1, column=0, sticky="ew", padx=18)
tk.Label(root, text="Message to Send", font=("Meiryo UI", 11, "bold")).grid(
    row=2, column=0, sticky="w", padx=18, pady=(14, 4)
)
message_input = tk.Text(root, height=7, wrap="word", font=("Meiryo UI", 11))
message_input.grid(row=3, column=0, sticky="nsew", padx=18)
status = tk.Label(root, text="Enter Webhook URL and message.", anchor="w")
status.grid(row=4, column=0, sticky="ew", padx=18, pady=8)

def send_message():
    webhook = webhook_input.get().strip()
    content = message_input.get("1.0", "end-1c").strip()
    parsed = urlparse(webhook)
    if parsed.scheme != "https" or parsed.netloc not in ("discord.com", "discordapp.com") or not parsed.path.startswith("/api/webhooks/"):
        messagebox.showerror("URL Error", "Please enter a Discord Webhook URL.")
        return
    if not content:
        messagebox.showerror("Input Error", "Please enter a message to send.")
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
        status.config(text="Sent successfully.")
    except HTTPError as error:
        messagebox.showerror("Discord Error", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}")
    except (URLError, TimeoutError, RuntimeError) as error:
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
        "description": "GUI for sending messages via LINE official API. Requires channel access token and recipient ID. Cannot send to official LINE with just Webhook URL.",
        "code": '''import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("LINE Message Sender")
root.geometry("620x520")
root.minsize(540, 470)
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(7, weight=1)

tk.Label(root, text="Send messages via LINE Messaging API", font=("Meiryo UI", 14, "bold")).grid(
    row=0, column=0, sticky="w", padx=18, pady=(18, 4)
)
tk.Label(root, text="Uses channel access token and recipient ID, not Webhook URL.",
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
        status.config(text="Sent to LINE successfully.")
    except HTTPError as error:
        messagebox.showerror("LINE API Error", f"HTTP {error.code}: {error.read().decode('utf-8', errors='replace')[:500]}")
    except (URLError, TimeoutError, RuntimeError) as error:
        messagebox.showerror("Send Error", str(error))

tk.Button(root, text="Send to LINE", command=send_message,
          font=("Meiryo UI", 12, "bold"), padx=24, pady=10).grid(
              row=9, column=0, sticky="e", padx=18, pady=(0, 16)
          )
root.mainloop()
'''
    },
    {
        "category": "Advanced Projects", "name": "GUI Form (Designer)", "kind": "designer",
        "description": "Place buttons, labels, and input fields to create a GUI. Switches to form creation tab.",
        "code": ""
    },
]

def load_project_code(code):
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
    return True

def open_hotkey_builder():
    win = tk.Toplevel(root)
    win.title("Hotkey and Button Creator")
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
    tk.Label(content, text="Register Hotkey and Button Actions", font=("Meiryo UI", 14, "bold")).pack(anchor="w")

    settings = tk.Frame(content)
    settings.pack(fill="x", pady=(10, 8))
    tk.Label(settings, text="Window Name").pack(side="left")
    title_value = tk.StringVar(value=str(builder_config.get("title", "Simple Hotkey")))
    ttk.Entry(settings, textvariable=title_value, width=24).pack(side="left", padx=(6, 16))
    tk.Label(settings, text="Width").pack(side="left")
    width_value = tk.StringVar(value=str(builder_config.get("width", 240)))
    ttk.Entry(settings, textvariable=width_value, width=7).pack(side="left", padx=6)
    tk.Label(settings, text="Height").pack(side="left")
    height_value = tk.StringVar(value=str(builder_config.get("height", 420)))
    ttk.Entry(settings, textvariable=height_value, width=7).pack(side="left", padx=6)
    tk.Label(settings, text="Icon Operation").pack(side="left", padx=(10, 4))
    tray_click_value = tk.StringVar(value=builder_config.get("tray_click_exit", "double"))
    ttk.Combobox(settings, textvariable=tray_click_value,
                 values=("Exit on Single Click", "Exit on Double Click"),
                 state="readonly", width=22).pack(side="left")
    if tray_click_value.get() not in ("Exit on Single Click", "Exit on Double Click"):
        tray_click_value.set("Exit on Double Click")

    icon_settings = tk.Frame(content)
    icon_settings.pack(fill="x", pady=(0, 8))
    tk.Label(icon_settings, text="Tray Icon").pack(side="left")
    tray_icon_style_value = tk.StringVar(value=builder_config.get("tray_icon_style", "Original (H)"))
    icon_style_options = ("Original (H)", "Info", "Warning", "Error", "ICO File")
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
            parent=win, title="Select Tray Icon", filetypes=[("Icon Files", "*.ico")]
        )
        if selected_path:
            tray_icon_path_value.set(selected_path)
            tray_icon_style_value.set("ICO File")

    ttk.Button(icon_settings, text="Select ICO...", command=choose_tray_icon).pack(side="left")

    body = tk.Frame(content)
    body.pack(fill="both", expand=True)
    columns = ("shortcut", "button", "kind", "target")
    table = ttk.Treeview(body, columns=columns, show="headings", height=9, selectmode="browse")
    for column, label, width in (("shortcut", "Hotkey", 125), ("button", "Button Name", 145), ("kind", "Action", 145), ("target", "Content", 400)):
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

    tk.Label(form, text="Key (e.g., Alt+a)").grid(row=0, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="Button Name (optional)").grid(row=0, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="Action").grid(row=1, column=0, sticky="w", padx=4, pady=3)
    kind_menu = ttk.Combobox(form, textvariable=kind_value, values=("Open URL", "Launch App/File", "Send Keys", "Run Command"), state="readonly", width=18)
    kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="URL / Path / Key / Command").grid(row=1, column=2, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
    tk.Label(form, text="Wait seconds after execution").grid(row=2, column=0, sticky="w", padx=4, pady=3)
    ttk.Entry(form, textvariable=wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
    tk.Label(form, text="Key to send after wait (optional)").grid(row=2, column=2, sticky="w", padx=4, pady=3)
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
                "height": height_value.get(), "tray_click_exit": tray_click_value.get(),
                "tray_icon_style": tray_icon_style_value.get(),
                "tray_icon_path": tray_icon_path_value.get(),
                "actions": actions}

    def persist_configuration():
        try:
            with open(builder_config_path, "w", encoding="utf-8") as config_file:
                json.dump(configuration_data(), config_file, ensure_ascii=False, indent=2)
        except OSError as error:
            messagebox.showerror("Settings Save Error", str(error), parent=win)

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
            messagebox.showinfo("Settings Saved", "Settings saved.", parent=win)
        except OSError as error:
            messagebox.showerror("Settings Save Error", str(error), parent=win)

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
                    raise ValueError("Wait time must be between 0 and 3600 seconds.")
                normalized_actions.append({
                    "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                    "kind": str(item.get("kind", "Open URL")), "target": str(item.get("target", "")),
                    "wait": wait_seconds, "followup": str(item.get("followup", ""))
                })
            actions[:] = normalized_actions
            title_value.set(str(loaded.get("title", "Simple Hotkey")))
            width_value.set(str(loaded.get("width", 240)))
            height_value.set(str(loaded.get("height", 420)))
            tray_click_value.set(loaded.get("tray_click_exit", "Exit on Double Click"))
            if tray_click_value.get() not in ("Exit on Single Click", "Exit on Double Click"):
                tray_click_value.set("Exit on Double Click")
            tray_icon_style_value.set(loaded.get("tray_icon_style", "Original (H)"))
            if tray_icon_style_value.get() not in icon_style_options:
                tray_icon_style_value.set(icon_style_options[0])
            tray_icon_path_value.set(str(loaded.get("tray_icon_path", "")))
            refresh_table()
            clear_form()
            persist_configuration()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            messagebox.showerror("Settings Load Error", str(error), parent=win)

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
            messagebox.showerror("Input Error", "Please enter a hotkey or button name.", parent=win)
            return
        if not target:
            messagebox.showerror("Input Error", "Please enter action content.", parent=win)
            return
        try:
            wait = float(wait_value.get())
            if not 0 <= wait <= 3600:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input Error", "Please enter a number between 0 and 3600 for wait time.", parent=win)
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
            messagebox.showerror("Input Error", "Please enter integers between 120 and 3000 for width and height.", parent=win)
            return
        seen_shortcuts = set()
        for item in actions:
            key = item["shortcut"].lower().replace(" ", "")
            if key and key in seen_shortcuts:
                messagebox.showerror("Input Error", f"Duplicate hotkey: {item['shortcut']}", parent=win)
                return
            seen_shortcuts.add(key)
        if tray_icon_style_value.get() == "ICO File" and not os.path.isfile(tray_icon_path_value.get()):
            messagebox.showerror("Icon Error", "Selected ICO file not found.", parent=win)
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
    raise ValueError(f"Unsupported key: {name}")

def parse_hotkey(shortcut):
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    modifiers = 0
    key = None
    for part in parts:
        if part in HOTKEY_MODIFIERS:
            modifiers |= HOTKEY_MODIFIERS[part]
        else:
            if key is not None:
                raise ValueError(f"Please specify only one key: {shortcut}")
            key = get_key_code(part)
    if key is None:
        raise ValueError(f"No key specified: {shortcut}")
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
        if kind == "Open URL":
            webbrowser.open(target, new=2)
        elif kind == "Launch App/File":
            os.startfile(target)
        elif kind == "Run Command":
            subprocess.Popen(target, shell=True)
        elif kind == "Send Keys":
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
                    raise OSError("Could not register this key. It may be in use by another app.")
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
            messagebox.showerror("Hotkey", value, parent=root)
    root.after(50, process_events)

def restore_window():
    root.deiconify()
    root.state("normal")
    root.lift()
    root.focus_force()

def show_tray_menu():
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Show Window", command=restore_window)
    menu.add_separator()
    menu.add_command(label="Exit", command=close_window)
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
    if TRAY_ICON_STYLE == "ICO File" and os.path.isfile(TRAY_ICON_PATH):
        user32.LoadImageW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.LoadImageW.restype = wintypes.HICON
        icon_handle = user32.LoadImageW(None, TRAY_ICON_PATH, 1, 0, 0, 0x0010)
    elif TRAY_ICON_STYLE in ("Info", "Warning", "Error"):
        user32.LoadIconW.restype = wintypes.HICON
        stock_icons = {"Info": 32516, "Warning": 32515, "Error": 32513}
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
    icon_data.szTip = f"{WINDOW_TITLE} - Running"
    previous_window_proc = set_window_long(hwnd, -4, ctypes.cast(tray_window_proc, ctypes.c_void_p))
    tray_added = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(icon_data)))
    if tray_added:
        root.withdraw()
    else:
        root.deiconify()
        messagebox.showerror("System Tray", "Could not register icon in notification area. Showing window.", parent=root)

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
icon_data.szTip = f"{WINDOW_TITLE} - Running"
root.protocol("WM_DELETE_WINDOW", close_window)
threading.Thread(target=hotkey_loop, daemon=True).start()
root.after(50, process_events)
root.withdraw()
root.after(100, install_tray_icon)
root.mainloop()
'''
        source = source.replace("__TITLE__", repr(title_value.get().strip() or "Simple Hotkey"))
        source = source.replace("__WIDTH__", str(window_width)).replace("__HEIGHT__", str(window_height))
        source = source.replace("__TRAY_EXIT_ON__", repr(
            "single" if tray_click_value.get() == "Exit on Single Click" else "double"
        ))
        source = source.replace("__TRAY_ICON_STYLE__", repr(tray_icon_style_value.get()))
        source = source.replace("__TRAY_ICON_PATH__", repr(tray_icon_path_value.get()))
        source = source.replace("__ACTIONS__", json.dumps(action_data, ensure_ascii=False, indent=4))
        if load_project_code(source):
            win.destroy()

    row_buttons = tk.Frame(content)
    row_buttons.pack(fill="x", pady=(4, 8))
    ttk.Button(row_buttons, text="New Row", command=clear_form).pack(side="left")
    ttk.Button(row_buttons, text="Add / Update", command=save_action).pack(side="left", padx=6)
    ttk.Button(row_buttons, text="Delete Selected", command=delete_action).pack(side="left")
    ttk.Button(row_buttons, text="Load Settings", command=load_configuration).pack(side="left", padx=(12, 0))
    ttk.Button(row_buttons, text="Save Settings", command=save_configuration_as).pack(side="left", padx=6)
    ttk.Button(row_buttons, text="Generate Code", command=make_code).pack(side="right")
    ttk.Button(row_buttons, text="Close", command=close_builder).pack(side="right", padx=6)
    refresh_table()
    table.bind("<<TreeviewSelect>>", show_selected)
    win.protocol("WM_DELETE_WINDOW", close_builder)


def open_project_catalog():
    win = tk.Toplevel(root)
    win.title("Beginner Project Catalog")
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
    name_label = tk.Label(details, text="Select a project", anchor="w", font=("Meiryo UI", 13, "bold"))
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
    load_button = tk.Button(buttons, text="Load Code to Editor", state="disabled")
    load_button.pack(side="right", padx=(6, 0))
    designer_button = tk.Button(buttons, text="Open Form Designer", state="disabled")
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
    fname = os.path.basename(quick_save.current_file_path) if hasattr(quick_save, 'current_file_path') and quick_save.current_file_path else "Untitled"
    mod = " ●" if text_modified else ""
    status_label.config(text=f" 📂 {fname}{mod}   |   Line: {line}  Col: {col}  Chars: {char_count} ")
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
            messagebox.showinfo("Replace Complete", "Replaced all occurrences.")
        else:
            messagebox.showinfo("Replace", "No matches found.")

    tk.Button(search_window, text="Find Next", command=do_find, width=12).place(x=90, y=110)
    tk.Button(search_window, text="Replace", command=do_replace, width=10).place(x=200, y=110)
    tk.Button(search_window, text="Replace All", command=do_replace_all, width=12).place(x=290, y=110)
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
        messagebox.showerror("Error", f"Failed to check autopep8:\n{e}")
        return
    if availability.returncode != 0:
        if messagebox.askyesno("Confirm", "autopep8 is not installed.\nInstall it?"):
            try:
                subprocess.run([venv_python, "-m", "pip", "install", "autopep8"],
                               check=True, capture_output=True, text=True, timeout=60)
            except Exception as e:
                messagebox.showerror("Error", f"Installation failed:\n{e}")
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
        if messagebox.askyesno("Confirm", "Unsaved changes exist. Save before test run?"):
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
            out = res.stdout if res.returncode == 0 else f"【Error】\n{error_output}"
            if res.returncode == 0 and not out.strip():
                out = "Test run completed successfully.\nNo standard output."
            if res.returncode == 0:
                root.after(0, lambda: messagebox.showinfo("Test Result", out[:1500] + ("\n...(truncated)" if len(out) > 1500 else "")))
            else:
                root.after(0, lambda: messagebox.showerror("Test Error", out))
        except subprocess.TimeoutExpired:
            root.after(0, lambda: messagebox.showerror("Timeout", f"Execution exceeded time limit ({test_timeout_seconds} seconds)."))
        except Exception as e:
            root.after(0, lambda: messagebox.showerror("Execution Error", str(e)))
        finally:
            try:
                os.unlink(tpath)
            except Exception:
                pass
    Thread(target=run, daemon=True).start()

def parse_and_install_code_modules():
    code = text.get("1.0", tk.END)
    if not code.strip():
        messagebox.showwarning("Warning", "No code in editor.")
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
        messagebox.showinfo("Confirm", "No external modules to install found!")
        return
    try:
        python_executable = get_virtualenv_python()
        check_script = "import importlib.util, json, sys; names=json.loads(sys.argv[1]); print(json.dumps([name for name in names if importlib.util.find_spec(name) is None]))"
        result = subprocess.run([python_executable, "-c", check_script, json.dumps(candidate_modules)],
                                check=True, capture_output=True, text=True, timeout=30)
        target_modules = json.loads(result.stdout)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to check virtual environment modules:\n{e}")
        return
    if not target_modules:
        messagebox.showinfo("Confirm", "No external modules to install found!")
        return
    win = tk.Toplevel(root)
    win.title("Auto Module Install")
    win.geometry("450x320")
    win.resizable(False, False)
    win.configure(bg="#f8f9fa")
    tk.Label(win, text="📦 Uninstalled External Modules Found", font=("Meiryo UI", 11, "bold"),
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
            messagebox.showwarning("Warning", "Please select modules.")
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
        msg = f"Install complete: {', '.join(success_list) if success_list else 'None'}"
        if fail_list:
            msg += f"\nFailed: {', '.join(fail_list)}"
        messagebox.showinfo("Install Result", msg)
        win.destroy()
    tk.Button(win, text="🚀 Install Selected Modules", command=do_install,
              bg="#198754", fg="white", font=("Meiryo UI", 10, "bold"), padx=10, pady=8, cursor="hand2").pack(side="bottom", fill="x", padx=15, pady=15)


# ==================== Main UI ====================
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
        display_text = error_text[:1500] + "\n...(truncated. Full text copied to clipboard)"
    else:
        display_text = error_text + "\n\nError content copied to clipboard."
    return original_showerror(title, display_text, **options)

messagebox.showerror = showerror_with_clipboard

if platform.system() == "Windows":
    root.after(10, lambda: root.state('zoomed'))
else:
    try:
        root.attributes('-zoomed', True)
    except Exception:
        root.geometry("1400x900")

# Set minimum size
root.minsize(1200, 800)

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
top_notebook.add(tab_samples, text="🧩 Sample Catalog")

tab_hotkey = ttk.Frame(top_notebook)
top_notebook.add(tab_hotkey, text="⌨ Hotkey Creator")

tab_designer = ttk.Frame(top_notebook)
top_notebook.add(tab_designer, text="🎨 Form Designer")

tab_robot = ttk.Frame(top_notebook)
top_notebook.add(tab_robot, text="🚁 Drone Robot Control")

tab_tools = ttk.Frame(top_notebook)
top_notebook.add(tab_tools, text="🛠 Tools Environment Info")


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
add_btn(top_btn_frame, "📦 Detect Modules", parse_and_install_code_modules, "#6610f2")
add_btn(top_btn_frame, "🔍 Search", open_search_dialog, "#6c757d")
add_btn(top_btn_frame, "🌓 Toggle Theme", toggle_theme, "#ffc107", "#000")

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
status_label = tk.Label(status_bar, text=" 📂 Untitled   |   Line: 1  Col: 0  Chars: 0 ",
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


# ---------- Tab 2: Sample Catalog ----------
samples_content = tk.Frame(tab_samples, padx=12, pady=12)
samples_content.pack(fill="both", expand=True)
tk.Label(samples_content, text="Select what you want to create", font=("Meiryo UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
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
samples_name_label = tk.Label(samples_details, text="Select a project", anchor="w", font=("Meiryo UI", 13, "bold"))
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
samples_load_button = tk.Button(samples_buttons, text="Load Code to Editor", state="disabled")
samples_load_button.pack(side="right", padx=(6, 0))
samples_designer_button = tk.Button(samples_buttons, text="Open Form Designer", state="disabled")
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
hotkey_content = tk.Frame(tab_hotkey, padx=14, pady=12)
hotkey_content.pack(fill="both", expand=True)
tk.Label(hotkey_content, text="Register Hotkey and Button Actions", font=("Meiryo UI", 14, "bold")).pack(anchor="w")

hotkey_settings = tk.Frame(hotkey_content)
hotkey_settings.pack(fill="x", pady=(10, 8))
tk.Label(hotkey_settings, text="Window Name").pack(side="left")
hotkey_title_value = tk.StringVar(value="Simple Hotkey")
ttk.Entry(hotkey_settings, textvariable=hotkey_title_value, width=24).pack(side="left", padx=(6, 16))
tk.Label(hotkey_settings, text="Width").pack(side="left")
hotkey_width_value = tk.StringVar(value="240")
ttk.Entry(hotkey_settings, textvariable=hotkey_width_value, width=7).pack(side="left", padx=6)
tk.Label(hotkey_settings, text="Height").pack(side="left")
hotkey_height_value = tk.StringVar(value="420")
ttk.Entry(hotkey_settings, textvariable=hotkey_height_value, width=7).pack(side="left", padx=6)
tk.Label(hotkey_settings, text="Icon Operation").pack(side="left", padx=(10, 4))
hotkey_tray_click_value = tk.StringVar(value="double")
ttk.Combobox(hotkey_settings, textvariable=hotkey_tray_click_value,
             values=("Exit on Single Click", "Exit on Double Click"),
             state="readonly", width=22).pack(side="left")
if hotkey_tray_click_value.get() not in ("Exit on Single Click", "Exit on Double Click"):
    hotkey_tray_click_value.set("Exit on Double Click")

hotkey_icon_settings = tk.Frame(hotkey_content)
hotkey_icon_settings.pack(fill="x", pady=(0, 8))
tk.Label(hotkey_icon_settings, text="Tray Icon").pack(side="left")
hotkey_tray_icon_style_value = tk.StringVar(value="Original (H)")
hotkey_icon_style_options = ("Original (H)", "Info", "Warning", "Error", "ICO File")
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
        title="Select Tray Icon", filetypes=[("Icon Files", "*.ico")]
    )
    if selected_path:
        hotkey_tray_icon_path_value.set(selected_path)
        hotkey_tray_icon_style_value.set("ICO File")

ttk.Button(hotkey_icon_settings, text="Select ICO...", command=hotkey_choose_tray_icon).pack(side="left")

hotkey_body = tk.Frame(hotkey_content)
hotkey_body.pack(fill="both", expand=True)
hotkey_columns = ("shortcut", "button", "kind", "target")
hotkey_table = ttk.Treeview(hotkey_body, columns=hotkey_columns, show="headings", height=9, selectmode="browse")
for column, label, width in (("shortcut", "Hotkey", 125), ("button", "Button Name", 145), ("kind", "Action", 145), ("target", "Content", 400)):
    hotkey_table.heading(column, text=label)
    hotkey_table.column(column, width=width, minwidth=70, stretch=column == "target")
hotkey_table.pack(side="left", fill="both", expand=True)
hotkey_table_scroll = ttk.Scrollbar(hotkey_body, orient="vertical", command=hotkey_table.yview)
hotkey_table_scroll.pack(side="right", fill="y")
hotkey_table.configure(yscrollcommand=hotkey_table_scroll.set)

hotkey_form = tk.LabelFrame(hotkey_content, text="Add/Edit Action", padx=10, pady=8)
hotkey_form.pack(fill="x", pady=(10, 4))
hotkey_shortcut_value = tk.StringVar()
hotkey_button_value = tk.StringVar()
hotkey_kind_value = tk.StringVar(value="Open URL")
hotkey_target_value = tk.StringVar()
hotkey_wait_value = tk.StringVar(value="0")
hotkey_followup_value = tk.StringVar()

tk.Label(hotkey_form, text="Key (e.g., Alt+a)").grid(row=0, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_shortcut_value, width=20).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="Button Name (optional)").grid(row=0, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_button_value, width=24).grid(row=0, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="Action").grid(row=1, column=0, sticky="w", padx=4, pady=3)
hotkey_kind_menu = ttk.Combobox(hotkey_form, textvariable=hotkey_kind_value, values=("Open URL", "Launch App/File", "Send Keys", "Run Command"), state="readonly", width=18)
hotkey_kind_menu.grid(row=1, column=1, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="URL / Path / Key / Command").grid(row=1, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_target_value).grid(row=1, column=3, sticky="ew", padx=4, pady=3)
tk.Label(hotkey_form, text="Wait seconds after execution").grid(row=2, column=0, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_wait_value, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)
tk.Label(hotkey_form, text="Key to send after wait (optional)").grid(row=2, column=2, sticky="w", padx=4, pady=3)
ttk.Entry(hotkey_form, textvariable=hotkey_followup_value).grid(row=2, column=3, sticky="ew", padx=4, pady=3)
hotkey_form.columnconfigure(1, weight=1)
hotkey_form.columnconfigure(3, weight=2)
tk.Label(hotkey_content, text="Key send examples: Ctrl+w, Alt+F4, Left. Leave key field empty to execute with button only.", anchor="w").pack(fill="x", pady=(2, 4))

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
        
        tray_exit_match = re.search(r'TRAY_EXIT_ON\s*=\s*[\'"]([^\'"]+)[\'"]', code)
        if tray_exit_match:
            exit_value = tray_exit_match.group(1)
            if exit_value == "single":
                hotkey_tray_click_value.set("Exit on Single Click")
            else:
                hotkey_tray_click_value.set("Exit on Double Click")
        
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
        messagebox.showinfo("Load Complete", f"Loaded {len(hotkey_actions)} hotkey settings.")
    else:
        messagebox.showerror("Error", "ACTIONS setting not found in code.")

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
        messagebox.showerror("Settings Save Error", str(error))

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
        messagebox.showinfo("Settings Saved", "Settings saved.")
    except OSError as error:
        messagebox.showerror("Settings Save Error", str(error))

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
                raise ValueError("Wait time must be between 0 and 3600 seconds.")
            normalized_actions.append({
                "shortcut": str(item.get("shortcut", "")), "button": str(item.get("button", "")),
                "kind": str(item.get("kind", "Open URL")), "target": str(item.get("target", "")),
                "wait": wait_seconds, "followup": str(item.get("followup", ""))
            })
        hotkey_actions[:] = normalized_actions
        hotkey_title_value.set(str(loaded.get("title", "Simple Hotkey")))
        hotkey_width_value.set(str(loaded.get("width", 240)))
        hotkey_height_value.set(str(loaded.get("height", 420)))
        hotkey_tray_click_value.set(loaded.get("tray_click_exit", "Exit on Double Click"))
        if hotkey_tray_click_value.get() not in ("Exit on Single Click", "Exit on Double Click"):
            hotkey_tray_click_value.set("Exit on Double Click")
        hotkey_tray_icon_style_value.set(loaded.get("tray_icon_style", "Original (H)"))
        if hotkey_tray_icon_style_value.get() not in hotkey_icon_style_options:
            hotkey_tray_icon_style_value.set(hotkey_icon_style_options[0])
        hotkey_tray_icon_path_value.set(str(loaded.get("tray_icon_path", "")))
        hotkey_refresh_table()
        hotkey_clear_form()
        hotkey_persist_configuration()
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        messagebox.showerror("Settings Load Error", str(error))

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
        messagebox.showerror("Input Error", "Please enter a hotkey or button name.")
        return
    if not target:
        messagebox.showerror("Input Error", "Please enter action content.")
        return
    try:
        wait = float(hotkey_wait_value.get())
        if not 0 <= wait <= 3600:
            raise ValueError
    except ValueError:
        messagebox.showerror("Input Error", "Please enter a number between 0 and 3600 for wait time.")
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
        messagebox.showerror("Input Error", "Please enter integers between 120 and 3000 for width and height.")
        return
    seen_shortcuts = set()
    for item in hotkey_actions:
        key = item["shortcut"].lower().replace(" ", "")
        if key and key in seen_shortcuts:
            messagebox.showerror("Input Error", f"Duplicate hotkey: {item['shortcut']}")
            return
        seen_shortcuts.add(key)
    if hotkey_tray_icon_style_value.get() == "ICO File" and not os.path.isfile(hotkey_tray_icon_path_value.get()):
        messagebox.showerror("Icon Error", "Selected ICO file not found.")
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
    raise ValueError(f"Unsupported key: {name}")

def parse_hotkey(shortcut):
    parts = [part.strip().lower() for part in shortcut.split("+") if part.strip()]
    modifiers = 0
    key = None
    for part in parts:
        if part in HOTKEY_MODIFIERS:
            modifiers |= HOTKEY_MODIFIERS[part]
        else:
            if key is not None:
                raise ValueError(f"Please specify only one key: {shortcut}")
            key = get_key_code(part)
    if key is None:
        raise ValueError(f"No key specified: {shortcut}")
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
        if kind == "Open URL":
            webbrowser.open(target, new=2)
        elif kind == "Launch App/File":
            os.startfile(target)
        elif kind == "Run Command":
            subprocess.Popen(target, shell=True)
        elif kind == "Send Keys":
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
                    raise OSError("Could not register this key. It may be in use by another app.")
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
            messagebox.showerror("Hotkey", value, parent=root)
    root.after(50, process_events)

def restore_window():
    root.deiconify()
    root.state("normal")
    root.lift()
    root.focus_force()

def show_tray_menu():
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Show Window", command=restore_window)
    menu.add_separator()
    menu.add_command(label="Exit", command=close_window)
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
    if TRAY_ICON_STYLE == "ICO File" and os.path.isfile(TRAY_ICON_PATH):
        user32.LoadImageW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
                                      ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.LoadImageW.restype = wintypes.HICON
        icon_handle = user32.LoadImageW(None, TRAY_ICON_PATH, 1, 0, 0, 0x0010)
    elif TRAY_ICON_STYLE in ("Info", "Warning", "Error"):
        user32.LoadIconW.restype = wintypes.HICON
        stock_icons = {"Info": 32516, "Warning": 32515, "Error": 32513}
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
    icon_data.szTip = f"{WINDOW_TITLE} - Running"
    previous_window_proc = set_window_long(hwnd, -4, ctypes.cast(tray_window_proc, ctypes.c_void_p))
    tray_added = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(icon_data)))
    if tray_added:
        root.withdraw()
    else:
        root.deiconify()
        messagebox.showerror("System Tray", "Could not register icon in notification area. Showing window.", parent=root)

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
icon_data.szTip = f"{WINDOW_TITLE} - Running"
root.protocol("WM_DELETE_WINDOW", close_window)
threading.Thread(target=hotkey_loop, daemon=True).start()
root.after(50, process_events)
root.withdraw()
root.after(100, install_tray_icon)
root.mainloop()
'''
    source = source.replace("__TITLE__", repr(hotkey_title_value.get().strip() or "Simple Hotkey"))
    source = source.replace("__WIDTH__", str(window_width)).replace("__HEIGHT__", str(window_height))
    source = source.replace("__TRAY_EXIT_ON__", repr(
        "single" if hotkey_tray_click_value.get() == "Exit on Single Click" else "double"
    ))
    source = source.replace("__TRAY_ICON_STYLE__", repr(hotkey_tray_icon_style_value.get()))
    source = source.replace("__TRAY_ICON_PATH__", repr(hotkey_tray_icon_path_value.get()))
    source = source.replace("__ACTIONS__", json.dumps(action_data, ensure_ascii=False, indent=4))
    if load_project_code(source):
        messagebox.showinfo("Generation Complete", "Hotkey app code transferred to editor!")

hotkey_row_buttons = tk.Frame(hotkey_content)
hotkey_row_buttons.pack(fill="x", pady=(4, 8))
ttk.Button(hotkey_row_buttons, text="New Row", command=hotkey_clear_form).pack(side="left")
ttk.Button(hotkey_row_buttons, text="Add / Update", command=hotkey_save_action).pack(side="left", padx=6)
ttk.Button(hotkey_row_buttons, text="Delete Selected", command=hotkey_delete_action).pack(side="left")
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
        messagebox.showerror("Settings Save Error", str(error))


# ---------- Tab 4: Visual Form Designer ----------
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
                    text=f"📱 Form Size: {form_window_width} x {form_window_height}  |  🖥 Screen Position: X={form_pos_x}, Y={form_pos_y}",
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
tk.Label(size_control_frame, text="Form Size", bg="#2d2d2d", fg="#eeeeee",
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
    pos_str = "Center of Screen" if form_pos_mode == "center" else f"X={form_pos_x}, Y={form_pos_y}"
    size_lbl.config(text=f"📱 Form Size: {form_window_width} x {form_window_height}  |  🖥 Screen Position: {pos_str}")

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

form_color_controls = tk.Frame(designer_toolbar, bg="#2d2d2d")
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
    global form_pos_x, form_pos_y, form_pos_mode
    w_diag = tk.Toplevel(root)
    w_diag.title("Window Screen Position Settings")
    w_diag.geometry("450x340")
    w_diag.resizable(False, False)
    w_diag.configure(bg="#f8f9fa")
    w_diag.transient(root)
    w_diag.grab_set()

    tk.Label(w_diag, text="🖥 Desktop Screen Position at App Launch",
             font=("Meiryo UI", 11, "bold"), bg="#0d6efd", fg="white",
             padx=10, pady=10).pack(side="top", fill="x")

    f_body = tk.Frame(w_diag, bg="#f8f9fa", padx=20, pady=15)
    f_body.pack(fill="both", expand=True)

    mode_var = tk.StringVar(value=form_pos_mode)
    tk.Radiobutton(f_body, text="Automatically display at center of screen", variable=mode_var, value="center",
                   bg="#f8f9fa", font=("Meiryo UI", 10)).pack(anchor="w", pady=5)
    tk.Radiobutton(f_body, text="Display at specified coordinates (X, Y) on desktop", variable=mode_var, value="manual",
                   bg="#f8f9fa", font=("Meiryo UI", 10)).pack(anchor="w", pady=(10, 5))

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

    # Bind to both main and input field (so Home works without clicking)
    w_diag.bind("<Home>", capture_mouse_pos_here)
    x_entry.bind("<Home>", capture_mouse_pos_here)
    y_entry.bind("<Home>", capture_mouse_pos_here)

    tk.Label(f_body, text="💡 [Home] key to auto-enter current mouse coordinates",
             bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 9)).pack(anchor="w", pady=(10, 0))

    def save_pos():
        global form_pos_x, form_pos_y, form_pos_mode
        form_pos_mode = mode_var.get()
        if form_pos_mode == "manual":
            try:
                form_pos_x = int(x_entry.get().strip())
                form_pos_y = int(y_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Please enter valid integers for coordinates.")
                return
        update_size_label()
        messagebox.showinfo("Save Complete", "Window screen position configured!")
        w_diag.destroy()

    tk.Button(w_diag, text="💾 Save Settings", command=save_pos, bg="#198754", fg="white",
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

    # Force focus when opened
    w_diag.after(50, lambda: w_diag.focus_force())


def add_component(ctype):
    global selected_component
    wrapper = tk.Frame(form_preview, bg="#cccccc", bd=1, relief="raised")
    wrapper.place(x=40, y=40, width=150, height=36)

    default_bg = "#e8e8e8" if ctype == "Button" else form_bg_color
    default_fg = form_fg_color

    if ctype == "Button":
        inner = tk.Button(wrapper, text="Button", relief="flat", font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    elif ctype == "Label":
        inner = tk.Label(wrapper, text="Text Label", bg=default_bg, fg=default_fg, font=("Meiryo UI", 10))
    else:
        inner = tk.Entry(wrapper, font=("Meiryo UI", 10), bg=default_bg, fg=default_fg)
    inner.pack(fill="both", expand=True)

    comp_resize_handle = tk.Label(wrapper, text="◢", bg="#0d6efd", fg="white", font=("Meiryo UI", 8), cursor="sizing")
    comp_resize_handle.place(relx=1.0, rely=1.0, x=-12, y=-12, width=12, height=12)

    comp_info = {
        "type": ctype, "wrapper": wrapper, "inner": inner,
        "text": "Button" if ctype == "Button" else ("Text Label" if ctype == "Label" else ""),
        "bg_color": default_bg, "fg_color": default_fg, "font_size": 10,
        "custom_background": False, "custom_foreground": False,
        "action": "none", "param": "", "close_after_action": True,
        "browser_choice": "Default Browser", "browser_window_mode": "Maximize"
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
        messagebox.showwarning("Warning", "Please select a component.")
        return
    diag = tk.Toplevel(root)
    diag.title("Component Detailed Properties Settings")
    diag.geometry("640x620")
    diag.resizable(False, False)
    diag.configure(bg="#f8f9fa")
    diag.transient(root)

    tk.Label(diag, text="🎨 Component Appearance and Action Detailed Settings",
             font=("Meiryo UI", 11, "bold"), bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    bottom_frame = tk.Frame(diag, bg="#e9ecef", padx=15, pady=12)
    bottom_frame.pack(side="bottom", fill="x")

    diag_notebook = ttk.Notebook(diag)
    diag_notebook.pack(fill="both", expand=True, padx=10, pady=10)

    tab_design = ttk.Frame(diag_notebook)
    tab_action = ttk.Frame(diag_notebook)
    diag_notebook.add(tab_design, text="① Text Design Settings")
    diag_notebook.add(tab_action, text="② Action Settings")

    f_des = tk.Frame(tab_design, bg="#f8f9fa", padx=20, pady=20)
    f_des.pack(fill="both", expand=True)

    tk.Label(f_des, text="Display Text (content):", bg="#f8f9fa", font=("Meiryo UI", 10, "bold")).pack(anchor="w")
    txt_entry = tk.Entry(f_des, width=48, font=("Meiryo UI", 10))
    txt_entry.pack(anchor="w", pady=(2, 15))
    txt_entry.insert(0, comp["text"])

    style_frame = tk.LabelFrame(f_des, text=" Design (Color Font Size) ", bg="#f8f9fa",
                                font=("Meiryo UI", 9, "bold"), padx=15, pady=12)
    style_frame.pack(fill="x", pady=5)

    tk.Label(style_frame, text="Background Color:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
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
                          command=lambda: choose_component_color(bg_entry, bg_swatch, "Select Component Background Color"),
                          cursor="hand2")
    bg_swatch.grid(row=0, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="Text Color:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
    fg_entry = tk.Entry(style_frame, width=18, font=("Consolas", 10))
    fg_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)
    fg_entry.insert(0, comp["fg_color"])
    fg_swatch = tk.Button(style_frame, text="  ", width=3, bg=comp["fg_color"],
                          command=lambda: choose_component_color(fg_entry, fg_swatch, "Select Component Text Color"),
                          cursor="hand2")
    fg_swatch.grid(row=1, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="Font Size:", bg="#f8f9fa", font=("Meiryo UI", 9)).grid(row=2, column=0, sticky="w", pady=5)
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

        tk.Label(f_act, text="Select action to execute (many beginner-friendly options added):", bg="#f8f9fa",
                 font=("Meiryo UI", 10, "bold")).pack(anchor="w", pady=(0, 5))

        action_categories = [
            ("--- Basic ---", [
                ("Do Nothing", "none"),
                ("🚪 Exit App", "close_app"),
            ]),
            ("📁 File Folder Operations (Highly Recommended)", [
                ("📄 Copy File", "copy_file"),
                ("📂 Copy Folder", "copy_folder"),
                ("✂ Move File", "move_file"),
                ("🗑 Delete File (with confirmation)", "delete_file"),
                ("📂 Open Folder", "open_folder"),
                ("📄 Open File (associated app)", "open_file_default"),
                ("📁 Create New Folder", "create_folder"),
                ("📝 Create Text File", "create_text_file"),
            ]),
            ("🖥 Open Common Folders", [
                ("🖥 Open Desktop", "open_desktop"),
                ("📄 Open Documents", "open_documents"),
                ("⬇ Open Downloads", "open_downloads"),
                ("📂 Open Explorer", "open_explorer"),
            ]),
            ("🌐 Web Search", [
                ("Open Specified URL", "open_url"),
                ("Open X", "open_x"),
                ("Open ABEMA TV", "open_abema"),
                ("Google Search", "google_search"),
                ("YouTube Search", "youtube_search"),
                ("Google Translate", "google_translate"),
                ("Google Maps", "google_maps"),
            ]),
            ("💬 Message Utility Functions", [
                ("Show Message Box", "show_msg"),
                ("Confirmation Dialog", "ask_yesno"),
                ("Copy Text to Clipboard", "copy_clipboard"),
                ("Copy Current Time to Clipboard", "copy_time"),
                ("Show Current Time", "show_time"),
            ]),
            ("🖥 System Tools", [
                ("Open Notepad", "open_notepad"),
                ("Open Calculator", "open_calc"),
                ("Open Command Prompt Terminal", "open_terminal"),
                ("Play Beep Sound", "beep"),
            ]),
            ("🎲 Fun", [
                ("1-100 Lottery", "random_num"),
                ("Roll Dice", "dice_roll"),
                ("Fortune Telling", "omikuji"),
                ("Generate Password", "gen_password"),
            ]),
        ]

        act_var = tk.StringVar(value=comp["action"])
        for cat_name, acts in action_categories:
            tk.Label(f_act, text=cat_name, bg="#f8f9fa", fg="#0d6efd",
                     font=("Meiryo UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
            for text_lbl, val in acts:
                tk.Radiobutton(f_act, text=text_lbl, variable=act_var, value=val,
                               bg="#f8f9fa", font=("Meiryo UI", 9), anchor="w").pack(anchor="w", padx=12, pady=1)

        tk.Label(f_act, text="Action Parameter (URL message content etc):", bg="#f8f9fa",
                 font=("Meiryo UI", 9, "bold")).pack(anchor="w", pady=(14, 2))
        param_entry = tk.Entry(f_act, width=50, font=("Meiryo UI", 10))
        param_entry.pack(anchor="w")
        param_entry.insert(0, comp["param"])
        close_after_var = tk.BooleanVar(value=comp.get("close_after_action", True))
        tk.Checkbutton(
            f_act,
            text="Exit this app after action execution",
            variable=close_after_var,
            bg="#f8f9fa",
            font=("Meiryo UI", 9),
            anchor="w",
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(f_act, text="Browser to use for open browser action:", bg="#f8f9fa",
                 font=("Meiryo UI", 9)).pack(anchor="w", pady=(8, 2))
        browser_var = tk.StringVar(value=comp.get("browser_choice", "Default Browser"))
        browser_combo = ttk.Combobox(
            f_act,
            textvariable=browser_var,
            values=("Default Browser", "Microsoft Edge", "Google Chrome", "Mozilla Firefox", "Brave"),
            state="readonly",
            width=24,
        )
        browser_combo.pack(anchor="w")
        tk.Label(f_act, text="Browser display method:", bg="#f8f9fa",
                 font=("Meiryo UI", 9)).pack(anchor="w", pady=(6, 2))
        browser_window_mode_var = tk.StringVar(value=comp.get("browser_window_mode", "Maximize"))
        browser_window_mode_combo = ttk.Combobox(
            f_act,
            textvariable=browser_window_mode_var,
            values=("Maximize", "Left Half", "Right Half"),
            state="readonly",
            width=12,
        )
        browser_window_mode_combo.pack(anchor="w")
        tk.Label(f_act, text="Note: For copy operations specify source destination in detailed settings below.",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).pack(anchor="w", pady=(4, 0))

        path_frame = tk.LabelFrame(f_act, text="Source Destination Settings",
                                   bg="#f8f9fa", font=("Meiryo UI", 9, "bold"), padx=8, pady=6)
        path_frame.pack(fill="x", pady=(12, 0))
        tk.Label(path_frame, text="Required for copy operations. Specified location used at button execution.",
                 bg="#f8f9fa", fg="#666666", font=("Meiryo UI", 8)).grid(
                     row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

        tk.Label(path_frame, text="Source:", bg="#f8f9fa").grid(row=1, column=0, sticky="w", pady=3)
        source_entry = tk.Entry(path_frame, width=38, font=("Consolas", 9))
        source_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        source_entry.insert(0, comp.get("source_path", ""))

        tk.Label(path_frame, text="Destination Folder:", bg="#f8f9fa").grid(row=2, column=0, sticky="w", pady=3)
        destination_entry = tk.Entry(path_frame, width=38, font=("Consolas", 9))
        destination_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        destination_entry.insert(0, comp.get("destination_path", ""))
        path_frame.grid_columnconfigure(1, weight=1)

        def browse_source_path():
            if act_var.get() == "copy_folder":
                path = filedialog.askdirectory(parent=diag, title="Select Source Folder")
            else:
                path = filedialog.askopenfilename(parent=diag, title="Select Source File")
            if path:
                source_entry.delete(0, tk.END)
                source_entry.insert(0, path)

        def browse_destination_path():
            path = filedialog.askdirectory(parent=diag, title="Select Destination Folder")
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
        close_after_var = None
        browser_var = None
        browser_window_mode_var = None
        tk.Label(tab_action, text="Labels and input fields cannot have actions set.",
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
                    "Copy Settings Required",
                    "Please configure source and destination folder.",
                    parent=diag,
                )
                return
            if selected_action == "copy_file" and not os.path.isfile(source_path):
                messagebox.showerror("Settings Error", "Source file not found.", parent=diag)
                return
            if selected_action == "copy_folder" and not os.path.isdir(source_path):
                messagebox.showerror("Settings Error", "Source folder not found.", parent=diag)
                return
            if not os.path.isdir(destination_path):
                messagebox.showerror("Settings Error", "Destination folder not found.", parent=diag)
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
        messagebox.showinfo("Save Complete", "Component settings updated!")
        diag.destroy()

    tk.Button(bottom_frame, text="💾 Save Settings and Confirm", command=save_config,
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
        messagebox.showwarning("Warning", "Please select a component to delete.")

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

def generate_code_from_designer():
    missing_copy_settings = [
        comp for comp in designer_components
        if comp["type"] == "Button"
        and comp["action"] in ("copy_file", "copy_folder")
        and (not comp.get("source_path", "").strip() or not comp.get("destination_path", "").strip())
    ]
    if missing_copy_settings:
        messagebox.showwarning(
            "Copy Settings Required",
            "Copy operation buttons need source and destination folder configured in detailed settings.",
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
        (comp.get("browser_choice", "Default Browser"), comp.get("browser_window_mode", "Maximize"))
        for comp in designer_components
        if comp["type"] == "Button" and comp["action"] in browser_actions
    }
    simple_browser = browser_configs == {("Default Browser", "Maximize")}
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
        "root.title('Created Form App')",
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
        "        'Default Browser': {'msedge.exe', 'chrome.exe', 'firefox.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe'},",
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
        "        if browser_choice == 'Default Browser':",
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
        "                raise FileNotFoundError(f'{browser_choice} not found.')",
        "            subprocess.Popen([browser_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
        "            opened = True",
        "        else:",
        "            browser_aliases = {'Microsoft Edge': 'edge', 'Google Chrome': 'chrome', 'Mozilla Firefox': 'firefox', 'Brave': 'chrome'}",
        "            opened = webbrowser.get(browser_aliases[browser_choice]).open(url, new=2)",
        "        if not opened:",
        "            raise RuntimeError('Could not launch browser.')",
        "        if os.name == 'nt':",
        "            expected_names = browser_executables.get(browser_choice, browser_executables['Default Browser'])",
        "            enum_callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)",
        "            user32.IsWindowVisible.argtypes = [wintypes.HWND]",
        "            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]",
        "            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]",
        "            kernel32.OpenProcess.restype = wintypes.HANDLE",
        "            kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]",
        "            kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL",
        "            kernel32.CloseHandle.argtypes = [wintypes.HWND]",
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
        "                    if browser_window_mode == 'Maximize':",
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
        "                        if browser_window_mode == 'Left Half':",
        "                            window_x, window_width = area_left, half_width",
        "                        else:",
        "                            window_x, window_width = area_left + half_width, area_width - half_width",
        "                        user32.MoveWindow(browser_window, window_x, area_top, window_width, area_height, True)",
        "                    user32.BringWindowToTop(browser_window)",
        "                    user32.SetForegroundWindow(browser_window)",
        "                    if user32.GetForegroundWindow() == browser_window:",
        "                        return True",
        "                time.sleep(0.1)",
        "            raise RuntimeError(f'Could not bring {browser_choice} to front.')",
        "        return True",
        "    except Exception as e:",
        "        error = str(e)",
        "    root.deiconify()",
        "    root.lift()",
        "    root.focus_force()",
        "        messagebox.showerror('Browser Launch Error', error, parent=root)",
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
            "                raise OSError('Could not launch browser.')",
            "        elif not webbrowser.open(url, new=2):",
            "            raise RuntimeError('Could not launch browser.')",
            "        return True",
            "    except Exception as e:",
            "        root.deiconify()",
            "        root.lift()",
            "        root.focus_force()",
            "        messagebox.showerror('Browser Launch Error', str(e), parent=root)",
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
        browser_choice = comp.get("browser_choice", "Default Browser")
        browser_window_mode = comp.get("browser_window_mode", "Maximize")
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
                    code.append("            raise ValueError('Cannot set destination to source folder itself or inside.')")
                    code.append("        if os.path.exists(dest):")
                    code.append("            if not messagebox.askyesno('Confirm', 'Folder with same name exists. Overwrite merge contents?', parent=root): return")
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
                    code.append("        os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "open_file_default":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='Select file to open', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "create_folder":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='Select location to create', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    new_name = 'New Folder'")
                    code.append("    path = os.path.join(parent, new_name)")
                    code.append("    try:")
                    code.append("        os.makedirs(path, exist_ok=True)")
                    code.append("        messagebox.showinfo('Complete', f'Folder created\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                elif act == "create_text_file":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='Select location to create', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    path = os.path.join(parent, 'New Text.txt')")
                    code.append("    try:")
                    code.append("        with open(path, 'w', encoding='utf-8') as f:")
                    code.append("            f.write('')")
                    code.append("        messagebox.showinfo('Complete', f'Text file created\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
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
                    code.append(f"    messagebox.showinfo('Notification', {(param or 'Hello!')!r})")
                elif act == "ask_yesno":
                    code.append(f"    res = messagebox.askyesno('Confirm', {(param or 'Execute?')!r})")
                    code.append("    messagebox.showinfo('Result', f'Selection result: {res}')")
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
                    code.append("    messagebox.showinfo('Lottery', f'Drawn number: {n}')")
                elif act == "dice_roll":
                    code.append("    d = random.randint(1, 6)")
                    code.append("    messagebox.showinfo('Dice', f'Rolled: 🎲 {d}')")
                elif act == "omikuji":
                    code.append("    omi = random.choice(['Great Luck ✨', 'Middle Luck 🌟', 'Small Luck 👍', 'Luck 😊', 'Bad Luck 💦'])")
                    code.append("    messagebox.showinfo('Fortune', f'Today fortune: {omi}')")
                elif act == "gen_password":
                    code.append("    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$*'")
                    code.append("    pwd = ''.join(random.choices(chars, k=12))")
                    code.append("    messagebox.showinfo('Password Generation', f'Generated password:\\n{pwd}')")
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
        if not messagebox.askyesno("Overwrite Confirm", "Replace editor content with generated code?"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", "\n".join(code) + "\n")
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    messagebox.showinfo("Generation Complete", "Editor content replaced with form code!\nFile operations show selection dialog at runtime.")

# Toolbar buttons
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

add_designer_toolbar_button("＋ Button", lambda: add_component("Button"), "#1769aa", active_bg="#12558a")
add_designer_toolbar_button("＋ Label", lambda: add_component("Label"), "#0f766e", active_bg="#0b5c56")
add_designer_toolbar_button("＋ Entry", lambda: add_component("Entry"), "#3a7d44", active_bg="#2d6335")
add_designer_toolbar_button("⚙ Window Position", open_window_position_dialog, "#6610f2")
add_designer_toolbar_button("⚙ Detailed Settings", lambda: open_properties_dialog(selected_component) if selected_component else messagebox.showwarning("Warning", "Please select a component"), "#ffc107", fg="#000")
add_designer_toolbar_button("🗑 Delete", delete_component, "#dc3545")
add_designer_toolbar_button("🧹 Clear All", clear_designer, "#6c757d")
add_designer_toolbar_button("📝 Generate Code and Transfer", generate_code_from_designer, "#0d6efd")


# ---------- Tab 5: Drone Robot Control ----------
robot_control_mode = tk.StringVar(value="drone")
robot_blocks = []
robot_code_output = tk.StringVar()

def robot_create_block_ui():
    block_frame = tk.Frame(robot_canvas, bg=THEMES[current_theme]['bg'], relief="raised", bd=2)
    return block_frame

def robot_add_block(block_type, params=None):
    if params is None:
        params = {}
    
    if len(robot_blocks) >= 100:
        messagebox.showwarning("Limit", "Maximum 100 blocks allowed")
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
    
    # Default values (first display)
    if canvas_width < 100:
        canvas_width = 700
    if canvas_height < 100:
        canvas_height = 300
    
    block_width = 80      # Block width
    block_height = 28      # Block height
    block_gap = 2          # Gap between blocks
    padding = 10           # Padding
    
    # Calculate blocks per row
    items_per_row = max(1, int((canvas_width - padding * 2) / (block_width + block_gap)))
    max_rows = 10          # Maximum rows
    
    for i, block in enumerate(robot_blocks):
        # Calculate row and column (horizontal layout)
        row = i // items_per_row
        column = i % items_per_row
        
        # Don't exceed max rows
        if row >= max_rows:
            row = max_rows - 1
            column = i  # Overflow goes to same row
        
        x_pos = padding + (column * (block_width + block_gap))
        y_pos = padding + (row * (block_height + block_gap))
        
        block_frame = robot_create_block_ui()
        block_frame.place(x=x_pos, y=y_pos, width=block_width, height=block_height)
        
        block_text = robot_get_block_text(block)
        tk.Label(block_frame, text=f"{i+1}. {block_text}", 
                bg=THEMES[current_theme]['button_bg'], fg=THEMES[current_theme]['text_fg'],
                font=("Meiryo UI", 7), wraplength=70).pack(fill="both", expand=True, padx=2, pady=1)
    
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
        return f"Up ({params.get('height', 5)} meters)"
    elif block_type == "down":
        return f"Down ({params.get('height', 5)} meters)"
    elif block_type == "rotate_left":
        return "Rotate Left (90 degrees)"
    elif block_type == "rotate_right":
        return "Rotate Right (90 degrees)"
    elif block_type == "rotate_180":
        return "Turn 180 degrees"
    elif block_type == "wait":
        return f"Wait ({params.get('seconds', 1)} seconds)"
    elif block_type == "return_home":
        return "⚠️ Return Home on Signal Loss"
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
            # DJI Tello code
            code_lines.extend([
                "# DJI Tello Drone Control Program",
                "# Installation required: pip install djitellopy",
                "",
                "from djitellopy import Tello",
                "import time",
                "",
                "# Connect to drone",
                "drone = Tello()",
                "drone.connect()",
                "",
                "# Check battery",
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
                    dist = params.get('distance', 5) * 100  # Convert to cm
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
                elif block_type == "wait":
                    code_lines.append(f"time.sleep({params.get('seconds', 1)})")
                elif block_type == "return_home":
                    code_lines.append("# On signal loss Tello auto-lands")
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
                "            messagebox.showwarning('Warning', 'Already launched')",
                "            return",
                "        self.start_x = self.x",
                "        self.start_y = self.y",
                "        self.start_z = self.z",
                "        self.z += height",
                "        self.launched = True",
                "        print(f'{height} meters up and launched')",
                "",
                "    def land(self):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.z = 0",
                "        self.launched = False",
                "        print('Landed')",
                "",
                "    def forward(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.x += distance",
                "        print(f'{distance} meters forward')",
                "",
                "    def backward(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.x -= distance",
                "        print(f'{distance} meters backward')",
                "",
                "    def left(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.y -= distance",
                "        print(f'{distance} meters left')",
                "",
                "    def right(self, distance):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.y += distance",
                "        print(f'{distance} meters right')",
                "",
                "    def up(self, height):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.z += height",
                "        print(f'{height} meters up')",
                "",
                "    def down(self, height):",
                "        if not self.launched:",
                "            messagebox.showwarning('Warning', 'Not launched')",
                "            return",
                "        self.z -= height",
                "        if self.z < 0:",
                "            self.z = 0",
                    "            self.launched = False",
                "            print('Landed')",
                "        else:",
                "            print(f'{height} meters down')",
                "",
                "    def wait(self, seconds):",
                "        import time",
                "        time.sleep(seconds)",
                "",
                "    def return_home(self):",
                "        if not self.launched:",
                "            print('Not launched, no return needed')",
                "            return",
                "        print('⚠️ Signal lost! Auto return started')",
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
                "# Note: This is a simulation.",
                "# To control actual drone, select hardware."
            ])
    
    else:  # robot mode
        if hardware == "rpi":
            # Raspberry Pi code
            code_lines.extend([
                "# Raspberry Pi Robot Control Program",
                "# Required library: pip install gpiozero",
                "",
                "from gpiozero import Robot",
                "from time import sleep",
                "",
                "# Motor pin settings (change to match your pins)",
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
                    code_lines.append("# Return: Turn and go forward")
                    code_lines.append("robot.left()")
                    code_lines.append("sleep(1.0)")
                    code_lines.append("robot.stop()")
            
            code_lines.extend([
                "",
                "# Preparation before use:",
                "# 1. Install gpiozero on Raspberry Pi: pip install gpiozero",
                "# 2. Connect motor driver (L298N etc)",
                "# 3. Wire GPIO pins correctly",
                "# 4. Check and change pin numbers"
            ])
        else:
            # Simulation
            code_lines.extend([
                "import tkinter as tk",
                "from tkinter import messagebox",
                "",
                "# Self-Propelled Robot Control Program (Simulation)",
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
                "        print(f'{distance} meters forward (heading: {self.directions[self.direction]}')",
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
                "        print(f'{distance} meters backward (heading: {self.directions[self.direction]}')",
                "",
                "    def rotate_left(self):",
                "        self.direction = (self.direction + 3) % 4",
                "        print(f'Turned left 90 degrees (current heading: {self.directions[self.direction]}')",
                "",
                "    def rotate_right(self):",
                "        self.direction = (self.direction + 1) % 4",
                "        print(f'Turned right 90 degrees (current heading: {self.directions[self.direction]}')",
                "",
                "    def rotate_180(self):",
                "        self.direction = (self.direction + 2) % 4",
                "        print(f'Turned 180 degrees (current heading: {self.directions[self.direction]}')",
                "",
                "    def face_direction(self, direction):",
                "        direction_map = {'North': 0, 'East': 1, 'South': 2, 'West': 3}",
                "        if direction in direction_map:",
                "            self.direction = direction_map[direction]",
                "            print(f'Facing {direction}')",
                "",
                "    def wait(self, seconds):",
                "        import time",
                "        time.sleep(seconds)",
                "",
                "    def return_home(self):",
                "        print('⚠️ Signal lost! Auto return started')",
                "        self.x = self.start_x",
                "        self.y = self.start_y",
                "        self.direction = self.start_direction",
                "        print('✅ Returned to original position')",
                "",
                "    def show_status(self):",
                "        print(f'Current position: X={self.x}, Y={self.y}, Heading={self.directions[self.direction]}')",
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
                "# Note: This is a simulation.",
                "# To control actual robot, select hardware."
            ])
    
    generated_code = "\n".join(code_lines)
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
    
    # Message based on hardware
    if hardware == "tello":
        messagebox.showinfo("Generation Complete", "DJI Tello code generated!\n\nPreparation:\n1. pip install djitellopy\n2. Turn on Tello\n3. Connect WiFi to Tello\n4. Run program")
    elif hardware == "rpi":
        messagebox.showinfo("Generation Complete", "Raspberry Pi code generated!\n\nPreparation:\n1. pip install gpiozero\n2. Connect motor driver\n3. Wire GPIO pins\n4. Check pin numbers")
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
    
    tk.Label(dialog, text="Height in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    
    tk.Label(dialog, text="Distance in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    
    tk.Label(dialog, text="Distance in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    
    tk.Label(dialog, text="Distance in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    
    tk.Label(dialog, text="Distance in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    dialog.title("Up Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Height in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    dialog.title("Down Settings")
    dialog.geometry("350x180")
    dialog.transient(root)
    dialog.grab_set()
    
    tk.Label(dialog, text="Height in meters:", font=("Meiryo UI", 12)).pack(pady=15)
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
    robot_add_block("rotate_left")

def robot_add_rotate_right():
    robot_add_block("rotate_right")

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

# Drone Robot Control Tab UI
robot_main_frame = tk.Frame(tab_robot, bg=THEMES[current_theme]['bg'])
robot_main_frame.pack(expand=True, fill="both", padx=15, pady=15)

# Mode selection
robot_mode_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_mode_frame.pack(fill="x", pady=(0, 15))
tk.Label(robot_mode_frame, text="Control Mode:", font=("Meiryo UI", 13, "bold"), 
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(side="left", padx=(0, 15))
mode_drone_btn = tk.Radiobutton(robot_mode_frame, text="🚁 Drone", variable=robot_control_mode, 
                                value="drone", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                font=("Meiryo UI", 12), selectcolor=THEMES[current_theme]['button_bg'])
mode_drone_btn.pack(side="left", padx=8)
mode_robot_btn = tk.Radiobutton(robot_mode_frame, text="🤖 Self-Propelled Robot", variable=robot_control_mode, 
                                value="robot", bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                font=("Meiryo UI", 12), selectcolor=THEMES[current_theme]['button_bg'])
mode_robot_btn.pack(side="left", padx=8)

# Hardware selection
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

# Main content area (left-right split)
robot_content_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_content_frame.pack(expand=True, fill="both", pady=(0, 15))

# Left: Button area
robot_buttons_frame = tk.LabelFrame(robot_content_frame, text=" Add Blocks ", 
                                   bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                   font=("Meiryo UI", 12, "bold"), padx=12, pady=12)
robot_buttons_frame.pack(side="left", fill="y", padx=(0, 10))

# Drone buttons (vertical)
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
tk.Button(drone_btns, text="🔼 Up", command=robot_add_up, bg="#17a2b8", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🔽 Down", command=robot_add_down, bg="#17a2b8", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="⏱️ Wait", command=robot_add_wait, bg="#fd7e14", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(drone_btns, text="🏠 Return Home on Signal Loss", command=robot_add_return_home, bg="#ffc107", fg="#000", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)

# Robot buttons (vertical, initially hidden)
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
tk.Button(robot_btns, text="🔄 Turn 180", command=robot_add_rotate_180, bg="#6610f2", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🧭 Face Direction", command=robot_add_face_direction, bg="#20c997", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="⏱️ Wait", command=robot_add_wait, bg="#fd7e14", fg="white", 
          font=("Meiryo UI", 10, "bold"), width=16, height=1).pack(fill="x", pady=3)
tk.Button(robot_btns, text="🏠 Return Home on Signal Loss", command=robot_add_return_home, bg="#ffc107", fg="#000", 
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

# Right: Program display area
robot_program_frame = tk.LabelFrame(robot_content_frame, text=" Program ", 
                                   bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                                   font=("Meiryo UI", 12, "bold"), padx=12, pady=12)
robot_program_frame.pack(side="left", expand=True, fill="both")

robot_canvas_frame = tk.Frame(robot_program_frame, bg=THEMES[current_theme]['bg'])
robot_canvas_frame.pack(expand=True, fill="both")
robot_canvas = tk.Canvas(robot_canvas_frame, bg=THEMES[current_theme]['text_bg'], 
                        highlightthickness=0)
robot_canvas.pack(side="left", expand=True, fill="both")

# Reconfigure blocks on canvas resize
robot_canvas.bind("<Configure>", lambda e: robot_refresh_blocks_display())

# Operation buttons
robot_control_frame = tk.Frame(robot_main_frame, bg=THEMES[current_theme]['bg'])
robot_control_frame.pack(fill="x")
tk.Button(robot_control_frame, text="🗑️ Delete Last Block", command=robot_delete_last_block, 
          bg="#dc3545", fg="white", font=("Meiryo UI", 11, "bold"), width=22, height=2).pack(side="left", padx=6, pady=6)
tk.Button(robot_control_frame, text="🧹 Clear All Blocks", command=robot_clear_blocks, 
          bg="#6c757d", fg="white", font=("Meiryo UI", 11, "bold"), width=22, height=2).pack(side="left", padx=6, pady=6)
tk.Button(robot_control_frame, text="📝 Generate Code and Transfer", command=robot_generate_code, 
          bg="#0d6efd", fg="white", font=("Meiryo UI", 12, "bold"), width=28, height=2).pack(side="right", padx=6, pady=6)


# ---------- Tab 4: Tools ----------
tools_frame = tk.Frame(tab_tools, bg=THEMES[current_theme]['bg'], padx=20, pady=20)
tools_frame.pack(expand=True, fill="both")
tk.Label(tools_frame, text="🛠 Development Environment and Tools Management",
         font=("Meiryo UI", 12, "bold"), bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=(0, 10))
tk.Label(tools_frame, text=f"Python Executable Path: {sys.executable}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
virtualenv_path_display = tk.StringVar(value=f"Module Virtual Environment: {get_virtualenv_path()}")
tk.Label(tools_frame, textvariable=virtualenv_path_display, font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"Settings Save Folder: {SETTINGS_FOLDER}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"OS: {platform.system()} {platform.release()}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)

mod_frame = tk.LabelFrame(tools_frame, text=" 📦 External Module Installation ",
                          bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                          font=("Meiryo UI", 10, "bold"), padx=15, pady=12)
mod_frame.pack(anchor="w", fill="x", pady=15)
tk.Label(mod_frame, text="Module Name (e.g., requests):", bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg'], font=("Meiryo UI", 9)).pack(side="left", padx=(0, 10))
mod_entry = tk.Entry(mod_frame, width=20, font=("Consolas", 10))
mod_entry.pack(side="left", padx=5)

def install_custom_module():
    mname = mod_entry.get().strip()
    if not mname:
        messagebox.showwarning("Warning", "Please enter module name to install.")
        return
    try:
        python_executable = get_virtualenv_python()
        res = subprocess.run([python_executable, "-m", "pip", "install", mname],
                             capture_output=True, text=True, timeout=90)
        if res.returncode == 0:
            messagebox.showinfo("Install Success", f"Module '{mname}' installation complete!")
        else:
            messagebox.showerror("Error", f"Installation failed:\n{res.stderr[:500]}")
    except Exception as e:
        messagebox.showerror("Error", f"Error occurred:\n{e}")

tk.Button(mod_frame, text="pip install Execute", command=install_custom_module,
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
    tk.Label(content, text="Test Run Timeout", font=("Meiryo UI", 10, "bold")).grid(
        row=0, column=0, sticky="w", padx=(0, 12), pady=6
    )
    ttk.Spinbox(content, from_=1, to=3600, increment=1, textvariable=timeout_value,
                width=8).grid(row=0, column=1, sticky="w", pady=6)
    tk.Label(content, text="seconds (1-3600)").grid(row=0, column=2, sticky="w", padx=(6, 0))

    tk.Label(content, text="Virtual Environment Save Location", font=("Meiryo UI", 10, "bold")).grid(
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
            title="Select Virtual Environment Save Location",
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
            messagebox.showerror("Input Error", "Please enter integer for timeout.", parent=dialog)
            return
        if not 1 <= timeout <= 3600:
            messagebox.showerror("Input Error", "Please enter between 1 and 3600 seconds.", parent=dialog)
            return
        selected_path = virtualenv_path_value.get().strip()
        if not selected_path:
            messagebox.showerror("Input Error", "Please specify virtual environment save location.", parent=dialog)
            return
        test_timeout_seconds = timeout
        VIRTUALENV_PATH = os.path.abspath(os.path.expanduser(selected_path))
        save_settings()
        virtualenv_path_display.set(f"Module Virtual Environment: {get_virtualenv_path()}")
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
file_menu.add_command(label="Save (Ctrl+S)", command=quick_save)
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
