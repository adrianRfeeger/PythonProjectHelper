"""Full content JSON exporter with complete source code."""
from __future__ import annotations

import json
from typing import Any, Dict

from .base import Exporter, register_exporter
from analysis.schema import ProjectAnalysis


@register_exporter
class FullContentJSONExporter(Exporter):
    """JSON format with complete file content included."""
    
    @property
    def name(self) -> str:
        return "full-content-json"
    
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Render analysis with full file content as JSON."""
        # Get the raw project report from options if available
        project_report = options.get('project_report')
        if not project_report:
            raise ValueError("full-content-json exporter requires project_report in options")
        
        # Create enhanced data structure with full content
        result = {
            "format": "full-content-json",
            "format_version": "1.0",
            "metadata": {
                "root": project_report.root,
                "generated_at": project_report.generated_at,
                "include_contents": True,
                "disclaimer": "This report includes full source code content and can be used for project recovery."
            },
            "summary": {
                "total_files": len(project_report.files),
                "text_files": sum(1 for f in project_report.files if f.content is not None),
                "total_size_bytes": sum(f.size_bytes for f in project_report.files),
                "total_lines": sum(f.lines if isinstance(f.lines, int) else 0 for f in project_report.files),
                "total_words": sum(f.words if isinstance(f.words, int) else 0 for f in project_report.files)
            },
            "files": []
        }
        
        # Add all files with full content
        for file_info in project_report.files:
            file_data = {
                "path": file_info.path,
                "size_bytes": file_info.size_bytes,
                "lines": file_info.lines,
                "words": file_info.words,
                "mtime_iso": file_info.mtime_iso,
                "language": self._detect_language(file_info.path),
                "content": file_info.content,  # Full source code content
                "has_content": file_info.content is not None
            }
            
            # Add enhanced metadata
            if file_info.content:
                file_data["content_preview"] = self._get_content_preview(file_info.content)
                file_data["encoding"] = "utf-8"
                
            result["files"].append(file_data)
        
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    
    def mimetype(self) -> str:
        return "application/json"
    
    def is_lossless(self) -> bool:
        return True  # Includes full source code
    
    def is_llm_friendly(self) -> bool:
        return False  # Too large for most LLM contexts
    
    def supports_bundling(self) -> bool:
        return True  # Can be used for complete project archival
    
    def _detect_language(self, filepath: str) -> str:
        """Detect programming language from file extension."""
        from pathlib import Path
        
        ext = Path(filepath).suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.md': 'markdown',
            '.json': 'json',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.xml': 'xml',
            '.txt': 'text',
            '.sh': 'bash',
            '.sql': 'sql',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby'
        }
        
        return language_map.get(ext, 'text')
    
    def _get_content_preview(self, content: str, max_lines: int = 10) -> str:
        """Get a preview of file content (first N lines)."""
        if not content:
            return ""
        
        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content
        
        preview_lines = lines[:max_lines]
        return "\n".join(preview_lines) + f"\n... ({len(lines) - max_lines} more lines)"