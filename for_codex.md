Extending PythonProjectHelper: Options, Report Types & Improvements
Introduction
The PythonProjectHelper tool generates a variety of reports summarising the structure and health of a Python project. The existing design includes a deep analysis report with several optional sections (functions, API index, dependency map, call graph, CLI inventory, config schema, UI catalogue, tests, strings, binary manifest and an LLM bundle) and an LRC capsule for machine‑readable bundles. These features are controlled by a DeepAnalysisOptions dataclass with boolean flags. The graphical user interface (GUI) presents checkboxes for each option and allows the user to choose output formats. There is also a command‑line interface (CLI) to drive the exporter.
To support new features or research modes, developers may need to add new options, introduce additional report types or improve the architecture. This document outlines how to extend the existing design and proposes improvements. It references authoritative sources for dataclasses and plugin discovery so that changes remain idiomatic and maintainable.
Extending Analysis Options
1. Add a new option to the DeepAnalysisOptions dataclass
The current options are defined in the DeepAnalysisOptions dataclass. Python’s dataclasses automatically generate the __init__ and __repr__ methods for classes with annotated fields[1], so adding a new boolean flag is as simple as adding a new field with a default value. For example:
@dataclass
class DeepAnalysisOptions:
    include_functions: bool = True
    include_classes: bool = True
    include_api_index: bool = True
    # … existing fields …

    # New option to include complexity & risk metrics
    include_complexity_panel: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, bool] | None) -> "DeepAnalysisOptions":
        # existing implementation uses dataclasses.fields() to merge defaults
        …
When adding fields, remember that dataclasses use the order in which fields are defined[2] for the generated __init__ signature. If you need keyword‑only parameters, you can set kw_only=True in the @dataclass decorator.
2. Update the GUI to expose the new option
The exporter’s Tkinter GUI defines a list named deep_option_specs that pairs option names with human‑readable labels. To surface a new option you must:
1.	Add the option to the dictionary of BooleanVar instances (often stored in self.deep_option_vars).
2.	Append a (name, label) tuple to the deep_option_specs list. The existing code iterates over this list to create checkboxes.
deep_option_specs = [
    ("include_functions", "Include function signatures"),
    …
    ("include_llm_bundle", "Include LLM bundle JSON"),
    # Add your new option here
    ("include_complexity_panel", "Include complexity & risk panel"),
]
1.	Handle option‑specific behaviour in callbacks. If the option triggers additional UI elements or warnings, update the _on_deep_option_changed method accordingly.
3. Update the CLI to accept the new flag
If your tool exposes command‑line flags, extend the CLI parser to include a --include-complexity-panel/--no-include-complexity-panel flag. The value should default to the dataclass’s default. Rather than hand‑coding each flag, consider generating CLI options dynamically from the dataclass fields. The Maskset article on improving Python CLIs with dataclasses demonstrates how to loop over dataclasses.fields() and create click options automatically[3]. This pattern keeps the CLI in sync with the dataclass so that adding a new field automatically introduces a corresponding flag.
For example, using click:
import click
from dataclasses import fields

class DynamicExporterCommand(click.Command):
    def __init__(self, *args, **kwargs):
        for field in fields(DeepAnalysisOptions):
            option_name = f"--{field.name.replace('_', '-')}"
            default_value = getattr(DeepAnalysisOptions, field.name)
            if field.type is bool:
                option = click.Option([option_name], is_flag=True, default=default_value)
            else:
                option = click.Option([option_name], default=default_value, type=field.type)
            kwargs.setdefault('params', []).append(option)
        super().__init__(*args, **kwargs)

@click.command(cls=DynamicExporterCommand)
def export(**options):
    opts = DeepAnalysisOptions(**options)
    …
4. Respect the option in report generation
The analysis or export functions should check the new flag before performing expensive work. For the complexity panel example, add logic after function signature parsing to compute metrics only when options.include_complexity_panel is true. This approach avoids performance overhead when the user has not requested the extra section.
Adding New Report Types
1. Decide on the report’s scope and structure
Before coding, define what information the new report will contain (e.g., code quality metrics, security audit results, documentation coverage). For inspiration, the existing deep analysis report specification lists various modes such as API index, dependency map and call graph【12090†L290-L303】. Each mode includes a clear description of the data collected and the safety measures (e.g., no code bodies).
2. Create a report model
Define a new dataclass or Pydantic model representing the report. For example:
@dataclass
class ComplexityReport:
    root: str
    generated_at: str
    complexity_by_file: dict[str, int]
    todo_counts: dict[str, int]
    risk_hotspots: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
