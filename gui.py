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
import subprocess
import sys
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
        self.folder_path = None
        self.save_path = None
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

        # Load last save file if available
        if self.config.last_save_file:
            self.save_path = Path(self.config.last_save_file)
            self.save_label.configure(text=str(self.save_path))

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

        self.quit_btn = ttk.Button(button_frame, text="Quit", command=self.on_quit)
        self.quit_btn.pack(side="right", padx=(10, 0))

        self.export_btn = ttk.Button(button_frame, text="Start Export", 
                command=self.on_export, state="disabled")
        self.export_btn.pack(side="right", padx=(0, 10))

        # Recover button
        self.recover_btn = ttk.Button(button_frame, text="Recover Project", command=self.on_recover)
        self.recover_btn.pack(side="right", padx=(0, 10))
    def on_recover(self) -> None:
        """Handle recovery of files from a report file via recover.py"""
        # Ask user to select a report file
        report_path = filedialog.askopenfilename(
            title="Select Report File to Recover From",
            filetypes=[
                ("Report Files", "*.md *.txt *.html *.json"),
                ("All Files", "*.*")
            ]
        )
        if not report_path:
            return
        # Ask user for output directory
        output_dir = filedialog.askdirectory(
            title="Select Output Directory for Recovery (will create subfolder)",
        )
        if not output_dir:
            return
        self.status_var.set("Recovering project from report... (see terminal for details)")

        def run_recover():
            try:
                # Run recover.py as a subprocess so it works even if run as packaged app
                cmd = [sys.executable, "recover.py", report_path, output_dir]
                result = subprocess.run(cmd, cwd=os.path.dirname(__file__), capture_output=True, text=True)
                # Print all output to terminal/debug console for debugging
                print("[RECOVER STDOUT]\n" + (result.stdout or ""))
                print("[RECOVER STDERR]\n" + (result.stderr or ""))
                if result.returncode == 0:
                    self.status_var.set("Recovery complete. See output directory.")
                    messagebox.showinfo("Recovery Complete", f"Project recovered to: {output_dir}")
                else:
                    self.status_var.set("Recovery failed. See terminal for details.")
                    messagebox.showerror("Recovery Failed", result.stderr or result.stdout)
            except Exception as e:
                self.status_var.set("Recovery failed.")
                print(f"[RECOVER EXCEPTION] {e}")
                messagebox.showerror("Recovery Failed", str(e))

        threading.Thread(target=run_recover, daemon=True).start()
        
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
            # Save to config (folder and file)
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