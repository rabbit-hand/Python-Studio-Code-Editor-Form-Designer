📘 Python Studio Editor – README
GUI Form Designer & Python Code Editor
(Drone Control, Hotkeys, External Device Integration)

🏷️ Overview
Python Studio Editor is a lightweight integrated development environment that combines:

GUI Form Designer

Python Code Editor

Project Management

Execution Environment

Extensible Tools

It provides a Visual Basic / Delphi–style drag‑and‑drop GUI builder together with Python code editing, hotkey customization, virtual environment management, and optional external device control such as drones. 

✨ Features
🎨 GUI Form Designer
Drag‑and‑drop widget placement

Resize, move, align, snap

Property editor (position, size, color, font, text, event name)

Automatic event code generation

GUI preview

Widget hierarchy tree

Multi‑form support 

✏️ Python Code Editor
Syntax highlighting (Pygments)

Undo / Redo

Search & Replace

Auto‑indent

Code formatting via autopep8

Multi‑file editing

Linked form‑generation code

Basic code completion 

🗂️ Project Management
Automatic project folder creation

Save forms, code, and settings

Switch between multiple projects

Create template projects 

🧪 Execution & Testing
One‑click run

Safe execution inside a virtual environment (venv)

Timeout execution (test_timeout_seconds)

Log output window

Error stack trace display 

🧰 Virtual Environment (venv) Management
Automatic creation of a dedicated virtual environment

Auto‑installation of required libraries:

pillow

pywin32

pygments

autopep8

tkinter

Python path management

Automatic pip upgrade 

🎛️ Hotkey Builder
Custom hotkeys for editor actions

Custom hotkeys for form designer operations

Save hotkey configuration

Load and apply settings 

🎨 Theme & UI Customization
Light / Dark themes

Adjustable font size

Window size memory

Save UI configuration 

📡 External Device Control
(Drone, Robot Arm, Custom Machines)

Python Studio Editor supports development of control applications using external APIs and libraries. 

Possible integrations
Drone control

DJI / Tello / MAVLink

GUI buttons for takeoff, landing, forward, stop, etc.

Robot arm control

Autonomous robots / custom devices

Sensor input (temperature, distance, GPS)

Network control (UDP / TCP / WebSocket) 

By combining GUI buttons with Python API calls, you can build a full GUI‑based drone controller. 

🔌 External Integration & Extensions
Web API calls

HTTP / HTTPS communication

File I/O

Image processing (Pillow)

Windows API (pywin32)

Script auto‑generation

Plugin‑style extension code 

🧱 Internal Structure (For Developers)
~4,800 lines of Python

Tkinter‑based GUI

Custom widget management system

Property binding

Event dispatcher

Code generation engine

JSON‑based configuration 

📥 Installation
Install Python 3.x

Run install_python.bat

Required libraries will be installed automatically

A virtual environment will be created on the desktop

Launch Python Studio Editor English.pyw 

📚 Basic Workflow
Create a new project

Build the GUI using the form designer

Write event code

Save the project

Run and test the application 

⚠️ Disclaimer
This software is independently developed and is not affiliated with Python, PSF, or any organization. 

No guarantee of correct operation

No obligation to fix bugs or issues

No responsibility for data loss or corruption

No liability for commercial, educational, or operational damages

No responsibility for accidents involving external devices (e.g., drones)

No obligation to provide support 

Important:  
Use this software at your own risk.
Always back up important data before use. 
