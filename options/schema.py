"""Helpers for turning dataclass option bundles into UI-friendly schemas."""
from __future__ import annotations

from dataclasses import MISSING, fields, is_dataclass
from typing import Any, get_args, get_origin


def dataclass_to_schema(cls: type) -> dict[str, Any]:
    """Return a JSON-serialisable schema description for a dataclass."""

    if not is_dataclass(cls):  # pragma: no cover - defensive guardrail
        raise TypeError(f"{cls!r} is not a dataclass")

    schema: dict[str, Any] = {
        "name": cls.__name__,
        "module": cls.__module__,
        "fields": [],
    }

    for field in fields(cls):
        field_schema: dict[str, Any] = {
            "name": field.name,
            "type": _type_name(field.type),
            "python_type": field.type,
        }

        default = _resolve_default(field)
        if default is not MISSING:
            field_schema["default"] = default

        if field.metadata:
            ui_meta = field.metadata.get("ui")
            if ui_meta:
                field_schema["ui"] = dict(ui_meta)

        schema["fields"].append(field_schema)

    return schema


def _resolve_default(field) -> Any:
    if field.default is not MISSING:
        return field.default
    if field.default_factory is not MISSING:  # type: ignore[attr-defined]
        try:
            return field.default_factory()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - factory side effects
            return MISSING
    return MISSING


def _type_name(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return repr(annotation)

    args = get_args(annotation)
    arg_names = ", ".join(_type_name(arg) for arg in args)
    origin_name = getattr(origin, "__name__", repr(origin))
    return f"{origin_name}[{arg_names}]"
