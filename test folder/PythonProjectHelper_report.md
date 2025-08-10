# Project Structure: PythonProjectHelper

**Generated:** 2025-08-10 17:46  
**Root Path:** `/Users/adrianfeeger/Development/Python/PythonProjectHelper`

## 📊 Summary

- **Total Files:** 8
- **Text Files:** 7
- **Total Size:** 52 KB

## 📁 File Listing

```
├── 📄 PythonProjectHelper.code-workspace (0 KB, — lines, — words, modified 2025-08-10 17:41)
├── 🐍 config.py (4 KB, 135 lines, 445 words, modified 2025-08-10 17:13)
├── 🐍 gui.py (18 KB, 488 lines, 1362 words, modified 2025-08-10 17:13)
├── 🐍 main.py (0 KB, 19 lines, 51 words, modified 2025-08-10 01:25)
├── 📄 main.spec (2 KB, 66 lines, 189 words, modified 2025-08-08 23:59)
├── 🐍 outputs.py (16 KB, 442 lines, 1565 words, modified 2025-08-10 17:34)
├── 🐍 report.py (1 KB, 49 lines, 146 words, modified 2025-08-10 01:25)
└── 🐍 scan.py (8 KB, 231 lines, 716 words, modified 2025-08-10 15:58)
```

---

## 📄 File Contents

### 📄 `config.py`

**Size:** 4 KB | **Lines:** 135 | **Words:** 445 | **Modified:** 2025-08-10 17:13

```py
# file: config.py
"""Configuration management for persistent user settings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from report import OutputFormat

@dataclass
class AppConfig:
    """Application configuration settings"""
    # Last used paths
    last_source_folder: Optional[str] = None
    last_save_folder: Optional[str] = None
    
    # Export options
    output_format: str = OutputFormat.MARKDOWN.value
    include_contents: bool = True
    
    # Window settings
    window_width: int = 720
    window_height: int = 500
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create config from dictionary"""
        # Filter out any unknown keys to handle version changes
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)

class ConfigManager:
    """Manages loading and saving application configuration"""
    
    def __init__(self, config_name: str = "project_export_helper.json"):
        self.config_path = self._get_config_dir() / config_name
        self._config: Optional[AppConfig] = None
    
    def _get_config_dir(self) -> Path:
        """Get the appropriate config directory for the platform"""
        import os
        import sys
        
        if sys.platform == "win32":
            # Windows: %APPDATA%
            config_dir = Path(os.environ.get("APPDATA", "~")).expanduser()
        elif sys.platform == "darwin":
            # macOS: ~/Library/Application Support
            config_dir = Path("~/Library/Application Support").expanduser()
        else:
            # Linux/Unix: ~/.config
            config_dir = Path("~/.config").expanduser()
        
        app_config_dir = config_dir / "ProjectExportHelper"
        app_config_dir.mkdir(parents=True, exist_ok=True)
        return app_config_dir
    
    def load_config(self) -> AppConfig:
        """Load configuration from disk, or create default if not found"""
        if self._config is not None:
            return self._config
        
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._config = AppConfig.from_dict(data)
            else:
                self._config = AppConfig()
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            # If config is corrupted or unreadable, use defaults
            self._config = AppConfig()
        
        return self._config
    
    def save_config(self, config: AppConfig) -> None:
        """Save configuration to disk"""
        self._config = config
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except OSError:
            # Silently fail if we can't save - don't crash the app
            pass
    
    def update_source_folder(self, path: str) -> None:
        """Update the last used source folder"""
        config = self.load_config()
        config.last_source_folder = path
        self.save_config(config)
    
    def update_save_folder(self, path: str) -> None:
        """Update the last used save folder"""
        config = self.load_config()
        config.last_save_folder = str(Path(path).parent)
        self.save_config(config)
    
    def update_export_options(self, format_value: str, include_contents: bool) -> None:
        """Update export format and content inclusion setting"""
        config = self.load_config()
        config.output_format = format_value
        config.include_contents = include_contents
        self.save_config(config)
    
    def update_window_geometry(self, width: int, height: int, x: int, y: int) -> None:
        """Update window size and position"""
        config = self.load_config()
        config.window_width = width
        config.window_height = height
        config.window_x = x
        config.window_y = y
        self.save_config(config)

# Global config manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Get the global config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
```

### 📄 `gui.py`

**Size:** 18 KB | **Lines:** 488 | **Words:** 1362 | **Modified:** 2025-08-10 17:13

