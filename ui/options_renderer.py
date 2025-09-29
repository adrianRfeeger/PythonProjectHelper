"""Tk widgets for rendering exporter option schemas."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict


class OptionsRenderer(ttk.Frame):
    """Render dataclass-derived option schemas into Tk controls."""

    def __init__(self, master: tk.Misc, schema: Dict[str, Any], initial: Dict[str, Any] | None = None) -> None:
        super().__init__(master)
        self.schema = schema
        self.initial = initial or {}
        self._controls: dict[str, dict[str, Any]] = {}
        self._build()

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def get_values(self) -> dict[str, Any]:
        """Return the current control values, converted to Python types."""

        values: dict[str, Any] = {}
        for name, control in self._controls.items():
            widget_type = control["widget_type"]
            field = control["field"]

            if widget_type == "pattern-list":
                widget: tk.Text = control["widget"]
                text = widget.get("1.0", tk.END).strip()
                patterns = [line.strip() for line in text.splitlines() if line.strip()]
                values[name] = tuple(patterns)
            elif widget_type in {"textarea", "multiline"}:
                widget = control["widget"]
                values[name] = widget.get("1.0", tk.END).rstrip("\n")
            else:
                variable = control.get("variable")
                raw_value = variable.get() if variable is not None else None
                values[name] = _convert_value(raw_value, field.get("type"))

        return values

    def set_values(self, values: Dict[str, Any]) -> None:
        """Programmatically update controls with new values."""

        for name, value in values.items():
            if name not in self._controls:
                continue

            control = self._controls[name]
            widget_type = control["widget_type"]
            if widget_type == "pattern-list":
                widget: tk.Text = control["widget"]
                widget.delete("1.0", tk.END)
                for pattern in value or []:
                    widget.insert(tk.END, f"{pattern}\n")
            elif widget_type in {"textarea", "multiline"}:
                widget: tk.Text = control["widget"]
                widget.delete("1.0", tk.END)
                widget.insert(tk.END, value or "")
            else:
                variable = control.get("variable")
                if isinstance(variable, tk.Variable):
                    variable.set(value)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build(self) -> None:
        groups: dict[str, list[dict[str, Any]]] = {}
        for field in self.schema.get("fields", []):
            ui = field.get("ui", {})
            group = ui.get("group", "General")
            groups.setdefault(group, []).append(field)

        for group_name, group_fields in sorted(groups.items(), key=lambda item: item[0]):
            container = ttk.LabelFrame(self, text=group_name)
            container.pack(fill="x", pady=6, padx=2)
            for field in group_fields:
                self._build_field(container, field)

    def _build_field(self, container: ttk.LabelFrame, field: dict[str, Any]) -> None:
        ui_meta = field.get("ui", {})
        widget_type = ui_meta.get("widget") or _infer_widget(field)
        label_text = ui_meta.get("label") or field["name"].replace("_", " ").title()

        row = ttk.Frame(container)
        row.pack(fill="x", padx=8, pady=4)

        label = ttk.Label(row, text=label_text)
        label.grid(row=0, column=0, sticky="w")

        default = self.initial.get(field["name"], field.get("default"))

        control_info: dict[str, Any]
        if widget_type == "pattern-list":
            frame = ttk.Frame(row)
            frame.grid(row=0, column=1, sticky="ew")
            frame.columnconfigure(0, weight=1)
            text = tk.Text(frame, height=4, width=40)
            text.grid(row=0, column=0, sticky="nsew")
            if default:
                for pattern in default:
                    text.insert(tk.END, f"{pattern}\n")
            control_info = {"widget": text, "widget_type": widget_type}
        elif widget_type == "select":
            variable = tk.StringVar(value=default)
            choices = ui_meta.get("choices", [])
            widget = ttk.Combobox(row, textvariable=variable, values=list(choices), state="readonly")
            widget.grid(row=0, column=1, sticky="ew", padx=(12, 0))
            control_info = {"variable": variable, "widget": widget, "widget_type": widget_type}
        elif widget_type in {"number", "spinbox"}:
            variable = tk.IntVar(value=default)
            widget = ttk.Spinbox(
                row,
                from_=ui_meta.get("min", -10**9),
                to=ui_meta.get("max", 10**9),
                increment=ui_meta.get("step", 1),
                textvariable=variable,
                width=10,
            )
            widget.grid(row=0, column=1, sticky="w", padx=(12, 0))
            control_info = {"variable": variable, "widget": widget, "widget_type": widget_type}
        elif widget_type == "checkbox":
            variable = tk.BooleanVar(value=bool(default))
            widget = ttk.Checkbutton(row, variable=variable)
            widget.grid(row=0, column=1, sticky="w", padx=(12, 0))
            control_info = {"variable": variable, "widget": widget, "widget_type": widget_type}
        elif widget_type == "multiline":
            text = tk.Text(row, height=4, width=40)
            text.grid(row=0, column=1, sticky="ew", padx=(12, 0))
            if default:
                text.insert(tk.END, default)
            control_info = {"widget": text, "widget_type": widget_type}
        else:  # Fallback to a simple entry
            variable = tk.StringVar()
            variable.set("" if default is None else str(default))
            widget = ttk.Entry(row, textvariable=variable)
            widget.grid(row=0, column=1, sticky="ew", padx=(12, 0))
            control_info = {"variable": variable, "widget": widget, "widget_type": widget_type}

        row.columnconfigure(1, weight=1)

        help_text = ui_meta.get("help")
        if help_text:
            help_label = ttk.Label(row, text=help_text, style="Body.TLabel", wraplength=360)
            help_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        control_info["field"] = field
        self._controls[field["name"]] = control_info


def _infer_widget(field: dict[str, Any]) -> str:
    py_type = field.get("type", "str")
    if "bool" in py_type:
        return "checkbox"
    if any(token in py_type for token in ("int", "float")):
        return "number"
    return "text"


def _convert_value(value: Any, type_name: str | None) -> Any:
    if type_name is None:
        return value
    lower_type = type_name.lower()
    if "int" in lower_type:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if "float" in lower_type:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if "bool" in lower_type:
        return bool(value)
    return value
