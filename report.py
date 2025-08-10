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
