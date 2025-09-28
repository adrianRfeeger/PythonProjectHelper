"""Basic JSON exporter for machine-readable output."""
from __future__ import annotations

import json
from typing import Any, Dict

from .base import Exporter, register_exporter
from analysis.schema import ProjectAnalysis


@register_exporter
class BasicJSONExporter(Exporter):
    """Machine-readable JSON format."""
    
    @property
    def name(self) -> str:
        return "basic-json"
    
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        """Render analysis as clean JSON."""
        project_analysis = ProjectAnalysis(**analysis)
        
        # Convert to dictionary and ensure proper serialization
        result = project_analysis.dict()
        
        # Add format metadata
        result["format"] = "basic-json"
        result["format_version"] = "1.0"
        
        return json.dumps(result, indent=2, ensure_ascii=False, default=str)
    
    def mimetype(self) -> str:
        return "application/json"
    
    def is_lossless(self) -> bool:
        return True  # For the analysis data (no source code bodies)
    
    def is_llm_friendly(self) -> bool:
        return False  # Structured for machines, not optimized for LLMs