Using dataclasses gives you auto‑generated methods[4]. If validation is important or you need nested models, Pydantic can provide type enforcement and a .model_dump() method.
3. Implement a generator function
Add a function (e.g., generate_complexity_report) that accepts a ProjectScan or existing analysis and returns an instance of your new report. Reuse the existing AST parsing and metrics calculation where possible. Ensure that the function can accept option flags to toggle parts of the report.
4. Wire the report into the export flow
To make the new report available:
1.	Register the report in the CLI. Add a new --mode=complexity flag or extend the dynamic generator described earlier to recognise the report name.
2.	Add the report to the GUI. Extend the list of available formats in the exporter (e.g., add “Complexity Report (JSON)” to the combobox) and handle it in the on_format_changed callback.
3.	Implement exporters for each desired format. For Markdown and HTML you may need Jinja2 templates; for JSON the dataclass .to_json() suffices.
5. Consider a plugin architecture for report types
If many new report types are anticipated, adopt a plugin system so they can be added without modifying the core code. The Python Packaging User Guide outlines several ways to discover plugins: naming conventions, namespace packages and entry points[5]. Using entry points allows external packages to register a report generator under a defined group. During startup, your exporter can iterate over importlib.metadata.entry_points(group='python_project_helper.reports') to dynamically load all available report types. This decouples the core from optional reports and encourages community contributions.
CLI & Configuration Improvements
1.	Generate CLI options from dataclasses: as noted above, you can reduce duplication and mistakes by dynamically creating click options from dataclass fields[3]. Libraries such as Typer or pydanclick offer direct support for dataclasses and Pydantic models.
2.	Support configuration files: allow users to provide a toml or yaml file with defaults, then override values via CLI. The Maskset article demonstrates loading a TOML config and merging it with dataclass defaults[6].
3.	Provide sensible defaults and safety flags: maintain options like --limit-body=0 to guarantee that code bodies are not included; consider adding a --strict-redaction flag to remove API keys or personal data. Exposing these controls in the CLI and GUI gives users confidence when sharing reports.
User Interface Enhancements
1.	Responsive disclosure: the current UI lists all deep analysis options by default. To avoid overwhelming users, group related options under collapsible panels (already done) and add context tooltips explaining what each option does.
2.	Real‑time size estimation: continue to update the “estimated report size” label as users toggle options and select files. Estimate the number of files multiplied by typical metadata sizes; update when options like include_llm_bundle are toggled.
3.	Theme support: ensure the UI respects the user’s OS dark/light mode settings. Provide custom themes for high contrast accessibility.
4.	Validation and warnings: if a user selects a binary format that is incompatible with a chosen report type, display a warning. For instance, if they choose Markdown but request the binary manifest, note that binary file names will be listed but not embedded.
Additional Improvements and Ideas
Complexity & Risk Panel
Include a new section that computes per‑file cyclomatic complexity, count of TODO/FIXME markers and a simple “hotspot” score (size × modification frequency). This idea is inspired by the proposed “Complexity & Risk Panel” in the deep analysis report specification【12130†L0-L13】. Metrics can be estimated using radon or similar libraries. The panel helps developers focus on the most complex parts of their project.
Licensing & Compliance Checks
Extend licence detection beyond SPDX identifiers. Use regular expressions to find common licences (MIT, GPL, Apache) and cross‑check with a list of approved licences. Report files without licence headers or with conflicting licences.
Improved LRC Capsule
The LRC capsule currently supports zstd_b64 and brotli_b64 codecs and includes LLM layers. Consider adding:
•	Support for additional codecs such as plain JSON (none) for debugging and gzip_b64 for compatibility.
•	Selective AST outlines: allow users to toggle AST outlines for specific languages (e.g., only include Python outlines).
•	Integrity metadata: record both the pre‑ and post‑redaction hashes as discussed in the specification. Ensure the Merkle tree builder uses sorted section identifiers to guarantee deterministic outputs.
Plugin‑friendly architecture
Implement a base Report interface or abstract base class with methods like generate(project_scan, options) and export(format). Each report type can subclass this base. Use entry points for discovery[5] so third‑party packages can register new report types without modifying the core code. Document the expected output schema so plugin authors can ensure compatibility.
Test automation
Unit tests should accompany every new option or report. Verify that:
•	Default options produce the same output as before.
•	Disabling an option removes the corresponding section.
•	Enabling new reports results in deterministic content (ideally by hashing the JSON output).
•	The CLI’s dynamic option generation correctly maps dataclass fields to click options.
Continuous integration should run on multiple OSes (Linux, macOS, Windows) to catch UI or path‑handling issues.
Conclusion
By structuring options into dataclasses and dynamically generating CLI flags and GUI elements, PythonProjectHelper becomes easier to extend and less error‑prone. Introducing a plugin architecture will allow new report types to be added modularly, fostering a community ecosystem. Implementing additional panels like complexity & risk metrics, improved licence checks and richer LRC capsules will make the tool more valuable to developers and researchers while preserving the safety guarantees that no code bodies or secrets are exposed.
 
[1] [2] [4] dataclasses — Data Classes — Python 3.13.7 documentation
https://docs.python.org/3/library/dataclasses.html
[3] [6] Improving Python CLIs with Pydantic and Dataclasses | Maskset
https://www.maskset.net/blog/2025/07/01/improving-python-clis-with-pydantic-and-dataclasses/
[5] Creating and discovering plugins - Python Packaging User Guide
https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
