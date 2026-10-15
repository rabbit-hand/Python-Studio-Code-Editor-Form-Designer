# Python Studio Editor
A beginner‑friendly Python IDE that integrates a GUI Form Designer, Code Editor, Project Manager, and Virtual Environment automation.  
Designed for education, rapid prototyping, and helping children and new learners avoid common Python pitfalls.

This README covers:
- Features
- How to use the editor
- Project structure
- Settings & themes
- Error handling
- Differences between **v0.1** and **v0.2t** (major improvements)

---

## 🚀 Overview
**Python Studio Editor** is an all‑in‑one development environment that allows users to build Python GUI applications using drag‑and‑drop components.  
The editor automatically generates event code, manages project files, and runs Python scripts inside an isolated virtual environment.

Key capabilities:
- GUI Form Designer  
- Python Code Editor  
- Auto‑generated event code  
- Virtual environment (venv) auto‑creation  
- Syntax highlighting  
- Code formatting  
- Search & replace  
- Hotkey customization  
- Sample project loader  
- Error reporting with line numbers  
- Child‑friendly explanations for mistakes (v0.2t)

---

## 🖥️ Main Components

### **1. Code Editor**
- Line numbers  
- Syntax highlighting  
- Auto‑indent  
- Code formatting  
- Change detection  
- Search & replace  
- Hotkey support  
- Error highlighting (v0.2t)

### **2. GUI Form Designer**
- Drag‑and‑drop widgets  
- Property editor  
- Auto‑generated event handlers  
- Undo / Redo  
- Component duplication & deletion  
- Improved stability in v0.2t

### **3. Project Manager**
- Load sample projects  
- Import project code  
- Save / Save As / Quick Save  
- Safe Exit with change detection  
- Virtual environment auto‑setup

### **4. Execution & Testing**
- Run Python code inside venv  
- Timeout protection  
- Error popup with line numbers  
- Multi‑error analysis (v0.2t)

### **5. Settings**
- Theme selection  
- Font size adjustment  
- Hotkey builder  
- Persistent configuration  
- Settings stored in dedicated folder

---

## 📁 Project Structure
The editor automatically manages:
- Project folder  
- Python source files  
- GUI layout metadata  
- Virtual environment directory  
- Settings files  
- Hotkey configuration  
- Theme configuration

---

## 🎨 Themes & Appearance
Themes are defined in the `THEMES` configuration and include:
- Light / Dark modes  
- Accent colors  
- Syntax highlight styles  
- Editor background & foreground colors  

Users can switch themes instantly.

---

## ⌨️ Hotkeys
Common hotkeys include:
- **Ctrl + S** — Save  
- **Ctrl + N** — New File  
- **Ctrl + F** — Search  
- **Ctrl + R** — Run Code  
- **Ctrl + Shift + F** — Format Code  

Hotkeys can be customized via the Hotkey Builder.

---

## 🧪 Running Code
The editor uses a dedicated virtual environment:

- Automatically created on first run  
- Python interpreter resolved via `get_virtualenv_python()`  
- Modules installed automatically when needed  
- Execution errors displayed with line numbers  
- Timeout protection prevents infinite loops

---

## ⚠️ Error Handling
### v0.1:
- Basic error popup  
- Only first runtime error shown  
- No multi‑error detection  
- No child‑friendly explanations

### v0.2t:
- Line‑numbered error messages  
- Multiple error detection (lint‑style)  
- Clear explanations for beginners  
- More stable execution  
- Better exception handling

---

# 🔄 **Version Comparison: v0.1 vs v0.2t**

This section summarizes the improvements found in the two versions  
(derived from the source code in your open tabs:  
v0.1  and v0.2t ).

## ✔️ 1. Code Structure
| Feature | v0.1 | v0.2t |
|--------|------|--------|
| File size | ~5123 lines | ~5157 lines |
| Organization | Dense, monolithic | Better structured |
| Readability | Lower | Improved |
| Redundant code | More | Reduced |

---

## ✔️ 2. Error Handling
| Feature | v0.1 | v0.2t |
|--------|------|--------|
| Runtime error | Single error only | Multiple errors supported |
| Line numbers | Basic | Enhanced |
| Explanation | Technical | Beginner‑friendly |
| Stability | Lower | Higher |

---

## ✔️ 3. GUI Designer
| Feature | v0.1 | v0.2t |
|--------|------|--------|
| Drag & drop | Supported | More stable |
| Property updates | Occasional lag | Faster & reliable |
| Undo/Redo | Basic | Improved |
| Crash rate | Higher | Reduced |

---

## ✔️ 4. Settings System
| Feature | v0.1 | v0.2t |
|--------|------|--------|
| Theme settings | Basic | Expanded |
| Font size | Basic | Improved |
| Hotkey builder | Present | More robust |
| Persistent config | Limited | Stronger persistence |

---

## ✔️ 5. Execution System
| Feature | v0.1 | v0.2t |
|--------|------|--------|
| venv handling | Basic | More reliable |
| Timeout | Present | Improved |
| Module auto‑install | Present | More stable |
| Error popup | Basic | Enhanced UI |

---

## ✔️ 6. UI & UX
| Feature | v0.1 | v0.2t |
|--------|------|--------|
| Menu layout | Older | Cleaner |
| Status bar | Basic | Improved |
| Tab organization | Less clear | More intuitive |
| Overall UX | Good | Much better |

---

# 📘 Summary
**v0.2t is a major refinement of v0.1**, focusing on:
- Stability  
- Error clarity  
- Educational usability  
- Cleaner UI  
- Better project handling  
- Stronger settings system  
- Improved GUI designer  

It is the recommended version for:
- Children learning Python  
- Classroom environments  
- Beginners  
- Rapid GUI prototyping  
- Anyone who needs a simple, guided Python IDE

---

# 📦 Future Improvements (Suggested)
- Auto‑layout for GUI components  
- Multi‑error lint panel  
- Asset manager (images, sounds)  
- Code explanation tool  
- Debugger with step‑through execution  
- More sample projects  

---

# 📝 License
(Insert your license information here.)

---

# 🙌 Author
rabbit-hand  
Python Studio Code Editor & Form Designer  
GitHub Repository: *(link from your tab)*