```py
# file: gui.py
"""Enhanced Tkinter GUI with improved functionality and error handling.
Includes better UX, file filtering, and robust export flow.
"""
from __future__ import annotations

import threading
import os
from pathlib import Path
from tkinter import Tk, filedialog, ttk, StringVar, BooleanVar, messagebox, IntVar
from typing import Optional

from report import OutputFormat
from scan import scan_project
from outputs import export_report
from config import ConfigManager

class ExportApp(Tk):
    def __init__(self) -> None:
        super().__init__()
        
        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        self.title("Project Export Helper v1.1")
        
        # Set window geometry from config
        if self.config.window_x is not None and self.config.window_y is not None:
            self.geometry(f"{self.config.window_width}x{self.config.window_height}+{self.config.window_x}+{self.config.window_y}")
        else:
            self.geometry(f"{self.config.window_width}x{self.config.window_height}")
        
        self.resizable(True, True)
        self.minsize(600, 450)

        # State
        self.folder_path: Optional[Path] = None
        self.save_path: Optional[Path] = None
        self.fmt_var = StringVar(value=self.config.output_format)
        self.include_var = BooleanVar(value=self.config.include_contents)
        self.status_var = StringVar(value="Select a project folder to begin...")
        self.file_count_var = IntVar(value=0)
        self.export_running = False

        # Setup UI
        self._setup_ui()
        self._center_window()
        
        # Load last source folder if available
        if self.config.last_source_folder and Path(self.config.last_source_folder).exists():
            self.folder_path = Path(self.config.last_source_folder)
            self.path_label.configure(text=str(self.folder_path))
            self.status_var.set("Scanning folder for files...")
            self._quick_scan()

    def _setup_ui(self) -> None:
        """Setup the complete user interface"""
        pad = dict(padx=15, pady=6)
        
        # Create main container with scrollable frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=pad["padx"], pady=pad["pady"])

        # Header
        header_frame = ttk.LabelFrame(main_frame, text="Project Selection", padding=8)
        header_frame.pack(fill="x", pady=(0, 8))
        
        # Folder selection row
        folder_frame = ttk.Frame(header_frame)
        folder_frame.pack(fill="x", pady=5)
        
        ttk.Label(folder_frame, text="Project folder:").pack(side="left", anchor="w")
        self.path_label = ttk.Label(folder_frame, text="No folder selected", 
                                   relief="sunken", width=50, anchor="w")
        self.path_label.pack(side="left", padx=(10, 10), fill="x", expand=True)
        
        self.browse_btn = ttk.Button(folder_frame, text="Browse", 
                                    command=self.on_browse)
        self.browse_btn.pack(side="right")

        # File count display
        self.count_label = ttk.Label(header_frame, text="Files found: 0", 
                                    font=("TkDefaultFont", 9))
        self.count_label.pack(anchor="w", pady=(5, 0))

        # Options section
        options_frame = ttk.LabelFrame(main_frame, text="Export Options", padding=8)
        options_frame.pack(fill="x", pady=(0, 8))

        # Output format row
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill="x", pady=5)
        
        ttk.Label(format_frame, text="Output format:").pack(side="left")
        self.combo = ttk.Combobox(format_frame, textvariable=self.fmt_var, 
                                 state="readonly", width=30,
                                 values=[f.value for f in OutputFormat])
        self.combo.pack(side="left", padx=(10, 0))
        
        # Content inclusion checkbox
        content_frame = ttk.Frame(options_frame)
        content_frame.pack(fill="x", pady=5)
        
        self.content_check = ttk.Checkbutton(content_frame, 
                                           text="Include file contents in export", 
                                           variable=self.include_var)
        self.content_check.pack(side="left")
        
        # Help text
        help_text = ttk.Label(options_frame, 
                             text="💡 Tip: Including contents creates detailed reports but larger files",
                             font=("TkDefaultFont", 8), foreground="gray")
        help_text.pack(anchor="w", pady=(2, 0))

        # Save destination section
        save_frame = ttk.LabelFrame(main_frame, text="Save Destination", padding=8)
        save_frame.pack(fill="x", pady=(0, 8))
        
        dest_frame = ttk.Frame(save_frame)
        dest_frame.pack(fill="x", pady=5)
        
        ttk.Label(dest_frame, text="Save as:").pack(side="left")
        self.save_label = ttk.Label(dest_frame, text="Choose destination file...", 
                                   relief="sunken", width=50, anchor="w")
        self.save_label.pack(side="left", padx=(10, 10), fill="x", expand=True)
        
        self.choose_btn = ttk.Button(dest_frame, text="Choose File...", 
                                    command=self.on_choose_save, state="disabled")
        self.choose_btn.pack(side="right")

        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding=8)
        progress_frame.pack(fill="x", pady=(0, 8))
        
        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 5))
        
        # Status label
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.pack(anchor="w")

        # Action buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=(10, 10))
        
        # Right-aligned button frame
        button_frame = ttk.Frame(action_frame)
        button_frame.pack(side="right")
        
        ttk.Button(button_frame, text="Quit", command=self.on_quit).pack(side="right", padx=(10, 0))
        self.export_btn = ttk.Button(button_frame, text="Start Export", 
                                    command=self.on_export, state="disabled")
        self.export_btn.pack(side="right", padx=(0, 10))
        
        # Bind format change event
        self.combo.bind('<<ComboboxSelected>>', self.on_format_changed)
        
        # Bind content checkbox change event
        self.content_check.configure(command=self._on_content_changed)

    def _center_window(self) -> None:
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ---- Event Handlers ----
    def on_browse(self) -> None:
        """Handle folder selection"""
        if self.export_running:
            messagebox.showwarning("Export in Progress", 
                                 "Please wait for the current export to finish.")
            return
        
        # Use last folder as initial directory if available
        initial_dir = None
        if self.config.last_source_folder and Path(self.config.last_source_folder).exists():
            initial_dir = self.config.last_source_folder
            
        folder = filedialog.askdirectory(
            title="Select Project Folder to Scan",
            mustexist=True,
            initialdir=initial_dir
        )
        if not folder:
            return
            
        self.folder_path = Path(folder)
        
        # Validate folder
        if not self.folder_path.exists():
            messagebox.showerror("Invalid Folder", "Selected folder does not exist.")
            return
            
        if not os.access(self.folder_path, os.R_OK):
            messagebox.showerror("Access Denied", "Cannot read from selected folder.")
            return

        # Save to config
        self.config_manager.update_source_folder(str(self.folder_path))

        # Update UI
        self.path_label.configure(text=str(self.folder_path))
        self.status_var.set("Scanning folder for files...")
        
        # Quick scan for file count in background
        self._quick_scan()

    def _quick_scan(self) -> None:
        """Perform a quick scan to count files"""
        def scan_worker() -> None:
            try:
                if self.folder_path is not None:
                    count = self._count_files(self.folder_path)
                    self.after(0, lambda: self._update_file_count(count))
                else:
                    self.after(0, lambda: self.status_var.set("No folder selected"))
            except Exception as e:
                self.after(0, lambda: self.status_var.set(f"Error scanning folder: {e}"))
        
        threading.Thread(target=scan_worker, daemon=True).start()

    def _count_files(self, path: Path) -> int:
        """Count files in the project (excluding hidden/ignored)"""
        from report import EXCLUDED_DIRS
        
        count = 0
        try:
            for root, dirs, files in os.walk(path):
                # Filter directories
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
                # Count non-hidden files
                count += len([f for f in files if not f.startswith('.')])
        except Exception:
            return 0
        return count

    def _update_file_count(self, count: int) -> None:
        """Update the file count display"""
        self.file_count_var.set(count)
        self.count_label.configure(text=f"Files found: {count}")
        
        if count > 0:
            self.status_var.set("Folder scanned successfully. Choose save destination.")
            self.choose_btn.configure(state="normal")
        else:
            self.status_var.set("No files found in selected folder.")
            self.choose_btn.configure(state="disabled")
        
        self._update_export_state()

    def _on_content_changed(self) -> None:
        """Handle content inclusion checkbox change"""
        self.config_manager.update_export_options(
            self.fmt_var.get(),
            self.include_var.get()
        )

    def on_format_changed(self, event=None) -> None:
        """Handle format selection change"""
        # Save format preference
        self.config_manager.update_export_options(
            self.fmt_var.get(), 
            self.include_var.get()
        )
        
        if self.folder_path and self.save_path:
            # Update save path extension to match format
            self._suggest_filename()

    def on_choose_save(self) -> None:
        """Handle save destination selection"""
        if not self.folder_path:
            messagebox.showwarning("No Folder Selected", 
                                 "Please select a project folder first.")
            return

        fmt = OutputFormat.from_label(self.fmt_var.get())
        ext_map = {
            OutputFormat.MARKDOWN: (".md", "Markdown files"),
            OutputFormat.PLAINTEXT: (".txt", "Text files"),
            OutputFormat.HTML: (".html", "HTML files"),
            OutputFormat.JSON: (".json", "JSON files"),
            OutputFormat.ZIP: (".zip", "Zip archives"),
        }
        
        ext, desc = ext_map[fmt]
        default_name = f"{self.folder_path.name}_report{ext}"
        
        filetypes = [
            (desc, f"*{ext}"),
            ("All files", "*.*")
        ]
        
        # Use last save folder as initial directory if available
        initial_dir = None
        if self.config.last_save_folder and Path(self.config.last_save_folder).exists():
            initial_dir = self.config.last_save_folder
        
        save_path_str = filedialog.asksaveasfilename(
            title=f"Save {fmt.value} Report",
            defaultextension=ext,
            initialfile=default_name,
            initialdir=initial_dir,
            filetypes=filetypes,
            parent=self
        )
        
        if save_path_str:
            self.save_path = Path(save_path_str)
            self.save_label.configure(text=str(self.save_path))
            
            # Save to config
            self.config_manager.update_save_folder(str(self.save_path))
            
            # Ask user if they want to export immediately
            auto_export = messagebox.askyesno(
                "Export Now?", 
                f"File destination set to:\n{self.save_path.name}\n\n"
                "Would you like to start the export now?",
                default="no"
            )
            
            if auto_export:
                self.on_export()
            else:
                self.status_var.set("Ready to export. Click 'Start Export' when ready.")
                self._update_export_state()

    def _suggest_filename(self) -> None:
        """Update suggested filename when format changes"""
        if not self.save_path or not self.folder_path:
            return
            
        fmt = OutputFormat.from_label(self.fmt_var.get())
        ext_map = {
            OutputFormat.MARKDOWN: ".md",
            OutputFormat.PLAINTEXT: ".txt", 
            OutputFormat.HTML: ".html",
            OutputFormat.JSON: ".json",
            OutputFormat.ZIP: ".zip",
        }
        
        new_ext = ext_map[fmt]
        new_path = self.save_path.with_suffix(new_ext)
        self.save_path = new_path
        self.save_label.configure(text=str(self.save_path))

    def on_export(self) -> None:
        """Handle export operation"""
        if not self.folder_path or not self.save_path:
            messagebox.showwarning("Missing Information", 
                                 "Please select both source folder and destination file.")
            return
            
        if self.export_running:
            messagebox.showwarning("Export in Progress", 
                                 "An export is already running.")
            return

        # Confirm overwrite if file exists
        if self.save_path.exists():
            if not messagebox.askyesno("File Exists", 
                                     f"File already exists:\n{self.save_path}\n\nOverwrite it?"):
                return

        fmt = OutputFormat.from_label(self.fmt_var.get())
        include = bool(self.include_var.get())

        self._set_working(True)
        self.status_var.set("Scanning project files...")
        self.progress.start(10)

        def export_worker() -> None:
            try:
                # Type guards to ensure paths are not None
                assert self.folder_path is not None
                assert self.save_path is not None
                
                # Scan project
                self.after(0, lambda: self.status_var.set("Analyzing project structure..."))
                report = scan_project(self.folder_path)
                
                # Export report
                self.after(0, lambda: self.status_var.set("Generating export file..."))
                export_report(report, fmt, include, self.save_path, self.folder_path)
                
                # Success
                self.after(0, lambda: self._export_success())
                
            except PermissionError as e:
                self.after(0, lambda: messagebox.showerror("Permission Error", 
                    f"Cannot write to destination:\n{e}"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Export Error", 
                    f"Export failed:\n{str(e)[:200]}..."))
            finally:
                self.after(0, lambda: self._export_complete())

        threading.Thread(target=export_worker, daemon=True).start()

    def _export_success(self) -> None:
        """Handle successful export"""
        if self.save_path is not None:
            size_mb = self.save_path.stat().st_size / (1024 * 1024)
            result = messagebox.askquestion("Export Complete", 
                              f"Report exported successfully!\n\n"
                              f"File: {self.save_path.name}\n"
                              f"Size: {size_mb:.1f} MB\n"
                              f"Location: {self.save_path.parent}\n\n"
                              f"Would you like to open the file location?")
            
            if result == 'yes':
                # Try to open file location
                try:
                    import subprocess
                    import sys
                    if sys.platform == "win32":
                        subprocess.run(["explorer", "/select,", str(self.save_path)])
                    elif sys.platform == "darwin":  # macOS
                        subprocess.run(["open", "-R", str(self.save_path)])
                    else:  # Linux
                        subprocess.run(["xdg-open", str(self.save_path.parent)])
                except Exception:
                    messagebox.showinfo("File Location", f"File saved to:\n{self.save_path}")
        else:
            messagebox.showinfo("Export Complete", "Report exported successfully!")

    def _export_complete(self) -> None:
        """Cleanup after export completion"""
        self.progress.stop()
        self._set_working(False)
        self.status_var.set("Export complete.")

    def on_quit(self) -> None:
        """Handle application quit"""
        # Save window geometry before quitting
        try:
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
            x = self.winfo_x()
            y = self.winfo_y()
            self.config_manager.update_window_geometry(width, height, x, y)
        except:
            # Don't let geometry saving prevent quitting
            pass
        
        if self.export_running:
            if messagebox.askyesno("Export in Progress", 
                                 "An export is currently running. Quit anyway?"):
                self.destroy()
        else:
            self.destroy()

    # ---- Helper Methods ----
    def _update_export_state(self) -> None:
        """Update export button state based on current selections"""
        enabled = (self.folder_path is not None and 
                  self.save_path is not None and 
                  not self.export_running and
                  self.file_count_var.get() > 0)
        self.export_btn.configure(state="normal" if enabled else "disabled")

    def _set_working(self, working: bool) -> None:
        """Set UI state for working/idle"""
        self.export_running = working
        state = "disabled" if working else "normal"
        
        widgets_to_disable = [
            self.export_btn, self.combo, self.browse_btn, 
            self.choose_btn, self.content_check
        ]
        
        for widget in widgets_to_disable:
            widget.configure(state=state)
        
        self._update_export_state()

def run_gui() -> None:
    """Launch the enhanced GUI application"""
    app = ExportApp()
    app.mainloop()
```

