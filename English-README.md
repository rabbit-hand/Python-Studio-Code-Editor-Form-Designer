# Python Studio Editor
A lightweight Python IDE featuring a GUI Form Designer, Code Editor, Hotkey Builder, and optional external device control (e.g., drones).

---

## 📌 What is Python Studio Editor?

Python Studio Editor is a standalone mini‑IDE designed to make GUI application development in Python simple and visual.  
It combines:

- A drag‑and‑drop **GUI Form Designer**
- A syntax‑highlighted **Python Code Editor**
- **Project management** tools
- A built‑in **execution environment**
- Optional **external device control** (drones, robots, sensors)

It is inspired by tools like Visual Basic and Delphi, but built entirely with Python and Tkinter.

---

## 🎨 GUI Form Designer

The Form Designer allows you to visually build Python GUI applications.

### Features
- Drag‑and‑drop widget placement  
- Resize, move, align, snap‑to‑grid  
- Property editor for:
  - Position / Size  
  - Text / Font / Color  
  - Widget name  
  - Event handler name  
- Real‑time GUI preview  
- Widget hierarchy tree  
- Multi‑form support

### What it generates
The designer produces Python code that builds the GUI automatically.  
You can edit this generated code directly in the editor.

---

## ✏️ Python Code Editor

A built‑in editor for writing and modifying Python scripts.

### Features
- Syntax highlighting (Pygments)
- Undo / Redo
- Search & Replace
- Auto‑indent
- Code formatting via autopep8
- Multi‑file editing
- Event handler code integration
- Basic code completion

### Purpose
The editor is tightly integrated with the Form Designer, allowing you to write logic for GUI events (button clicks, etc.) without switching tools.

---

## 🗂️ Project Management

Python Studio Editor organizes your work into project folders.

### Features
- Automatic project folder creation
- Save forms, code files, and settings
- Switch between multiple projects
- Create template projects for reuse

### Why it matters
This keeps GUI layouts, Python scripts, and configuration files together, making your project portable and easy to manage.

---

## 🧪 Execution & Testing

You can run your Python project directly from the editor.

### Features
- One‑click execution
- Runs inside a dedicated virtual environment (venv)
- Timeout execution (prevents infinite loops)
- Log output window
- Error stack trace display

### Benefit
You don’t need to open a terminal or external IDE—everything runs inside the editor.

---

## 🧰 Virtual Environment (venv) Management

The editor automatically creates and manages a Python virtual environment.

### Features
- Auto‑creation of a venv on first launch
- Auto‑installation of required libraries:
  - pillow  
  - pywin32  
  - pygments  
  - autopep8  
  - tkinter  
- Python path detection
- Automatic pip upgrade

### Why this is important
It ensures your GUI applications run consistently, regardless of your system’s Python setup.

---

## 🎛️ Hotkey Builder

Customize keyboard shortcuts for both the editor and the form designer.

### Features
- Assign hotkeys to common actions
- Save hotkey configuration
- Load and apply settings
- Useful for power users and rapid development

---

## 🎨 Theme & UI Customization

Make the editor look the way you want.

### Features
- Light / Dark themes
- Adjustable font size
- Window size memory
- Save UI configuration

---

## 📡 External Device Control (Optional)

Python Studio Editor can be used to build control interfaces for external devices.

### Supported concepts
- Drone control (DJI / Tello / MAVLink)
- Robot arm control
- Autonomous robots
- Sensors (temperature, distance, GPS)
- Network control (UDP / TCP / WebSocket)

### Example use case
Create a GUI with buttons like:

- Takeoff  
- Land  
- Move Forward  
- Stop  

Then connect these buttons to Python API calls to control a drone.

---

## 🔌 External Integration & Extensions

You can extend your project with additional Python libraries.

### Examples
- Web API calls
- HTTP / HTTPS communication
- File I/O
- Image processing (Pillow)
- Windows API (pywin32)
- Plugin‑style extension modules

---

## 🧱 Internal Architecture

Python Studio Editor is built using:

- Tkinter for GUI
- Custom widget management system
- Property binding engine
- Event dispatcher
- Code generation engine
- JSON‑based configuration system

The project contains ~4,800 lines of Python code.

---

## 📥 Installation

1. Install Python 3.x  
2. Run `install_python.bat`  
3. Required libraries will be installed automatically  
4. A virtual environment will be created on the desktop  
5. Launch `Python Studio Editor English.pyw`

---

## 📚 Basic Workflow

1. Create a new project  
2. Design the GUI using the Form Designer  
3. Write event logic in the Code Editor  
4. Save the project  
5. Run and test the application  

---

## ⚠️ Disclaimer

This software is independently developed and is **not affiliated with Python, PSF, or any organization**.

- No guarantee of correct operation  
- No obligation to fix bugs or issues  
- No responsibility for data loss or corruption  
- No liability for commercial, educational, or operational damages  
- No responsibility for accidents involving external devices (e.g., drones)  
- No obligation to provide support  

**Use this software at your own risk. Always back up important data before use.**
---
<img width="1600" height="852" alt="image" src="https://github.com/user-attachments/assets/d75daa7e-1520-4a7c-9456-aa7dce9388da" />
<img width="1600" height="852" alt="image" src="https://github.com/user-attachments/assets/0e85509a-441e-4388-806b-8aab8b850273" />
<img width="1600" height="852" alt="image" src="https://github.com/user-attachments/assets/017c3a72-fe93-4d84-9ec8-65795ba07712" />
<img width="1600" height="852" alt="image" src="https://github.com/user-attachments/assets/1d2a9371-40d5-4550-9666-8333cd9ccead" />

