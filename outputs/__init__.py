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
from deep_report import (
    build_deep_analysis,
    DeepAnalysisReport,
    DeepAnalysisOptions,
)
from .lrc_capsule import (
    build_lrc_capsule,
    build_compact_lrc_capsule,
    write_lrc_capsule,
    LRCCapsuleOptions,
)

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
    
    buf = io.StringIO()

    def _print(line=""):
        # Always use LF endings, strip trailing whitespace
        buf.write(str(line).rstrip() + "\n")

    _print("=" * 60)
    _print(f"PROJECT STRUCTURE REPORT")
    _print("=" * 60)
    _print(f"Project: {Path(report.root).name}")
    _print(f"Generated: {report.generated_at}")
    _print(f"Root Path: {report.root}")
    _print()

    # Summary
    total_files = len(report.files)
    total_size = sum(f.size_bytes for f in report.files)
    text_files = sum(1 for f in report.files if f.content is not None)

    _print("SUMMARY:")
    _print(f"  Total Files: {total_files:,}")
    _print(f"  Text Files: {text_files:,}")
    _print(f"  Total Size: {format_size(total_size)}")
    _print()

    _print("FILE LISTING:")
    _print("-" * 60)

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

    def render_tree(node, prefix_stack=None, level=0, is_last_dir=False):
        if prefix_stack is None:
            prefix_stack = []
        out = []
        keys = sorted(k for k in node.keys() if k != "__files__")
        n_keys = len(keys)
        for i, key in enumerate(keys):
            is_last = (i == n_keys - 1 and not node.get("__files__"))
            prefix = "".join(["│   " if draw else "    " for draw in prefix_stack])
            branch = "└── " if is_last else "├── "
            out.append(f"{prefix}{branch}📁 {key}/")
            out.extend(render_tree(node[key], prefix_stack + [not is_last], level+1, is_last))
        files = sorted(node.get("__files__", []), key=lambda f: f.path)
        n_files = len(files)
        for j, fi in enumerate(files):
            is_last_file = (j == n_files - 1)
            prefix = "".join(["│   " if draw else "    " for draw in prefix_stack])
            branch = "└── " if is_last_file else "├── "
            size = format_size(fi.size_bytes)
            lines_str = str(fi.lines) if fi.lines != "?" else "—"
            words_str = str(fi.words) if fi.words != "?" else "—"
            ext = Path(fi.path).suffix.lower()
            emoji = _get_file_emoji(ext)
            meta = f"{size}, {lines_str} lines, {words_str} words, modified {fi.mtime_iso}"
            out.append(f"{prefix}{branch}{emoji} {Path(fi.path).name} [{meta}]")
        return out

    tree = build_tree(report.files)
    tree_lines = render_tree(tree)
    for line in tree_lines:
        _print(line)

    if include_contents:
        _print()
        _print("=" * 60)
        _print("FILE CONTENTS")
        _print("=" * 60)
        for fi in report.files:
            if fi.content is None:
                continue
            _print(f"\n--- {fi.path} ---")
            _print(f"Size: {format_size(fi.size_bytes)} | Lines: {fi.lines} | Words: {fi.words}")
            _print(f"Modified: {fi.mtime_iso}")
            _print("-" * 40)
            # Write file content, normalize to LF, strip trailing whitespace
            for line in (fi.content or '').splitlines():
                _print(line)

    # Always return with LF endings
    return buf.getvalue().replace('\r\n', '\n').replace('\r', '\n')
    
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
    
    # File listing as a tree (rendered as ASCII tree in <pre><code> for visual parity with Markdown)
    out.append('<h2>📁 File Listing</h2>')

    def build_tree(files):
        tree = {}
        for fi in files:
            parts = fi.path.split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node.setdefault("__files__", []).append(fi)
        return tree

    def render_ascii_tree(node, prefix_stack=None, level=0, is_last_dir=False):
        if prefix_stack is None:
            prefix_stack = []
        out = []
        keys = sorted(k for k in node.keys() if k != "__files__")
        n_keys = len(keys)
        for i, key in enumerate(keys):
            is_last = (i == n_keys - 1 and not node.get("__files__"))
            prefix = ""
            for draw in prefix_stack:
                prefix += ("│   " if draw else "    ")
            branch = "└── " if is_last else "├── "
            out.append(f"{prefix}{branch}📁 {esc(key)}/")
            out.extend(render_ascii_tree(node[key], prefix_stack + [not is_last], level+1, is_last))
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
            out.append(f"{prefix}{branch}{emoji} {esc(Path(fi.path).name)} ({esc(meta)})")
        return out

    tree = build_tree(report.files)
    tree_lines = render_ascii_tree(tree)
    out.append('<pre><code>')
    out.append("\n".join(tree_lines))
    out.append('</code></pre>')
    
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


