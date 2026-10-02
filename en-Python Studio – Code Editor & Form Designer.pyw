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
import importlib.util
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

current_theme = 'dark'
current_font_size = 11
test_timeout_seconds = 5

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

def get_settings_path(filename):
    if not os.path.exists(SETTINGS_FOLDER):
        try:
            os.makedirs(SETTINGS_FOLDER, exist_ok=True)
        except Exception:
            pass
    return os.path.join(SETTINGS_FOLDER, filename)

def load_settings():
    global current_theme, current_font_size, test_timeout_seconds
    path = get_settings_path(THEME_SETTINGS_FILE)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                current_theme = data.get('theme', 'dark')
                current_font_size = data.get('font_size', 11)
                test_timeout_seconds = data.get('test_timeout_seconds', 5)
        except Exception:
            pass

def save_settings():
    path = get_settings_path(THEME_SETTINGS_FILE)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({
                'theme': current_theme,
                'font_size': current_font_size,
                'test_timeout_seconds': test_timeout_seconds
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
        res = messagebox.askyesnocancel("Confirm", "You have unsaved changes. Save them?")
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
            messagebox.showinfo("Saved", f"File saved:\n{os.path.basename(quick_save.current_file_path)}")
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
            ("Python File (*.py)", "*.py"),
            ("Python without console (*.pyw)", "*.pyw"),
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
            messagebox.showinfo("Saved", f"File saved as:\n{os.path.basename(path)}")
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
            messagebox.showerror("Error", f"Could not open file: {e}")

def new_file():
    global text_modified, last_saved_content
    if text_modified and not messagebox.askyesno("Confirm", "Discard the current contents and create a new file?"):
        return
    text.delete("1.0", tk.END)
    apply_syntax_highlighting()
    last_saved_content = ""
    text_modified = False
    quick_save.current_file_path = None
    update_line_numbers()
    update_status_bar()

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
    status_label.config(text=f" 📂 {fname}{mod}   |   Line: {line}  Column: {col}  Characters: {char_count} ")
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
    search_window.title("Find and Replace")
    search_window.geometry("420x180")
    search_window.resizable(False, False)
    th = THEMES[current_theme]
    search_window.configure(bg=th['bg'])

    tk.Label(search_window, text="Find:", bg=th['bg'], fg=th['text_fg']).place(x=20, y=20)
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
            messagebox.showinfo("Find", "No matches found.")

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
            messagebox.showinfo("ReplaceDone", "Replaced all occurrences.")
        else:
            messagebox.showinfo("Replace", "No matching text found.")

    tk.Button(search_window, text="Find Next", command=do_find, width=12).place(x=90, y=110)
    tk.Button(search_window, text="Replace", command=do_replace, width=10).place(x=200, y=110)
    tk.Button(search_window, text="Replace All", command=do_replace_all, width=12).place(x=290, y=110)
    return 'break'

def format_code():
    code = text.get("1.0", tk.END).strip()
    if not code:
        return
    try:
        import autopep8
    except ImportError:
        if messagebox.askyesno("Confirm", "autopep8 is not installed.\nWould you like to install it?"):
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "autopep8"], check=True, timeout=60)
            except Exception as e:
                messagebox.showerror("Error", f"Installation failed:\n{e}")
                return
        else:
            return
    try:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tf:
            tf.write(code)
            tpath = tf.name
        subprocess.run([sys.executable, "-m", "autopep8", "--in-place", "--aggressive", tpath],
                       capture_output=True, text=True, timeout=15)
        with open(tpath, "r", encoding="utf-8") as f:
            formatted = f.read()
        text.delete("1.0", tk.END)
        text.insert("1.0", formatted)
        apply_syntax_highlighting()
        update_line_numbers()
        messagebox.showinfo("Formatting Complete", "Code formatted to follow PEP 8.")
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
        if messagebox.askyesno("Confirm", "There are unsaved changes. Save before running the test?"):
            if not quick_save():
                return
    code = text.get("1.0", tk.END).strip()
    if not code:
        return
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(code)
        tpath = tf.name

    def run():
        try:
            res = subprocess.run([sys.executable, tpath], capture_output=True, text=True, timeout=test_timeout_seconds)
            error_output = res.stderr.strip() or res.stdout.strip() or f"Exit code: {res.returncode}"
            out = res.stdout if res.returncode == 0 else f"[Error]\n{error_output}"
            if res.returncode == 0 and not out.strip():
                out = "The test completed successfully.\nThere was no standard output."
            if res.returncode == 0:
                root.after(0, lambda: messagebox.showinfo("Test Results", out[:1500] + ("\n...(more omitted)" if len(out) > 1500 else "")))
            else:
                root.after(0, lambda: messagebox.showerror("Test Error", out))
        except subprocess.TimeoutExpired:
            root.after(0, lambda: messagebox.showerror("Timeout", f"Execution exceeded the configured time limit（{test_timeout_seconds} seconds)."))
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
        messagebox.showwarning("Warning", "There is no code in the editor.")
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
    target_modules = [m for m in modules if m not in stdlib_set and importlib.util.find_spec(m) is None]
    if not target_modules:
        messagebox.showinfo("Confirm", "No missing external modules requiring installation were found.")
        return
    win = tk.Toplevel(root)
    win.title("Automatic Module Installation")
    win.geometry("450x320")
    win.resizable(False, False)
    win.configure(bg="#f8f9fa")
    tk.Label(win, text="📦 Missing External Modules Found", font=("Segoe UI", 11, "bold"),
             bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    tk.Label(win, text="Install the following modules with pip?", font=("Segoe UI", 9), bg="#f8f9fa").pack(anchor="w", padx=15, pady=(10, 5))
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
            messagebox.showwarning("Warning", "Select at least one module.")
            return
        success_list, fail_list = [], []
        for idx in selected_indices:
            mname = lb.get(idx)
            try:
                res = subprocess.run([sys.executable, "-m", "pip", "install", mname], capture_output=True, text=True, timeout=90)
                if res.returncode == 0:
                    success_list.append(mname)
                else:
                    fail_list.append(mname)
            except Exception:
                fail_list.append(mname)
        msg = f"Installation complete: {', '.join(success_list) if success_list else 'None'}"
        if fail_list:
            msg += f"\nFailed: {', '.join(fail_list)}"
        messagebox.showinfo("Installation Results", msg)
        win.destroy()
    tk.Button(win, text="🚀 Install Selected Modules", command=do_install,
              bg="#198754", fg="white", font=("Segoe UI", 10, "bold"), padx=10, pady=8, cursor="hand2").pack(side="bottom", fill="x", padx=15, pady=15)


# ==================== Main UI ====================
root = tk.Tk()
root.title("Python Studio - Code Editor and Form Designer")

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
        display_text = error_text[:1500] + "\n...(truncated。full text copied to the clipboard)"
    else:
        display_text = error_text + "\n\nError details were copied to the clipboard."
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
style.configure('TNotebook.Tab', padding=[14, 8], font=('Segoe UI', 10, 'bold'))

top_notebook = ttk.Notebook(root)
top_notebook.pack(expand=True, fill="both", padx=6, pady=6)

tab_editor = ttk.Frame(top_notebook)
top_notebook.add(tab_editor, text="📝 Code Editor")

tab_designer = ttk.Frame(top_notebook)
top_notebook.add(tab_designer, text="🎨 Form Designer")

tab_tools = ttk.Frame(top_notebook)
top_notebook.add(tab_tools, text="🛠 Tools and Environment")


# ---------- Tab 1: Code Editor ----------
top_btn_frame = tk.Frame(tab_editor, bg=THEMES[current_theme]['bg'])
top_btn_frame.pack(fill="x", pady=6, padx=6)

def add_btn(parent, text, cmd, bg="#333333", fg="white"):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, relief="flat",
                  padx=10, pady=5, font=("Segoe UI", 9, "bold"), cursor="hand2")
    b.pack(side="left", padx=3)
    return b

