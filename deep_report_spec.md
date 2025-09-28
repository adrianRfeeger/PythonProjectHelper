# Deep Analysis Report Specification for Copilot

## Overview
This document describes how to implement an enhanced **Deep Analysis Report** mode for the project. The goal is to provide detailed structural and functional context of each file **without exposing raw source code**, so that the output can be safely used for documentation, AI model ingestion, or code reviews.

---

## Objectives

- Generate detailed, non-recoverable reports that explain the program's **structure**, **intent**, and **relationships** between files.
- Ensure reports remain safe for public sharing: **no code bodies or sensitive content should be included**.
- Allow developers to toggle depth and focus of reports.
- Support both human-readable (Markdown, HTML) and machine-readable (JSON) formats.
- Include a clear safety disclaimer to warn users these reports are **not suitable for project recovery**.

---

## Proposed Report Modes

### 1. Deep Outline (Per File)
- **Details Included:**
  - File path, size, timestamps.
  - Programming language.
  - Top-level constructs (modules, classes, functions).
  - Function/class **signatures only** (no bodies).
  - First line of docstrings.
  - TODO/FIXME counts.
  - Brief inferred responsibility description (via heuristics).

### 2. API Signature Index
- Global index of public classes/functions.
- Parameter lists, return type hints.
- One-line docstring summaries (if available).
- Grouped by module.

### 3. Import & Dependency Map
- Per-file imports (internal vs external).
- Condensed dependency graph.
- Highlight circular dependencies or "hub" files.
- Output in JSON and optionally DOT/Mermaid for visualisation.

### 4. Call Graph Sketch (Shallow)
- Lists call targets per file (qualnames only).
- No function bodies.
- Useful to show orchestration points.

### 5. CLI & Entrypoint Inventory
- Detect `if __name__ == "__main__"` blocks.
- Capture argparse/click/typer command definitions.
- Include CLI options and descriptions.

### 6. Config & Environment Schema
- Extract environment variable reads.
- Detect `.env`, YAML, JSON, or TOML keys.
- Infer data types and defaults.

### 7. UI Widget Catalogue
- For GUI-related files (Tkinter, CTk, Pygubu):
  - Windows, frames, and major widgets.
  - Command/callback bindings.

### 8. Test Surface Map
- List discovered tests and their target modules.
- Include fixtures and parameterisation hints.

### 9. Complexity & Risk Panel
- Per file:
  - SLOC (non-blank lines).
  - Cyclomatic complexity estimate.
  - Number of TODO/FIXME/XXX markers.
  - Heuristic "hotspot" score (size × churn if Git is available).

### 10. Strings & i18n Catalogue
- Collect all user-visible strings.
- Extract translation keys and placeholders.

### 11. Licence/Headers & Compliance
- Detect licences, copyright notices, and licence mismatches.

### 12. Binary/Asset Manifest (Expanded)
- MIME type, dimensions (for images), duration (for media).
- No actual file content.

### 13. LLM Bundle (Machine-Readable JSON)
- Compact file "cards" for ingestion into AI models.
- Each card contains:
  - Path, hash, language, signatures, imports, complexity band.
  - Docstring summaries, inferred file role.
  - Truncated metadata safe for tokenised input.

---

## Command-Line Flags & Options

| Flag / Option               | Description |
|----------------------------|-------------|
| `--mode=deep-outline`      | Generate full per-file deep outline. |
| `--mode=api-index`         | Generate API-only signature report. |
| `--mode=deps`              | Generate dependency map. |
| `--mode=llm-bundle`        | Generate machine-readable JSON bundle. |
| `--redact=secrets,emails` | Redact sensitive content. |
| `--limit-body=0`          | Ensures no code body text is included. |
| `--sig-doclines=1`        | Number of docstring lines to include. |
| `--graph=imports|calls`   | Select graph type to generate. |
| `--formats=md,html,json`  | Output in multiple formats. |
| `--llm-bundle-chunk=4000` | Max characters per JSON record. |

---

## Safety Disclaimer
> **Important:** This is a **non-recoverable report**. It intentionally omits code bodies and raw file content. It is suitable for providing context to developers or AI systems but must **not** be used as a substitute for project backups.

---

## Implementation Notes

- Use AST parsing (Python) and lightweight static analysis to extract structure.
- Heuristically label file roles: e.g., UI, Core, Config, Test.
- Automatically redact or omit minified files where reconstruction risk is high.
- Generate human-readable and machine-readable outputs in a single pass.
- Ensure all outputs are consistent across formats.

---

## Example File Card (Deep Outline)

```yaml
path: app/gui.py
meta:
  language: Python
  size: 42 KB
  sloc: 1079
  modified: 2025-09-28
imports:
  - tkinter
  - customtkinter
  - app.config
classes:
  - name: MainWindow
    base: ctk.CTk
    methods:
      - __init__(...)
      - build_menu(...)
      - open_profile_studio(...)
functions:
  - name: launch_app
    signature: (argv: list[str]) -> int
    doc: "Initialises theme, creates MainWindow, enters mainloop"
responsibility: "Defines the root CTk window and manages main navigation."
tests:
  - tests/test_gui_smoke.py::test_mainwindow_starts
risk:
  complexity: medium-high
  todo_count: 3
```

