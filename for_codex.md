PythonProjectHelper — Exporter/Report Formats Implementation Guide (for Codex)
0) Locate the codebase & current report logic

The report already references a Deep Analysis / modulegraph output and shows a file called deep_report.py in the project (size ~24 KB). Start there; this is likely where the current report logic or scaffolding lives.
(See entry with "path": "deep_report.py" and the associated LLM “Deep Analysis Report Specification” content embedded inside the .lrc.json.)

The existing export uses an LLM codec layer with a lossy disclaimer (not for recovery) and a tool codec using zstd→base64. We’ll generalise these into pluggable “export formats” shortly.
(You can see the LLM disclaimer text in the sections[].codecs.llm.disclaimer, and codecs.tool.codec: "zstd_b64".)

1) Goal

Create a modular Exporter subsystem that can emit multiple report formats:

A. LLM-oriented (lossy, compression-friendly)

LLM-TDS (text-dictionary substitution): token dictionary + structure normalisation (expand on current tds_v1 idea) — compact and easy for models to ingest. Non-restorative by design.

LLM-Outline / API-Index / Import-Map: the “Deep Analysis” modes already specced in the report payload (per-file outline, API signature index, import & dependency map, UI widget catalogue, complexity panel, etc.). Implement them as first-class formats that can be selected individually or bundled. No code bodies.

B. Basic human/machine formats

Markdown (MD): Readable summaries (per-file cards), with tables for imports/classes/functions.

HTML: Same as MD but styled, optionally with collapsible sections.

JSON: Machine-readable version of the outline/API/graph (good for automation pipelines).

C. Compressed variants

Tool-codec (lossless blobs):

zstd_b64 (already present) and brotli_b64 as alternatives.

LLM-codec (lossy text):

Always textual; optional secondary compression via run-length or token coalescing (but keep it ASCII/UTF-8). No Merkle tree required for the LLM variant (lighter, “less secure”).

2) Architecture
app/
  exporters/
    __init__.py
    base.py              # Exporter interface
    llm_tds.py           # LLM-TDS text codec (token dict + structure)
    llm_outline.py       # Deep Outline (per-file)
    llm_api_index.py     # API signature index
    llm_import_map.py    # Imports & dep graph
    basic_markdown.py    # Human-readable
    basic_html.py
    basic_json.py        # Machine-readable (schema below)
    tool_zstd_b64.py     # Lossless compressed payload
    tool_brotli_b64.py
  analysis/
    scan_tree.py         # walks files, collects meta
    py_ast_extract.py    # extracts signatures, docstrings 1st line
    import_graph.py      # builds import map (internal/external)
    ui_catalogue.py      # Tk/CTk/Pygubu widget scan
    complexity.py        # SLOC, cyclomatic estimate, TODO counts
    tests_map.py         # pytest surface mapping
  config/
    schema.py            # pydantic models for JSON schema
    options.py           # CLI & config defaults
cli.py                   # adds --format / --codec flags

Exporter interface (base)
# app/exporters/base.py
from typing import Protocol, Any, Dict

class Exporter(Protocol):
    name: str
    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> bytes | str: ...
    def mimetype(self) -> str: ...
    def is_lossless(self) -> bool: ...
    def is_llm_friendly(self) -> bool: ...


A central registry maps --format to concrete exporters.

3) Data pipeline (single pass)

Scan & analyse (no source bodies in memory dump):

File meta (path, size, timestamps), language, SLOC

AST pass: collect signatures only; first line of docstrings; public API (classes, functions)

Imports: internal vs. third-party; circulars/hubs

Complexity/risk heuristics: TODO/FIXME counts, cyclomatic estimate

UI catalogue (Tk/CTk/Pygubu): windows/frames/major widgets, callbacks

Tests surface map (pytest modules, test names)
(These items are explicitly part of your Deep Analysis spec.)

Normalise into an analysis model (pydantic) to feed exporters.

Exporters serialise that model per target format.

Optional tool-codec compression (zstd/brotli) after serialisation for “tool” formats.

4) Formats to implement (MVP list)
4.1 LLM formats (lossy, compact)

llm-tds

Uses a token dictionary + text payload (current tds_v1 concept) to minimise tokens.

Must include the lossy disclaimer (not for recovery).

llm-outline (per-file deep outline)

Fields (no bodies): path, size, sloc, language, imports, classes & functions signatures, first-line docstrings, inferred responsibility, TODO counts, risk.

Mirrors the spec inside your report.

llm-api-index

Global index of public classes/functions with parameter lists and return hints; one-line docstrings.

llm-import-map

Internal/external imports and condensed graph; optionally emit Mermaid diagram text in MD/HTML flavours.

Optional: llm-ui-catalogue, llm-tests-map, llm-complexity as separate skimmable chunks (toggle via flags).

4.2 Basic formats

basic-markdown — Overview + per-file cards.

basic-html — As above with minimal styling and collapsible sections.

basic-json — Canonical machine schema (see §6).

4.3 Compressed / tool formats

tool-zstd_b64 — Serialise a chosen format (e.g., basic-json) then zstd+base64 it. Already referenced in the report.

tool-brotli_b64 — Same, with brotli+base64.

Note: These are lossless for the selected serialised representation, but “less secure” than a per-section Merkle tree because it’s a single blob. (We’ll make integrity pluggable.)

5) CLI / config

Add flags to cli.py:

--format           one of: llm-tds, llm-outline, llm-api-index, llm-import-map,
                           basic-markdown, basic-html, basic-json
--bundle           comma-separated list to emit multiple in one run
--tool-codec       none | zstd_b64 | brotli_b64
--integrity        none | per-section-sha256 | merkle_v1
--pii-scrub        true|false
--depth            shallow|default|deep
--out              path to file or directory


Defaults mirror the behaviour shown in the existing .lrc.json: PII scrubbing on, and LLM outputs carry the “lossy” disclaimer.

6) JSON schema (for basic-json and as backing for MD/HTML)

Top-level:

{
  "version": "1.0",
  "generated_at": "ISO-8601",
  "project": {
    "name": "str",
    "fingerprint": "sha256-hex",
    "root_rel": ".",
    "totals": { "files": 0, "sloc": 0 }
  },
  "options": { "...": "as run" },
  "files": [
    {
      "path": "str",
      "language": "python",
      "size_bytes": 0,
      "sloc": 0,
      "imports": { "internal": ["..."], "external": ["..."] },
      "classes": [
        { "name": "str", "bases": ["..."], "methods": ["sig", "..."], "doc1": "first line" }
      ],
      "functions": [
        { "name": "str", "signature": "str", "returns": "hint?", "doc1": "first line" }
      ],
      "ui": { "windows": [], "widgets": [], "callbacks": [] },
      "tests": ["module::test_name", "..."],
      "complexity": { "cyclomatic": 0, "todo_count": 0, "hotspot": 0.0 },
      "responsibility": "short inferred role"
    }
  ],
  "graphs": {
    "imports": { "nodes": [], "edges": [] }
  }
}

7) Security, integrity & compression matrix
Mode / Format	Recoverable	Integrity option	Typical size	Use case
llm-tds	No	None (by default)	Very small	Model ingestion/context
llm-outline	No	None	Small	Reviews, shareable docs
llm-api-index	No	None	Small	API surface mapping
basic-json	N/A (no bodies)	Optional per-section SHA256	Medium	Automation
basic-markdown	N/A	N/A	Medium	Human review
basic-html	N/A	N/A	Medium	Human review (UI)
tool-zstd_b64	Yes (of the serialised JSON/HTML/MD)	Whole-blob hash only	Small	Archival/agent workflows
tool-brotli_b64	Yes	Whole-blob hash only	Small	As above
.lrc.json (current)	Mixed (LLM lossy + tool blob)	Merkle tree per section	Larger	Tamper evidence / determinism

Note: The report you uploaded demonstrates LLM lossy (tds) + tool zstd_b64 and Merkle per-section integrity in the same capsule. We’re making each part independently selectable.

8) Implementation steps (ordered)

Create analysis/ modules to produce the unified analysis model (no code bodies).
Use the items listed in the Deep Analysis spec found in your report payload (imports map, API signatures, UI catalogue, test surface, complexity/risk).

Define pydantic models in config/schema.py matching §6 above.

Exporter base + registry (exporters/base.py + exporters/__init__.py). Register concrete exporters.

Implement LLM exporters:

llm_tds.py — emit dictionary + compacted text (follow existing tds_v1 pattern seen in the report). Include lossy disclaimer.

llm_outline.py, llm_api_index.py, llm_import_map.py — mirror fields described in the embedded spec (per-file details, API signatures, import graph).

Implement basic exporters: basic_markdown.py, basic_html.py, basic_json.py.

Implement tool codecs: tool_zstd_b64.py, tool_brotli_b64.py. The report shows zstd_b64 already; replicate pattern and abstract behind --tool-codec.

Integrate CLI flags and config defaults (cli.py, config/options.py).

Integrity options:

none (fast),

per-section-sha256 (hash each file’s JSON chunk),

merkle_v1 (replicate current behaviour in .lrc.json). The report demonstrates a Merkle tree with sec-000x leaves; keep compatibility.

Tests:

Golden-file tests for each exporter.

Round-trip tests for tool-codecs (decompress → compare JSON).

Security tests: verify no bodies or sensitive payloads leak into LLM/basic outputs.

Docs: One README page with format matrix, examples, and CLI recipes.

9) CLI recipes (examples)

LLM-only outline (shareable):

python -m app.cli export --format llm-outline --out report_outline.md


Machine JSON + brotli tool-codec:

python -m app.cli export --format basic-json --tool-codec brotli_b64 --out report.json.br.b64


Bundle: outline + API index + import map as HTML (no tool codec):

python -m app.cli export --bundle llm-outline,llm-api-index,llm-import-map \
    --format basic-html --out report.html


Deterministic capsule (Merkle + LLM + tool zstd):

python -m app.cli export --bundle llm-tds,basic-json \
    --tool-codec zstd_b64 --integrity merkle_v1 --out project.lrc.json

10) Backwards compatibility

Keep reading the existing .lrc.json (current structure shows sections[].codecs.llm + sections[].codecs.tool and a Merkle tree over sec-000x items). Emit the same when --integrity merkle_v1 is selected.

11) Notes for Codex (where to look)

deep_report.py — contains or references the spec for “Deep Analysis Report”; use it as the seed for llm-outline and friends.

LLM disclaimer & TDS dictionary/payload — replicate semantics from the example in the uploaded capsule.

zstd_b64 tool codec — already evidenced in the file; abstract behind a ToolCodec interface and add brotli_b64.