add_btn(top_btn_frame, "📄 New", new_file, "#495057")
add_btn(top_btn_frame, "📂 Open", open_file, "#495057")
add_btn(top_btn_frame, "💾 Save", quick_save, "#0d6efd")
add_btn(top_btn_frame, "✨ Format Code", format_code, "#6c757d")
add_btn(top_btn_frame, "▶ Run Test", test_python_code, "#198754")
add_btn(top_btn_frame, "📦 Find Modules in Code", parse_and_install_code_modules, "#6610f2")
add_btn(top_btn_frame, "🔍 Find", open_search_dialog, "#6c757d")
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
status_label = tk.Label(status_bar, text=" 📂 Untitled   |   Line: 1  Column: 0  Characters: 0 ",
                        bg=THEMES[current_theme]['sidebar_bg'], fg=THEMES[current_theme]['text_fg'],
                        anchor="w", font=("Segoe UI", 9))
status_label.pack(side="left", padx=6)

text.bind("<KeyRelease>", lambda e: (update_line_numbers(), update_status_bar(), update_highlight_on_idle()))
text.bind("<ButtonRelease-1>", update_status_bar)
text.bind("<Control-MouseWheel>", lambda e: (change_font_size(1 if e.delta > 0 else -1), "break"))
text.bind("<Control-a>", select_all)
root.bind("<Control-s>", lambda e: quick_save())
root.bind("<Control-f>", open_search_dialog)
root.bind("<Control-z>", lambda e: undo_action())
root.bind("<Control-y>", lambda e: redo_action())


