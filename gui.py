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

from report import OutputFormat, EXCLUDED_DIRS, ProjectReport
from scan import scan_project, is_content_readable
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
        self.node_states: dict[str, bool | None] = {}
        self.node_labels: dict[str, str] = {}
        self.tree_ready = False
        self._tree_build_id = 0
        self._tree_file_total = 0
        self._tree_root_id = "D:ROOT"
        self.format_extensions: dict[OutputFormat, str] = {
            OutputFormat.MARKDOWN: ".md",
            OutputFormat.PLAINTEXT: ".txt",
            OutputFormat.HTML: ".html",
            OutputFormat.JSON: ".json",
            OutputFormat.ZIP: ".zip",
        }

        # Setup UI
        self._setup_ui()
        self._update_tree_enable_state()
        self._center_window()
        
        # Load last source folder if available
        if self.config.last_source_folder and Path(self.config.last_source_folder).exists():
            self.folder_path = Path(self.config.last_source_folder)
            self.path_label.configure(text=str(self.folder_path))
            self.status_var.set("Scanning folder for files...")
            self._quick_scan()
            self._schedule_tree_build()

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

        # File selection tree for content inclusion
        tree_frame = ttk.LabelFrame(main_frame, text="File Content Selection", padding=8)
        tree_frame.pack(fill="both", expand=True, pady=(0, 8))

        self.tree_message = ttk.Label(
            tree_frame,
            text="Select a project folder to preview file contents.",
            font=("TkDefaultFont", 9)
        )
        self.tree_message.pack(anchor="w", pady=(0, 6))

        tree_container = ttk.Frame(tree_frame)
        tree_container.pack(fill="both", expand=True)

        self.file_tree = ttk.Treeview(
            tree_container,
            show="tree",
            selectmode="none"
        )
        self.file_tree.column("#0", stretch=True, minwidth=200, width=260)
        self.file_tree.pack(side="left", fill="both", expand=True)

        tree_scroll_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.file_tree.yview)
        tree_scroll_y.pack(side="right", fill="y")
        self.file_tree.configure(yscrollcommand=tree_scroll_y.set)

        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.file_tree.xview)
        tree_scroll_x.pack(fill="x", pady=(6, 0))
        self.file_tree.configure(xscrollcommand=tree_scroll_x.set)

        self.file_tree.bind("<Double-1>", self._on_tree_double_click)

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
        self._schedule_tree_build()
        
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

    def _clear_tree(self, message: str) -> None:
        """Reset the file selection tree and show a message."""
        if not hasattr(self, "file_tree") or self.file_tree is None:
            return
        for child in self.file_tree.get_children():
            self.file_tree.delete(child)
        self.node_states.clear()
        self.node_labels.clear()
        self.tree_ready = False
        self._tree_file_total = 0
        try:
            self.file_tree.state(("disabled",))
        except Exception:
            pass
        self.tree_message.configure(text=message)

    def _schedule_tree_build(self) -> None:
        """Begin asynchronous build of the file selection tree."""
        if not hasattr(self, "file_tree") or self.file_tree is None:
            return

        if self.folder_path is None:
            self._clear_tree("Select a project folder to preview file contents.")
            return

        self._tree_build_id += 1
        request_id = self._tree_build_id
        self._clear_tree("Building file preview...")
        target_path = self.folder_path

        def worker() -> None:
            try:
                dirs_map, files_map, total_files = self._gather_tree_snapshot(target_path)
            except Exception as exc:
                self.after(0, lambda: self._handle_tree_failure(str(exc), request_id))
                return
            self.after(0, lambda: self._populate_tree(dirs_map, files_map, total_files, request_id))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_tree_failure(self, error: str, request_id: int) -> None:
        """Display a friendly message if the tree build fails."""
        if request_id != self._tree_build_id:
            return
        truncated = (error[:120] + "...") if len(error) > 120 else error
        print(f"[TREE BUILD ERROR] {error}")
        self._clear_tree(f"Unable to build file preview: {truncated}")

    def _gather_tree_snapshot(self, root_path: Path) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
        """Collect directory/file relationships for readable files under the root."""
        readable_files: list[str] = []

        for current_root, dirs, files in os.walk(root_path, followlinks=False):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]

            for filename in files:
                if filename.startswith('.'):
                    continue

                full_path = Path(current_root) / filename

                try:
                    if full_path.is_symlink():
                        continue
                    if not is_content_readable(full_path):
                        continue
                except Exception:
                    continue

                try:
                    rel_path = full_path.relative_to(root_path).as_posix()
                except ValueError:
                    continue

                readable_files.append(rel_path)

        readable_files.sort()

        directories: set[str] = {""}
        for rel_path in readable_files:
            parts = rel_path.split('/')
            for idx in range(1, len(parts)):
                directories.add('/'.join(parts[:idx]))

        dirs_map: dict[str, list[str]] = {key: [] for key in directories}
        files_map: dict[str, list[str]] = {key: [] for key in directories}

        for directory in directories:
            if not directory:
                continue
            parent = directory.rsplit('/', 1)[0] if '/' in directory else ''
            dirs_map.setdefault(parent, []).append(directory)

        for rel_path in readable_files:
            parent = rel_path.rsplit('/', 1)[0] if '/' in rel_path else ''
            files_map.setdefault(parent, []).append(rel_path)

        for key in dirs_map:
            dirs_map[key].sort()
        for key in files_map:
            files_map[key].sort()

        return dirs_map, files_map, len(readable_files)

    def _populate_tree(
        self,
        dirs_map: dict[str, list[str]],
        files_map: dict[str, list[str]],
        total_files: int,
        request_id: int
    ) -> None:
        """Populate the UI tree with the gathered snapshot."""
        if request_id != self._tree_build_id:
            return

        if not hasattr(self, "file_tree") or self.file_tree is None:
            return

        for child in self.file_tree.get_children():
            self.file_tree.delete(child)

        self.node_states.clear()
        self.node_labels.clear()
        self.tree_ready = True
        self._tree_file_total = total_files

        root_label = f"{self.folder_path.name}/" if self.folder_path is not None else "Project/"
        self.node_labels[self._tree_root_id] = root_label
        self.node_states[self._tree_root_id] = True
        self.file_tree.insert(
            "",
            "end",
            iid=self._tree_root_id,
            text=f"{self._checkbox_prefix(True)} {root_label}",
            open=True
        )

        self._insert_tree_children(self._tree_root_id, "", dirs_map, files_map)

        if total_files == 0:
            self.tree_message.configure(text="No text-readable files found to include.")
        elif self.include_var.get():
            self.tree_message.configure(text="Double-click entries to include file contents in the export.")
        else:
            self.tree_message.configure(text="Enable 'Include file contents' to make selections.")

        self._update_tree_enable_state()

    def _insert_tree_children(
        self,
        parent_item: str,
        directory_key: str,
        dirs_map: dict[str, list[str]],
        files_map: dict[str, list[str]]
    ) -> None:
        """Insert directory and file nodes beneath the given parent."""
        for dir_key in dirs_map.get(directory_key, []):
            name = dir_key.split('/')[-1] if '/' in dir_key else dir_key
            label = f"{name}/"
            item_id = f"D:{dir_key}" if dir_key else self._tree_root_id
            if item_id == self._tree_root_id:
                continue
            self.node_labels[item_id] = label
            self.node_states[item_id] = True
            self.file_tree.insert(
                parent_item,
                "end",
                iid=item_id,
                text=f"{self._checkbox_prefix(True)} {label}",
                open=False
            )
            self._insert_tree_children(item_id, dir_key, dirs_map, files_map)

        for file_key in files_map.get(directory_key, []):
            name = file_key.split('/')[-1]
            item_id = f"F:{file_key}"
            self.node_labels[item_id] = name
            self.node_states[item_id] = True
            self.file_tree.insert(
                parent_item,
                "end",
                iid=item_id,
                text=f"{self._checkbox_prefix(True)} {name}"
            )

    def _checkbox_prefix(self, state: bool | None) -> str:
        """Return the ASCII checkbox representation for a node state."""
        if state is True:
            return "[x]"
        if state is False:
            return "[ ]"
        return "[~]"

    def _update_tree_item_text(self, item_id: str) -> None:
        """Refresh the displayed text for a tree node."""
        label = self.node_labels.get(item_id, "")
        state = self.node_states.get(item_id, False)
        self.file_tree.item(item_id, text=f"{self._checkbox_prefix(state)} {label}")

    def _set_children_state(self, parent_id: str, state: bool) -> None:
        """Apply a state to all descendant nodes."""
        for child_id in self.file_tree.get_children(parent_id):
            self.node_states[child_id] = state
            self._update_tree_item_text(child_id)
            self._set_children_state(child_id, state)

    def _update_parent_state(self, item_id: str) -> None:
        """Update parent nodes to reflect their children's combined state."""
        parent_id = self.file_tree.parent(item_id)
        if not parent_id:
            return

        child_states = [self.node_states.get(child) for child in self.file_tree.get_children(parent_id)]
        if child_states and all(state is True for state in child_states):
            parent_state: bool | None = True
        elif child_states and all(state is False for state in child_states):
            parent_state = False
        else:
            parent_state = None

        self.node_states[parent_id] = parent_state
        self._update_tree_item_text(parent_id)
        self._update_parent_state(parent_id)

    def _toggle_tree_node(self, item_id: str) -> None:
        """Toggle a node's selection state and propagate the change."""
        if item_id not in self.node_states:
            return

        current = self.node_states[item_id]
        target = True if current is None else not current

        self.node_states[item_id] = target
        self._update_tree_item_text(item_id)
        self._set_children_state(item_id, target)
        self._update_parent_state(item_id)

    def _on_tree_double_click(self, event):
        """Handle double-click events to toggle checkbox states."""
        if not self.include_var.get() or not self.tree_ready:
            return

        try:
            if "disabled" in self.file_tree.state():
                return
        except Exception:
            pass

        item_id = self.file_tree.identify_row(event.y)
        if not item_id:
            item_id = self.file_tree.focus()
        if not item_id:
            return

        self._toggle_tree_node(item_id)

        # Mirror the default Treeview behavior: double-click toggles expansion
        if self.file_tree.get_children(item_id):
            current_open = bool(self.file_tree.item(item_id, "open"))
            self.file_tree.item(item_id, open=not current_open)
        return "break"

    def _update_tree_enable_state(self) -> None:
        """Enable or disable the treeview based on current options."""
        if not hasattr(self, "file_tree") or self.file_tree is None:
            return

        if not self.include_var.get() or not self.tree_ready or self._tree_file_total == 0:
            try:
                self.file_tree.state(("disabled",))
            except Exception:
                pass
            if self.tree_ready and self._tree_file_total and not self.include_var.get():
                self.tree_message.configure(text="Enable 'Include file contents' to make selections.")
            return

        try:
            self.file_tree.state(("!disabled",))
        except Exception:
            pass

        if self.tree_ready and self._tree_file_total:
            self.tree_message.configure(text="Double-click entries to include file contents in the export.")

    def _get_selected_file_paths(self) -> set[str] | None:
        """Return selected file paths, or None if no tree snapshot is available."""
        if not self.include_var.get():
            return set()
        if not self.tree_ready or not self.node_states:
            return None

        selected: set[str] = set()
        for node_id, state in self.node_states.items():
            if not node_id.startswith("F:"):
                continue
            if state is True:
                selected.add(node_id[2:])
        return selected

    def _resolve_format_from_suffix(self, suffix: str) -> Optional[OutputFormat]:
        """Map a file suffix to a known output format, if possible."""
        normalized = suffix.lower()
        for fmt, ext in self.format_extensions.items():
            if normalized == ext:
                return fmt
        return None

    def _apply_content_selection(self, report: ProjectReport, selected: set[str] | None) -> None:
        """Drop file contents that are not selected for inclusion."""
        if selected is None:
            return

        if not selected:
            for fi in report.files:
                fi.content = None
            return

        allowed = set(selected)
        for fi in report.files:
            if fi.content is None:
                continue
            normalized = fi.path.replace(os.sep, "/")
            if normalized not in allowed:
                fi.content = None

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
        self._update_tree_enable_state()

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
        elif self.folder_path:
            self._suggest_placeholder_filename()

    def on_choose_save(self) -> None:
        """Handle save destination selection"""
        if not self.folder_path:
            messagebox.showwarning("No Folder Selected", 
                                 "Please select a project folder first.")
            return

        fmt = OutputFormat.from_label(self.fmt_var.get())
        current_ext = self.format_extensions[fmt]
        default_name = f"{self.folder_path.name}_report{current_ext}"

        ordered_formats = [fmt] + [f for f in OutputFormat if f != fmt]
        filetypes = [
            (f_option.value, f"*{self.format_extensions[f_option]}")
            for f_option in ordered_formats
        ]
        filetypes.append(("All files", "*.*"))

        # Use last save folder as initial directory if available
        initial_dir = None
        if self.config.last_save_folder and Path(self.config.last_save_folder).exists():
            initial_dir = self.config.last_save_folder
        
        save_path_str = filedialog.asksaveasfilename(
            title=f"Save {fmt.value} Report",
            defaultextension=current_ext,
            initialfile=default_name,
            initialdir=initial_dir,
            filetypes=filetypes,
            parent=self
        )

        if save_path_str:
            self.save_path = Path(save_path_str)
            self.save_label.configure(text=str(self.save_path))
            # Update format selection if user picked a different extension
            selected_fmt = self._resolve_format_from_suffix(self.save_path.suffix)
            if selected_fmt and selected_fmt != fmt:
                self.fmt_var.set(selected_fmt.value)
                self.combo.set(selected_fmt.value)
                self.on_format_changed()
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
        new_ext = self.format_extensions[fmt]
        new_path = self.save_path.with_suffix(new_ext)
        self.save_path = new_path
        self.save_label.configure(text=str(self.save_path))

    def _suggest_placeholder_filename(self) -> None:
        """Show a suggested filename when no save path is chosen yet."""
        if self.save_path is not None or not self.folder_path:
            return

        fmt = OutputFormat.from_label(self.fmt_var.get())
        suggested = self.folder_path.with_suffix("")
        placeholder = suggested.name + "_report" + self.format_extensions[fmt]
        self.save_label.configure(text=placeholder)

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
        selected_paths = self._get_selected_file_paths() if include else None

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

                if include:
                    self._apply_content_selection(report, selected_paths)
                
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