def render_deep_markdown(deep_report: DeepAnalysisReport) -> str:
    """Render a deep analysis report as Markdown."""
    lines: list[str] = []
    disclaimer = (
        "**Important:** This deep analysis omits raw code and is unsuitable for project recovery."
    )
    lines.extend(
        [
            f"# Deep Analysis Report for `{Path(deep_report.root).name}`",
            "",
            disclaimer,
            "",
            f"Generated: {deep_report.generated_at}",
            "",
            "## Overview",
            "",
            f"- Files analysed: {len(deep_report.files)}",
            f"- API items indexed: {len(deep_report.api_index)}",
            f"- Binary assets: {len(deep_report.binary_manifest)}",
            "",
            "---",
        ]
    )

    lines.extend(["## Per-File Deep Outline", ""])
    for file_card in deep_report.files:
        lines.extend(
            [
                f"### `{file_card.path}`",
                "",
                f"- Language: {file_card.language}",
                f"- Size: {format_size(file_card.size_bytes)} | SLOC: {file_card.sloc}",
                f"- Modified: {file_card.mtime_iso}",
                f"- Responsibility: {file_card.responsibility or '—'}",
                f"- Complexity: {file_card.complexity} (score {file_card.risk_score:.1f})",
                f"- TODO markers: {file_card.todo_count}",
            ]
        )
        if file_card.imports:
            lines.append(f"- Imports: {', '.join(file_card.imports[:12])}{'…' if len(file_card.imports) > 12 else ''}")
        if file_card.call_targets:
            lines.append(f"- Call targets: {', '.join(file_card.call_targets[:10])}{'…' if len(file_card.call_targets) > 10 else ''}")
        if file_card.env_vars:
            lines.append(f"- Environment vars: {', '.join(file_card.env_vars)}")
        if file_card.cli_commands:
            lines.append(f"- CLI commands: {', '.join(file_card.cli_commands)}")
        if file_card.entrypoints:
            lines.append(f"- Entrypoints: {', '.join(file_card.entrypoints)}")
        if file_card.ui_widgets:
            lines.append(f"- UI widgets: {', '.join(file_card.ui_widgets)}")
        if file_card.tests:
            lines.append(f"- Tests: {', '.join(file_card.tests)}")
        if file_card.licence:
            lines.append(f"- Licence: {file_card.licence}")
        if file_card.asset_meta:
            lines.append(f"- Asset: {file_card.asset_meta['mime']} ({file_card.asset_meta['size']})")
        if file_card.functions:
            lines.append("")
            lines.append("**Functions**")
            for fn in file_card.functions[:15]:
                doc = f" — {fn.doc}" if fn.doc else ""
                lines.append(f"- `{fn.signature}`{doc}")
        if file_card.classes:
            lines.append("")
            lines.append("**Classes**")
            for cls in file_card.classes[:15]:
                doc = f" — {cls.doc}" if cls.doc else ""
                lines.append(f"- `{cls.signature}`{doc}")
        if file_card.strings:
            lines.append("")
            preview = ", ".join(f'“{s}”' for s in file_card.strings[:5])
            lines.append(f"Key strings: {preview}{'…' if len(file_card.strings) > 5 else ''}")
        lines.extend(["", "---", ""])

    if deep_report.api_index:
        lines.extend(["## API Signature Index", ""])
        by_module: dict[str, list[str]] = {}
        for item in deep_report.api_index:
            by_module.setdefault(item.module, []).append(f"- `{item.qualname}` :: `{item.signature}`")
        for module, entries in sorted(by_module.items()):
            lines.append(f"### `{module}`")
            lines.extend(entries)
            lines.append("")

    if deep_report.dependency_map:
        lines.extend(["## Dependency Map", ""])
        for module, deps in sorted(deep_report.dependency_map.items()):
            lines.append(f"- `{module}` ➜ {', '.join(deps) if deps else 'None'}")
        lines.append("")

    if deep_report.call_graph:
        lines.extend(["## Call Graph Sketch", ""])
        for module, calls in sorted(deep_report.call_graph.items()):
            if not calls:
                continue
            lines.append(f"- `{module}` calls {', '.join(calls[:12])}{'…' if len(calls) > 12 else ''}")
        lines.append("")

    if deep_report.cli_inventory:
        lines.extend(["## CLI & Entrypoints", ""])
        for item in deep_report.cli_inventory:
            lines.append(f"- `{item['file']}` ➜ `{item['command']}`")
        lines.append("")

    if deep_report.config_schema:
        lines.extend(["## Config & Environment Schema", ""])
        for section, values in sorted(deep_report.config_schema.items()):
            lines.append(f"- **{section}**: {', '.join(values[:12])}{'…' if len(values) > 12 else ''}")
        lines.append("")

    if deep_report.ui_catalogue:
        lines.extend(["## UI Widget Catalogue", ""])
        for item in deep_report.ui_catalogue:
            lines.append(f"- `{item['file']}` ➜ {item['widget']}")
        lines.append("")

    if deep_report.test_map:
        lines.extend(["## Test Surface Map", ""])
        for file_path, tests in sorted(deep_report.test_map.items()):
            lines.append(f"- `{file_path}`: {', '.join(tests)}")
        lines.append("")

    if deep_report.string_catalogue:
        lines.extend(["## Strings & i18n Catalogue", ""])
        for string, locations in list(deep_report.string_catalogue.items())[:50]:
            lines.append(f"- “{string}” → {', '.join(set(locations))}")
        lines.append("")

    if deep_report.licence_findings:
        lines.extend(["## Licence & Compliance", ""])
        for finding in deep_report.licence_findings:
            lines.append(f"- `{finding['file']}`: {finding['note']}")
        lines.append("")

    if deep_report.binary_manifest:
        lines.extend(["## Binary & Asset Manifest", ""])
        for asset in deep_report.binary_manifest:
            lines.append(f"- `{asset['path']}` ({asset['mime']}, {asset['size']})")
        lines.append("")

    lines.extend(["---", "", "Report generated without storing raw source code."])
    return "\n".join(lines) + "\n"

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