# ---------- Tab 2: Visual Form Designer ----------
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
                              font=("Segoe UI", 10, "bold"), cursor="sizing")
form_resize_handle.place(relx=1.0, rely=1.0, x=-16, y=-16, width=16, height=16)

size_lbl = tk.Label(canvas_container,
                    text=f"📱 Form Size: {form_window_width} x {form_window_height}  |  🖥 Window Position: X={form_pos_x}, Y={form_pos_y}",
                    bg="#1e1e1e", fg="#cccccc", font=("Segoe UI", 9))
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
         font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
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
    pos_str = "Centered on screen" if form_pos_mode == "center" else f"X={form_pos_x}, Y={form_pos_y}"
    size_lbl.config(text=f"📱 Form Size: {form_window_width} x {form_window_height}  |  🖥 Window Position: {pos_str}")

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
        title="Choose Form Background Color" if color_type == "background" else "Choose Form Text Color",
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
         font=("Segoe UI", 9)).pack(side="left", padx=(0, 3))
form_bg_swatch = tk.Button(form_color_controls, text="Choose", width=5, bg=form_bg_color,
                           command=lambda: choose_form_color("background"), cursor="hand2")
form_bg_swatch.pack(side="left", padx=(0, 8))
tk.Label(form_color_controls, text="Form Text", bg="#2d2d2d", fg="#eeeeee",
         font=("Segoe UI", 9)).pack(side="left", padx=(0, 3))
