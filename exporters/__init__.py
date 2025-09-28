"""Exporters package initialization and registry."""
from __future__ import annotations

from .base import ExporterRegistry, Exporter, register_exporter

# Import all exporters to ensure they're registered
from .llm_tds import LLMTDSExporter
from .basic_json import BasicJSONExporter
from .basic_markdown import BasicMarkdownExporter
from .full_content_json import FullContentJSONExporter
from .full_content_markdown import FullContentMarkdownExporter
from .legacy_html import LegacyHTMLExporter

# Export main classes and functions
__all__ = [
    'ExporterRegistry',
    'Exporter', 
    'register_exporter',
    'LLMTDSExporter',
    'BasicJSONExporter',
    'BasicMarkdownExporter',
    'FullContentJSONExporter',
    'FullContentMarkdownExporter',
    'LegacyHTMLExporter',
]


def get_exporter(format_name: str) -> Exporter | None:
    """Get an exporter instance by format name."""
    exporter_class = ExporterRegistry.get(format_name)
    if exporter_class:
        return exporter_class()
    return None


def list_available_formats() -> list[str]:
    """List all available export formats."""
    return ExporterRegistry.list_formats()


def get_llm_formats() -> list[str]:
    """Get formats optimized for LLM consumption."""
    return ExporterRegistry.get_llm_formats()


def get_lossless_formats() -> list[str]:
    """Get lossless formats."""
    return ExporterRegistry.get_lossless_formats()