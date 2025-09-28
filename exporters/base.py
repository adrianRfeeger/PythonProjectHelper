"""Base exporter interface and registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Type


class Exporter(ABC):
    """Base interface for all export formats."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Format name (e.g., 'llm-tds', 'basic-json')."""
        pass
    
    @abstractmethod
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> bytes | str:
        """Render the analysis data to the target format."""
        pass
    
    @abstractmethod
    def mimetype(self) -> str:
        """MIME type for the output format."""
        pass
    
    @abstractmethod
    def is_lossless(self) -> bool:
        """Whether this format preserves all information."""
        pass
    
    @abstractmethod
    def is_llm_friendly(self) -> bool:
        """Whether this format is optimized for LLM consumption."""
        pass


class ExporterRegistry:
    """Registry for available exporters."""
    
    _exporters: Dict[str, Type[Exporter]] = {}
    
    @classmethod
    def register(cls, exporter_class: Type[Exporter]) -> None:
        """Register an exporter by its name."""
        instance = exporter_class()
        cls._exporters[instance.name] = exporter_class
    
    @classmethod
    def get(cls, name: str) -> Type[Exporter] | None:
        """Get an exporter class by name."""
        return cls._exporters.get(name)
    
    @classmethod
    def list_formats(cls) -> list[str]:
        """List all available format names."""
        return list(cls._exporters.keys())
    
    @classmethod
    def get_llm_formats(cls) -> list[str]:
        """List LLM-friendly formats."""
        formats = []
        for name, exporter_class in cls._exporters.items():
            instance = exporter_class()
            if instance.is_llm_friendly():
                formats.append(name)
        return formats
    
    @classmethod
    def get_lossless_formats(cls) -> list[str]:
        """List lossless formats."""
        formats = []
        for name, exporter_class in cls._exporters.items():
            instance = exporter_class()
            if instance.is_lossless():
                formats.append(name)
        return formats


def register_exporter(exporter_class: Type[Exporter]) -> Type[Exporter]:
    """Decorator to register an exporter."""
    ExporterRegistry.register(exporter_class)
    return exporter_class