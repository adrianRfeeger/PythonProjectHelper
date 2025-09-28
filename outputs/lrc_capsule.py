"""Build and write LLM-Ready Capsule (LRC) JSON exports."""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import platform
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from report import ProjectReport, FileInfo

_WORD_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")


@dataclass
class LRCCapsuleOptions:
    """Options controlling capsule construction."""

    include_patterns: tuple[str, ...] = ("**",)
    exclude_patterns: tuple[str, ...] = ("**/.venv/**", "**/__pycache__/**", "**/.git/**")
    pii_scrub: bool = True
    redact_ruleset: str = "default"
    normalise_eol: str = "LF"
    deterministic_seed: int = 0
    dictionary_size: int = 256  # Reduced from 512
    tool_codec: str = "zstd_b64"
    max_file_size: int = 1024 * 1024  # Skip files larger than 1MB
    include_binary_files: bool = False  # Skip binary files by default
    max_summary_lines: int = 3  # Reduced from 5
    max_outline_items: int = 10  # Limit outline complexity


def build_compact_lrc_capsule(project_scan: ProjectReport) -> dict:
    """Build a smaller, more efficient LRC capsule with reduced metadata."""
    compact_options = LRCCapsuleOptions(
        dictionary_size=128,  # Much smaller dictionary
        max_file_size=512 * 1024,  # 512KB limit
        include_binary_files=False,  # No binary files
        max_summary_lines=2,  # Minimal summary
        max_outline_items=5,  # Minimal outline
        tool_codec="zstd_b64"  # Keep compression
    )
    return build_lrc_capsule(project_scan, compact_options)