### 📄 `main.py`

**Size:** 0 KB | **Lines:** 19 | **Words:** 51 | **Modified:** 2025-08-10 01:25

```py
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
```

### 📄 `main.spec`

**Size:** 2 KB | **Lines:** 66 | **Words:** 189 | **Modified:** 2025-08-08 23:59

```spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter.ttk'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProjectHelper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    name='ProjectHelper'
)

app = BUNDLE(
    coll,
    name='ProjectHelper.app',
    icon=None,
    bundle_identifier='com.projecthelper',
    info_plist={
        'CFBundleName': 'ProjectHelper',
        'CFBundleDisplayName': 'ProjectHelper',
        'CFBundleGetInfoString': 'ProjectHelper',
        'CFBundleIdentifier': 'com.projecthelper',
        'CFBundleVersion': '1.0.1',
        'CFBundleShortVersionString': '1.0.1',
        # macOS privacy permission prompts
        'NSDesktopFolderUsageDescription': 'ProjectHelper needs access to your Desktop folder to read and save project files.',
        'NSDocumentsFolderUsageDescription': 'ProjectHelper needs access to your Documents folder to open and store project files.',
        'NSDownloadsFolderUsageDescription': 'ProjectHelper needs access to your Downloads folder to import downloaded resources.',
        'NSPicturesFolderUsageDescription': 'ProjectHelper needs access to your Pictures folder to manage image assets.',
        'NSMoviesFolderUsageDescription': 'ProjectHelper needs access to your Movies folder to handle video assets.',
        'NSMusicFolderUsageDescription': 'ProjectHelper needs access to your Music folder to associate audio resources.',
        'NSNetworkVolumesUsageDescription': 'ProjectHelper needs access to network volumes to open and save projects stored on shared drives.',
        'NSRemovableVolumesUsageDescription': 'ProjectHelper needs access to removable drives (USB, external disks) to import and export projects.'
    }
)
```

