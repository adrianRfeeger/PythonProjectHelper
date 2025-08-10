"""
PySide6-based GUI for Project Export Helper
Implements similar features as the Tkinter and DearPyGui versions.
"""
import sys
import threading
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QComboBox, QCheckBox, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from report import OutputFormat
from scan import scan_project
from outputs import export_report
from config import ConfigManager

class WorkerSignals(QObject):
    file_count = Signal(int)
    status = Signal(str)
    export_done = Signal(bool, str)

class ProjectExportHelper(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Export Helper")
        self.resize(600, 300)
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        self.state = {
            'folder_path': None,
            'save_path': None,
            'file_count': 0,
            'export_running': False,
            'status': 'Select a project folder to begin...',
            'output_format': self.config.output_format,
            'include_contents': self.config.include_contents,
        }
        self.signals = WorkerSignals()
        self.signals.file_count.connect(self.update_file_count)
        self.signals.status.connect(self.update_status)
        self.signals.export_done.connect(self.on_export_done)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Project folder selection
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Project folder:"))
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        # Initialize folder from config
        last_folder = getattr(self.config, 'last_source_folder', None)
        if last_folder:
            self.folder_input.setText(last_folder)
            self.state['folder_path'] = Path(last_folder)
        folder_layout.addWidget(self.folder_input)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.on_browse)
        folder_layout.addWidget(browse_btn)
        self.file_count_label = QLabel("")
        folder_layout.addWidget(self.file_count_label)
        layout.addLayout(folder_layout)

        # Export options
        layout.addWidget(QLabel("Export Options:"))
        options_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        for f in OutputFormat:
            self.format_combo.addItem(f.value)
        # Initialize format from config
        self.format_combo.setCurrentText(self.state['output_format'])
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        options_layout.addWidget(self.format_combo)
        self.include_checkbox = QCheckBox("Include file contents in export")
        # Initialize include_contents from config
        self.include_checkbox.setChecked(self.state['include_contents'])
        self.include_checkbox.stateChanged.connect(self.on_include_changed)
        options_layout.addWidget(self.include_checkbox)
        layout.addLayout(options_layout)

        # Save as
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("Save as:"))
        self.save_input = QLineEdit()
        self.save_input.setReadOnly(True)
        # Initialize save path from config
        last_save = getattr(self.config, 'last_save_file', None)
        if last_save:
            self.save_input.setText(last_save)
            self.state['save_path'] = Path(last_save)
        save_layout.addWidget(self.save_input)
        choose_btn = QPushButton("Choose File...")
        choose_btn.clicked.connect(self.on_choose_save)
        save_layout.addWidget(choose_btn)
        layout.addLayout(save_layout)

        # Progress and status
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel(self.state['status'])
        layout.addWidget(self.status_label)

        # Action buttons
        action_layout = QHBoxLayout()
        self.export_btn = QPushButton("Start Export")
        self.export_btn.clicked.connect(self.on_export)
        # Enable export if both folder and save path are set
        self.export_btn.setEnabled(bool(self.state['folder_path']) and bool(self.state['save_path']))
        action_layout.addWidget(self.export_btn)

        self.recover_btn = QPushButton("Recover Project")
        self.recover_btn.clicked.connect(self.on_recover)
        action_layout.addWidget(self.recover_btn)

        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        action_layout.addWidget(quit_btn)
        layout.addLayout(action_layout)
        self.setLayout(layout)

    def on_recover(self):
        # Select report file
        report_file, _ = QFileDialog.getOpenFileName(self, "Select Report File", "", "Report Files (*.md *.txt *.html *.json);;All Files (*)")
        if not report_file:
            return
        # Select output directory
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
        self.update_status("Recovering project from report... (see terminal for details)")
        def run_recover():
            import subprocess
            import sys
            try:
                cmd = [sys.executable, "recover.py", report_file, output_dir]
                result = subprocess.run(cmd, cwd=os.path.dirname(__file__), capture_output=True, text=True)
                print("[RECOVER STDOUT]\n" + (result.stdout or ""))
                print("[RECOVER STDERR]\n" + (result.stderr or ""))
                if result.returncode == 0:
                    QTimer.singleShot(0, lambda: self.update_status("Recovery complete. See output directory."))
                else:
                    QTimer.singleShot(0, lambda: self.update_status("Recovery failed. See terminal for details."))
            except Exception as e:
                QTimer.singleShot(0, lambda: self.update_status(f"Recovery failed: {e}"))
        threading.Thread(target=run_recover, daemon=True).start()


    def update_status(self, msg):
        self.state['status'] = msg
        # Ensure this runs in the main thread
        if QTimer.singleShot:
            self.status_label.setText(msg)

    def update_file_count(self, count):
        self.state['file_count'] = count
        self.file_count_label.setText(f"Files found: {count}")
        if count > 0:
            self.update_status("Folder scanned successfully. Choose save destination.")
            self.export_btn.setEnabled(True)
        else:
            self.update_status("No files found in selected folder.")
            self.export_btn.setEnabled(False)

    def on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            folder_path = Path(folder)
            if not folder_path.exists() or not os.access(folder_path, os.R_OK):
                self.update_status("Invalid or unreadable folder selected.")
                return
            self.state['folder_path'] = folder_path
            self.config_manager.update_source_folder(str(folder_path))
            self.folder_input.setText(str(folder_path))
            self.update_status("Scanning folder for files...")
            threading.Thread(target=self.scan_folder_thread, args=(folder_path,), daemon=True).start()

    def scan_folder_thread(self, folder_path):
        count = 0
        try:
            from report import EXCLUDED_DIRS
            for root, dirs, files in os.walk(folder_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith('.')]
                count += len([f for f in files if not f.startswith('.')])
        except Exception:
            count = 0
        self.signals.file_count.emit(count)

    def on_choose_save(self):
        if not self.state['folder_path']:
            self.update_status("Please select a project folder first.")
            return
        fmt = OutputFormat.from_label(self.format_combo.currentText())
        ext_map = {
            OutputFormat.MARKDOWN: ".md",
            OutputFormat.PLAINTEXT: ".txt",
            OutputFormat.HTML: ".html",
            OutputFormat.JSON: ".json",
            OutputFormat.ZIP: ".zip",
        }
        ext = ext_map[fmt]
        default_name = f"{self.state['folder_path'].name}_report{ext}"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Report As", default_name, f"*{ext}")
        if save_path:
            self.state['save_path'] = Path(save_path)
            self.save_input.setText(str(save_path))
            self.config_manager.update_save_folder(str(save_path))
            self.update_status("Ready to export. Click 'Start Export' when ready.")

    def on_export(self):
        if not self.state['folder_path'] or not self.state['save_path']:
            self.update_status("Please select both source folder and destination file.")
            return
        if self.state['export_running']:
            self.update_status("An export is already running.")
            return
        # Overwrite confirmation
        if self.state['save_path'].exists():
            reply = QMessageBox.question(
                self,
                "Overwrite File?",
                f"File already exists: {self.state['save_path']}\nDo you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.update_status("Export cancelled by user.")
                return
        self.state['export_running'] = True
        self.update_status("Scanning project files...")
        self.progress_bar.setValue(0)
        fmt = OutputFormat.from_label(self.format_combo.currentText())
        include = self.include_checkbox.isChecked()
        threading.Thread(target=self.export_worker_thread, args=(fmt, include), daemon=True).start()

    def export_worker_thread(self, fmt, include):
        try:
            self.signals.status.emit("Analyzing project structure...")
            report = scan_project(self.state['folder_path'])
            self.signals.status.emit("Generating export file...")
            export_report(report, fmt, include, self.state['save_path'], self.state['folder_path'])
            self.signals.export_done.emit(True, "Export complete.")
        except Exception as e:
            self.signals.export_done.emit(False, f"Export failed: {e}")
    def on_export_done(self, success, msg):
        self.update_status(msg)
        if success:
            self.progress_bar.setValue(100)
        self.state['export_running'] = False

    def on_format_changed(self, value):
        self.state['output_format'] = value
        self.config_manager.update_export_options(value, self.include_checkbox.isChecked())

    def on_include_changed(self, state):
        self.state['include_contents'] = bool(state)
        self.config_manager.update_export_options(self.format_combo.currentText(), bool(state))

def run_gui():
    app = QApplication(sys.argv)
    window = ProjectExportHelper()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_gui()
