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