### 📄 `outputs.py`

**Size:** 16 KB | **Lines:** 442 | **Words:** 1565 | **Modified:** 2025-08-10 17:34

```py
# file: outputs.py
"""Enhanced renderers and export functionality with better formatting and error handling."""
from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import asdict
from pathlib import Path
from tkinter import messagebox
from typing import Optional

from report import ProjectReport, OutputFormat, format_size, EXCLUDED_DIRS

def _get_file_emoji(ext: str) -> str:
    """Get appropriate emoji for file extension"""
    emoji_map = {
        '.py': '🐍', '.js': '🟨', '.html': '🌐', '.css': '🎨', '.json': '📋',
        '.md': '📝', '.txt': '📄', '.yml': '⚙️', '.yaml': '⚙️', '.xml': '📋',
        '.csv': '📊', '.sql': '🗄️', '.sh': '⚡', '.bat': '⚡', '.ps1': '⚡',
        '.dockerfile': '🐳', '.gitignore': '🚫', '.env': '🔒', '.log': '📜',
        '.ini': '⚙️', '.cfg': '⚙️', '.conf': '⚙️', '.toml': '⚙️'
    }
    return emoji_map.get(ext.lower(), '📄')

def render_markdown(report: ProjectReport, include_contents: bool = True) -> str:
    """Render project report as Markdown with enhanced formatting"""
    root_name = Path(report.root).name
    lines: list[str] = [
        f"# Project Structure: {root_name}\n",
        f"**Generated:** {report.generated_at}  ",
        f"**Root Path:** `{report.root}`\n"
    ]
    
    # Summary statistics
    total_files = len(report.files)
    total_size = sum(f.size_bytes for f in report.files)
    text_files = sum(1 for f in report.files if f.content is not None)
    
    lines.extend([
        "## 📊 Summary",
        "",
        f"- **Total Files:** {total_files:,}",
        f"- **Text Files:** {text_files:,}",
        f"- **Total Size:** {format_size(total_size)}",
        "",
        "## 📁 File Listing",
        ""
    ])
    
    # Build a tree structure from file paths
    from collections import defaultdict
    def build_tree(files):
        tree = {}
        for fi in files:
            parts = fi.path.split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node.setdefault("__files__", []).append(fi)
        return tree

    def render_tree(node, prefix_stack=None, level=0, is_last_dir=False):
        if prefix_stack is None:
            prefix_stack = []
        out = []
        keys = sorted(k for k in node.keys() if k != "__files__")
        n_keys = len(keys)
        for i, key in enumerate(keys):
            is_last = (i == n_keys - 1 and not node.get("__files__"))
            # Build prefix
            prefix = ""
            for draw in prefix_stack:
                prefix += ("│   " if draw else "    ")
            branch = "└── " if is_last else "├── "
            out.append(f"{prefix}{branch}📁 {key}/")
            # For children, add to prefix_stack
            out.extend(render_tree(node[key], prefix_stack + [not is_last], level+1, is_last))
        files = sorted(node.get("__files__", []), key=lambda f: f.path)
        n_files = len(files)
        for j, fi in enumerate(files):
            is_last_file = (j == n_files - 1)
            prefix = ""
            for draw in prefix_stack:
                prefix += ("│   " if draw else "    ")
            branch = "└── " if is_last_file else "├── "
            size = format_size(fi.size_bytes)
            lines_str = str(fi.lines) if fi.lines != "?" else "—"
            words_str = str(fi.words) if fi.words != "?" else "—"
            ext = Path(fi.path).suffix.lower()
            emoji = _get_file_emoji(ext)
            meta = f"{size}, {lines_str} lines, {words_str} words, modified {fi.mtime_iso}"
            out.append(f"{prefix}{branch}{emoji} {Path(fi.path).name} ({meta})")
        return out

    tree = build_tree(report.files)
    # Render the tree as a code block to preserve formatting and line breaks
    tree_lines = render_tree(tree)
    lines.append('```')
    lines.extend(tree_lines)
    lines.append('```')
    
    if include_contents:
        lines.extend(["\n---\n", "## 📄 File Contents\n"])
        
        for fi in report.files:
            if fi.content is None:
                continue
                
            ext = Path(fi.path).suffix.lower().lstrip(".") or "text"
            
            lines.extend([
                f"### 📄 `{fi.path}`",
                "",
                f"**Size:** {format_size(fi.size_bytes)} | **Lines:** {fi.lines} | **Words:** {fi.words} | **Modified:** {fi.mtime_iso}",
                "",
                f"```{ext}",
                fi.content.strip(),
                "```",
                ""
            ])
    
    return "\n".join(lines) + "\n"