def build_lrc_capsule(project_scan: ProjectReport, options: LRCCapsuleOptions | None = None) -> dict:
    """Return a capsule dictionary ready to be serialised to JSON."""

    opts = options or LRCCapsuleOptions()
    root_path = Path(project_scan.root)
    now = datetime.now(timezone.utc)

    files_meta: list[tuple[FileInfo, Path, bytes, str | None]] = []
    total_bytes = 0
    language_counts: Counter[str] = Counter()
    text_samples: list[str] = []

    for file_info in sorted(project_scan.files, key=lambda f: f.path):
        rel_path = Path(file_info.path)
        if not _should_include(rel_path, opts.include_patterns, opts.exclude_patterns):
            continue

        abs_path = (root_path / rel_path).resolve()
        try:
            data = abs_path.read_bytes()
        except OSError:
            continue

        # Skip large files to keep capsule size manageable
        if len(data) > opts.max_file_size:
            continue

        # Skip binary files if not requested
        if not opts.include_binary_files and not _is_text_file(rel_path):
            continue

        total_bytes += len(data)
        language = _detect_language(rel_path)
        language_counts[language] += 1

        text_payload: str | None = None
        if _is_text_file(rel_path):
            text_payload = _normalise_text(data.decode("utf-8", errors="replace"), opts.normalise_eol)
            # Limit text sample size for dictionary building
            if len(text_payload) > 50000:  # Limit to ~50KB per file for dictionary
                text_samples.append(text_payload[:50000])
            else:
                text_samples.append(text_payload)

        files_meta.append((file_info, rel_path, data, text_payload))

    dictionary, dictionary_lookup = _build_token_dictionary(text_samples, opts.dictionary_size)

    sections: list[dict] = []
    file_hash_map: dict[str, str] = {}

    for index, (file_info, rel_path, data, text_payload) in enumerate(sorted(files_meta, key=lambda item: (_section_kind(item[1], item[3]), str(item[1]))), start=1):
        section_id = f"sec-{index:04d}"
        language = _detect_language(rel_path)
        kind = _section_kind(rel_path, text_payload)

        normalized_bytes = _normalise_bytes(data, text_payload, opts.normalise_eol)
        sha_hex = hashlib.sha256(normalized_bytes).hexdigest()
        file_hash_map[section_id] = sha_hex

        tool_payload = to_tool_codec(data, opts.tool_codec)

        llm_layers: dict[str, object] = {}
        if text_payload is not None:
            summary_lines = _summarise_text(rel_path, text_payload, opts.max_summary_lines)
            outline = _build_outline(rel_path, text_payload, opts.max_outline_items)
            tokenised, used_tokens = _apply_dictionary(text_payload, dictionary_lookup)
            llm_layers = {
                "summary": {"lines": summary_lines},
                "outline": {
                    "codec": outline.get("codec", "text_norm_v1"),
                    "payload": outline.get("payload", outline),
                },
                "content": {
                    "codec": "tds_v1",
                    "dict": {token: dictionary[token] for token in used_tokens},
                    "payload": tokenised,
                },
            }

        section = {
            "id": section_id,
            "kind": kind,
            "path": rel_path.as_posix(),
            "language": language,
            "size_bytes": len(data),
            "hash": f"sha256:{sha_hex}",
            "redactions": [],
            "codecs": {
                "tool": {
                    "codec": opts.tool_codec,
                    "payload": tool_payload,
                    "original_mimetype": _guess_mimetype(rel_path),
                },
                "llm": {
                    "layers": llm_layers,
                    "disclaimer": "LLM codec is lossy and not intended for project recovery.",
                } if llm_layers else {},
            },
        }
        sections.append(section)

    merkle_nodes, merkle_root = _build_merkle_tree(file_hash_map)

    capsule = {
        "lrc_version": "1.0",
        "generator": {
            "app": "PythonProjectHelper",
            "version": "1.0.0",
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": {
            "name": root_path.name,
            "root": str(root_path),
            "fingerprint": _project_fingerprint(files_meta),
        },
        "options": {
            "include_patterns": list(opts.include_patterns),
            "exclude_patterns": list(opts.exclude_patterns),
            "pii_scrub": opts.pii_scrub,
            "redact_ruleset": opts.redact_ruleset,
            "normalise_eol": opts.normalise_eol,
            "deterministic_seed": opts.deterministic_seed,
        },
        "integrity": {
            "algo": "sha256",
            "tree": {
                "type": "merkle_v1",
                "files": file_hash_map,
                "nodes": merkle_nodes,
                "root": merkle_root,
            },
        },
        "summary": {
            "stats": {
                "files": len(files_meta),
                "bytes": total_bytes,
                "languages": dict(sorted(language_counts.items())),
            },
            "highlights": _build_highlights(language_counts, len(files_meta)),
        },
        "dictionary": {
            "codec": "tds_v1",
            "entries": dictionary,
        },
        "sections": sections,
    }

    return capsule


