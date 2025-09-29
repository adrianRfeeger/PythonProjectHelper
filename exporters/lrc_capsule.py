"""Exporter bridging the LRC capsule builder into the registry."""
from __future__ import annotations

import json
from dataclasses import fields
from typing import Any, Dict

from .base import Exporter, register_exporter
from outputs.lrc_capsule import LRCCapsuleOptions, build_lrc_capsule
from report import ProjectReport


@register_exporter
class LRCCapsuleExporter(Exporter):
    """Generate machine-readable LRC capsules."""

    @property
    def name(self) -> str:
        return "lrc-capsule"

    def render(self, analysis: Dict[str, Any], options: Dict[str, Any]) -> str:
        project_report = options.get("project_report")
        if not isinstance(project_report, ProjectReport):
            raise ValueError("project_report is required to build an LRC capsule")

        capsule_options = self._build_options(options)
        capsule = build_lrc_capsule(project_report, capsule_options)
        return json.dumps(capsule, indent=2, ensure_ascii=False)

    def mimetype(self) -> str:
        return "application/json"

    def is_lossless(self) -> bool:
        return False

    def is_llm_friendly(self) -> bool:
        return True

    def describe_options(self) -> dict[str, Any]:
        return LRCCapsuleOptions.schema()

    def _build_options(self, payload: Dict[str, Any]) -> LRCCapsuleOptions:
        field_names = {field.name for field in fields(LRCCapsuleOptions)}
        filtered = {key: payload[key] for key in field_names if key in payload}
        return LRCCapsuleOptions(**filtered)
