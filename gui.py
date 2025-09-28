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

from report import EXCLUDED_DIRS, ProjectReport, format_size
from scan import scan_project, is_content_readable
from exporters.base import ExporterRegistry
from analysis import AnalysisEngine
import subprocess
import sys
from config import ConfigManager


class CollapsibleSection(ttk.Frame):
    """Simple collapsible container with a header button."""

    def __init__(self, master, title: str, initially_open: bool = True, expand_on_open: bool = False) -> None:
        super().__init__(master)
        self._title = title
        self._open = initially_open
        self._expand_on_open = expand_on_open
        self.columnconfigure(0, weight=1)

        self._button = ttk.Button(self, text=self._header_text(), command=self.toggle, style="Collapsible.TButton")
        self._button.grid(row=0, column=0, sticky="ew")

        self.body = ttk.Frame(self)
        if initially_open:
            self.body.grid(row=1, column=0, sticky="nsew")
        self.after(0, self._apply_pack_state)

    def _header_text(self) -> str:
        arrow = "▼" if self._open else "▶"
        return f"{arrow} {self._title}"

    def toggle(self) -> None:
        self._open = not self._open
        if self._open:
            self.body.grid(row=1, column=0, sticky="nsew")
        else:
            self.body.grid_remove()
        self._button.configure(text=self._header_text())
        self._apply_pack_state()
        # Look for callback on the root window (ExportApp instance)
        root = self.winfo_toplevel()
        if hasattr(root, '_section_toggle_callback'):
            callback = getattr(root, '_section_toggle_callback', None)
            if callable(callback):
                try:
                    callback()
                except Exception:
                    pass

    def _apply_pack_state(self) -> None:
        if self.winfo_manager() == "pack":
            expand_value = 1 if (self._open and self._expand_on_open) else 0
            try:
                self.pack_configure(expand=expand_value)
            except Exception:
                pass