def render_plaintext(report: ProjectReport, include_contents: bool = False) -> str:
    """Render project report as plain text with improved formatting"""
    buf = io.StringIO()
    
    print("=" * 60, file=buf)
    print(f"PROJECT STRUCTURE REPORT", file=buf)
    print("=" * 60, file=buf)
    print(f"Project: {Path(report.root).name}", file=buf)
    print(f"Generated: {report.generated_at}", file=buf)
    print(f"Root Path: {report.root}", file=buf)
    print("", file=buf)
    
    # Summary
    total_files = len(report.files)
    total_size = sum(f.size_bytes for f in report.files)
    text_files = sum(1 for f in report.files if f.content is not None)
    
    print("SUMMARY:", file=buf)
    print(f"  Total Files: {total_files:,}", file=buf)
    print(f"  Text Files: {text_files:,}", file=buf)
    print(f"  Total Size: {format_size(total_size)}", file=buf)
    print("", file=buf)
    
    print("FILE LISTING:", file=buf)
    print("-" * 60, file=buf)

    # Tree structure for plaintext
    from collections import defaultdict
    def build_tree(files):
        tree = {}
        for fi in files:
            parts = fi.path.split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node.setdefault("__files__", []).append(fi)
        return tree

    def render_tree(node, prefix=""):
        out = []
        for key in sorted(k for k in node.keys() if k != "__files__"):
            out.append(f"{prefix}{key}/")
            out.extend(render_tree(node[key], prefix + "    "))
        for fi in sorted(node.get("__files__", []), key=lambda f: f.path):
            size = format_size(fi.size_bytes)
            lines_str = str(fi.lines) if fi.lines != "?" else "—"
            words_str = str(fi.words) if fi.words != "?" else "—"
            out.append(f"{prefix}- {Path(fi.path).name} [{size}, {lines_str} lines, {words_str} words, {fi.mtime_iso}]")
        return out

    tree = build_tree(report.files)
    for line in render_tree(tree):
        print(line, file=buf)
    
    if include_contents:
        print("\n" + "=" * 60, file=buf)
        print("FILE CONTENTS", file=buf)
        print("=" * 60, file=buf)
        
        for fi in report.files:
            if fi.content is None:
                continue
                
            print(f"\n--- {fi.path} ---", file=buf)
            print(f"Size: {format_size(fi.size_bytes)} | Lines: {fi.lines} | Words: {fi.words}", file=buf)
            print(f"Modified: {fi.mtime_iso}", file=buf)
            print("-" * 40, file=buf)
            print(fi.content, file=buf)
    
    return buf.getvalue()

