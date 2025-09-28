"""Full content Markdown exporter with complete source code."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .base import Exporter, register_exporter


@register_exporter
class FullContentMarkdownExporter(Exporter):
    """Markdown format with complete file content included."""
    
    @property
    def name(self) -> str:
        return "full-content-markdown"
    
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Render analysis with full file content as Markdown."""
        # Get the raw project report from options if available
        project_report = options.get('project_report')
        if not project_report:
            raise ValueError("full-content-markdown exporter requires project_report in options")
        
        root_name = Path(project_report.root).name
        lines = [
            f"# Project Structure: {root_name}\n",
            f"**Generated:** {project_report.generated_at}  ",
            f"**Root Path:** `{project_report.root}`",
            "",
            "⚠️ **Note:** This report includes complete source code content and can be used for project recovery.",
            ""
        ]
        
        # Summary statistics
        total_files = len(project_report.files)
        total_size = sum(f.size_bytes for f in project_report.files)
        text_files = sum(1 for f in project_report.files if f.content is not None)
        total_lines = sum(f.lines if isinstance(f.lines, int) else 0 for f in project_report.files)
        total_words = sum(f.words if isinstance(f.words, int) else 0 for f in project_report.files)
        
        lines.extend([
            "## 📊 Summary",
            "",
            f"- **Total Files:** {total_files:,}",
            f"- **Text Files:** {text_files:,}",
            f"- **Total Size:** {self._format_size(total_size)}",
            f"- **Total Lines:** {total_lines:,}",
            f"- **Total Words:** {total_words:,}",
            "",
            "## 📁 File Listing",
            ""
        ])
        
        # Build a tree structure from file paths
        tree = self._build_tree(project_report.files)
        tree_lines = self._render_tree(tree)
        lines.append('```')
        lines.extend(tree_lines)
        lines.append('```')
        
        # File contents section
        lines.extend(["\n---\n", "## 📄 File Contents\n"])
        
        for fi in project_report.files:
            if fi.content is None:
                continue
                
            # Detect file type for syntax highlighting
            ext = Path(fi.path).suffix.lower().lstrip(".") or "text"
            emoji = self._get_file_emoji(ext)
            
            lines.extend([
                f"### {emoji} `{fi.path}`",
                "",
                f"**Size:** {self._format_size(fi.size_bytes)} | **Lines:** {fi.lines} | **Words:** {fi.words} | **Modified:** {fi.mtime_iso}",
                "",
                f"```{ext}",
                fi.content.strip(),
                "```",
                ""
            ])
        
        return "\n".join(lines) + "\n"
    
    def mimetype(self) -> str:
        return "text/markdown"
    
    def is_lossless(self) -> bool:
        return True  # Includes full source code
    
    def is_llm_friendly(self) -> bool:
        return True  # Markdown is LLM-readable, though may be large
    
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
            'sql': '🗃️',
            'java': '☕',
            'cpp': '⚡',
            'c': '⚡',
            'go': '🐹',
            'rs': '🦀',
            'php': '🐘',
            'rb': '💎'
        }
        return emoji_map.get(ext, '📄')
    
    def _build_tree(self, files):
        """Build a nested tree structure from file paths."""
        from collections import defaultdict
        tree = {}
        
        for fi in files:
            parts = fi.path.split("/")
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node.setdefault("__files__", []).append(fi)
        
        return tree
    
    def _render_tree(self, node, prefix_stack=None, level=0, is_last_dir=False):
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
            out.extend(self._render_tree(node[key], prefix_stack + [not is_last], level+1, is_last))
        
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
            ext = Path(fi.path).suffix.lower().lstrip(".")
            emoji = self._get_file_emoji(ext)
            filename = Path(fi.path).name
            meta = f"{size}, {lines_str} lines, {words_str} words, modified {fi.mtime_iso}"
            out.append(f"{prefix}{branch}{emoji} {filename} [{meta}]")
        
        return out