def export_report(
    report: ProjectReport,
    fmt: OutputFormat,
    include_contents: bool,
    save_path: Path,
    root_path: Path,
    deep_options: Optional[dict[str, bool]] = None,
) -> None:
    """Export report in specified format with error handling"""
    try:
        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        if fmt.name == "MARKDOWN":
            text = render_markdown(report, include_contents)
            save_path.write_text(text, encoding="utf-8")
            
        elif fmt.name == "PLAINTEXT":
            text = render_plaintext(report, include_contents)
            # Write as UTF-8 without BOM, force LF endings
            with open(save_path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            
        elif fmt.name == "HTML":
            # Inline HTML rendering logic (copied from the HTML section above)
            def esc(s):
                return (str(s)
                        .replace('&', '&amp;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;')
                        .replace('"', '&quot;')
                        .replace("'", '&#39;'))

            root_name = Path(report.root).name
            css = """
            <style>
            body { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; background: #f9fafb; color: #222; margin: 0; padding: 0; }
            .container { max-width: 900px; margin: 2rem auto; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px #0001; padding: 2rem; }
            h1, h2, h3 { color: #2563eb; }
            pre { background: #1f2937; color: #f9fafb; border-radius: 6px; padding: 1rem; overflow-x: auto; margin: 1rem 0; }
            code { font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace; }
            .content-header { background: #eff6ff; padding: 0.75rem; border-radius: 6px; margin: 1rem 0 0.5rem 0; border-left: 4px solid #3b82f6; }
            hr { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
            </style>
            """
            head = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\">
    <title>Project Structure: {root_name}</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    {css}
</head>
<body>
<div class=\"container\">"""
            out = [
                head,
                f"<h1>📁 Project Structure: {root_name}</h1>",
                f'<div class="meta">Generated: {esc(report.generated_at)} | Root: <code>{esc(report.root)}</code></div>'
            ]
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
            out.append('<h2>📁 File Listing</h2>')
            def build_tree(files):
                tree = {}
                for fi in files:
                    parts = fi.path.split("/")
                    node = tree
                    for part in parts[:-1]:
                        node = node.setdefault(part, {})
                    node.setdefault("__files__", []).append(fi)
                return tree
            def render_ascii_tree(node, prefix_stack=None, level=0, is_last_dir=False):
                if prefix_stack is None:
                    prefix_stack = []
                out = []
                keys = sorted(k for k in node.keys() if k != "__files__")
                n_keys = len(keys)
                for i, key in enumerate(keys):
                    is_last = (i == n_keys - 1 and not node.get("__files__"))
                    prefix = ""
                    for draw in prefix_stack:
                        prefix += ("│   " if draw else "    ")
                    branch = "└── " if is_last else "├── "
                    out.append(f"{prefix}{branch}📁 {esc(key)}/")
                    out.extend(render_ascii_tree(node[key], prefix_stack + [not is_last], level+1, is_last))
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
                    out.append(f"{prefix}{branch}{emoji} {esc(Path(fi.path).name)} [{meta}]")
                return out
            tree = build_tree(report.files)
            tree_lines = render_ascii_tree(tree)
            out.append('<pre><code>')
            out.extend([esc(line) for line in tree_lines])
            out.append('</code></pre>')
            if include_contents:
                out.append('<hr>')
                out.append('<h2>📄 File Contents</h2>')
                for fi in report.files:
                    if fi.content is None:
                        continue
                    out.append(f'<div class="content-header"><strong>{esc(fi.path)}</strong><br>Size: {format_size(fi.size_bytes)} | Lines: {fi.lines} | Words: {fi.words} | Modified: {fi.mtime_iso}</div>')
                    out.append('<pre><code>')
                    out.extend([esc(line) for line in (fi.content or '').splitlines()])
                    out.append('</code></pre>')
            out.extend(['</div>', '</body></html>'])
            text = "".join(out)
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

        elif fmt.name == "DEEP_MARKDOWN":
            deep = build_deep_analysis(
                report,
                root_path,
                DeepAnalysisOptions.from_dict(deep_options),
            )
            text = render_deep_markdown(deep)
            save_path.write_text(text, encoding="utf-8")

        elif fmt.name == "DEEP_JSON":
            deep = build_deep_analysis(
                report,
                root_path,
                DeepAnalysisOptions.from_dict(deep_options),
            )
            save_path.write_text(deep.to_json(), encoding="utf-8")

        elif fmt.name == "LRC":
            capsule = build_compact_lrc_capsule(report)
            write_lrc_capsule(capsule, save_path)

        else:
            raise ValueError(f"Unsupported export format: {fmt}")
            
    except PermissionError as e:
        raise RuntimeError(f"Permission denied writing to {save_path}: {e}")
    except OSError as e:
        raise RuntimeError(f"File system error: {e}")
    except Exception as e:
        raise RuntimeError(f"Export failed: {e}")
