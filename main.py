# file: main.py
"""Entry point: launch the GUI app with progress bar/export flow."""
from __future__ import annotations

import traceback
from tkinter import messagebox

from gui import run_gui

def main() -> None:
    try:
        run_gui()
    except Exception as exc:
        traceback.print_exc()
        messagebox.showerror("Fatal Error", f"The application encountered a fatal error:\n{exc}")

if __name__ == "__main__":
    main()