def render_html(report: ProjectReport, include_contents: bool = True) -> str:
    """Render project report as HTML with modern styling"""
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    root_name = esc(Path(report.root).name)
    
    # Enhanced CSS styling
    css = """
    <style>
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Ubuntu, Arial, sans-serif;
        line-height: 1.6;
        margin: 0;
        padding: 2rem;
        background: #fafafa;
        color: #333;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        padding: 2rem;
    }
    h1 { margin-top: 0; color: #2563eb; border-bottom: 3px solid #2563eb; padding-bottom: 0.5rem; }
    h2 { color: #1f2937; margin-top: 2rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25rem; }
    h3 { color: #374151; margin-top: 1.5rem; }
    .meta { color: #6b7280; font-size: 0.9rem; margin-bottom: 1rem; }
    .summary { background: #f3f4f6; padding: 1rem; border-radius: 6px; margin: 1rem 0; }
    .file-list { list-style: none; padding: 0; }
    .file-item { 
        padding: 0.5rem; 
        margin: 0.25rem 0; 
        background: #f9fafb; 
        border-left: 3px solid #10b981; 
        border-radius: 4px; 
    }
    .file-meta { font-size: 0.85rem; color: #6b7280; margin-left: 1rem; }
    pre { 
        background: #1f2937; 
        color: #f9fafb; 
        border-radius: 6px; 
        padding: 1rem; 
        overflow-x: auto; 
        margin: 1rem 0;
    }
    code { font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace; }
    .content-header { 
        background: #eff6ff; 
        padding: 0.75rem; 
        border-radius: 6px; 
        margin: 1rem 0 0.5rem 0; 
        border-left: 4px solid #3b82f6;
    }
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
    </style>
    """
    
    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Project Structure: {root_name}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    {css}