form_fg_swatch = tk.Button(form_color_controls, text="Choose", width=5, bg=form_fg_color,
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
    w_diag.title("Window Position Settings")
    w_diag.geometry("450x340")
    w_diag.resizable(False, False)
    w_diag.configure(bg="#f8f9fa")
    w_diag.transient(root)
    w_diag.grab_set()

    tk.Label(w_diag, text="🖥 Application Position on the Desktop at Startup",
             font=("Segoe UI", 11, "bold"), bg="#0d6efd", fg="white",
             padx=10, pady=10).pack(side="top", fill="x")

    f_body = tk.Frame(w_diag, bg="#f8f9fa", padx=20, pady=15)
    f_body.pack(fill="both", expand=True)

    mode_var = tk.StringVar(value=form_pos_mode)
    tk.Radiobutton(f_body, text="Center on the screen automatically", variable=mode_var, value="center",
                   bg="#f8f9fa", font=("Segoe UI", 10)).pack(anchor="w", pady=5)
    tk.Radiobutton(f_body, text="Use the specified desktop coordinates (X, Y)", variable=mode_var, value="manual",
                   bg="#f8f9fa", font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 5))

    coord_frame_diag = tk.Frame(f_body, bg="#f8f9fa", padx=20)
    coord_frame_diag.pack(anchor="w", pady=5)

    tk.Label(coord_frame_diag, text="X coordinate:", bg="#f8f9fa", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
    x_entry = tk.Entry(coord_frame_diag, width=12, font=("Consolas", 10))
    x_entry.grid(row=0, column=1, padx=10, pady=5)
    x_entry.insert(0, str(form_pos_x))

    tk.Label(coord_frame_diag, text="Y coordinate:", bg="#f8f9fa", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
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

    # Bind both the dialog and entry fields so Home works without clicking first
    w_diag.bind("<Home>", capture_mouse_pos_here)
    x_entry.bind("<Home>", capture_mouse_pos_here)
    y_entry.bind("<Home>", capture_mouse_pos_here)

    tk.Label(f_body, text="💡 Press [Home] to enter the current mouse coordinates",
             bg="#f8f9fa", fg="#666666", font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))

    def save_pos():
        global form_pos_x, form_pos_y, form_pos_mode
        form_pos_mode = mode_var.get()
        if form_pos_mode == "manual":
            try:
                form_pos_x = int(x_entry.get().strip())
                form_pos_y = int(y_entry.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Enter valid integers for the coordinates.")
                return
        update_size_label()
        messagebox.showinfo("Saved", "Window position settings saved.")
        w_diag.destroy()

    tk.Button(w_diag, text="💾 Save Settings", command=save_pos, bg="#198754", fg="white",
              font=("Segoe UI", 10, "bold"), padx=10, pady=10, cursor="hand2").pack(side="bottom", fill="x", padx=20, pady=15)

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

    # Focus the dialog immediately when it opens
    w_diag.after(50, lambda: w_diag.focus_force())


def add_component(ctype):
    global selected_component
    wrapper = tk.Frame(form_preview, bg="#cccccc", bd=1, relief="raised")
    wrapper.place(x=40, y=40, width=150, height=36)

    default_bg = "#e8e8e8" if ctype == "Button" else form_bg_color
    default_fg = form_fg_color

    if ctype == "Button":
        inner = tk.Button(wrapper, text="Button", relief="flat", font=("Segoe UI", 10), bg=default_bg, fg=default_fg)
    elif ctype == "Label":
        inner = tk.Label(wrapper, text="Text Label", bg=default_bg, fg=default_fg, font=("Segoe UI", 10))
    else:
        inner = tk.Entry(wrapper, font=("Segoe UI", 10), bg=default_bg, fg=default_fg)
    inner.pack(fill="both", expand=True)

    comp_resize_handle = tk.Label(wrapper, text="◢", bg="#0d6efd", fg="white", font=("Segoe UI", 8), cursor="sizing")
    comp_resize_handle.place(relx=1.0, rely=1.0, x=-12, y=-12, width=12, height=12)

    comp_info = {
        "type": ctype, "wrapper": wrapper, "inner": inner,
        "text": "Button" if ctype == "Button" else ("Text Label" if ctype == "Label" else ""),
        "bg_color": default_bg, "fg_color": default_fg, "font_size": 10,
        "custom_background": False, "custom_foreground": False,
        "action": "none", "param": "", "close_after_action": True,
        "browser_choice": "System Default Browser", "browser_window_mode": "Maximized"
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
        messagebox.showwarning("Warning", "Select a component.")
        return
    diag = tk.Toplevel(root)
    diag.title("Component Properties")
    diag.geometry("640x620")
    diag.resizable(False, False)
    diag.configure(bg="#f8f9fa")
    diag.transient(root)

    tk.Label(diag, text="🎨 Component Appearance and Behavior Settings",
             font=("Segoe UI", 11, "bold"), bg="#0d6efd", fg="white", padx=10, pady=10).pack(side="top", fill="x")
    bottom_frame = tk.Frame(diag, bg="#e9ecef", padx=15, pady=12)
    bottom_frame.pack(side="bottom", fill="x")

    diag_notebook = ttk.Notebook(diag)
    diag_notebook.pack(fill="both", expand=True, padx=10, pady=10)

    tab_design = ttk.Frame(diag_notebook)
    tab_action = ttk.Frame(diag_notebook)
    diag_notebook.add(tab_design, text="① Text and Design")
    diag_notebook.add(tab_action, text="② Actions")

    f_des = tk.Frame(tab_design, bg="#f8f9fa", padx=20, pady=20)
    f_des.pack(fill="both", expand=True)

    tk.Label(f_des, text="Display Text:", bg="#f8f9fa", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    txt_entry = tk.Entry(f_des, width=48, font=("Segoe UI", 10))
    txt_entry.pack(anchor="w", pady=(2, 15))
    txt_entry.insert(0, comp["text"])

    style_frame = tk.LabelFrame(f_des, text=" Design (Color and Font Size) ", bg="#f8f9fa",
                                font=("Segoe UI", 9, "bold"), padx=15, pady=12)
    style_frame.pack(fill="x", pady=5)

    tk.Label(style_frame, text="Background color:", bg="#f8f9fa", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=5)
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
                          command=lambda: choose_component_color(bg_entry, bg_swatch, "Choose Component Background Color"),
                          cursor="hand2")
    bg_swatch.grid(row=0, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="Text color:", bg="#f8f9fa", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
    fg_entry = tk.Entry(style_frame, width=18, font=("Consolas", 10))
    fg_entry.grid(row=1, column=1, sticky="w", padx=10, pady=5)
    fg_entry.insert(0, comp["fg_color"])
    fg_swatch = tk.Button(style_frame, text="  ", width=3, bg=comp["fg_color"],
                          command=lambda: choose_component_color(fg_entry, fg_swatch, "Choose Component Text Color"),
                          cursor="hand2")
    fg_swatch.grid(row=1, column=2, padx=4, pady=5)

    tk.Label(style_frame, text="Font size:", bg="#f8f9fa", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=5)
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

        tk.Label(f_act, text="Choose an action:", bg="#f8f9fa",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))

        action_categories = [
            ("--- Basic ---", [
                ("Do nothing", "none"),
                ("🚪 Exit the application", "close_app"),
            ]),
            ("📁 File and Folder Operations", [
                ("📄 Copy a file", "copy_file"),
                ("📂 Copy a folder", "copy_folder"),
                ("✂ Move a file", "move_file"),
                ("🗑 Delete a file (with confirmation)", "delete_file"),
                ("📂 Open a folder", "open_folder"),
                ("📄 Open a file with its associated app", "open_file_default"),
                ("📁 Create a new folder", "create_folder"),
                ("📝 Create a text file", "create_text_file"),
            ]),
            ("🖥 Common Folders", [
                ("🖥 Open Desktop", "open_desktop"),
                ("📄 Open Documents", "open_documents"),
                ("⬇ Open Downloads", "open_downloads"),
                ("📂 Open File Explorer", "open_explorer"),
            ]),
            ("🌐 Web and Search", [
                ("Open a URL", "open_url"),
                ("Open X", "open_x"),
                ("Open ABEMA TV", "open_abema"),
                ("Google Search", "google_search"),
                ("YouTube Search", "youtube_search"),
                ("Google Translate", "google_translate"),
                ("Google Maps", "google_maps"),
            ]),
            ("💬 Messages and Utilities", [
                ("Show a message", "show_msg"),
                ("Confirmation dialog", "ask_yesno"),
                ("Copy text to clipboard", "copy_clipboard"),
                ("Copy current time to clipboard", "copy_time"),
                ("Show current time", "show_time"),
            ]),
            ("🖥 System and Tools", [
                ("Open Notepad", "open_notepad"),
                ("Open Calculator", "open_calc"),
                ("Open Command Prompt / Terminal", "open_terminal"),
                ("Play a beep", "beep"),
            ]),
            ("🎲 Fun", [
                ("Random Number (1-100)", "random_num"),
                ("Roll a Die", "dice_roll"),
                ("Fortune", "omikuji"),
                ("Generate Password", "gen_password"),
            ]),
        ]

        act_var = tk.StringVar(value=comp["action"])
        for cat_name, acts in action_categories:
            tk.Label(f_act, text=cat_name, bg="#f8f9fa", fg="#0d6efd",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 2))
            for text_lbl, val in acts:
                tk.Radiobutton(f_act, text=text_lbl, variable=act_var, value=val,
                               bg="#f8f9fa", font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=12, pady=1)

        tk.Label(f_act, text="Action parameter (URL, message, etc.):", bg="#f8f9fa",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(14, 2))
        param_entry = tk.Entry(f_act, width=50, font=("Segoe UI", 10))
        param_entry.pack(anchor="w")
        param_entry.insert(0, comp["param"])
        close_after_var = tk.BooleanVar(value=comp.get("close_after_action", True))
        tk.Checkbutton(
            f_act,
            text="Exit this application after the action",
            variable=close_after_var,
            bg="#f8f9fa",
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(anchor="w", pady=(8, 2))
        tk.Label(f_act, text="Browser to use for browser actions:", bg="#f8f9fa",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 2))
        browser_var = tk.StringVar(value=comp.get("browser_choice", "System Default Browser"))
        browser_combo = ttk.Combobox(
            f_act,
            textvariable=browser_var,
            values=("System Default Browser", "Microsoft Edge", "Google Chrome", "Mozilla Firefox", "Brave"),
            state="readonly",
            width=24,
        )
        browser_combo.pack(anchor="w")
        tk.Label(f_act, text="Browser window mode:", bg="#f8f9fa",
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 2))
        browser_window_mode_var = tk.StringVar(value=comp.get("browser_window_mode", "Maximized"))
        browser_window_mode_combo = ttk.Combobox(
            f_act,
            textvariable=browser_window_mode_var,
            values=("Maximized", "Left Half", "Right Half"),
            state="readonly",
            width=12,
        )
        browser_window_mode_combo.pack(anchor="w")
        tk.Label(f_act, text="For copy actions, specify the source and destination below.",
                 bg="#f8f9fa", fg="#666666", font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        path_frame = tk.LabelFrame(f_act, text="Copy Source and Destination",
                                   bg="#f8f9fa", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        path_frame.pack(fill="x", pady=(12, 0))
        tk.Label(path_frame, text="Required for copy actions. These locations are used when the button runs.",
                 bg="#f8f9fa", fg="#666666", font=("Segoe UI", 8)).grid(
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
        tk.Label(tab_action, text="Actions can only be assigned to buttons.",
                 bg="#f8f9fa", fg="#6c757d", font=("Segoe UI", 10)).pack(padx=20, pady=20)

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
                    "Set both the source and destination folders.",
                    parent=diag,
                )
                return
            if selected_action == "copy_file" and not os.path.isfile(source_path):
                messagebox.showerror("Configuration Error", "Source file not found.", parent=diag)
                return
            if selected_action == "copy_folder" and not os.path.isdir(source_path):
                messagebox.showerror("Configuration Error", "Source folder not found.", parent=diag)
                return
            if not os.path.isdir(destination_path):
                messagebox.showerror("Configuration Error", "Destination folder not found.", parent=diag)
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
                comp["inner"].config(bg=comp["bg_color"], fg=comp["fg_color"], font=("Segoe UI", comp["font_size"]))
            else:
                comp["inner"].config(text=comp["text"], bg=comp["bg_color"], fg=comp["fg_color"],
                                     font=("Segoe UI", comp["font_size"]))
        except Exception:
            pass
        messagebox.showinfo("Saved", "Component settings updated.")
        diag.destroy()

    tk.Button(bottom_frame, text="💾 Save Settings", command=save_config,
              bg="#198754", fg="white", font=("Segoe UI", 11, "bold"),
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
        messagebox.showwarning("Warning", "Select a component to delete.")

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
            "For copy buttons, set the source and destination folder in Advanced Settings.",
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

    code = [
        "import tkinter as tk",
        "from tkinter import messagebox, filedialog",
        "import webbrowser",
        "import datetime",
        "import random",
        "import time",
        "import urllib.parse",
        "import subprocess",
        "import os",
        "import shutil",
        "import platform",
        "",
        "try:",
        "    import winsound",
        "except ImportError:",
        "    winsound = None",
        "",
        "root = tk.Tk()",
        "root.title('Generated Form App')",
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
        "        'System Default Browser': {'msedge.exe', 'chrome.exe', 'firefox.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe'},",
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
        "        if browser_choice == 'System Default Browser':",
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
        "                raise FileNotFoundError(f'{browser_choice} was not found.')",
        "            subprocess.Popen([browser_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
        "            opened = True",
        "        else:",
        "            browser_aliases = {'Microsoft Edge': 'edge', 'Google Chrome': 'chrome', 'Mozilla Firefox': 'firefox', 'Brave': 'chrome'}",
        "            opened = webbrowser.get(browser_aliases[browser_choice]).open(url, new=2)",
        "        if not opened:",
        "            raise RuntimeError('Could not launch the browser.')",
        "        if os.name == 'nt':",
        "            expected_names = browser_executables.get(browser_choice, browser_executables['System Default Browser'])",
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
        "                    if browser_window_mode == 'Maximized':",
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
        "            raise RuntimeError(f'{browser_choice} could not be brought to the foreground.')",
        "        return True",
        "    except Exception as e:",
        "        error = str(e)",
        "    root.deiconify()",
        "    root.lift()",
        "    root.focus_force()",
        "    messagebox.showerror('Browser Launch Error', error, parent=root)",
        "    return False",
        ""
    ]

    for i, comp in enumerate(designer_components):
        w = comp["wrapper"]
        x, y = w.winfo_x(), w.winfo_y()
        width, height = w.winfo_width(), w.winfo_height()
        ctype, act, param, label_text = comp["type"], comp["action"], comp["param"], comp["text"]
        source_path = comp.get("source_path", "").strip()
        destination_path = comp.get("destination_path", "").strip()
        browser_choice = comp.get("browser_choice", "System Default Browser")
        browser_window_mode = comp.get("browser_window_mode", "Maximized")
        bg, fg, f_size = comp["bg_color"], comp["fg_color"], comp["font_size"]
        font_str = f"('Segoe UI', {f_size})"

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
                    code.append("        messagebox.showinfo('Done', f'File copied\\n{os.path.basename(src)}')")
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
                    code.append("            raise ValueError('The destination cannot be the source folder or a folder inside it.')")
                    code.append("        if os.path.exists(dest):")
                    code.append("            if not messagebox.askyesno('Confirm', 'A folder with the same name already exists. Merge and overwrite its contents?', parent=root): return")
                    code.append("        shutil.copytree(src, dest, dirs_exist_ok=True)")
                    code.append("        messagebox.showinfo('Done', f'Folder copied\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                    code.append("        return")
                elif act == "move_file":
                    code.append("    src = filedialog.askopenfilename(parent=root, title='Select File to Move', initialdir=os.getcwd())")
                    code.append("    if not src: return")
                    code.append("    dest = filedialog.askdirectory(parent=root, title='Select Destination Folder', initialdir=os.path.dirname(src))")
                    code.append("    if not dest: return")
                    code.append("    try:")
                    code.append("        shutil.move(src, dest)")
                    code.append("        messagebox.showinfo('Done', f'File moved\\n{os.path.basename(src)}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                elif act == "delete_file":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='Select File to Delete', initialdir=os.getcwd())")
                    code.append("    if not path: return")
                    code.append("    if messagebox.askyesno('Confirm', f'Are you sure you want to delete this file?\\n{os.path.basename(path)}', parent=root):")
                    code.append("        try:")
                    code.append("            os.remove(path)")
                    code.append("            messagebox.showinfo('Done', 'File deleted')")
                    code.append("        except Exception as e:")
                    code.append("            messagebox.showerror('Error', str(e))")
                elif act == "open_folder":
                    code.append("    path = filedialog.askdirectory(parent=root, title='Select Folder to Open', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "open_file_default":
                    code.append("    path = filedialog.askopenfilename(parent=root, title='Select File to Open', initialdir=os.getcwd())")
                    code.append("    if path:")
                    code.append("        os.startfile(path) if os.name == 'nt' else subprocess.Popen(['xdg-open', path])")
                elif act == "create_folder":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='Select a Location', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    new_name = 'New Folder'")
                    code.append("    path = os.path.join(parent, new_name)")
                    code.append("    try:")
                    code.append("        os.makedirs(path, exist_ok=True)")
                    code.append("        messagebox.showinfo('Done', f'Folder created\\n{path}')")
                    code.append("    except Exception as e:")
                    code.append("        messagebox.showerror('Error', str(e))")
                elif act == "create_text_file":
                    code.append("    parent = filedialog.askdirectory(parent=root, title='Select a Location', initialdir=os.getcwd())")
                    code.append("    if not parent: return")
                    code.append("    path = os.path.join(parent, 'New Text File.txt')")
                    code.append("    try:")
                    code.append("        with open(path, 'w', encoding='utf-8') as f:")
                    code.append("            f.write('')")
                    code.append("        messagebox.showinfo('Done', f'Text file created\\n{path}')")
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
                    code.append(f"    if not open_browser({(param or 'https://www.google.com')!r}, {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "open_x":
                    code.append(f"    if not open_browser('https://x.com/', {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "open_abema":
                    code.append(f"    if not open_browser('https://abema.tv/', {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "google_search":
                    code.append(f"    if not open_browser(f'https://www.google.com/search?q={{urllib.parse.quote(\"{param or ''}\")}}', {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "youtube_search":
                    code.append(f"    if not open_browser(f'https://www.youtube.com/results?search_query={{urllib.parse.quote(\"{param or ''}\")}}', {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "google_translate":
                    code.append(f"    if not open_browser(f'https://translate.google.co.jp/?hl=en&sl=auto&tl=en&text={{urllib.parse.quote(\"{param or ''}\")}}', {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "google_maps":
                    code.append(f"    if not open_browser(f'https://www.google.com/maps/search/{{urllib.parse.quote(\"{param or ''}\")}}', {browser_choice!r}, {browser_window_mode!r}): return")
                elif act == "show_msg":
                    code.append(f"    messagebox.showinfo('Notice', '{param or 'Hello!'}')")
                elif act == "ask_yesno":
                    code.append(f"    res = messagebox.askyesno('Confirm', '{param or 'Do you want to continue?'}')")
                    code.append("    messagebox.showinfo('Result', f'Selection: {res}')")
                elif act == "copy_clipboard":
                    code.append("    root.clipboard_clear()")
                    code.append(f"    root.clipboard_append('{param or ''}')")
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
                    code.append("    messagebox.showinfo('Random Number', f'Number: {n}')")
                elif act == "dice_roll":
                    code.append("    d = random.randint(1, 6)")
                    code.append("    messagebox.showinfo('Die Roll', f'Roll: 🎲 {d}')")
                elif act == "omikuji":
                    code.append("    omi = random.choice(['Excellent ✨', 'Very Good 🌟', 'Good 👍', 'Fair 😊', 'Poor 💦'])")
                    code.append("    messagebox.showinfo('Fortune', f'Fortune: {omi}')")
                elif act == "gen_password":
                    code.append("    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$*'")
                    code.append("    pwd = ''.join(random.choices(chars, k=12))")
                    code.append("    messagebox.showinfo('Generate Password', f'Generated password:\\n{pwd}')")
                if comp.get("close_after_action", True) and act != "close_app":
                    code.append("    root.destroy()")
                code.append("")
                cmd_str = f", command=on_btn_{i}_click"
            else:
                cmd_str = ""

            code.append(f"btn_{i} = tk.Button(root, text='{label_text}', bg='{bg}', fg='{fg}', font={font_str}{cmd_str})")
            code.append(f"btn_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Label":
            code.append(f"lbl_{i} = tk.Label(root, text='{label_text}', bg='{bg}', fg='{fg}', font={font_str})")
            code.append(f"lbl_{i}.place(x={x}, y={y}, width={width}, height={height})")
        elif ctype == "Entry":
            code.append(f"ent_{i} = tk.Entry(root, bg='{bg}', fg='{fg}', font={font_str})")
            code.append(f"ent_{i}.place(x={x}, y={y}, width={width}, height={height})")

    code.extend(["", "root.mainloop()"])
    if text.get("1.0", tk.END).strip():
        if not messagebox.askyesno("Confirm Replacement", "Replace the editor contents with the generated code?"):
            return
    text.delete("1.0", tk.END)
    text.insert("1.0", "\n".join(code) + "\n")
    update_text_modified_state()
    apply_syntax_highlighting()
    update_line_numbers()
    update_status_bar()
    top_notebook.select(tab_editor)
    messagebox.showinfo("Generation Complete", "Editor contents replaced with the generated form code!\nFile operations will prompt you to select files when run.")

# Toolbar Buttons
tk.Button(designer_toolbar, text="＋ Button", command=lambda: add_component("Button"),
          bg="#1769aa", fg="white", activebackground="#12558a", activeforeground="white",
          relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=3)
tk.Button(designer_toolbar, text="＋ Label", command=lambda: add_component("Label"),
          bg="#0f766e", fg="white", activebackground="#0b5c56", activeforeground="white",
          relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=3)
tk.Button(designer_toolbar, text="＋ Entry", command=lambda: add_component("Entry"),
          bg="#3a7d44", fg="white", activebackground="#2d6335", activeforeground="white",
          relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left", padx=3)
tk.Button(designer_toolbar, text="⚙ Window Position", command=open_window_position_dialog,
          bg="#6610f2", fg="white", relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
tk.Button(designer_toolbar, text="⚙ Advanced Settings", command=lambda: open_properties_dialog(selected_component) if selected_component else messagebox.showwarning("Warning", "Select a component"),
          bg="#ffc107", fg="#000", relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left", padx=2)
tk.Button(designer_toolbar, text="🗑 Delete", command=delete_component,
          bg="#dc3545", fg="white", relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=8)
tk.Button(designer_toolbar, text="🧹 Clear All", command=clear_designer,
          bg="#6c757d", fg="white", relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=2)
tk.Button(designer_toolbar, text="📝 Generate Code", command=generate_code_from_designer,
          bg="#0d6efd", fg="white", relief="flat", font=("Segoe UI", 9, "bold")).pack(side="left", padx=2)


# ---------- Tab 4: Tools ----------
tools_frame = tk.Frame(tab_tools, bg=THEMES[current_theme]['bg'], padx=20, pady=20)
tools_frame.pack(expand=True, fill="both")
tk.Label(tools_frame, text="🛠 Development Environment and Tools",
         font=("Segoe UI", 12, "bold"), bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=(0, 10))
tk.Label(tools_frame, text=f"Python executable: {sys.executable}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"Settings folder: {SETTINGS_FOLDER}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)
tk.Label(tools_frame, text=f"OS: {platform.system()} {platform.release()}", font=("Consolas", 9),
         bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg']).pack(anchor="w", pady=2)

mod_frame = tk.LabelFrame(tools_frame, text=" 📦 Install External Modules ",
                          bg=THEMES[current_theme]['bg'], fg=THEMES[current_theme]['text_fg'],
                          font=("Segoe UI", 10, "bold"), padx=15, pady=12)
mod_frame.pack(anchor="w", fill="x", pady=15)
tk.Label(mod_frame, text="Module name (e.g. requests):", bg=THEMES[current_theme]['bg'],
         fg=THEMES[current_theme]['text_fg'], font=("Segoe UI", 9)).pack(side="left", padx=(0, 10))
mod_entry = tk.Entry(mod_frame, width=20, font=("Consolas", 10))
mod_entry.pack(side="left", padx=5)

def install_custom_module():
    mname = mod_entry.get().strip()
    if not mname:
        messagebox.showwarning("Warning", "Enter a module name to install.")
        return
    try:
        res = subprocess.run([sys.executable, "-m", "pip", "install", mname], capture_output=True, text=True, timeout=90)
        if res.returncode == 0:
            messagebox.showinfo("Installation Successful", f"Module '{mname}' was installed successfully.")
        else:
            messagebox.showerror("Error", f"Installation failed:\n{res.stderr[:500]}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred:\n{e}")

tk.Button(mod_frame, text="Run pip install", command=install_custom_module,
          bg="#198754", fg="white", relief="flat", font=("Segoe UI", 9, "bold"),
          padx=10, pady=4).pack(side="left", padx=15)


# Menu Bar
menubar = tk.Menu(root)
file_menu = tk.Menu(menubar, tearoff=0)
file_menu.add_command(label="New File", command=new_file)
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
edit_menu.add_command(label="Find (Ctrl+F)", command=open_search_dialog)
edit_menu.add_command(label="Select All (Ctrl+A)", command=select_all)
menubar.add_cascade(label="Edit", menu=edit_menu)

root.config(menu=menubar)

apply_theme(current_theme)
update_line_numbers()
update_status_bar()
root.protocol("WM_DELETE_WINDOW", safe_exit)
root.mainloop()