class ExportApp(Tk):
    FILE_ICON_MAP: dict[str, str] = {
        ".py": "🐍", ".pyw": "🐍", ".spec": "🛠️",
        ".txt": "📄", ".md": "📝", ".rst": "📄",
        ".json": "📋", ".yml": "⚙️", ".yaml": "⚙️",
        ".toml": "⚙️", ".ini": "⚙️", ".cfg": "⚙️",
        ".html": "🌐", ".htm": "🌐", ".css": "🎨",
        ".js": "🟨", ".jsx": "🟨", ".ts": "🟦", ".tsx": "🟦",
        ".sql": "🗄️", ".csv": "📊", ".log": "📜",
        ".sh": "⚡", ".bat": "⚡", ".ps1": "⚡",
        ".env": "🔒", ".dockerfile": "🐳",
        ".go": "🐹", ".java": "☕",
        ".c": "💾", ".h": "💾", ".cpp": "💾", ".hpp": "💾",
        ".rs": "🦀", ".swift": "🕊️",
        ".kt": "🧡", ".kts": "🧡",
        ".php": "🐘", ".rb": "💎",
        ".dart": "🎯",
    }

    def __init__(self) -> None:
        super().__init__()

        # Load configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()

        self.title("🐍 Python Project Helper v2.0")
        
        # Configure modern styling
        style = ttk.Style(self)
        
        # Choose a theme that allows better customization
        available_themes = style.theme_names()
        if 'clam' in available_themes:  # Best for customization
            style.theme_use('clam')
        elif 'default' in available_themes:  # Fallback
            style.theme_use('default')
        else:
            style.theme_use(available_themes[0])
        
        # Configure high contrast colors for maximum readability
        bg_color = "#ffffff"  # Pure white background
        accent_color = "#0066cc"  # Slightly darker blue
        text_color = "#000000"  # Pure black text for maximum contrast
        secondary_text_color = "#333333"  # Very dark gray for secondary text
        border_color = "#cccccc"
        
        # Main window styling
        self.configure(bg=bg_color)
        
        # Button styles
        style.configure("Modern.TButton", 
                       background=accent_color,
                       foreground="white",
                       borderwidth=0,
                       focuscolor="none",
                       padding=(12, 8))
        style.map("Modern.TButton",
                 background=[('active', '#005a9e'), ('pressed', '#004080')])
        
        style.configure("Secondary.TButton",
                       background="#6c757d",
                       foreground="white", 
                       borderwidth=0,
                       focuscolor="none",
                       padding=(10, 6))
        style.map("Secondary.TButton",
                 background=[('active', '#545b62'), ('pressed', '#3d4348')])
        
        style.configure("Collapsible.TButton", 
                       anchor="w", 
                       padding=(12, 8),
                       background="#f0f0f0",
                       foreground=text_color,
                       borderwidth=2,
                       relief="solid",
                       font=("Helvetica", 11, "bold"))
        style.map("Collapsible.TButton",
                 background=[('active', '#e0e0e0')],
                 foreground=[('active', text_color)])
        
        # Frame styles
        style.configure("Card.TFrame",
                       background="white",
                       borderwidth=1,
                       relief="solid")
        
        # Label styles with maximum contrast
        style.configure("Heading.TLabel",
                       background=bg_color,
                       foreground=text_color,
                       font=("Helvetica", 16, "bold"))
        
        style.configure("Subheading.TLabel",
                       background="white",
                       foreground=text_color,
                       font=("Helvetica", 12, "bold"))
        
        style.configure("Body.TLabel",
                       background="white",
                       foreground=text_color,
                       font=("Helvetica", 11))
        
        # Entry and Combobox styles
        style.configure("Modern.TCombobox",
                       fieldbackground="white",
                       foreground=text_color,
                       borderwidth=2,
                       relief="solid",
                       font=("Helvetica", 11))
        
        # Progress bar style
        style.configure("Modern.Horizontal.TProgressbar",
                       background=accent_color,
                       troughcolor="#e9ecef",
                       borderwidth=0,
                       lightcolor=accent_color,
                       darkcolor=accent_color)
        
        # Treeview style with better contrast
        style.configure("Modern.Treeview",
                       background="white",
                       foreground=text_color,
                       fieldbackground="white",
                       borderwidth=1,
                       relief="solid")
        style.configure("Modern.Treeview.Heading",
                       background="#f8f9fa",
                       foreground=text_color,
                       relief="flat")
        
        # Checkbutton style with better contrast
        style.configure("Body.TCheckbutton",
                       background="white",
                       foreground=text_color,
                       font=("Helvetica", 11, "normal"),
                       focuscolor="none")

        # Set modern window geometry
        min_width, min_height = 900, 700
        default_width, default_height = 1200, 900
        
        if self.config.window_x is not None and self.config.window_y is not None:
            width = max(self.config.window_width, min_width)
            height = max(self.config.window_height, min_height)
            self.geometry(f"{width}x{height}+{self.config.window_x}+{self.config.window_y}")
        else:
            self.geometry(f"{default_width}x{default_height}")
        
        self.resizable(True, True)
        self.minsize(min_width, min_height)

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
        self.node_icons: dict[str, str] = {}
        self.tree_ready = False
        self._tree_build_id = 0
        self._tree_file_total = 0
        self._tree_root_id = "D:ROOT"
        self.node_file_sizes: dict[str, int] = {}
        
        # Initialize exporter registry and get available formats
        self.registry = ExporterRegistry()
        self.available_formats = self._get_available_formats()
        self.format_extensions = self._build_format_extensions()
        self.deep_option_defaults: dict[str, bool] = {
            "include_functions": True,
            "include_classes": True,
            "include_api_index": True,
            "include_dependency_map": True,
            "include_call_graph": True,
            "include_cli_inventory": True,
            "include_config_schema": True,
            "include_ui_catalogue": True,
            "include_tests": True,
            "include_string_catalogue": True,
            "include_binary_manifest": True,
            "include_llm_bundle": True,
        }
        saved_deep_options = self.config_manager.get_deep_options()
        self.deep_option_vars: dict[str, BooleanVar] = {
            key: BooleanVar(value=saved_deep_options.get(key, default))
            for key, default in self.deep_option_defaults.items()
        }

        # Setup UI
        self._setup_ui()
        self._update_deep_controls_visibility()
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
            # Clean up any malformed filenames from previous versions
            if '.lrc.lrc' in str(self.save_path) or str(self.save_path).count('.lrc') > 1:
                fmt_name = self._format_name_from_display(self.fmt_var.get())
                if fmt_name and fmt_name in self.format_extensions:
                    self.save_path = self._replace_extension_properly(self.save_path, self.format_extensions[fmt_name])
            self.save_label.configure(text=str(self.save_path))
            self._align_save_path_with_format(persist=True)

        self._recalculate_minimum_height()

    def _get_available_formats(self) -> list[dict[str, str]]:
        """Get available export formats from the registry."""
        formats = []
        # Define friendly display names for each format
        format_display_names = {
            'basic-json': '📋 Basic JSON - Analysis Only',
            'basic-markdown': '📝 Basic Markdown - Analysis Only', 
            'llm-tds': '🤖 LLM Optimised - Compressed',
            'full-content-json': '📦 Complete JSON - With Source Code',
            'full-content-markdown': '📄 Complete Markdown - With Source Code',
            'legacy-html': '🌐 Styled HTML - With Source Code'
        }
        
        for name in self.registry.list_formats():
            exporter_class = self.registry.get(name)
            if exporter_class:
                exporter = exporter_class()
                # Get file extension from exporter
                ext = self._guess_extension(exporter.mimetype())
                display_name = format_display_names.get(name, f"{name.title().replace('-', ' ')} ({ext})")
                
                formats.append({
                    'name': name,
                    'display': display_name,
                    'extension': ext,
                    'mimetype': exporter.mimetype(),
                    'llm_friendly': exporter.is_llm_friendly(),
                    'lossless': exporter.is_lossless(),
                    'has_source_code': name.startswith('full-content') or name == 'legacy-html'
                })
        return formats

    def _guess_extension(self, mimetype: str) -> str:
        """Guess file extension from MIME type."""
        if mimetype == 'application/json':
            return '.json'
        elif mimetype == 'text/markdown':
            return '.md'
        elif mimetype == 'text/plain':
            return '.txt'
        elif mimetype == 'text/html':
            return '.html'
        else:
            return '.txt'

    def _build_format_extensions(self) -> dict[str, str]:
        """Build format name to extension mapping."""
        return {fmt['name']: fmt['extension'] for fmt in self.available_formats}

    def _format_from_name(self, name: str) -> dict[str, str] | None:
        """Get format info by name."""
        for fmt in self.available_formats:
            if fmt['name'] == name:
                return fmt
        return None

    def _format_name_from_display(self, display: str) -> str | None:
        """Get format name from display string."""
        for fmt in self.available_formats:
            if fmt['display'] == display:
                return fmt['name']
        return None

    def _display_from_name(self, name: str) -> str | None:
        """Get display string from format name."""
        for fmt in self.available_formats:
            if fmt['name'] == name:
                return fmt['display']
        return None

    def _setup_ui(self) -> None:
        """Setup the complete user interface with modern design"""
        
        # Create main container with modern styling
        main_container = ttk.Frame(self, style="Card.TFrame")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # App header
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill="x", pady=(0, 20))
        
        title_label = ttk.Label(header_frame, 
                               text="🐍 Python Project Helper",
                               style="Heading.TLabel")
        title_label.pack(side="left")
        
        subtitle_label = ttk.Label(header_frame,
                                  text="Export your Python projects in multiple formats",
                                  style="Body.TLabel")
        subtitle_label.pack(side="left", padx=(15, 0), pady=(5, 0))
        
        # Main content area with better spacing
        main_frame = ttk.Frame(main_container)
        main_frame.pack(fill="both", expand=True)
        
        # Store the callback reference for sections
        self._section_toggle_callback = self._recalculate_minimum_height

        # Project selection section with modern card design
        project_section = CollapsibleSection(main_frame, "📁 Project Selection")
        project_section.pack(fill="x", pady=(0, 15))
        project_inner = ttk.Frame(project_section.body, style="Card.TFrame", padding=20)
        project_inner.pack(fill="x", padx=5, pady=5)

        # Project folder selection with modern layout
        folder_label = ttk.Label(project_inner, text="Select your Python project folder:", 
                                style="Subheading.TLabel")
        folder_label.pack(anchor="w", pady=(0, 10))

        folder_frame = ttk.Frame(project_inner)
        folder_frame.pack(fill="x", pady=(0, 15))

        self.path_label = ttk.Label(folder_frame, text="No folder selected",
                                   relief="solid", borderwidth=2,
                                   background="white", foreground="#000000",
                                   font=("Helvetica", 11),
                                   anchor="w", padding=(12, 8))
        self.path_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browse_btn = ttk.Button(folder_frame, text="📂 Browse",
                                    style="Modern.TButton",
                                    command=self.on_browse)
        self.browse_btn.pack(side="right")

        # File count with icon
        self.count_label = ttk.Label(project_inner, text="📊 Files found: 0",
                                    style="Body.TLabel")
        self.count_label.pack(anchor="w")

        # Export options section with modern styling
        options_section = CollapsibleSection(main_frame, "⚙️ Export Options")
        options_section.pack(fill="x", pady=(0, 15))
        options_inner = ttk.Frame(options_section.body, style="Card.TFrame", padding=20)
        options_inner.pack(fill="x", padx=5, pady=5)

        # Format selection with modern layout
        format_label = ttk.Label(options_inner, text="Choose output format:", 
                                style="Subheading.TLabel")
        format_label.pack(anchor="w", pady=(0, 10))

        format_frame = ttk.Frame(options_inner)
        format_frame.pack(fill="x", pady=(0, 15))

        self.combo = ttk.Combobox(format_frame, textvariable=self.fmt_var,
                                 state="readonly", width=35,
                                 style="Modern.TCombobox",
                                 font=("Helvetica", 11),
                                 values=[f['display'] for f in self.available_formats])
        self.combo.pack(side="left", pady=(0, 0))
        self.combo.bind('<<ComboboxSelected>>', self.on_format_changed)

        # Format description
        self.format_description = ttk.Label(format_frame,
                                          text="",
                                          style="Body.TLabel",
                                          foreground="#666666",
                                          font=("Helvetica", 10))
        self.format_description.pack(fill="x", pady=(8, 0))

        # Content inclusion option
        content_frame = ttk.Frame(options_inner)
        content_frame.pack(fill="x", pady=(0, 15))

        self.content_check = ttk.Checkbutton(content_frame,
                                           text="📄 Include file contents in export",
                                           variable=self.include_var,
                                           style="Body.TCheckbutton",
                                           command=self._on_content_changed)
        self.content_check.pack(anchor="w")

        # Help text with better styling
        help_text = ttk.Label(options_inner,
                             text="💡 Including contents creates detailed reports but larger files",
                             style="Body.TLabel",
                             foreground="#333333")
        help_text.pack(anchor="w")

        self.deep_options_frame = ttk.LabelFrame(options_inner, text="Deep Analysis Details", padding=8)
        self.deep_option_checks: dict[str, ttk.Checkbutton] = {}
        deep_option_specs = [
            ("include_functions", "Include function signatures"),
            ("include_classes", "Include class signatures"),
            ("include_api_index", "Include API index"),
            ("include_dependency_map", "Include dependency map"),
            ("include_call_graph", "Include call graph"),
            ("include_cli_inventory", "Include CLI inventory"),
            ("include_config_schema", "Include config schema"),
            ("include_ui_catalogue", "Include UI catalogue"),
            ("include_tests", "Include test surface"),
            ("include_string_catalogue", "Include string catalogue"),
            ("include_binary_manifest", "Include asset manifest"),
            ("include_llm_bundle", "Include LLM bundle JSON"),
        ]
        for idx, (key, label) in enumerate(deep_option_specs):
            variable = self.deep_option_vars[key]
            chk = ttk.Checkbutton(
                self.deep_options_frame,
                text=label,
                variable=variable,
                command=self._on_deep_option_changed,
            )
            chk.grid(row=idx // 2, column=idx % 2, sticky="w", padx=4, pady=2)
            self.deep_option_checks[key] = chk

        # File selection section with modern card design
        tree_section = CollapsibleSection(main_frame, "📋 File Content Selection", expand_on_open=True)
        tree_section.pack(fill="both", expand=True, pady=(0, 15))
        tree_inner = ttk.Frame(tree_section.body, style="Card.TFrame", padding=20)
        tree_inner.pack(fill="both", expand=True, padx=5, pady=5)

        # Section header
        tree_header = ttk.Label(tree_inner, text="Select which files to include:",
                               style="Subheading.TLabel")
        tree_header.pack(anchor="w", pady=(0, 10))

        self.tree_message = ttk.Label(
            tree_inner,
            text="Select a project folder to preview file contents.",
            style="Body.TLabel",
            foreground="#333333"
        )
        self.tree_message.pack(anchor="w", pady=(0, 8))

        self.size_hint_label = ttk.Label(
            tree_inner,
            text="📏 Estimated report size: —",
            style="Body.TLabel",
            foreground="#28a745"
        )
        self.size_hint_label.pack(anchor="w", pady=(0, 10))

        # Tree container with modern styling
        tree_container = ttk.Frame(tree_inner)
        tree_container.pack(fill="both", expand=True)
        tree_container.configure(style="Card.TFrame")

        self.file_tree = ttk.Treeview(
            tree_container,
            show="tree",
            selectmode="none",
            style="Modern.Treeview"
        )
        self.file_tree.column("#0", stretch=True, minwidth=250, width=300)
        self.file_tree.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tree_scroll_y = ttk.Scrollbar(tree_container, orient="vertical", command=self.file_tree.yview)
        tree_scroll_y.pack(side="right", fill="y")
        self.file_tree.configure(yscrollcommand=tree_scroll_y.set)

        tree_scroll_x = ttk.Scrollbar(tree_inner, orient="horizontal", command=self.file_tree.xview)
        tree_scroll_x.pack(fill="x", pady=(8, 0))
        self.file_tree.configure(xscrollcommand=tree_scroll_x.set)

        self.file_tree.bind("<Double-1>", self._on_tree_double_click)

        # Save destination section with modern card design
        save_section = CollapsibleSection(main_frame, "💾 Save Destination")
        save_section.pack(fill="x", pady=(0, 15))
        save_inner = ttk.Frame(save_section.body, style="Card.TFrame", padding=20)
        save_inner.pack(fill="x", padx=5, pady=5)

        # Save destination header
        save_label_header = ttk.Label(save_inner, text="Choose where to save your export:",
                                     style="Subheading.TLabel")
        save_label_header.pack(anchor="w", pady=(0, 10))

        dest_frame = ttk.Frame(save_inner)
        dest_frame.pack(fill="x", pady=(0, 10))

        self.save_label = ttk.Label(dest_frame, text="Choose destination file...",
                                   relief="solid", borderwidth=2,
                                   background="white", foreground="#000000",
                                   font=("Helvetica", 11),
                                   anchor="w", padding=(12, 8))
        self.save_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.choose_btn = ttk.Button(dest_frame, text="💾 Choose File",
                                    style="Modern.TButton",
                                    command=self.on_choose_save, state="disabled")
        self.choose_btn.pack(side="right")

        # Progress section with modern card design
        progress_section = CollapsibleSection(main_frame, "⚡ Progress")
        progress_section.pack(fill="x", pady=(0, 15))
        progress_inner = ttk.Frame(progress_section.body, style="Card.TFrame", padding=20)
        progress_inner.pack(fill="x", padx=5, pady=5)

        self.progress = ttk.Progressbar(progress_inner, mode="indeterminate",
                                       style="Modern.Horizontal.TProgressbar",
                                       length=400)
        self.progress.pack(fill="x", pady=(0, 10))

        self.status_label = ttk.Label(progress_inner, textvariable=self.status_var,
                                     style="Body.TLabel")
        self.status_label.pack(anchor="w")

        # Action buttons with modern styling
        action_frame = ttk.Frame(main_container)
        action_frame.pack(fill="x", pady=(20, 0))

        # Create a modern button bar
        button_bar = ttk.Frame(action_frame, style="Card.TFrame", padding=(20, 15))
        button_bar.pack(fill="x")

        # Left side - secondary actions  
        left_buttons = ttk.Frame(button_bar)
        left_buttons.pack(side="left")

        self.recover_btn = ttk.Button(left_buttons, text="🔄 Recover Project", 
                                     style="Secondary.TButton",
                                     command=self.on_recover)
        self.recover_btn.pack(side="left")

        # Right side - primary actions
        right_buttons = ttk.Frame(button_bar)
        right_buttons.pack(side="right")

        self.quit_btn = ttk.Button(right_buttons, text="❌ Quit", 
                                  style="Secondary.TButton",
                                  command=self.on_quit)
        self.quit_btn.pack(side="right", padx=(10, 0))

        self.export_btn = ttk.Button(right_buttons, text="🚀 Start Export", 
                                    style="Modern.TButton",
                                    command=self.on_export, state="disabled")
        self.export_btn.pack(side="right", padx=(0, 10))

        # Initialize format description
        self.on_format_changed()

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

    def _center_window(self) -> None:
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self._recalculate_minimum_height()

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
        self._auto_update_save_destination()
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
        self.node_icons.clear()
        self.tree_ready = False
        self._tree_file_total = 0
        self.node_file_sizes.clear()
        try:
            self.file_tree.state(("disabled",))
        except Exception:
            pass
        self.tree_message.configure(text=message)
        self.size_hint_label.configure(text="Estimated report size: —")

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
                dirs_map, files_map, total_files, file_sizes = self._gather_tree_snapshot(target_path)
            except Exception as exc:
                self.after(0, lambda: self._handle_tree_failure(str(exc), request_id))
                return
            self.after(0, lambda: self._populate_tree(dirs_map, files_map, total_files, file_sizes, request_id))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_tree_failure(self, error: str, request_id: int) -> None:
        """Display a friendly message if the tree build fails."""
        if request_id != self._tree_build_id:
            return
        truncated = (error[:120] + "...") if len(error) > 120 else error
        print(f"[TREE BUILD ERROR] {error}")
        self._clear_tree(f"Unable to build file preview: {truncated}")

    def _gather_tree_snapshot(self, root_path: Path) -> tuple[dict[str, list[str]], dict[str, list[str]], int, dict[str, int]]:
        """Collect directory/file relationships and sizes for readable files under the root."""
        readable_files: list[str] = []
        file_sizes: dict[str, int] = {}

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
                    stat_result = full_path.stat()
                    rel_path = full_path.relative_to(root_path).as_posix()
                except ValueError:
                    continue
                except (PermissionError, OSError):
                    continue

                readable_files.append(rel_path)
                file_sizes[rel_path] = stat_result.st_size

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

        return dirs_map, files_map, len(readable_files), file_sizes

    def _populate_tree(
        self,
        dirs_map: dict[str, list[str]],
        files_map: dict[str, list[str]],
        total_files: int,
        file_sizes: dict[str, int],
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
        self.node_file_sizes = file_sizes

        root_label = f"{self.folder_path.name}/" if self.folder_path is not None else "Project/"
        self.node_labels[self._tree_root_id] = root_label
        self.node_states[self._tree_root_id] = True
        self.node_icons[self._tree_root_id] = "📁"
        self.file_tree.insert(
            "",
            "end",
            iid=self._tree_root_id,
            text="",
            open=True
        )
        self._update_tree_item_text(self._tree_root_id)

        self._insert_tree_children(self._tree_root_id, "", dirs_map, files_map)
        self._restore_saved_selection()

        if total_files == 0:
            self.tree_message.configure(text="No text-readable files found to include.")
        elif self.include_var.get():
            self.tree_message.configure(text="Double-click entries to include file contents in the export.")
        else:
            self.tree_message.configure(text="Enable 'Include file contents' to make selections.")

        self._update_tree_enable_state()
        self._update_estimated_report_size()

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
            self.node_icons[item_id] = "📁"
            self.file_tree.insert(
                parent_item,
                "end",
                iid=item_id,
                text="",
                open=False
            )
            self._update_tree_item_text(item_id)
            self._insert_tree_children(item_id, dir_key, dirs_map, files_map)

        for file_key in files_map.get(directory_key, []):
            name = file_key.split('/')[-1]
            item_id = f"F:{file_key}"
            self.node_labels[item_id] = name
            self.node_states[item_id] = True
            self.node_icons[item_id] = self._icon_for_file(file_key)
            self.file_tree.insert(
                parent_item,
                "end",
                iid=item_id,
                text=""
            )
            self._update_tree_item_text(item_id)

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
        icon = self.node_icons.get(item_id, "")
        icon_prefix = f"{icon} " if icon else ""
        self.file_tree.item(item_id, text=f"{self._checkbox_prefix(state)} {icon_prefix}{label}")

    def _icon_for_file(self, rel_path: str) -> str:
        """Return an emoji to represent the file extension."""
        ext = Path(rel_path).suffix.lower()
        if ext == "" and rel_path.lower().startswith("makefile"):
            return "🛠️"
        return self.FILE_ICON_MAP.get(ext, "📄")

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
        self._update_estimated_report_size()
        self._save_tree_selection()

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

        fmt_name = self._format_name_from_display(self.fmt_var.get())
        fmt_info = self._format_from_name(fmt_name) if fmt_name else None
        
        # For now, all formats allow content selection since the new system handles this differently
        # We could add format-specific behavior later if needed
        if False:  # Placeholder for format-specific disable logic
            try:
                self.file_tree.state(("disabled",))
            except Exception:
                pass
            self.tree_message.configure(
                text="Selected format summarises files without raw contents."
            )
            self.size_hint_label.configure(text="Estimated report size: deep summary (no contents)")
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
        self._update_estimated_report_size()
        self._save_tree_selection()
        self._recalculate_minimum_height()

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

    def _resolve_format_from_suffix(self, filename: str) -> str | None:
        """Map a file suffix to a known format name, if possible."""
        normalized = filename.lower()
        # Check for extensions, preferring longer matches first
        for fmt_name, ext in sorted(self.format_extensions.items(), key=lambda x: -len(x[1])):
            if normalized.endswith(ext):
                return fmt_name
        return None

    def _update_estimated_report_size(self, selected: Optional[set[str]] = None) -> None:
        """Update the estimated report size label with high contrast styling."""
        if not self.include_var.get():
            self.size_hint_label.configure(text="📏 Estimated report size: contents excluded",
                                         foreground="#333333")
            return

        if not self.tree_ready:
            self.size_hint_label.configure(text="📏 Estimated report size: calculating...",
                                         foreground="#0066cc")
            return

        if selected is None:
            selected = self._get_selected_file_paths()
            if selected is None:
                self.size_hint_label.configure(text="📏 Estimated report size: calculating...",
                                             foreground="#0066cc")
                return

        total_bytes = 0
        for path in selected:
            total_bytes += self.node_file_sizes.get(path, 0)

        if not selected:
            self.size_hint_label.configure(text="📏 Estimated report size: minimal (no contents)",
                                         foreground="#006600")
            return

        overhead = max(len(selected) * 256, 0)
        estimated = int(total_bytes * 1.1) + overhead
        human_readable = format_size(estimated)
        
        # Color code based on size - using high contrast colors
        if estimated < 1024 * 1024:  # < 1MB
            color = "#006600"  # Dark green
        elif estimated < 10 * 1024 * 1024:  # < 10MB
            color = "#cc6600"  # Dark orange
        else:  # > 10MB
            color = "#cc0000"  # Dark red
            
        self.size_hint_label.configure(text=f"📏 Estimated report size: ~{human_readable}",
                                     foreground=color)

    def _restore_saved_selection(self) -> None:
        """Restore saved content selection for the current project if available."""
        if self.folder_path is None or not self.node_states:
            return

        saved = self.config_manager.get_content_exclusions(str(self.folder_path))
        if not saved:
            return

        for rel_path in saved:
            node_id = f"F:{rel_path}"
            if node_id in self.node_states:
                self.node_states[node_id] = False
                self._update_tree_item_text(node_id)
                self._update_parent_state(node_id)

        self._update_estimated_report_size()
        self._save_tree_selection()

    def _save_tree_selection(self) -> None:
        """Persist the current tree selection for the active project."""
        if self.folder_path is None or not self.node_states:
            return

        excluded = sorted(
            node_id[2:]
            for node_id, state in self.node_states.items()
            if node_id.startswith("F:") and state is not True
        )
        self.config_manager.update_content_exclusions(str(self.folder_path), excluded)

    def _update_deep_controls_visibility(self) -> None:
        """Show or hide deep-analysis toggles depending on selected format."""
        fmt_name = self._format_name_from_display(self.fmt_var.get())
        # For now, hide deep options since the new system handles options differently
        # We can add this back later if needed for specific exporters
        if False:  # fmt_name in ("deep-markdown", "deep-json"):
            if not self.deep_options_frame.winfo_ismapped():
                self.deep_options_frame.pack(fill="x", pady=(8, 0))
        else:
            if self.deep_options_frame.winfo_manager():
                self.deep_options_frame.pack_forget()

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

    def _collect_deep_options(self) -> dict[str, bool]:
        """Return deep analysis options as a simple dictionary."""
        return {key: bool(var.get()) for key, var in self.deep_option_vars.items()}

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
        """Update the file count display with modern styling"""
        self.file_count_var.set(count)
        
        if count > 0:
            self.count_label.configure(text=f"📊 Files found: {count:,}")
            self.status_var.set("✅ Folder scanned successfully. Choose save destination.")
            self.choose_btn.configure(state="normal")
            
            # Update path label color to show success
            self.path_label.configure(foreground="#1a1a1a")
        else:
            self.count_label.configure(text="📊 No files found")
            self.status_var.set("⚠️ No files found in selected folder.")
            self.choose_btn.configure(state="disabled")
            
            # Update path label color to show warning
            self.path_label.configure(foreground="#dc3545")
        
        self._update_export_state()

    def _on_content_changed(self) -> None:
        """Handle content inclusion checkbox change"""
        self.config_manager.update_export_options(
            self.fmt_var.get(),
            self.include_var.get()
        )
        self._update_tree_enable_state()
        self._update_estimated_report_size()
        self._save_tree_selection()
        self._recalculate_minimum_height()

    def _on_deep_option_changed(self) -> None:
        """Persist deep analysis option toggles."""
        options = {key: bool(var.get()) for key, var in self.deep_option_vars.items()}
        self.config_manager.update_deep_options(options)
        self._recalculate_minimum_height()

    def on_format_changed(self, event=None) -> None:
        """Handle format selection change"""
        fmt_name = self._format_name_from_display(self.fmt_var.get())
        format_info = self._format_from_name(fmt_name) if fmt_name else None
        
        # Update format description
        format_descriptions = {
            'basic-json': 'Structured analysis without source code. Best for automation and APIs.',
            'basic-markdown': 'Human-readable analysis without source code. Perfect for documentation.',
            'llm-tds': 'AI-optimised compressed format. 90% smaller, ideal for language models.',
            'full-content-json': 'Complete backup with all source code. Machine-readable, fully recoverable.',
            'full-content-markdown': 'Complete documentation with all source code. Human-readable, fully recoverable.',
            'legacy-html': 'Styled web format with all source code. Beautiful for presentations and sharing.'
        }
        
        if fmt_name:
            description = format_descriptions.get(fmt_name, "")
            self.format_description.configure(text=description)
        
        # Update content checkbox based on format capabilities
        if format_info:
            if format_info.get('has_source_code', False):
                # Full-content formats always include source code
                self.include_var.set(True)
                self.content_check.configure(state="disabled", 
                                           text="✅ Source code included (full-content format)")
            else:
                # Analysis-only formats have optional content inclusion
                self.content_check.configure(state="normal",
                                           text="📄 Include file contents in export")
        
        # Save format preference  
        self.config_manager.update_export_options(
            self.fmt_var.get(), 
            self.include_var.get()
        )
        
        if self.folder_path and self.save_path:
            # Update save path extension to match format
            self._suggest_filename(persist=True)
        elif self.folder_path:
            self._suggest_placeholder_filename()
        
        self._update_deep_controls_visibility()
        self._update_tree_enable_state()
        self._recalculate_minimum_height()

    def on_choose_save(self) -> None:
        """Handle save destination selection"""
        if not self.folder_path:
            messagebox.showwarning("No Folder Selected", 
                                 "Please select a project folder first.")
            return

        fmt_name = self._format_name_from_display(self.fmt_var.get())
        current_ext = self.format_extensions.get(fmt_name, '.txt') if fmt_name else '.txt'
        default_name = f"{self.folder_path.name}_report{current_ext}"

        # Build filetypes from available formats
        filetypes = [
            (fmt['display'], f"*{fmt['extension']}")
            for fmt in self.available_formats
        ]
        filetypes.append(("All files", "*.*"))

        # Use last save folder as initial directory if available
        initial_dir = None
        if self.config.last_save_folder and Path(self.config.last_save_folder).exists():
            initial_dir = self.config.last_save_folder
        
        fmt_display = self.fmt_var.get() or "Export"
        save_path_str = filedialog.asksaveasfilename(
            title=f"Save {fmt_display} Report",
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
            selected_fmt = self._resolve_format_from_suffix(self.save_path.name)
            if selected_fmt and selected_fmt != fmt_name:
                selected_display = self._display_from_name(selected_fmt)
                if selected_display:
                    self.fmt_var.set(selected_display)
                    self.combo.set(selected_display)
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

    def _clean_filename_base(self, filename: str) -> str:
        """Extract the base name by removing repeated or malformed extensions"""
        # Handle repeated extensions like .lrc.lrc.lrc.json
        name = filename
        
        # First, clean up any repeated .lrc patterns
        while '.lrc.lrc' in name:
            name = name.replace('.lrc.lrc', '.lrc')
        
        # Remove any known format extensions from the end
        for fmt_ext in sorted(self.format_extensions.values(), key=len, reverse=True):
            if name.endswith(fmt_ext):
                name = name[:-len(fmt_ext)]
                break
        
        # If the name ends with just .lrc (partial extension), remove it
        if name.endswith('.lrc'):
            name = name[:-4]
            
        # Remove any remaining single extensions that might be left
        if '.' in name:
            # Keep removing extensions until we get to a reasonable base name
            while name.count('.') > 0 and any(name.endswith(ext) for ext in ['.md', '.txt', '.html', '.json', '.zip', '.lrc']):
                name = '.'.join(name.split('.')[:-1])
        
        return name
    
    def _replace_extension_properly(self, path: Path | str, new_ext: str) -> Path:
        """Replace file extension properly, handling multi-part extensions like .lrc.json"""
        path_obj = Path(path) if isinstance(path, str) else path
        base_name = self._clean_filename_base(path_obj.name)
        return path_obj.parent / (base_name + new_ext)

    def _suggest_filename(self, persist: bool = False) -> None:
        """Update suggested filename when format changes"""
        if not self.save_path or not self.folder_path:
            return
            
        fmt_name = self._format_name_from_display(self.fmt_var.get())
        if fmt_name and fmt_name in self.format_extensions:
            new_ext = self.format_extensions[fmt_name]
            new_path = self._replace_extension_properly(self.save_path, new_ext)
            self.save_path = new_path
            self.save_label.configure(text=str(self.save_path))
            if persist:
                self.config_manager.update_save_folder(str(self.save_path))

    def _suggest_placeholder_filename(self) -> None:
        """Show a suggested filename when no save path is chosen yet."""
        if self.save_path is not None or not self.folder_path:
            return

        fmt_name = self._format_name_from_display(self.fmt_var.get())
        ext = self.format_extensions.get(fmt_name, '.txt') if fmt_name else '.txt'
        suggested = self.folder_path.with_suffix("")
        placeholder = suggested.name + "_report" + ext
        self.save_label.configure(text=placeholder)

    def _align_save_path_with_format(self, persist: bool = False) -> None:
        """Ensure the stored save path matches the current output format."""
        if not self.save_path:
            return

        fmt_name = self._format_name_from_display(self.fmt_var.get())
        if fmt_name and fmt_name in self.format_extensions:
            desired_ext = self.format_extensions[fmt_name]
            
            # Check if the current filename already ends with the desired extension
            if not str(self.save_path).endswith(desired_ext):
                self.save_path = self._replace_extension_properly(self.save_path, desired_ext)
                self.save_label.configure(text=str(self.save_path))
                if persist:
                    self.config_manager.update_save_folder(str(self.save_path))

    def _auto_update_save_destination(self) -> None:
        """Refresh the suggested save location when a new project is chosen."""
        if self.folder_path is None:
            return

        fmt_name = self._format_name_from_display(self.fmt_var.get())
        ext = self.format_extensions.get(fmt_name, '.txt') if fmt_name else '.txt'
        default_name = f"{self.folder_path.name}_report{ext}"

        parent: Optional[Path] = None
        if self.save_path and self.save_path.parent.exists():
            parent = self.save_path.parent
        elif self.config.last_save_folder and Path(self.config.last_save_folder).exists():
            parent = Path(self.config.last_save_folder)

        if parent is not None:
            new_path = parent / default_name
            self.save_path = new_path
            self.save_label.configure(text=str(self.save_path))
            self.config_manager.update_save_folder(str(self.save_path))
        else:
            self.save_path = None
            self._suggest_placeholder_filename()

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

        fmt_name = self._format_name_from_display(self.fmt_var.get())
        if not fmt_name:
            messagebox.showerror("Invalid Format", "Please select a valid export format.")
            return
            
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

                # Apply content selection based on format and checkbox
                format_info = self._format_from_name(fmt_name)
                is_full_content_format = format_info and format_info.get('has_source_code', False)
                
                if is_full_content_format:
                    # Full-content formats always include content, respect tree selection
                    if selected_paths is not None:
                        self._apply_content_selection(report, selected_paths)
                    # If selected_paths is None, keep all content (no filtering)
                elif include:
                    # Analysis formats with content enabled, respect tree selection
                    self._apply_content_selection(report, selected_paths)
                else:
                    # Analysis formats with content disabled, remove all content
                    self._apply_content_selection(report, set())
                
                # Use new export system
                self.after(0, lambda: self.status_var.set("Converting to analysis format..."))
                engine = AnalysisEngine()
                analysis = engine.analyze_project(report)
                
                # Export using new modular system
                self.after(0, lambda: self.status_var.set("Generating export file..."))
                exporter_class = self.registry.get(fmt_name)
                if not exporter_class:
                    raise ValueError(f"Unknown format: {fmt_name}")
                
                exporter = exporter_class()
                # Prepare export options with project report and content inclusion flag
                export_options = {
                    'project_report': report,
                    'include_content': include
                }
                output = exporter.render(analysis.model_dump(), export_options)
                
                # Write output
                if isinstance(output, str):
                    self.save_path.write_text(output, encoding='utf-8')
                else:
                    self.save_path.write_bytes(output)
                
                # Success
                self.after(0, lambda: self._export_success())
                
            except PermissionError as e:
                error_msg = f"Cannot write to destination:\n{e}"
                self.after(0, lambda: messagebox.showerror(
                    "Permission Error",
                    error_msg
                ))
            except Exception as e:
                error_msg = f"Export failed:\n{str(e)[:200]}..."
                self.after(0, lambda: messagebox.showerror(
                    "Export Error",
                    error_msg
                ))
            finally:
                self.after(0, lambda: self._export_complete())

        threading.Thread(target=export_worker, daemon=True).start()

    def _export_success(self) -> None:
        """Handle successful export with modern styling"""
        if self.save_path is not None:
            size_mb = self.save_path.stat().st_size / (1024 * 1024)
            result = messagebox.askquestion(
                "🎉 Export Complete", 
                f"Your project has been exported successfully!\n\n"
                f"📁 File: {self.save_path.name}\n"
                f"📊 Size: {size_mb:.1f} MB\n"
                f"📍 Location: {self.save_path.parent}\n\n"
                f"Would you like to open the file location?",
                icon='question'
            )
            
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
                    messagebox.showinfo("📁 File Location", f"File saved to:\n{self.save_path}")
        else:
            messagebox.showinfo("🎉 Export Complete", "Report exported successfully!")

    def _export_complete(self) -> None:
        """Cleanup after export completion with modern status"""
        self.progress.stop()
        self._set_working(False)
        self.status_var.set("✅ Export complete.")
        self._recalculate_minimum_height()

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
    def _recalculate_minimum_height(self) -> None:
        """Shrink window height when sections collapse to avoid large gaps."""
        try:
            self.update_idletasks()
            children = [child for child in self.winfo_children() if child.winfo_manager()]
            total_height = sum(child.winfo_reqheight() for child in children)
            padding = 40  # account for borders/margins
            min_height = max(total_height + padding, 420)
            min_width = max(self.winfo_width(), 600)
            self.minsize(600, min_height)
            current_height = self.winfo_height()
            if current_height > min_height:
                self.geometry(f"{min_width}x{min_height}")
        except Exception:
            pass

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