</head>
<body>
<div class="container">"""
    
    # Header and metadata
    out = [
        head,
        f"<h1>📁 Project Structure: {root_name}</h1>",
        f'<div class="meta">Generated: {esc(report.generated_at)} | Root: <code>{esc(report.root)}</code></div>'
    ]
    
    # Summary section
    total_files = len(report.files)
    total_size = sum(f.size_bytes for f in report.files)
    text_files = sum(1 for f in report.files if f.content is not None)
    
    out.extend([
        '<div class="summary">',
        '<h2>📊 Summary</h2>',
        f'<p><strong>Total Files:</strong> {total_files:,}<br>',
        f'<strong>Text Files:</strong> {text_files:,}<br>',
        f'<strong>Total Size:</strong> {esc(format_size(total_size))}</p>',
        '</div>'
    ])
    
    # File listing as a tree
    out.append('<h2>📁 File Listing</h2><div class="file-list">')

    from collections import defaultdict
    def build_tree(files):
        tree = {}
        for fi in files:
            parts = fi.path.split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node.setdefault("__files__", []).append(fi)
        return tree

    def render_tree(node, prefix=""):
        out = []
        for key in sorted(k for k in node.keys() if k != "__files__"):
            out.append(f'{prefix}<div class="file-item"><span style="color:#2563eb;font-weight:bold;">📁 {esc(key)}/</span></div>')
            out.extend(render_tree(node[key], prefix + "<span style=\"margin-left:2em;display:inline-block;\"></span>"))
        for fi in sorted(node.get("__files__", []), key=lambda f: f.path):
            meta = f"{format_size(fi.size_bytes)}, {fi.lines} lines, {fi.words} words, modified {fi.mtime_iso}"
            emoji = _get_file_emoji(Path(fi.path).suffix.lower())
            out.append(f'{prefix}<div class="file-item">{emoji} <strong>{esc(Path(fi.path).name)}</strong><div class="file-meta">{esc(meta)}</div></div>')
        return out

    tree = build_tree(report.files)
    out.extend(render_tree(tree))
    out.append('</div>')
    
    # File contents
    if include_contents:
        out.append('<h2>📄 File Contents</h2>')
        
        for fi in report.files:
            if fi.content is None:
                continue
                
            emoji = _get_file_emoji(Path(fi.path).suffix.lower())
            meta = f"{fi.lines} lines, {fi.words} words, {format_size(fi.size_bytes)}, modified {fi.mtime_iso}"
            
            out.extend([
                '<hr>',
                f'<h3>{emoji} <code>{esc(fi.path)}</code></h3>',
                f'<div class="content-header">{esc(meta)}</div>',
                f'<pre><code>{esc(fi.content)}</code></pre>'
            ])
    
    out.extend(['</div>', '</body></html>'])
    return "".join(out)

def render_json(report: ProjectReport, include_contents: bool = True) -> str:
    """Render project report as formatted JSON"""
    data = asdict(report)
    
    # Add summary statistics
    data["summary"] = {
        "total_files": len(report.files),
        "text_files": sum(1 for f in report.files if f.content is not None),
        "total_size_bytes": sum(f.size_bytes for f in report.files),
        "total_size_formatted": format_size(sum(f.size_bytes for f in report.files))
    }
    
    if not include_contents:
        for f in data["files"]:
            f["content"] = None
    
    return json.dumps(data, ensure_ascii=False, indent=2)

def write_zip(zip_path: Path, report_text: str, report_name: str, root_path: Path, include_project_copy: bool = False) -> None:
    """Write ZIP archive with report and optionally project files"""
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # Add the report file
            zf.writestr(report_name, report_text)
            
            if include_project_copy:
                # Add project files
                for root, dirs, files in os.walk(root_path):
                    # Filter out excluded directories
                    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
                    
                    rel_dir = os.path.relpath(root, root_path)
                    
                    for filename in files:
                        if filename.startswith('.'):
                            continue
                            
                        full_path = Path(root) / filename
                        
                        # Calculate relative path for archive
                        if rel_dir == ".":
                            rel_path = Path("project") / filename
                        else:
                            rel_path = Path("project") / rel_dir / filename
                        
                        try:
                            # Skip very large files in zip
                            if full_path.stat().st_size > 50 * 1024 * 1024:  # 50MB limit
                                continue
                            zf.write(full_path, arcname=str(rel_path))
                        except (PermissionError, OSError):
                            # Skip files we can't read
                            continue
                            
    except Exception as e:
        raise RuntimeError(f"Failed to create ZIP file: {e}")

def export_report(report: ProjectReport, fmt: OutputFormat, include_contents: bool, save_path: Path, root_path: Path) -> None:
    """Export report in specified format with error handling"""
    try:
        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        if fmt.name == "MARKDOWN":
            text = render_markdown(report, include_contents)
            save_path.write_text(text, encoding="utf-8")
            
        elif fmt.name == "PLAINTEXT":
            text = render_plaintext(report, include_contents)
            save_path.write_text(text, encoding="utf-8")
            
        elif fmt.name == "HTML":
            text = render_html(report, include_contents)
            save_path.write_text(text, encoding="utf-8")
            
        elif fmt.name == "JSON":
            text = render_json(report, include_contents)
            save_path.write_text(text, encoding="utf-8")
            
        elif fmt.name == "ZIP":
            # Ask user about including project files
            include_proj = messagebox.askyesno(
                "ZIP Export Options",
                "Include a copy of the project files in the ZIP archive?\n\n"
                "• Yes: Full backup with report and all project files\n"
                "• No: Report file only\n\n"
                "(Hidden files and excluded directories will be skipped)",
                default="no"
            )
            
            inner_name = f"{Path(root_path).name}_report.md"
            report_text = render_markdown(report, include_contents)
            write_zip(save_path, report_text, inner_name, root_path, include_project_copy=include_proj)
            
        else:
            raise ValueError(f"Unsupported export format: {fmt}")
            
    except PermissionError as e:
        raise RuntimeError(f"Permission denied writing to {save_path}: {e}")
    except OSError as e:
        raise RuntimeError(f"File system error: {e}")
    except Exception as e:
        raise RuntimeError(f"Export failed: {e}")
```

### 📄 `report.py`

**Size:** 1 KB | **Lines:** 49 | **Words:** 146 | **Modified:** 2025-08-10 01:25

```py
# file: report.py
"""Core models, constants, and enums used across the app."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Exclusions and file-type hints
EXCLUDED_DIRS: set[str] = {"__pycache__", ".git", ".svn", ".hg"}
CODE_EXTENSIONS: set[str] = {".py", ".spec", ".txt", ".md", ".json", ".yml", ".yaml"}
MAX_THREADS_FALLBACK = 4

def now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def format_size(size_bytes: int) -> str:
    return f"{max(size_bytes, 0) // 1024} KB"

@dataclass
class FileInfo:
    path: str
    size_bytes: int
    mtime_iso: str
    lines: int | str
    words: int | str
    content: str | None

@dataclass
class ProjectReport:
    root: str
    generated_at: str
    files: list[FileInfo]

class OutputFormat(Enum):
    MARKDOWN = "Markdown (.md)"
    PLAINTEXT = "Plain text (.txt)"
    HTML = "HTML (.html)"
    JSON = "JSON (.json)"
    ZIP = "Zip (.zip)"

    @staticmethod
    def from_label(label: str) -> "OutputFormat":
        for fmt in OutputFormat:
            if fmt.value == label:
                return fmt
        raise ValueError(f"Unknown format: {label}")
```

### 📄 `scan.py`

**Size:** 8 KB | **Lines:** 231 | **Words:** 716 | **Modified:** 2025-08-10 15:58

```py
# file: scan.py
"""Enhanced project scanning with better error handling, progress tracking, and file filtering."""
from __future__ import annotations

import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Tuple, Optional, Callable

from report import (
    CODE_EXTENSIONS,
    EXCLUDED_DIRS,
    MAX_THREADS_FALLBACK,
    FileInfo,
    ProjectReport,
    now_stamp,
)

# Additional file extensions to consider for content reading
READABLE_EXTENSIONS = CODE_EXTENSIONS | {
    ".css", ".js", ".html", ".xml", ".csv", ".ini", ".cfg", ".conf",
    ".log", ".sh", ".bat", ".ps1", ".sql", ".dockerfile", ".gitignore",
    ".env", ".properties", ".toml", ".rst", ".tex", ".makefile"
}

# Maximum file size to read (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024

def _is_text_file(file_path: Path) -> bool:
    """Check if a file is likely to be text-based"""
    ext = file_path.suffix.lower()
    if ext in READABLE_EXTENSIONS:
        return True
    
    # Check for files without extensions that might be text
    if not ext and file_path.name.lower() in {
        'readme', 'license', 'changelog', 'makefile', 'dockerfile'
    }:
        return True
    
    return False

