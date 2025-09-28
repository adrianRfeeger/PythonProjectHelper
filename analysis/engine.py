"""Analysis engine to convert ProjectReport to the new schema."""
from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Any

from .schema import (
    ProjectAnalysis, ProjectInfo, ProjectTotals, FileAnalysis,
    ClassInfo, FunctionInfo, ImportInfo, ComplexityInfo, UIInfo,
    ProjectGraphs, DependencyGraph, GraphNode, GraphEdge
)
from report import ProjectReport, FileInfo


class AnalysisEngine:
    """Converts ProjectReport to the new analysis schema."""
    
    def __init__(self):
        self.ui_frameworks = {
            'tkinter': ['Tk', 'Toplevel', 'Frame', 'Button', 'Label', 'Entry', 'Text', 'Canvas'],
            'customtkinter': ['CTk', 'CTkFrame', 'CTkButton', 'CTkLabel', 'CTkEntry'],
            'pygubu': ['Builder', 'Application'],
            'qt': ['QWidget', 'QMainWindow', 'QPushButton', 'QLabel', 'QLineEdit'],
            'gtk': ['Gtk.Window', 'Gtk.Button', 'Gtk.Label', 'Gtk.Entry'],
        }
    
    def analyze_project(self, project_report: ProjectReport, options: Dict[str, Any] | None = None) -> ProjectAnalysis:
        """Convert ProjectReport to ProjectAnalysis."""
        options = options or {}
        
        # Calculate project fingerprint
        fingerprint = self._calculate_fingerprint(project_report)
        
        # Calculate totals
        total_files = len(project_report.files)
        total_sloc = 0
        total_size = 0
        
        # Analyze each file
        file_analyses = []
        all_imports = {'internal': set(), 'external': set()}
        
        for file_info in project_report.files:
            analysis = self._analyze_file(file_info, project_report.root, options)
            file_analyses.append(analysis)
            
            total_sloc += analysis.sloc
            total_size += analysis.size_bytes
            
            # Collect imports for graph
            all_imports['internal'].update(analysis.imports.internal)
            all_imports['external'].update(analysis.imports.external)
        
        # Build dependency graph
        import_graph = self._build_import_graph(file_analyses)
        
        return ProjectAnalysis(
            project=ProjectInfo(
                name=Path(project_report.root).name,
                fingerprint=fingerprint,
                root_rel=".",
                totals=ProjectTotals(
                    files=total_files,
                    sloc=total_sloc,
                    size_bytes=total_size
                )
            ),
            options=options,
            files=file_analyses,
            graphs=ProjectGraphs(imports=import_graph)
        )
    
    def _analyze_file(self, file_info: FileInfo, project_root: str, options: Dict[str, Any] | None) -> FileAnalysis:
        """Analyze a single file."""
        file_path = Path(project_root) / file_info.path
        
        # Basic file info
        analysis = FileAnalysis(
            path=file_info.path,
            language=self._detect_language(file_info.path),
            size_bytes=file_info.size_bytes,
            sloc=file_info.lines if isinstance(file_info.lines, int) else 0
        )
        
        # Parse content if available
        if file_info.content and analysis.language == "python":
            self._analyze_python_content(file_info.content, analysis)
        
        # Infer responsibility
        analysis.responsibility = self._infer_responsibility(file_info.path, analysis)
        
        return analysis
    
    def _analyze_python_content(self, content: str, analysis: FileAnalysis) -> None:
        """Analyze Python file content using AST."""
        try:
            tree = ast.parse(content)
            
            # Extract imports, classes, and functions
            imports = {'internal': [], 'external': []}
            classes = []
            functions = []
            tests = []
            ui_elements = {'windows': [], 'widgets': [], 'callbacks': []}
            complexity = {'cyclomatic': 0, 'todo_count': 0}
            
            # Count TODO/FIXME items
            complexity['todo_count'] = len(re.findall(r'#\s*(TODO|FIXME|XXX)', content, re.IGNORECASE))
            
            for node in ast.walk(tree):
                # Handle imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports['external'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith('.'):
                        imports['internal'].append(module)
                    else:
                        imports['external'].append(module)
                
                # Handle classes
                elif isinstance(node, ast.ClassDef):
                    bases = [self._ast_to_string(base) for base in node.bases]
                    methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    doc = ast.get_docstring(node)
                    
                    classes.append(ClassInfo(
                        name=node.name,
                        bases=bases,
                        methods=methods,
                        doc1=doc.split('\n')[0] if doc else None,
                        lineno=node.lineno
                    ))
                    
                    # Check for UI elements
                    for base in bases:
                        self._check_ui_element(base, ui_elements)
                
                # Handle functions
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    signature = self._format_function_signature(node)
                    doc = ast.get_docstring(node)
                    returns = self._ast_to_string(node.returns) if node.returns else None
                    
                    func_info = FunctionInfo(
                        name=node.name,
                        signature=signature,
                        returns=returns,
                        doc1=doc.split('\n')[0] if doc else None,
                        lineno=node.lineno
                    )
                    functions.append(func_info)
                    
                    # Check if it's a test
                    if node.name.startswith('test_') or 'test' in analysis.path.lower():
                        tests.append(f"{analysis.path}::{node.name}")
                    
                    # Estimate cyclomatic complexity (basic approximation)
                    complexity['cyclomatic'] += self._estimate_complexity(node)
            
            # Update analysis
            analysis.imports = ImportInfo(
                internal=imports['internal'],
                external=imports['external']
            )
            analysis.classes = classes
            analysis.functions = functions
            analysis.tests = tests
            analysis.ui = UIInfo(**ui_elements)
            analysis.complexity = ComplexityInfo(
                cyclomatic=complexity['cyclomatic'],
                todo_count=complexity['todo_count'],
                hotspot=min(complexity['cyclomatic'] * 0.1 + complexity['todo_count'] * 0.2, 10.0)
            )
            
        except SyntaxError:
            # If parsing fails, just skip AST analysis
            pass
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
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
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'config',
            '.txt': 'text',
        }
        return language_map.get(ext, 'unknown')
    
    def _infer_responsibility(self, file_path: str, analysis: FileAnalysis) -> str:
        """Infer the purpose/responsibility of a file."""
        path_lower = file_path.lower()
        name = Path(file_path).stem.lower()
        
        # Common patterns
        if 'test' in path_lower:
            return "Testing"
        elif name in ['main', '__main__', 'app', 'run']:
            return "Entry point"
        elif name in ['config', 'settings', 'constants']:
            return "Configuration"
        elif name.startswith('gui') or name.endswith('_gui') or analysis.ui.windows:
            return "User interface"
        elif 'util' in name or 'helper' in name or 'tool' in name:
            return "Utilities"
        elif name in ['models', 'schema', 'data']:
            return "Data models"
        elif name.endswith('_client') or name.endswith('_api'):
            return "API client"
        elif analysis.classes and not analysis.functions:
            return "Class definitions"
        elif analysis.functions and not analysis.classes:
            return "Functions/utilities"
        elif analysis.imports.external:
            return "Module integration"
        else:
            return "Core logic"
    
    def _ast_to_string(self, node: ast.AST) -> str:
        """Convert AST node to string representation."""
        try:
            return ast.unparse(node)
        except AttributeError:
            # Fallback for Python < 3.9
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Constant):
                return str(node.value)
            else:
                return "<expression>"
    
    def _format_function_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Format function signature."""
        args = []
        
        # Regular arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._ast_to_string(arg.annotation)}"
            args.append(arg_str)
        
        # *args
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        
        # **kwargs
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}{node.name}({', '.join(args)})"
    
    def _estimate_complexity(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Estimate cyclomatic complexity (simplified)."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.With, ast.AsyncWith)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
        
        return complexity
    
    def _check_ui_element(self, element_name: str, ui_elements: Dict[str, List[str]]) -> None:
        """Check if an element is a UI component."""
        for framework, widgets in self.ui_frameworks.items():
            if element_name in widgets:
                if 'window' in element_name.lower() or 'top' in element_name.lower():
                    ui_elements['windows'].append(element_name)
                else:
                    ui_elements['widgets'].append(element_name)
                break
    
    def _calculate_fingerprint(self, project_report: ProjectReport) -> str:
        """Calculate project fingerprint based on file paths and sizes."""
        hasher = hashlib.sha256()
        
        for file_info in sorted(project_report.files, key=lambda f: f.path):
            content = f"{file_info.path}::{file_info.size_bytes}"
            hasher.update(content.encode('utf-8'))
        
        return hasher.hexdigest()
    
    def _build_import_graph(self, file_analyses: List[FileAnalysis]) -> DependencyGraph:
        """Build import dependency graph."""
        nodes = []
        edges = []
        
        # Create nodes for all files and external dependencies
        file_modules = set()
        external_modules = set()
        
        for analysis in file_analyses:
            module_name = analysis.path.replace('/', '.').replace('.py', '')
            file_modules.add(module_name)
            nodes.append(GraphNode(
                id=module_name,
                label=Path(analysis.path).name,
                type="internal_module"
            ))
            
            # Collect external modules
            external_modules.update(analysis.imports.external)
        
        # Add external module nodes
        for ext_mod in external_modules:
            if ext_mod:  # Skip empty strings
                nodes.append(GraphNode(
                    id=ext_mod,
                    label=ext_mod,
                    type="external_module"
                ))
        
        # Create edges for imports
        for analysis in file_analyses:
            source_module = analysis.path.replace('/', '.').replace('.py', '')
            
            # Internal imports
            for imp in analysis.imports.internal:
                if imp and imp in file_modules:
                    edges.append(GraphEdge(
                        source=source_module,
                        target=imp,
                        type="internal_import"
                    ))
            
            # External imports
            for imp in analysis.imports.external:
                if imp:
                    edges.append(GraphEdge(
                        source=source_module,
                        target=imp,
                        type="external_import"
                    ))
        
        return DependencyGraph(nodes=nodes, edges=edges)