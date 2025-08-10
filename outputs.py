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
