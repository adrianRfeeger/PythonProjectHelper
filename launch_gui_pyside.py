"""
Launcher for Project Export Helper (PySide6 version)
Run this script to start the PySide6-based GUI.
"""
import sys

if __name__ == "__main__":
    try:
        from gui_pyside import run_gui
    except ImportError as e:
        print("PySide6 is not installed or not working. Please run: pip install PySide6")
        sys.exit(1)
    run_gui()