def _read_file_counts(file_path: Path) -> Tuple[Path, int | str, int | str, str]:
    """Read file and count lines/words with enhanced error handling"""
    try:
        # Check file size before reading
        stat_result = file_path.stat()
        if stat_result.st_size > MAX_FILE_SIZE:
            return file_path, "large", "large", ""
        
        # Try to read as text
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        if not content.strip():  # Empty file
            return file_path, 0, 0, ""
        
        lines = content.count("\n") + 1 if content else 0
        words = len(content.split()) if content else 0
        
        return file_path, lines, words, content
        
    except (PermissionError, OSError):
        return file_path, "denied", "denied", ""
    except UnicodeDecodeError:
        # File is likely binary
        return file_path, "binary", "binary", ""
    except Exception:
        return file_path, "error", "error", ""

def _is_hidden_or_excluded(name: str) -> bool:
    """Check if a file/directory should be excluded"""
    return (name.startswith('.') or 
            name in EXCLUDED_DIRS or
            name.lower() in {'thumbs.db', 'desktop.ini', '.ds_store'})

def scan_project(root_path: Path, progress_callback: Optional[Callable[[str], None]] = None) -> ProjectReport:
    """
    Scan a project directory and build a comprehensive report.
    
    Args:
        root_path: Root directory to scan
        progress_callback: Optional callback for progress updates
        
    Returns:
        ProjectReport with file information and content
    """
    if progress_callback:
        progress_callback("Starting project scan...")
    
    files: list[FileInfo] = []
    readable_paths: list[Path] = []
    total_size = 0
    
    # Walk directory tree
    try:
        for root, dirs, filenames in os.walk(root_path, followlinks=False):
            # Filter directories to skip hidden/excluded ones
            dirs[:] = [d for d in dirs if not _is_hidden_or_excluded(d)]
            
            for filename in filenames:
                if _is_hidden_or_excluded(filename):
                    continue
                    
                file_path = Path(root) / filename
                
                try:
                    stat_result = file_path.stat(follow_symlinks=False)
                    
                    # Skip if it's a symbolic link
                    if file_path.is_symlink():
                        continue
                        
                    # Skip very large files (>100MB) entirely
                    if stat_result.st_size > 100 * 1024 * 1024:
                        continue
                    
                    mtime = datetime.datetime.fromtimestamp(stat_result.st_mtime).strftime("%Y-%m-%d %H:%M")
                    relative_path = file_path.relative_to(root_path)
                    
                    fi = FileInfo(
                        path=str(relative_path),
                        size_bytes=stat_result.st_size,
                        mtime_iso=mtime,
                        lines="?",
                        words="?",
                        content=None,
                    )
                    files.append(fi)
                    total_size += stat_result.st_size
                    
                    # Add to readable files if it's a text file
                    if _is_text_file(file_path):
                        readable_paths.append(file_path)
                        
                except (PermissionError, OSError, ValueError):
                    # Skip files we can't access or process
                    continue
                    
    except (PermissionError, OSError) as e:
        raise RuntimeError(f"Cannot access project directory: {e}")
    
    if progress_callback:
        progress_callback(f"Found {len(files)} files, reading {len(readable_paths)} text files...")
    
    # Read file contents in parallel for text files
    if readable_paths:
        max_threads = min(len(readable_paths), os.cpu_count() or MAX_THREADS_FALLBACK)
        counts_map: dict[Path, tuple[int | str, int | str, str]] = {}
        
        try:
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                # Submit all tasks
                future_to_path = {
                    executor.submit(_read_file_counts, path): path 
                    for path in readable_paths
                }
                
                completed = 0
                for future in as_completed(future_to_path):
                    path, lines, words, content = future.result()
                    counts_map[path] = (lines, words, content)
                    
                    completed += 1
                    if progress_callback and completed % 10 == 0:
                        progress_callback(f"Read {completed}/{len(readable_paths)} files...")
                        
        except Exception as e:
            if progress_callback:
                progress_callback(f"Warning: Error reading some files: {e}")
        
        # Update file info with counts and content
        for fi in files:
            full_path = root_path / fi.path
            if full_path in counts_map:
                lines, words, content = counts_map[full_path]
                fi.lines = lines
                fi.words = words
                fi.content = content
    
    # Sort files by path for consistent output
    files.sort(key=lambda f: f.path.lower())
    
    if progress_callback:
        progress_callback("Scan complete!")
    
    return ProjectReport(
        root=str(root_path),
        generated_at=now_stamp(),
        files=files
    )

def get_project_stats(root_path: Path) -> dict:
    """Get quick stats about a project without full scanning"""
    stats = {
        'total_files': 0,
        'text_files': 0,
        'total_size': 0,
        'directories': 0
    }
    
    try:
        for root, dirs, filenames in os.walk(root_path):
            dirs[:] = [d for d in dirs if not _is_hidden_or_excluded(d)]
            stats['directories'] += len(dirs)
            
            for filename in filenames:
                if _is_hidden_or_excluded(filename):
                    continue
                    
                file_path = Path(root) / filename
                try:
                    if file_path.is_symlink():
                        continue
                        
                    size = file_path.stat().st_size
                    stats['total_files'] += 1
                    stats['total_size'] += size
                    
                    if _is_text_file(file_path):
                        stats['text_files'] += 1
                        
                except (PermissionError, OSError):
                    continue
                    
    except (PermissionError, OSError):
        pass
    
    return stats
```

