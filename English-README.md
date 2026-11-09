
# Python Studio Editor v0.2.8 User Manual

Python Studio Editor is a lightweight, simple Python GUI code editor and Tkinter form designer designed for programming beginners, learners, and hobbyists. It allows you to create and learn desktop applications using Python and Tkinter through intuitive drag-and-drop operations without complex environment setup.

## Table of Contents

1. Key Features
2. System Requirements
3. Installation & Launch
4. Basic Usage
* Code Editor
* Beginner Project Catalog
* Tkinter Form Designer
* Hotkey & Button Creator


5. What's New in Version 0.2.8
6. Disclaimer

---

## Key Features

* **Simple & Lightweight Code Editor**
* Syntax highlighting (color-coded keywords, strings, and comments)
* Line numbers, font size adjustment, and light/dark theme switching
* Find & replace features, along with automatic code formatting via PEP8 (`autopep8`)


* **Rich Sample Project Catalog**
* Comes with pre-loaded practical sample codes such as a calculator, rock-paper-scissors, ToDo list, file manager, JSON editor, and calendar
* 1-click loading into the editor for instant execution


* **Intuitive Tkinter Form Designer**
* Drag-and-drop placement of GUI widgets like buttons, labels, and text inputs
* Automatic Python/Tkinter execution code generation from your visual layout


* **Hotkey & Button Creator**
* Automatically generates task automation code for opening websites, launching apps, or sending key presses via shortcuts or button clicks
* Supports embedding system tray (taskbar) residency features


* **Multi-Language Support**
* Available in both Japanese and English editions



---

## System Requirements

* **Supported OS**: Windows 10 / 11 (Recommended) / Linux (Ubuntu, etc.)
* **Python**: Python 3.8 or later
* **Dependencies**: Python standard library (`tkinter`, `ctypes`, `json`, `subprocess`, etc.)
* *Note: Some extended features utilize external libraries (`autopep8`, `pystray`, `pillow`, `keyboard`).*



---

## Installation & Launch

1. Download the script matching your environment (`Pythonエディター 日本語版 v0.2.8.pyw` or `Python Studio Editor v0.2.8 English.pyw`) from the repository.
2. Double-click the file in an environment where Python is installed to launch it.
3. To launch via command prompt or terminal, run the following command:

```bash
python "Python Studio Editor v0.2.8 English.pyw"

```

---

## Basic Usage

### 1. Code Editor

* Write Python code directly in the main editor interface.
* Perform file operations such as "Save", "Save As", and "Open" from the top toolbar.
* Trigger the find/replace dialog or execute automatic code formatting using keyboard shortcuts.

### 2. Beginner Project Catalog

* Open the "Beginner Project List" to browse sample programs categorized by topic.
* Select a project and click "Load Code into Editor" to instantly populate the editor with executable code.

### 3. Tkinter Form Designer

* Switch to the "Form Designer" tab to launch the visual layout designer.
* Add and position widgets like buttons, labels, and text boxes onto the canvas, and adjust their properties (text, size, etc.).
* Click the "Generate Code" button to automatically output the corresponding Python code for your UI layout.

### 4. Hotkey & Button Creator

* Assign specific actions (opening websites, launching files) to custom key combinations (e.g., `Alt+A`) or button triggers.
* Export clean standalone automation code configured to run seamlessly from the system tray.

---

## What's New in Version 0.2.8

* **File Extension & Naming Update**
* Changed the main executable script extension to `.pyw` to prevent unwanted console windows (black command prompts) from popping up upon launch.


* **Integration of Latest Scripts**
* Added and updated `Pythonエディター 日本語版 v0.2.8.pyw` and `Python Studio Editor v0.2.8 English.pyw`.


* **Improved Stability for Form Designer & Editor**
* Enhanced code generation logic during widget placement and stabilized file saving routines.



---

## Disclaimer

1. **Use at Your Own Risk**
* This software (Python Studio Editor) is provided "as is" without warranty of any kind.
* The developer and copyright holders assume no liability for any direct or indirect damages (including data loss, system failure, business interruption, or any other damages) arising from the use of or inability to use this software. Use it entirely at your own risk.


2. **No Warranty for Generated Code and Samples**
* No guarantees, explicit or implied, are made regarding the accuracy, completeness, safety, or fitness for a particular purpose of the sample codes and auto-generated code provided by this software.


3. **External Libraries and OS Dependencies**
* This software includes features that execute OS-specific APIs (such as Windows APIs) or external commands. Depending on your environment and execution permissions, behavior may vary, so please thoroughly test before use.


4. **Modifications and Support**
* The specifications of this software are subject to change, or development and distribution may be discontinued without prior notice. There is no obligation to provide individual support, bug fixes, or feature improvements.
