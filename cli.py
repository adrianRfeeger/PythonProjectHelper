#!/usr/bin/env python3
"""Command-line interface for PythonProjectHelper with modular exporters."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from analysis import AnalysisEngine
from exporters import ExporterRegistry
from report import ProjectReport
from scan import scan_project


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Python Project Helper - Analyze and export Python projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --gui                           # Launch GUI interface
  %(prog)s /path/to/project               # Analyze project using GUI
  %(prog)s /path/to/project --format llm-tds --output report.json
  %(prog)s /path/to/project --format basic-markdown --output docs.md
  %(prog)s /path/to/project --list-formats # Show available formats
  %(prog)s /path/to/project --bundle --output bundle.json
        """
    )
    
    # Positional arguments
    parser.add_argument(
        'path',
        nargs='?',
        help='Path to project directory to analyze'
    )
    
    # GUI mode
    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch GUI interface'
    )
    
    # Export options
    parser.add_argument(
        '--format', '-f',
        help='Export format (use --list-formats to see available)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file path'
    )
    
    parser.add_argument(
        '--bundle',
        action='store_true',
        help='Bundle multiple formats into one file'
    )
    
    parser.add_argument(
        '--formats',
        nargs='*',
        help='Formats to include in bundle (default: all)'
    )
    
    # Information
    parser.add_argument(
        '--list-formats',
        action='store_true',
        help='List available export formats'
    )
    
    parser.add_argument(
        '--format-info',
        help='Show detailed information about a specific format'
    )
    
    # Analysis options
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to include'
    )
    
    parser.add_argument(
        '--max-size',
        type=int,
        help='Maximum file size in bytes'
    )
    
    parser.add_argument(
        '--include-tests',
        action='store_true',
        help='Include test files in analysis'
    )
    
    parser.add_argument(
        '--compact',
        action='store_true',
        help='Use compact output format where supported'
    )
    
    # Verbosity
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Handle GUI mode
    if args.gui or (not args.path and not args.list_formats and not args.format_info):
        launch_gui()
        return
    
    # Handle format listing
    if args.list_formats:
        list_formats()
        return
    
    if args.format_info:
        show_format_info(args.format_info)
        return
    
    # Validate required arguments
    if not args.path:
        parser.error("Project path is required for CLI analysis")
    
    project_path = Path(args.path).resolve()
    if not project_path.exists():
        print(f"Error: Project path '{project_path}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not project_path.is_dir():
        print(f"Error: Project path '{project_path}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    # Analyze project
    try:
        if args.verbose:
            print(f"Analyzing project: {project_path}")
        
        # Build analysis options
        analysis_options = {}
        if args.max_files:
            analysis_options['max_files'] = args.max_files
        if args.max_size:
            analysis_options['max_size'] = args.max_size
        if args.include_tests:
            analysis_options['include_tests'] = args.include_tests
        if args.compact:
            analysis_options['compact'] = args.compact
        
        # Scan and analyze
        project_report = scan_project(project_path)
        engine = AnalysisEngine()
        analysis = engine.analyze_project(project_report, analysis_options)
        
        if args.verbose:
            print(f"Found {len(analysis.files)} files, {analysis.project.totals.sloc} SLOC")
        
        # Handle bundle mode
        if args.bundle:
            handle_bundle(analysis, args, args.verbose)
        else:
            handle_single_export(analysis, args, args.verbose)
            
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def launch_gui() -> None:
    """Launch the GUI interface."""
    try:
        from gui import run_gui
        run_gui()
    except ImportError as e:
        print(f"Error: GUI dependencies not available: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error launching GUI: {e}", file=sys.stderr)
        sys.exit(1)


def list_formats() -> None:
    """List all available export formats."""
    from exporters import list_available_formats, get_exporter
    
    formats = list_available_formats()
    
    if not formats:
        print("No export formats available")
        return
    
    print("Available export formats:")
    print()
    
    for format_id in formats:
        exporter = get_exporter(format_id)
        if exporter:
            print(f"  {format_id}")
            print(f"    Name: {exporter.name}")
            print(f"    MIME Type: {exporter.mimetype()}")
            print(f"    LLM Friendly: {exporter.is_llm_friendly()}")
            print(f"    Lossless: {exporter.is_lossless()}")
            print()


def show_format_info(format_id: str) -> None:
    """Show detailed information about a specific format."""
    from exporters import get_exporter
    
    exporter = get_exporter(format_id)
    if not exporter:
        print(f"Error: Unknown format '{format_id}'", file=sys.stderr)
        print("\nUse --list-formats to see available formats", file=sys.stderr)
        sys.exit(1)
        
    print(f"Format: {format_id}")
    print(f"Name: {exporter.name}")
    print(f"MIME Type: {exporter.mimetype()}")
    print(f"LLM Friendly: {exporter.is_llm_friendly()}")
    print(f"Lossless: {exporter.is_lossless()}")
    
    print()
    print("Example usage:")
    print(f"  python cli.py /path/to/project --format {format_id} --output report.out")


def handle_single_export(analysis, args, verbose: bool) -> None:
    """Handle single format export."""
    if not args.format:
        print("Error: --format is required for single export", file=sys.stderr)
        sys.exit(1)
    
    from exporters import get_exporter
    
    exporter = get_exporter(args.format)
    if not exporter:
        print(f"Error: Unknown format '{args.format}'", file=sys.stderr)
        print("\nUse --list-formats to see available formats", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Convert analysis to dict for compatibility
        analysis_dict = analysis.model_dump() if hasattr(analysis, 'model_dump') else analysis.__dict__
        
        # Generate export
        export_data = exporter.render(analysis_dict, args.__dict__)
        
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Auto-generate filename
            output_path = Path(f"{analysis.project.name}_{args.format}.out")
        
        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(export_data, str):
            output_path.write_text(export_data, encoding='utf-8')
        else:
            output_path.write_bytes(export_data)
        
        if verbose:
            print(f"Exported to: {output_path}")
            print(f"Size: {output_path.stat().st_size:,} bytes")
        else:
            print(str(output_path))
            
    except Exception as e:
        print(f"Error during export: {e}", file=sys.stderr)
        sys.exit(1)


def handle_bundle(analysis, args, verbose: bool) -> None:
    """Handle bundle export with multiple formats."""
    from exporters import list_available_formats, get_exporter
    
    # Determine which formats to include
    if args.formats:
        format_ids = args.formats
    else:
        # Use all available formats
        format_ids = list_available_formats()
    
    if verbose:
        print(f"Bundling formats: {', '.join(format_ids)}")
    
    bundle = {
        'project': analysis.project.model_dump() if hasattr(analysis.project, 'model_dump') else analysis.project.__dict__,
        'exports': {},
        'metadata': {
            'bundle_version': '1.0',
            'generated_by': 'PythonProjectHelper CLI',
            'formats': format_ids
        }
    }
    
    # Convert analysis to dict for compatibility
    analysis_dict = analysis.model_dump() if hasattr(analysis, 'model_dump') else analysis.__dict__
    
    # Generate exports for each format
    for format_id in format_ids:
        try:
            exporter = get_exporter(format_id)
            if not exporter:
                print(f"  ✗ {format_id}: Unknown format", file=sys.stderr)
                continue
            
            export_data = exporter.render(analysis_dict, args.__dict__)
            bundle['exports'][format_id] = {
                'name': exporter.name,
                'data': export_data.decode('utf-8') if isinstance(export_data, bytes) else export_data,
                'metadata': {
                    'mime_type': exporter.mimetype(),
                    'llm_friendly': exporter.is_llm_friendly(),
                    'lossless': exporter.is_lossless()
                }
            }
            
            if verbose:
                print(f"  ✓ {format_id}")
                
        except Exception as e:
            print(f"  ✗ {format_id}: {e}", file=sys.stderr)
            continue
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(f"{analysis.project.name}_bundle.json")
    
    # Write bundle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2), encoding='utf-8')
    
    if verbose:
        print(f"Bundle exported to: {output_path}")
        print(f"Size: {output_path.stat().st_size:,} bytes")
        print(f"Formats included: {len(bundle['exports'])}")
    else:
        print(str(output_path))


if __name__ == "__main__":
    main()