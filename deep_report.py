"""Deep analysis report generation based on deep_report_spec.md."""
from __future__ import annotations

import ast
import hashlib
import json
import mimetypes
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
from typing import Iterable, Optional

from report import ProjectReport, FileInfo


@dataclass
class DeepAnalysisOptions:
    """Toggles to control size/detail of deep analysis reports."""

    include_functions: bool = True
    include_classes: bool = True
    include_api_index: bool = True
    include_dependency_map: bool = True
    include_call_graph: bool = True
    include_cli_inventory: bool = True
    include_config_schema: bool = True
    include_ui_catalogue: bool = True
    include_tests: bool = True
    include_string_catalogue: bool = True
    include_binary_manifest: bool = True
    include_llm_bundle: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, bool] | None) -> "DeepAnalysisOptions":
        if not data:
            return cls()
        
        kwargs = {}
        for f in fields(cls):
            if f.name in data:
                kwargs[f.name] = data[f.name]
            else:
                kwargs[f.name] = f.default
        return cls(**kwargs)


@dataclass
class SignatureSummary:
    """Represents a function or class signature summary."""

    name: str
    signature: str
    doc: str | None
    decorators: list[str] = field(default_factory=list)
    lineno: int | None = None


@dataclass
class DeepFileAnalysis:
    """Structured, non-recoverable view of a file."""

    path: str
    language: str
    size_bytes: int
    mtime_iso: str
    sloc: int
    todo_count: int
    responsibility: str | None
    constructs: dict[str, list[str]]
    functions: list[SignatureSummary]
    classes: list[SignatureSummary]
    imports: list[str]
    internal_imports: list[str]
    external_imports: list[str]
    call_targets: list[str]
    env_vars: list[str]
    config_keys: list[str]
    cli_commands: list[str]
    entrypoints: list[str]
    ui_widgets: list[str]
    tests: list[str]
    strings: list[str]
    licence: str | None
    asset_meta: dict[str, str] | None
    complexity: str
    risk_score: float


@dataclass
class APIItem:
    """Public API member for index."""

    module: str
    qualname: str
    signature: str
    kind: str
    doc: str | None


