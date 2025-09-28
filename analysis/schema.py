"""Pydantic models for project analysis data."""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ClassInfo(BaseModel):
    """Information about a class definition."""
    name: str
    bases: List[str] = Field(default_factory=list)
    methods: List[str] = Field(default_factory=list)
    doc1: Optional[str] = None  # First line of docstring
    lineno: Optional[int] = None


class FunctionInfo(BaseModel):
    """Information about a function definition."""
    name: str
    signature: str
    returns: Optional[str] = None
    doc1: Optional[str] = None  # First line of docstring
    lineno: Optional[int] = None


class UIInfo(BaseModel):
    """Information about UI elements in the file."""
    windows: List[str] = Field(default_factory=list)
    widgets: List[str] = Field(default_factory=list)
    callbacks: List[str] = Field(default_factory=list)


class ComplexityInfo(BaseModel):
    """Complexity metrics for a file."""
    cyclomatic: int = 0
    todo_count: int = 0
    hotspot: float = 0.0  # Risk/complexity score


class ImportInfo(BaseModel):
    """Import information for a file."""
    internal: List[str] = Field(default_factory=list)
    external: List[str] = Field(default_factory=list)


class FileAnalysis(BaseModel):
    """Analysis data for a single file."""
    path: str
    language: str = "unknown"
    size_bytes: int = 0
    sloc: int = 0  # Source lines of code
    imports: ImportInfo = Field(default_factory=ImportInfo)
    classes: List[ClassInfo] = Field(default_factory=list)
    functions: List[FunctionInfo] = Field(default_factory=list)
    ui: UIInfo = Field(default_factory=UIInfo)
    tests: List[str] = Field(default_factory=list)
    complexity: ComplexityInfo = Field(default_factory=ComplexityInfo)
    responsibility: Optional[str] = None  # Inferred purpose/role


class ProjectTotals(BaseModel):
    """Project-level totals."""
    files: int = 0
    sloc: int = 0
    size_bytes: int = 0


class ProjectInfo(BaseModel):
    """Project metadata."""
    name: str
    fingerprint: str  # SHA256 hex
    root_rel: str = "."
    totals: ProjectTotals = Field(default_factory=ProjectTotals)


class GraphNode(BaseModel):
    """Node in a dependency graph."""
    id: str
    label: str
    type: str = "module"


class GraphEdge(BaseModel):
    """Edge in a dependency graph."""
    source: str
    target: str
    type: str = "imports"


class DependencyGraph(BaseModel):
    """Dependency graph structure."""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class ProjectGraphs(BaseModel):
    """All graphs for the project."""
    imports: DependencyGraph = Field(default_factory=DependencyGraph)


class ProjectAnalysis(BaseModel):
    """Complete project analysis data."""
    version: str = "1.0"
    generated_at: datetime = Field(default_factory=datetime.now)
    project: ProjectInfo
    options: Dict[str, Any] = Field(default_factory=dict)
    files: List[FileAnalysis] = Field(default_factory=list)
    graphs: ProjectGraphs = Field(default_factory=ProjectGraphs)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }