new plan:
LRC: LLM-Ready Capsule (JSON spec) — Implementation Instructions
Goal

Add a new export format to the app: LRC (LLM-Ready Capsule) — a single JSON that is:

Self-describing (header tells agents/LLMs what’s inside and how to read it),

Dual-codec per section (lossless Tool codec and text-only LLM codec),

Layered (summary → outline → compressed content),

Safe & scoped (optional PII scrubbing + redaction notes),

Deterministic (content hashes, stable IDs, Merkle-like integrity tree),

Non-restorative disclaimer for the LLM codec.

1) Project Integration

Implement as a new export target:

Module: outputs/lrc_capsule.py

Public API:

build_lrc_capsule(project_scan: ProjectScan, options: LRCCapsuleOptions) -> dict

write_lrc_capsule(capsule: dict, path: Path) -> None

CLI flag:

--export lrc (writes LRC_<project_name>_<ts>.json)

App settings (optional UI): Exports ▸ LLM-Ready Capsule (LRC) with toggles below.

2) JSON Top-Level Structure (stable order)

All maps must be serialised with sorted keys, UTF-8, and \n newlines. Use stable sorting for arrays where applicable.

{
  "lrc_version": "1.0",
  "generator": {
    "app": "PythonProjectHelper",
    "version": "<app_semver>",
    "python": "<py_ver>",
    "platform": "<os/arch>"
  },
  "created_at": "2025-09-28T09:41:00Z",
  "project": {
    "name": "<project_name>",
    "root": "<abs_or_rel_root>",
    "fingerprint": "<sha256(root_listing + sizes + mtimes)>"
  },
  "options": {
    "include_patterns": ["**/*.py", ...],
    "exclude_patterns": ["**/.venv/**", ...],
    "pii_scrub": true,
    "redact_ruleset": "default|custom",
    "normalise_eol": "LF",
    "deterministic_seed": 0
  },
  "integrity": {
    "algo": "sha256",
    "tree": {
      "type": "merkle_v1",
      "files": { "<file_id>": "<sha256(raw_bytes)>" },
      "nodes": { "<node_id>": "<sha256(child_hashes_concat)>" },
      "root": "<sha256(top_level_concat)>"
    }
  },
  "summary": {
    "stats": { "files": 123, "bytes": 456789, "languages": {"python": 98, "text": 25} },
    "highlights": ["Found 4 entrypoints", "3 config files", "..."]
  },
  "sections": [
    {
      "id": "sec-0001",
      "kind": "code|text|data|binary",
      "path": "src/pkg/module.py",
      "language": "python",
      "size_bytes": 1234,
      "hash": "sha256:...",
      "redactions": [
        {"rule": "email", "range": [123, 137], "note": "redacted email"}
      ],
      "codecs": {
        "tool": {
          "codec": "zstd_b64|brotli_b64",
          "payload": "<base64>",
          "original_mimetype": "text/x-python"
        },
        "llm": {
          "layers": {
            "summary": { "lines": ["Module X provides ...", "Key classes: A, B"] },
            "outline": {
              "codec": "ast_norm_v1|text_norm_v1",
              "payload": { /* structure, see below */ }
            },
            "content": {
              "codec": "tds_v1",
              "dict": { "§1": "import ", "§2": "def ", ... },
              "payload": "§1os\n§1sys\n... (normalised text with tokens)"
            }
          },
          "disclaimer": "LLM codec is not guaranteed to reconstruct original content."
        }
      }
    }
  ]
}

JSON Schema (concise)

Create schemas/lrc_v1.schema.json and validate before writing:

lrc_version: enum ["1.0"]

generator.*: strings

integrity.algo: "sha256"

integrity.tree.{files,nodes}: object<string,string>, hex SHA-256

sections[*].id: ^sec-\d{4,}$

sections[*].codecs.tool.codec: enum ["zstd_b64","brotli_b64"]

sections[*].codecs.llm.layers.outline.codec: enum ["ast_norm_v1","text_norm_v1"]

sections[*].codecs.llm.layers.content.codec: "tds_v1"

3) Determinism Rules

Ordering: Sort files by (kind, path). Sort dict keys lexicographically.

Timestamps: Use ISO-8601 Z (UTC). For fingerprinting, exclude volatile metadata.

Hashing: Always SHA-256 of pre-normalised bytes:

For text: normalise line endings to \n, strip trailing spaces if options.normalise_eol=="LF".

For binaries: hash raw bytes.

IDs:

section.id: sec- + zero-padded index (start at 0001).

node_id: n- + stable counter during tree build.

Randomness: Where a tie-break is needed (e.g., token assignment), use deterministic_seed.

4) Codecs
4.1 Tool codecs (lossless)

zstd_b64: compress with zstd level 10 (tunable), then base64 encode (URL-safe false, standard alphabet).

brotli_b64: Brotli quality 6 (tunable), then base64.

Implement:

def to_tool_codec(data: bytes, codec: Literal["zstd_b64","brotli_b64"]) -> str: ...
def from_tool_codec(b64: str, codec: Literal["zstd_b64","brotli_b64"]) -> bytes: ...

4.2 LLM codecs (text-only)
a) tds_v1 — Token Dictionary Substitution

Purpose: shrink textual payload while keeping structure readable.

Algorithm:

Pre-normalise text (EOL \n, optional whitespace compaction preserving indentation).

Candidate extraction:

Collect frequent substrings: identifiers, imports, keywords, common punctuation clusters, file-local boilerplate.

Use a deterministic greedy BPE-like approach:

Start from frequent bigrams/trigrams.

Limit dictionary size: default 512 entries.

Minimum tokenised gain threshold: ≥ 2 bytes saved per entry.

Token assignment: map in order of frequency to §1, §2, … §512. (§ is U+00A7; ensure it does not exist in source; otherwise choose fallback token prefix ⟦n⟧.)

Substitution: longest-match replace (left-to-right), preserving line breaks and block boundaries.

Output: dict (token→string) and payload (tokenised text).

Determinism:

Sort candidates by (gain desc, lex asc), seeded tie-breaks.

Don’t cross line breaks in tokens.

b) ast_norm_v1 — AST-normalised code outline

Python initial target; provide language hooks.

Output structure:

{
  "module": "pkg.module",
  "imports": ["os", "sys", "from pathlib import Path as Path"],
  "symbols": {
    "classes": [
      {"name": "Foo", "bases": ["Bar"], "doc": "doc...", "methods": ["__init__", "run"]}
    ],
    "functions": [
      {"name": "do_thing", "params": ["x:int","y:str='a'"], "doc": "doc..."}
    ],
    "constants": ["VERSION", "DEFAULTS"]
  },
  "calls": [
    {"caller": "Foo.run", "callee": "helper.process"},
    {"caller": "do_thing", "callee": "json.loads"}
  ],
  "top_order": ["imports", "constants", "classes", "functions"]
}


Implementation (Python):

Use ast to parse; walk nodes to collect:

Imports (incl. aliases),

Class defs (names, bases, method names, docstrings),

Function defs (name, signature, docstring),

Simple module-level assignments as constants (heuristic: ALL_CAPS or literal values).

Optional call graph:

Within module, collect ast.Call targets; derive qualname if resolvable locally.

Preserve declaration order in top_order.

Language extension points:

ast_norm_v1_python.py

Future: ast_norm_v1_js.ts, ast_norm_v1_go.go (leave stubs; emit "language":"python").

c) text_norm_v1 — documents

For Markdown/Plaintext:

Extract heading hierarchy, bullet lists, numbered steps.

Emit:

{
  "headings":[{"level":1,"text":"Title"},...],
  "bullets":[["point A","subpoint"],...],
  "entities":{"urls":["..."],"emails":["..."]}
}

d) diff_v1 — versioned runs (optional for now)

If previous LRC is provided, add per-file semantic diff:

Code: AST-aware (added/removed/changed symbols),

Text: heading and paragraph diffs,

Fallback: unified diff.

5) PII Scrubbing & Redaction

Pipeline (per section before hashing/encoding):

Detect: email, phone, API keys, secrets, IPs, local paths (heuristics + regex set).

Redact: replace with «REDACTED:<type>» preserving length if preserve_len=True.

Annotate: append entry to section.redactions.

Hashing:

hash field is of pre-redaction or post-redaction?

Design choice: set hash to post-redaction bytes (what the capsule actually contains). Add original_hash if options.pii_scrub==true.

Integrity tree must use the stored content (post-redaction).

Expose options:

@dataclass(frozen=True)
class LRCCapsuleOptions:
    patterns_include: list[str]
    patterns_exclude: list[str]
    tool_codec: Literal["zstd_b64","brotli_b64"] = "zstd_b64"
    enable_llm_layers: bool = True
    enable_ast_outline: bool = True
    enable_tds: bool = True
    pii_scrub: bool = True
    redact_ruleset: Literal["default","strict","off"] = "default"
    deterministic_seed: int = 0
    normalise_eol: Literal["LF","KEEP"] = "LF"

6) Integrity: Merkle-like Tree

Leaf: each section’s tool codec payload decoded bytes (i.e., the exact stored content) → sha256.

Intermediate nodes: concatenate child hashes in sorted order, sha256.

Root: concat of top node hashes (sorted by section.id).

Store per-file hashes in integrity.tree.files, node hashes in integrity.tree.nodes, and the final "root".

Helper:

class MerkleBuilder:
    def add_leaf(section_id: str, leaf_hash: bytes) -> None: ...
    def build() -> tuple[root_hex: str, nodes: dict[str,str]]

7) Layering

For each section (sections[*].codecs.llm.layers):

summary: 1–5 lines. Keep ≤ 400 chars.

outline: ast_norm_v1 (code) or text_norm_v1 (docs).

content: tds_v1 tokenised text (skip for binaries).

Stop-early behaviour: consumers can read only summary, or summary+outline, etc., to fit token budgets.

8) Non-Restorative Disclaimer

Add verbatim in each LLM codec:

LLM codec is not guaranteed to reconstruct original content and may be lossy by design.

9) API & CLI
Library
def build_lrc_capsule(scan: ProjectScan, options: LRCCapsuleOptions) -> dict:
    # 1) gather files from scan according to patterns
    # 2) for each file: load bytes, normalise, optional redact
    # 3) compute hashes, build tool codec payload
    # 4) build LLM layers as applicable
    # 5) accumulate sections and build integrity tree
    # 6) return dict ready for JSON dump (ensure sorted keys)

def write_lrc_capsule(capsule: dict, path: Path) -> None:
    json.dump(capsule, fp, ensure_ascii=False, sort_keys=True, indent=2)

CLI

python -m project_helper --export lrc --include "**/*.py" --exclude "**/.venv/**" --pii-scrub on --tool-codec zstd_b64

10) Testing & Acceptance Criteria
Unit Tests

Determinism: two runs on same tree produce identical JSON bytes.

Hashing: known file → expected SHA-256 (post-redaction).

TDS: dictionary ≤ limit; token payload round-trips when dictionary is reapplied.

AST: for sample module, parsed outline matches expected fixtures.

Integrity Tree: leaf and root hashes match recomputation.

Integration Tests

Generate LRC for a small mixed project (py, md, json). Verify:

Sorted keys, LF endings,

summary.stats counts correct,

redactions populated if secrets present,

disclaimer present.

Fuzz/Edge

Empty files, huge single-line files, binary blobs.

Source containing § — ensure prefix fallback triggers.

11) Example (truncated)
{
  "lrc_version": "1.0",
  "generator": {"app":"PythonProjectHelper","version":"0.9.0","python":"3.11.9","platform":"macOS-arm64"},
  "created_at": "2025-09-28T09:41:00Z",
  "project": {"name":"AudioTyper_tk","root":"./","fingerprint":"c7e1..."},
  "options": {"pii_scrub": true, "redact_ruleset": "default", "deterministic_seed": 0, "normalise_eol": "LF"},
  "integrity": {
    "algo":"sha256",
    "tree":{
      "type":"merkle_v1",
      "files": {"sec-0001":"b5d4...", "sec-0002":"9af3..."},
      "nodes": {"n-0001":"1ab2...", "n-0002":"77cc..."},
      "root":"f0f0..."
    }
  },
  "summary":{"stats":{"files":42,"bytes":123456,"languages":{"python":39,"text":3}},"highlights":["Entrypoint: main.py"]},
  "sections":[
    {
      "id":"sec-0001",
      "kind":"code",
      "path":"src/app/main.py",
      "language":"python",
      "size_bytes":2843,
      "hash":"sha256:3b1a...",
      "redactions":[{"rule":"email","range":[211,232],"note":"redacted email"}],
      "codecs":{
        "tool":{"codec":"zstd_b64","payload":"KLUv/QC...","original_mimetype":"text/x-python"},
        "llm":{
          "layers":{
            "summary":{"lines":["Entrypoint CLI; config load; GUI bootstrap"]},
            "outline":{
              "codec":"ast_norm_v1",
              "payload":{
                "module":"app.main",
                "imports":["sys","os","from gui import App"],
                "symbols":{"classes":[],"functions":[{"name":"main","params":[],"doc":"Start app"}],"constants":["VERSION"]},
                "calls":[{"caller":"main","callee":"App.run"}],
                "top_order":["imports","constants","functions"]
              }
            },
            "content":{
              "codec":"tds_v1",
              "dict":{"§1":"import ","§2":"def ","§3":"from ","§4":" as "},
              "payload":"§1sys\n§1os\n§3gui §4 App\n§2main():\n    App.run()\n"
            }
          },
          "disclaimer":"LLM codec is not guaranteed to reconstruct original content."
        }
      }
    }
  ]
}

12) Performance Notes

Stream processing for large files; avoid loading entire tree into RAM.

Cap tds_v1 dictionary to 512 entries and payload size to 2 MB per section (configurable).

Provide --no-llm-content to emit only summaries+outlines for huge repos.

13) Security Notes

Never store raw secrets. Default rules: emails, phone numbers, JWTs, AWS keys, generic key=..., .pem blocks.

Redaction replaces value, keeps structure.

Include redactions with byte ranges (post-normalisation offsets).

14) Backwards Compatibility & Versioning

lrc_version governs schema evolution.

For breaking changes, bump to 2.0 and include "compat":{"reads":["1.x"]} if possible.

Keep codec names stable; add new codecs with new identifiers (tds_v2, ast_norm_v2).

15) Tasks for Copilot

Create module outputs/lrc_capsule.py with APIs above.

Implement tool codecs using zstandard and brotli libs; add fallback if unavailable.

Implement PII scrubbing (redact.py) with composable regex rules; unit tests.

Implement tds_v1 (deterministic greedy BPE-like), respecting dictionary cap & ties.

Implement ast_norm_v1 (Python) using ast and inspect.signature rendering.

Implement text_norm_v1 for Markdown/plain text.

Build Merkle tree helper and integrate into integrity.

Add JSON schema + validation step.

Wire up CLI flag and settings panel toggle.

Write unit/integration tests and golden fixtures.

Update docs: docs/exports_lrc.md with consumer examples.

16) Acceptance Criteria

Export produces a single JSON file that validates against schemas/lrc_v1.schema.json.

Re-export with same inputs yields byte-identical output.

Tool codec round-trips losslessly (decode(encode(data)) == data).

LLM codec layers present, summaries concise, outlines accurate, TDS dictionary ≤ 512.

Integrity root hash recomputes successfully from stored payloads.

When pii_scrub=true, secrets are redacted and recorded in redactions.