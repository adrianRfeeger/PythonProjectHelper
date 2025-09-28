"""Legacy format exporter that mimics the original outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .base import Exporter, register_exporter


@register_exporter
class LegacyHTMLExporter(Exporter):
    """HTML format matching the original output style with full content."""
    
    @property
    def name(self) -> str:
        return "legacy-html"
    
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Render analysis as HTML matching the original format."""
        # Get the raw project report from options if available
        project_report = options.get('project_report')
        if not project_report:
            raise ValueError("legacy-html exporter requires project_report in options")
        
        def esc(s):
            """HTML escape."""
            return (str(s)
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))
        
        root_name = Path(project_report.root).name
        
        # CSS styling (modernised version of original)
        css = """
        <style>
        body { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; background: #f9fafb; color: #222; margin: 0; padding: 0; }
        .container { max-width: 900px; margin: 2rem auto; background: #fff; border-radius: 10px; box-shadow: 0 2px 8px #0001; padding: 2rem; }
        h1, h2, h3 { color: #2563eb; }
        h1 { border-bottom: 3px solid #3b82f6; padding-bottom: 0.5rem; }
        h2 { border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25rem; margin-top: 2rem; }
        h3 { margin-top: 1.5rem; }
        .meta { color: #6b7280; font-size: 0.9rem; margin-bottom: 2rem; }
        .summary { background: #f0f9ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #0ea5e9; margin: 1rem 0; }
        pre { background: #1f2937; color: #f9fafb; border-radius: 6px; padding: 1rem; overflow-x: auto; margin: 1rem 0; }
        code { font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace; }
        .content-header { background: #eff6ff; padding: 0.75rem; border-radius: 6px; margin: 1rem 0 0.5rem 0; border-left: 4px solid #3b82f6; }
        hr { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
        .file-tree { background: #f8fafc; padding: 1rem; border-radius: 6px; border: 1px solid #e2e8f0; }
        </style>
        """
        
        # HTML structure
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
        
        # Build content
        out = [
            head,
            f"<h1>📁 Project Structure: {root_name}</h1>",
            f'<div class="meta">Generated: {esc(project_report.generated_at)} | Root: <code>{esc(project_report.root)}</code></div>'
        ]
        
        # Summary section
        total_files = len(project_report.files)
        total_size = sum(f.size_bytes for f in project_report.files)
        text_files = sum(1 for f in project_report.files if f.content is not None)
        
        out.extend([
            '<div class="summary">',
            '<h2>📊 Summary</h2>',
            f'<p><strong>Total Files:</strong> {total_files:,}<br>',
            f'<strong>Text Files:</strong> {text_files:,}<br>',
            f'<strong>Total Size:</strong> {esc(self._format_size(total_size))}</p>',
            '</div>'
        ])
        
        # File tree
        out.append('<h2>📁 File Listing</h2>')
        tree = self._build_tree(project_report.files)
        tree_lines = self._render_ascii_tree(tree)
        out.append('<div class="file-tree">')
        out.append('<pre><code>')
        out.extend([esc(line) for line in tree_lines])
        out.append('</code></pre>')
        out.append('</div>')
        
        # File contents
        if any(f.content for f in project_report.files):
            out.append('<hr>')
            out.append('<h2>📄 File Contents</h2>')
            
            for fi in project_report.files:
                if fi.content is None:
                    continue
                
                emoji = self._get_file_emoji(Path(fi.path).suffix.lower())
                meta = f"Size: {self._format_size(fi.size_bytes)} | Lines: {fi.lines} | Words: {fi.words} | Modified: {fi.mtime_iso}"
                
                out.extend([
                    f'<h3>{emoji} <code>{esc(fi.path)}</code></h3>',
                    f'<div class="content-header">{esc(meta)}</div>',
                    '<pre><code>',
                    esc(fi.content or ''),
                    '</code></pre>'
                ])
        
        out.extend(['</div>', '</body>', '</html>'])
        return "\n".join(out)
    
    def mimetype(self) -> str:
        return "text/html"
    
    def is_lossless(self) -> bool:
        return True  # Includes full source code
    
    def is_llm_friendly(self) -> bool:
        return False  # HTML is not optimal for LLMs
    
    def supports_bundling(self) -> bool:
        return True  # Can be used for complete project documentation
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def _get_file_emoji(self, ext: str) -> str:
        """Get appropriate emoji for file extension."""
        ext = ext.lstrip('.')
        emoji_map = {
            'py': '🐍',
            'js': '📜',
            'ts': '📘',
            'html': '🌐',
            'css': '🎨',
            'md': '📝',
            'json': '📋',
            'yml': '⚙️',
            'yaml': '⚙️',
            'xml': '📄',
            'txt': '📄',
            'sh': '🔧',
            'sql': '🗃️'
        }
        return emoji_map.get(ext, '📄')
    
    def _build_tree(self, files):
        """Build a nested tree structure from file paths."""
        tree = {}
        for fi in files:
            parts = fi.path.split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node.setdefault("__files__", []).append(fi)
        return tree
    
    def _render_ascii_tree(self, node, prefix_stack=None, level=0, is_last_dir=False):
        """Render tree structure as ASCII art."""
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
            out.append(f"{prefix}{branch}📁 {key}/")
            out.extend(self._render_ascii_tree(node[key], prefix_stack + [not is_last], level+1, is_last))
        
        # Render files in this directory
        files = sorted(node.get("__files__", []), key=lambda f: f.path)
        n_files = len(files)
        
        for j, fi in enumerate(files):
            is_last_file = (j == n_files - 1)
            prefix = ""
            for draw in prefix_stack:
                prefix += ("│   " if draw else "    ")
            
            branch = "└── " if is_last_file else "├── "
            size = self._format_size(fi.size_bytes)
            lines_str = str(fi.lines) if fi.lines != "?" else "—"
            words_str = str(fi.words) if fi.words != "?" else "—"
            ext = Path(fi.path).suffix.lower()
            emoji = self._get_file_emoji(ext)
            filename = Path(fi.path).name
            meta = f"{size}, {lines_str} lines, {words_str} words, modified {fi.mtime_iso}"
            out.append(f"{prefix}{branch}{emoji} {filename} [{meta}]")
        
        return out