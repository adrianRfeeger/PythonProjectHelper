# file: report.py
"""Core models, constants, and enums used across the app."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Exclusions and file-type hints
EXCLUDED_DIRS: set[str] = {"__pycache__", ".git", ".svn", ".hg"}
CODE_EXTENSIONS: set[str] = {
    # Python
    ".py", ".pyw", ".spec",
    ".ipynb",

    # Go
    ".go", ".mod", ".sum",

    # C / C++
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx",

    # C#
    ".cs",

    # Java
    ".java",

    # Kotlin
    ".kt", ".kts",

    # Scala
    ".scala", ".sc",

    # Rust
    ".rs",

    # Swift
    ".swift",

    # Objective-C
    ".m", ".mm",

    # Dart / Flutter
    ".dart",

    # JavaScript / TypeScript
    ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".jsx",

    # PHP
    ".php", ".phtml",

    # Ruby
    ".rb", ".erb",

    # Perl
    ".pl", ".pm", ".t",

    # R
    ".r", ".R", ".Rmd",

    # Julia
    ".jl",

    # Shell / Batch
    ".sh", ".bash", ".zsh", ".ksh", ".csh", ".bat", ".cmd",

    # PowerShell
    ".ps1", ".psm1", ".psd1",

    # SQL & DB
    ".sql", ".psql",

    # Haskell
    ".hs", ".lhs",

    # Erlang / Elixir
    ".erl", ".hrl",
    ".ex", ".exs",

    # OCaml / F#
    ".ml", ".mli", ".fs", ".fsi", ".fsx",

    # Lisp / Scheme / Clojure
    ".lisp", ".lsp", ".cl", ".el", ".scm", ".clj", ".cljs", ".cljc",

    # Lua
    ".lua",

    # YAML / JSON / TOML / INI / ENV
    ".yml", ".yaml", ".json", ".toml", ".ini", ".env",

    # XML / HTML / Templates
    ".xml", ".xsd", ".xslt", ".html", ".htm", ".xhtml",
    ".jsp", ".asp", ".aspx",
    ".mustache", ".hbs", ".ejs", ".twig", ".jinja", ".jinja2",
    ".tmpl", ".tpl",

    # CSS & Preprocessors
    ".css", ".scss", ".sass", ".less",

    # Markdown / Docs
    ".md", ".markdown", ".rst", ".txt", ".tex",

    # Config / Misc
    ".cfg", ".conf", ".properties", ".gradle", ".groovy",
    ".make", ".mk", "Makefile", "CMakeLists.txt",
    ".dockerfile", "Dockerfile",
    ".gitignore", ".gitattributes",
    ".editorconfig",
    ".bazel", ".bzl",

    # Protocols
    ".proto", ".thrift", ".avdl",

    # Assembly
    ".s", ".asm",
}
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
    DEEP_MARKDOWN = "Deep analysis (.md)"
    DEEP_JSON = "Deep analysis (.json)"
    LRC = "LLM Capsule (.lrc.json)"

    @staticmethod
    def from_label(label: str) -> "OutputFormat":
        for fmt in OutputFormat:
            if fmt.value == label:
                return fmt
        raise ValueError(f"Unknown format: {label}")