@dataclass
class DeepAnalysisReport:
    """Aggregate report for an entire project."""

    root: str
    generated_at: str
    files: list[DeepFileAnalysis]
    api_index: list[APIItem]
    dependency_map: dict[str, list[str]]
    call_graph: dict[str, list[str]]
    cli_inventory: list[dict[str, str]]
    config_schema: dict[str, list[str]]
    ui_catalogue: list[dict[str, str]]
    test_map: dict[str, list[str]]
    string_catalogue: dict[str, list[str]]
    licence_findings: list[dict[str, str]]
    binary_manifest: list[dict[str, str]]
    llm_bundle: list[dict[str, object]]

    def to_json(self) -> str:
        """Return a machine-readable JSON string."""

        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class PythonAnalyzer(ast.NodeVisitor):
    """Collect per-file information for Python sources."""

    def __init__(self, module_path: str) -> None:
        self.module_path = module_path
        self.docstring = None
        self.functions: list[SignatureSummary] = []
        self.classes: list[SignatureSummary] = []
        self.imports: set[str] = set()
        self.call_targets: set[str] = set()
        self.env_vars: set[str] = set()
        self.config_keys: set[str] = set()
        self.cli_commands: set[str] = set()
        self.entrypoints: set[str] = set()
        self.ui_widgets: set[str] = set()
        self.tests: set[str] = set()
        self.todo_locations: int = 0
        self._current_class: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: D401 - part of NodeVisitor
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: D401
        module = node.module or ""
        for alias in node.names:
            if module:
                self.imports.add(f"{module}.{alias.name}")
            else:
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: D401
        target = self._expr_to_name(node.func)
        if target:
            self.call_targets.add(target)
            if target.endswith("ArgumentParser"):
                self.cli_commands.add(target)
            if target.endswith(("Tk", "CTk", "Frame", "Button", "Label")):
                self.ui_widgets.add(target)
            if target.endswith(("getenv", "environ.get")) and node.args:
                key = self._extract_string(node.args[0])
                if key:
                    self.env_vars.add(key)
        self.visit_Call_keywords(node.keywords)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: D401
        if isinstance(node.value, ast.Call):
            target = self._expr_to_name(node.value.func)
            if target and target.endswith("ArgumentParser"):
                self.cli_commands.add(target)
        self.generic_visit(node)

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Process both regular and async function definitions."""
        qual = self._qualname(node.name)
        signature = self._format_signature(node)
        doc = ast.get_docstring(node)
        summary = SignatureSummary(
            name=qual,
            signature=signature,
            doc=_first_line(doc),
            decorators=[self._expr_to_name(d) or "" for d in node.decorator_list if d],
            lineno=node.lineno,
        )
        self.functions.append(summary)

        if qual.startswith("test_") or "/tests/" in self.module_path.replace("\\", "/"):
            self.tests.add(qual)

        for stmt in node.body:
            if isinstance(stmt, ast.If):
                cond = ast.unparse(stmt.test) if hasattr(ast, "unparse") else None
                if cond and "__name__" in cond and "__main__" in cond:
                    self.entrypoints.add(qual)

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: D401
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: D401
        self._process_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: D401
        qual = self._qualname(node.name)
        bases = [self._expr_to_name(base) or ast.unparse(base) for base in node.bases] if node.bases else []
        signature = f"class {qual}({', '.join(bases)})"
        doc = ast.get_docstring(node)
        summary = SignatureSummary(
            name=qual,
            signature=signature,
            doc=_first_line(doc),
            decorators=[self._expr_to_name(d) or "" for d in node.decorator_list if d],
            lineno=node.lineno,
        )
        self.classes.append(summary)

        if any(base and "TestCase" in base for base in bases):
            self.tests.add(qual)

        self._current_class.append(node.name)
        self.generic_visit(node)
        self._current_class.pop()

    def visit_If(self, node: ast.If) -> None:  # noqa: D401
        cond = ast.unparse(node.test) if hasattr(ast, "unparse") else None
        if cond and "__name__" in cond and "__main__" in cond:
            self.entrypoints.add(f"{self.module_path}::<module>")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: D401
        target = self._expr_to_name(node.value)
        if target in {"os.environ", "environ"}:
            key = self._extract_string(node.slice)
            if key:
                self.env_vars.add(key)
        self.generic_visit(node)

    def visit_Call_keywords(self, keywords: Iterable[ast.keyword]) -> None:
        for keyword in keywords:
            if keyword.arg and "env" in keyword.arg.lower():
                constant = self._extract_string(keyword.value)
                if constant:
                    self.env_vars.add(constant)

    def _qualname(self, name: str) -> str:
        if self._current_class:
            return ".".join(self._current_class + [name])
        return name

    def _expr_to_name(self, expr: ast.AST | None) -> str | None:
        if expr is None:
            return None
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            value = self._expr_to_name(expr.value)
            return f"{value}.{expr.attr}" if value else expr.attr
        if hasattr(ast, "unparse"):
            try:
                return ast.unparse(expr)
            except Exception:  # pragma: no cover - defensive
                return None
        return None

    def _extract_string(self, node: ast.AST | None) -> str | None:
        if node is None:
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Str):  # py<3.8 compat
            if isinstance(node.s, str):
                return node.s
        return None

    def _format_signature(self, node: ast.AST) -> str:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return getattr(node, "name", "<lambda>")

        args = node.args
        parts: list[str] = []

        def format_arg(arg: ast.arg) -> str:
            annotation = self._expr_to_name(arg.annotation) if getattr(arg, "annotation", None) else None
            return f"{arg.arg}: {annotation}" if annotation else arg.arg

        for arg in getattr(args, "posonlyargs", []):
            parts.append(format_arg(arg))
        if getattr(args, "posonlyargs", []):
            parts.append("/")

        for arg in args.args:
            parts.append(format_arg(arg))

        if args.vararg:
            parts.append("*" + format_arg(args.vararg))
        elif args.kwonlyargs:
            parts.append("*")

        for arg in args.kwonlyargs:
            parts.append(format_arg(arg))

        if args.kwarg:
            parts.append("**" + format_arg(args.kwarg))

        return f"{node.name}({', '.join(parts)})"


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()
    return None


TODO_PATTERN = re.compile(r"\b(TODO|FIXME|XXX)\b", re.IGNORECASE)


def _language_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return "Python"
    if ext in {".yml", ".yaml"}:
        return "YAML"
    if ext in {".json"}:
        return "JSON"
    if ext in {".md", ".markdown"}:
        return "Markdown"
    if ext in {".ini", ".cfg", ".conf"}:
        return "Config"
    if ext in {".html", ".htm"}:
        return "HTML"
    if ext in {".css"}:
        return "CSS"
    if ext in {".js", ".ts"}:
        return "JavaScript/TypeScript"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".svg"}:
        return "Image"
    if ext in {".mp3", ".wav", ".flac"}:
        return "Audio"
    if ext in {".mp4", ".mov", ".avi"}:
        return "Video"
    return ext.lstrip(".") or "file"


def _compute_sloc(contents: str) -> int:
    return sum(1 for line in contents.splitlines() if line.strip())


def _count_todos(contents: str) -> int:
    return len(TODO_PATTERN.findall(contents))


def _compute_complexity(node: ast.AST) -> int:
    class ComplexityVisitor(ast.NodeVisitor):
        score = 1

        def generic_visit(self, node: ast.AST) -> None:  # noqa: D401
            if isinstance(node, (ast.If, ast.For, ast.While, ast.And, ast.Or, ast.Try, ast.BoolOp, ast.With)):
                self.score += 1
            super().generic_visit(node)

    visitor = ComplexityVisitor()
    visitor.visit(node)
    return visitor.score


def _risk_band(complexity: int, sloc: int, todo: int) -> tuple[str, float]:
    base = complexity + sloc / 200 + todo * 0.5
    if base < 5:
        return "low", base
    if base < 15:
        return "medium", base
    return "high", base


def _responsibility_hint(path: Path, contents: str) -> str | None:
    lower = contents.lower()
    if "tkinter" in lower or "customtkinter" in lower:
        return "GUI layer"
    if "argparse" in lower or "click" in lower:
        return "CLI or entrypoint"
    if "class " in contents and "test" in path.name.lower():
        return "Tests"
    if "config" in path.parts:
        return "Configuration"
    if "model" in lower and "class" in contents:
        return "Domain model"
    return None


def _detect_strings(node: ast.AST) -> set[str]:
    strings: set[str] = set()

    class StringsVisitor(ast.NodeVisitor):
        def visit_Constant(self, constant: ast.Constant) -> None:  # noqa: D401
            if isinstance(constant.value, str):
                value = constant.value.strip()
                if 0 < len(value) <= 200 and "\n" not in value:
                    strings.add(value)

    StringsVisitor().visit(node)
    return strings


def build_deep_analysis(
    report: ProjectReport,
    root_path: Path,
    options: DeepAnalysisOptions | None = None,
) -> DeepAnalysisReport:
    """Generate a deep analysis report compliant with the specification."""

    options = options or DeepAnalysisOptions()

    files: list[DeepFileAnalysis] = []
    api_index: list[APIItem] = []
    dependency_map: dict[str, list[str]] = {}
    call_graph: dict[str, list[str]] = {}
    cli_inventory: list[dict[str, str]] = []
    config_schema: dict[str, list[str]] = defaultdict(list)
    ui_catalogue: list[dict[str, str]] = []
    test_map: dict[str, list[str]] = defaultdict(list)
    string_catalogue: dict[str, list[str]] = defaultdict(list)
    licence_findings: list[dict[str, str]] = []
    binary_manifest: list[dict[str, str]] = []
    llm_bundle: list[dict[str, object]] = []

    internal_modules = _derive_internal_modules(report.files)

    for info in report.files:
        path = Path(root_path) / info.path
        language = _language_for_path(path)
        text: str | None = None
        try:
            if language.lower() not in {"image", "audio", "video"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = None

        sloc = _compute_sloc(text) if text else 0
        todo_count = _count_todos(text) if text else 0
        responsibility = _responsibility_hint(path, text or "")

        constructs: dict[str, list[str]] = defaultdict(list)
        functions: list[SignatureSummary] = []
        classes: list[SignatureSummary] = []
        imports: set[str] = set()
        internal_imports: set[str] = set()
        external_imports: set[str] = set()
        call_targets: set[str] = set()
        env_vars: set[str] = set()
        config_keys: set[str] = set()
        cli_commands: set[str] = set()
        entrypoints: set[str] = set()
        ui_widgets: set[str] = set()
        tests: set[str] = set()
        strings: set[str] = set()
        licence: str | None = None
        asset_meta: dict[str, str] | None = None
        complexity_score = 0

        if path.suffix.lower() == ".py" and text is not None:
            try:
                module_ast = ast.parse(text)
                module_doc = _first_line(ast.get_docstring(module_ast))
                analyzer = PythonAnalyzer(info.path.replace(os.sep, "/"))
                analyzer.visit(module_ast)

                functions = analyzer.functions
                classes = analyzer.classes
                imports = analyzer.imports
                call_targets = analyzer.call_targets
                env_vars = analyzer.env_vars
                cli_commands = analyzer.cli_commands
                entrypoints = analyzer.entrypoints
                ui_widgets = analyzer.ui_widgets
                tests = analyzer.tests
                strings = _detect_strings(module_ast)

                if module_doc:
                    constructs["docstring"] = [module_doc]

                headings = [
                    line.strip("# ")
                    for line in text.splitlines()
                    if line.strip().startswith("#")
                ][:10]
                if headings:
                    constructs["sections"] = headings

                if options.include_api_index:
                    for summary in functions:
                        api_index.append(
                            APIItem(
                                module=info.path,
                                qualname=summary.name,
                                signature=summary.signature,
                                kind="function",
                                doc=summary.doc,
                            )
                        )

                    for summary in classes:
                        api_index.append(
                            APIItem(
                                module=info.path,
                                qualname=summary.name,
                                signature=summary.signature,
                                kind="class",
                                doc=summary.doc,
                            )
                        )

                complexity_score = _compute_complexity(module_ast)

                # TODO counts already captured; tests map
                if options.include_tests:
                    for test in tests:
                        test_map[info.path].append(test)

                if options.include_ui_catalogue:
                    for widget in ui_widgets:
                        ui_catalogue.append({"file": info.path, "widget": widget})

                if options.include_config_schema:
                    for ev in env_vars:
                        config_schema['environment'].append(ev)

                if options.include_cli_inventory:
                    for command in cli_commands:
                        cli_inventory.append({"file": info.path, "command": command})

                if options.include_string_catalogue:
                    strings = {s for s in strings if len(s) < 160}
                    for s in strings:
                        string_catalogue[s].append(info.path)

            except SyntaxError:
                responsibility = responsibility or "Unparseable Python file"

        elif text is not None:
            if options.include_string_catalogue:
                strings = {line.strip() for line in text.splitlines() if line.strip() and len(line.strip()) < 120}
                for s in strings:
                    string_catalogue[s].append(info.path)
            else:
                strings = set()

        if options.include_config_schema and text and path.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}:
            key_pattern = re.compile(r"[\"']([A-Za-z0-9_.-]+)[\"']\s*[:=]")
            keys = sorted(set(key_pattern.findall(text)))
            if keys:
                config_keys.update(keys)
                config_schema[path.suffix.lower()].extend(f"{info.path}:{key}" for key in keys)

        if imports:
            for item in imports:
                namespace = item.split(".")[0]
                if namespace in internal_modules:
                    internal_imports.add(namespace)
                else:
                    external_imports.add(namespace)
        if options.include_dependency_map:
            dependency_map[info.path] = sorted({imp.split(".")[0] for imp in imports})
        if options.include_call_graph:
            call_graph[info.path] = sorted(call_targets)

        if text:
            top_lines = "\n".join(text.splitlines()[:20]).lower()
            if "license" in top_lines or "copyright" in top_lines:
                licence = "Possible licence header"

        mimetype, _ = mimetypes.guess_type(path.name)
        if options.include_binary_manifest and mimetype and not mimetype.startswith("text"):
            asset_meta = {
                "path": info.path,
                "mime": mimetype,
                "size": f"{info.size_bytes} bytes",
            }
            binary_manifest.append(asset_meta)

        risk, risk_score = _risk_band(complexity_score, sloc, todo_count)

        file_card = DeepFileAnalysis(
            path=info.path,
            language=language,
            size_bytes=info.size_bytes,
            mtime_iso=info.mtime_iso,
            sloc=sloc,
            todo_count=todo_count,
            responsibility=responsibility,
            constructs={k: v for k, v in constructs.items() if v},
            functions=functions if options.include_functions else [],
            classes=classes if options.include_classes else [],
            imports=sorted(imports),
            internal_imports=sorted(internal_imports),
            external_imports=sorted(external_imports),
            call_targets=sorted(call_targets),
            env_vars=sorted(env_vars),
            config_keys=sorted(config_keys) if options.include_config_schema else [],
            cli_commands=sorted(cli_commands) if options.include_cli_inventory else [],
            entrypoints=sorted(entrypoints),
            ui_widgets=sorted(ui_widgets) if options.include_ui_catalogue else [],
            tests=sorted(tests) if options.include_tests else [],
            strings=sorted(strings) if options.include_string_catalogue else [],
            licence=licence,
            asset_meta=asset_meta,
            complexity=risk,
            risk_score=risk_score,
        )
        files.append(file_card)

        if options.include_llm_bundle:
            llm_bundle.append(
                {
                    "path": info.path,
                    "hash": hashlib.sha256(info.path.encode()).hexdigest()[:16],
                    "language": language,
                    "sloc": sloc,
                    "todo_count": todo_count,
                    "imports": sorted(imports),
                    "complexity_band": risk,
                    "functions": [summary.signature for summary in functions] if options.include_functions else [],
                    "classes": [summary.signature for summary in classes] if options.include_classes else [],
                    "doc": file_card.constructs.get("docstring", [None])[0],
                }
            )

        if licence:
            licence_findings.append({"file": info.path, "note": licence})

    normalized_config_schema = (
        {key: sorted(set(values)) for key, values in config_schema.items()} if options.include_config_schema else {}
    )
    normalized_test_map = {key: sorted(values) for key, values in test_map.items()} if options.include_tests else {}
    normalized_string_catalogue = (
        {key: sorted(set(values)) for key, values in string_catalogue.items()} if options.include_string_catalogue else {}
    )

    return DeepAnalysisReport(
        root=report.root,
        generated_at=report.generated_at,
        files=files,
        api_index=api_index,
        dependency_map=dependency_map if options.include_dependency_map else {},
        call_graph=call_graph if options.include_call_graph else {},
        cli_inventory=cli_inventory if options.include_cli_inventory else [],
        config_schema=normalized_config_schema,
        ui_catalogue=ui_catalogue if options.include_ui_catalogue else [],
        test_map=normalized_test_map,
        string_catalogue=normalized_string_catalogue,
        licence_findings=licence_findings,
        binary_manifest=binary_manifest if options.include_binary_manifest else [],
        llm_bundle=llm_bundle if options.include_llm_bundle else [],
    )


def _derive_internal_modules(files: list[FileInfo]) -> set[str]:
    modules = set()
    for fi in files:
        path = Path(fi.path)
        if path.suffix == ".py":
            parts = path.parts
            if len(parts) > 1:
                modules.add(parts[0])
            modules.add(path.stem)
    return modules