def write_lrc_capsule(capsule: dict, path: Path) -> None:
    """Serialise the capsule dict to JSON on disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    json_data = json.dumps(capsule, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(json_data, encoding="utf-8")


# ----------------------------- helper utilities -----------------------------


def _should_include(path: Path, includes: Iterable[str], excludes: Iterable[str]) -> bool:
    posix = path.as_posix()
    if any(PathMatcher.match(posix, pattern) for pattern in excludes):
        return False
    if includes:
        return any(PathMatcher.match(posix, pattern) for pattern in includes)
    return True


class PathMatcher:
    """Lightweight fnmatch wrapper with caching."""

    _cache: dict[tuple[str, str], bool] = {}

    @classmethod
    def match(cls, value: str, pattern: str) -> bool:
        key = (value, pattern)
        if key not in cls._cache:
            cls._cache[key] = fnmatchcase(value, pattern)
        return cls._cache[key]


def fnmatchcase(value: str, pattern: str) -> bool:
    from fnmatch import fnmatchcase as _fn
    return _fn(value, pattern)


def _normalise_text(text: str, eol: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if eol.upper() == "LF":
        normalized = normalized.rstrip() + "\n" if normalized else normalized
    return normalized


def _normalise_bytes(data: bytes, text_payload: str | None, eol: str) -> bytes:
    if text_payload is None:
        return data
    return _normalise_text(text_payload, eol).encode("utf-8")


def _detect_language(path: Path) -> str:
    ext = path.suffix.lower()
    mapping = {
        ".py": "python",
        ".md": "markdown",
        ".json": "json",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".txt": "text",
        ".js": "javascript",
        ".ts": "typescript",
        ".css": "css",
        ".html": "html",
    }
    return mapping.get(ext, "binary" if not _is_text_extension(ext) else "text")


def _is_text_extension(ext: str) -> bool:
    return ext in {
        ".py", ".md", ".json", ".txt", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".css", ".html", ".js", ".ts",
    }


def _is_text_file(path: Path) -> bool:
    return _is_text_extension(path.suffix.lower())


def _section_kind(path: Path, text_payload: str | None) -> str:
    """Determine the section kind for sorting files in the capsule."""
    ext = path.suffix.lower()
    name = path.name.lower()
    
    # Configuration files
    if ext in {".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env"} or name in {"dockerfile", "makefile"}:
        return "config"
    
    # Documentation
    if ext in {".md", ".rst", ".txt"} or name.startswith("readme"):
        return "docs"
    
    # Code files
    if ext in {".py", ".js", ".ts", ".html", ".css", ".sql", ".sh", ".bat"}:
        return "code"
    
    # Data files
    if ext in {".csv", ".log"}:
        return "data"
    
    # Binary files (no text payload)
    if text_payload is None:
        return "binary"
    
    # Default to text
    return "text"


def _guess_mimetype(path: Path) -> str:
    import mimetypes

    mime, _ = mimetypes.guess_type(path.as_posix())
    return mime or "application/octet-stream"


def _build_token_dictionary(texts: Iterable[str], size: int) -> tuple[dict[str, str], dict[str, str]]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(match.group(0) for match in _WORD_PATTERN.finditer(text))

    most_common = counter.most_common(size)
    dictionary: dict[str, str] = {}
    lookup: dict[str, str] = {}
    for index, (word, _) in enumerate(most_common, start=1):
        token = f"§{index}"
        dictionary[token] = word
        lookup[word] = token
    return dictionary, lookup


def _apply_dictionary(text: str, lookup: dict[str, str]) -> tuple[str, set[str]]:
    if not lookup:
        return text, set()

    tokens_used: set[str] = set()
    if not lookup:
        return text, tokens_used

    # Sort words by length to avoid partial replacements
    words_sorted = sorted(lookup.keys(), key=len, reverse=True)
    pattern = re.compile(r"\b(" + "|".join(re.escape(word) for word in words_sorted) + r")\b")

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        token = lookup[word]
        tokens_used.add(token)
        return token

    return pattern.sub(replace, text), tokens_used


def _summarise_text(path: Path, text: str, max_lines: int = 3) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return [f"{path.name} (empty)"]
    return lines[:max_lines]


def _build_outline(path: Path, text: str, max_items: int = 10) -> dict:
    if path.suffix.lower() != ".py":
        headings = [line.strip("# ") for line in text.splitlines() if line.startswith("#")]
        return {
            "codec": "text_norm_v1",
            "payload": {"headings": headings[:max_items]},
        }

    try:
        module = ast.parse(text)
    except SyntaxError:
        return {
            "codec": "text_norm_v1",
            "payload": {"headings": []},
        }

    imports: list[str] = []
    symbols: list[dict[str, object]] = []
    calls: list[list[str]] = []

    class CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: D401
            target = _call_target(node.func)
            if target:
                calls.append([target])
            self.generic_visit(node)

    for node in module.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            for alias in node.names:
                full = f"{module_name}.{alias.name}" if module_name else alias.name
                imports.append(full)
        elif isinstance(node, ast.FunctionDef):
            sig = _format_signature(node)
            symbols.append({"kind": "func", "name": sig})
        elif isinstance(node, ast.AsyncFunctionDef):
            sig = _format_signature(node)
            symbols.append({"kind": "async", "name": sig})
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            symbols.append({"kind": "class", "name": node.name, "methods": methods})

    CallVisitor().visit(module)

    return {
        "codec": "ast_norm_v1",
        "payload": {
            "imports": sorted(set(imports))[:max_items],
            "symbols": symbols[:max_items],
            "calls": calls[:max_items],
        },
    }
def _call_target(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Attribute):
        value = _call_target(expr.value)
        return f"{value}.{expr.attr}" if value else expr.attr
    if isinstance(expr, ast.Name):
        return expr.id
    return None


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = []
    for arg in node.args.args:
        ann = ast.unparse(arg.annotation) if arg.annotation is not None else None
        args.append(f"{arg.arg}: {ann}" if ann else arg.arg)
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    for kwarg in node.args.kwonlyargs:
        ann = ast.unparse(kwarg.annotation) if kwarg.annotation is not None else None
        args.append(f"{kwarg.arg}: {ann}" if ann else kwarg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return f"{node.name}({', '.join(args)})"


def _project_fingerprint(files_meta: list[tuple[FileInfo, Path, bytes, str | None]]) -> str:
    hasher = hashlib.sha256()
    for _, rel_path, data, _ in sorted(files_meta, key=lambda item: item[1]):
        stat = f"{rel_path.as_posix()}::{len(data)}"
        hasher.update(stat.encode("utf-8"))
    return hasher.hexdigest()


def _build_highlights(language_counts: Counter[str], total_files: int) -> list[str]:
    if not total_files:
        return ["No files included in capsule"]
    top_lang = language_counts.most_common(1)[0][0] if language_counts else "unknown"
    return [
        f"Captured {total_files} files across {len(language_counts)} languages",
        f"Dominant language: {top_lang}",
    ]


def _build_merkle_tree(file_hash_map: dict[str, str]) -> tuple[dict[str, str], str]:
    if not file_hash_map:
        empty_hash = hashlib.sha256(b"").hexdigest()
        return {}, empty_hash

    level = list(file_hash_map.items())
    nodes: dict[str, str] = {}
    node_counter = 1

    while len(level) > 1:
        next_level: list[tuple[str, str]] = []
        for i in range(0, len(level), 2):
            chunk = level[i:i + 2]
            concat = "".join(hash_hex for _, hash_hex in chunk).encode("utf-8")
            combined = hashlib.sha256(concat).hexdigest()
            node_id = f"n-{node_counter:04d}"
            node_counter += 1
            nodes[node_id] = combined
            next_level.append((node_id, combined))
        level = next_level
    root = level[0][1]
    return nodes, root


def to_tool_codec(data: bytes, codec: str) -> str:
    """Encode raw bytes using the requested tool codec to base64."""

    if codec == "zstd_b64":
        try:
            import zstandard as zstd  # type: ignore

            compressor = zstd.ZstdCompressor(level=10)
            encoded = compressor.compress(data)
        except Exception:
            encoded = _zlib_compress(data)
    elif codec == "brotli_b64":
        try:
            import brotli  # type: ignore

            encoded = brotli.compress(data, quality=6)
        except Exception:
            encoded = _zlib_compress(data)
    else:
        encoded = data
    return base64.b64encode(encoded).decode("ascii")


def from_tool_codec(b64: str, codec: str) -> bytes:
    raw = base64.b64decode(b64)
    if codec == "zstd_b64":
        try:
            import zstandard as zstd  # type: ignore

            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(raw)
        except Exception:
            return _zlib_decompress(raw)
    if codec == "brotli_b64":
        try:
            import brotli  # type: ignore

            return brotli.decompress(raw)
        except Exception:
            return _zlib_decompress(raw)
    return raw


def _zlib_compress(data: bytes) -> bytes:
    import zlib

    return zlib.compress(data, level=9)


def _zlib_decompress(data: bytes) -> bytes:
    import zlib

    return zlib.decompress(data)
