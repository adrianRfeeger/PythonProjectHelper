"""Basic Markdown exporter for human-readable documentation."""
from __future__ import annotations

from typing import Any, Dict

from .base import Exporter, register_exporter
from analysis.schema import ProjectAnalysis


@register_exporter
class BasicMarkdownExporter(Exporter):
    """Human-readable Markdown format."""
    
    @property
    def name(self) -> str:
        return "basic-markdown"
    
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Render analysis as Markdown documentation."""
        project_analysis = ProjectAnalysis(**analysis)
        
        # Check if content should be included
        include_content = options.get('include_content', False)
        project_report = options.get('project_report')
        content_map = {}
        
        if include_content and project_report:
            # Create a mapping of file paths to content
            content_map = {f.path: f.content for f in project_report.files if f.content is not None}
        
        lines = []
        
        # Header
        lines.append(f"# {project_analysis.project.name}")
        lines.append("")
        lines.append(f"**Generated:** {project_analysis.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Root:** {project_analysis.project.root_rel}")
        if include_content:
            lines.append(f"**Content:** Included")
        lines.append("")
        
        # Summary
        totals = project_analysis.project.totals
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Files:** {totals.files:,}")
        lines.append(f"- **Lines of Code:** {totals.sloc:,}")
        lines.append(f"- **Total Size:** {self._format_size(totals.size_bytes)}")
        lines.append("")
        
        # File listing
        lines.append("## Files")
        lines.append("")
        
        for file_info in sorted(project_analysis.files, key=lambda f: f.path):
            lines.append(f"### 📄 {file_info.path}")
            lines.append("")
            
            # Basic info
            lines.append(f"- **Language:** {file_info.language}")
            lines.append(f"- **Size:** {self._format_size(file_info.size_bytes)}")
            lines.append(f"- **Lines:** {file_info.sloc}")
            
            if file_info.responsibility:
                lines.append(f"- **Purpose:** {file_info.responsibility}")
            
            lines.append("")
            
            # Imports
            if file_info.imports.internal or file_info.imports.external:
                lines.append("**Imports:**")
                lines.append("")
                
                if file_info.imports.internal:
                    lines.append("*Internal:*")
                    for imp in sorted(file_info.imports.internal):
                        lines.append(f"- `{imp}`")
                    lines.append("")
                
                if file_info.imports.external:
                    lines.append("*External:*")
                    for imp in sorted(file_info.imports.external):
                        lines.append(f"- `{imp}`")
                    lines.append("")
            
            # Classes
            if file_info.classes:
                lines.append("**Classes:**")
                lines.append("")
                lines.append("| Class | Bases | Methods | Description |")
                lines.append("|-------|-------|---------|-------------|")
                
                for cls in file_info.classes:
                    bases = ", ".join(cls.bases) if cls.bases else "—"
                    methods = f"{len(cls.methods)} methods" if cls.methods else "No methods"
                    doc = cls.doc1 or "—"
                    lines.append(f"| `{cls.name}` | `{bases}` | {methods} | {doc} |")
                
                lines.append("")
            
            # Functions
            if file_info.functions:
                lines.append("**Functions:**")
                lines.append("")
                lines.append("| Function | Returns | Description |")
                lines.append("|----------|---------|-------------|")
                
                for func in file_info.functions:
                    returns = func.returns or "—"
                    doc = func.doc1 or "—"
                    lines.append(f"| `{func.signature}` | `{returns}` | {doc} |")
                
                lines.append("")
            
            # Tests
            if file_info.tests:
                lines.append("**Tests:**")
                lines.append("")
                for test in file_info.tests:
                    lines.append(f"- `{test}`")
                lines.append("")
            
            # Complexity
            if file_info.complexity.todo_count > 0 or file_info.complexity.cyclomatic > 0:
                lines.append("**Complexity:**")
                lines.append("")
                if file_info.complexity.cyclomatic > 0:
                    lines.append(f"- Cyclomatic complexity: {file_info.complexity.cyclomatic}")
                if file_info.complexity.todo_count > 0:
                    lines.append(f"- TODO items: {file_info.complexity.todo_count}")
                if file_info.complexity.hotspot > 0:
                    lines.append(f"- Hotspot score: {file_info.complexity.hotspot:.2f}")
                lines.append("")
            
            # File content (if requested and available)
            if include_content and file_info.path in content_map:
                content = content_map[file_info.path]
                if content and content.strip():
                    lines.append("**Content:**")
                    lines.append("")
                    lines.append("```" + file_info.language)
                    lines.append(content)
                    lines.append("```")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def mimetype(self) -> str:
        return "text/markdown"
    
    def is_lossless(self) -> bool:
        return True  # For the analysis data
    
    def is_llm_friendly(self) -> bool:
        return True  # Markdown is LLM-readable
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"