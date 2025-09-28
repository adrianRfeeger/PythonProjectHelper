#!/usr/bin/env python3
"""Enhanced project recovery tool for the new full-content export formats."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def recover_from_full_content_json(json_path: Path, output_dir: Path) -> int:
    """Recover project from full-content-json format."""
    print(f"📄 Reading JSON file: {json_path}")
    
    try:
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)
        
        if data.get('format') != 'full-content-json':
            print(f"❌ Error: Not a full-content-json file (format: {data.get('format')})")
            return 1
        
        metadata = data.get('metadata', {})
        project_name = Path(metadata.get('root', 'recovered_project')).name
        recovery_dir = output_dir / project_name
        
        print(f"📁 Creating recovery directory: {recovery_dir}")
        recovery_dir.mkdir(parents=True, exist_ok=True)
        
        files = data.get('files', [])
        recovered_count = 0
        
        for file_info in files:
            if not file_info.get('has_content', False) or not file_info.get('content'):
                continue
            
            file_path = Path(file_info['path'])
            full_path = recovery_dir / file_path
            
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(file_info['content'])
            
            recovered_count += 1
            print(f"✅ Recovered: {file_path}")
        
        print(f"\n🎉 Successfully recovered {recovered_count} files!")
        print(f"📍 Location: {recovery_dir}")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def recover_from_full_content_markdown(md_path: Path, output_dir: Path) -> int:
    """Recover project from full-content-markdown format."""
    print(f"📄 Reading Markdown file: {md_path}")
    
    try:
        with open(md_path, encoding='utf-8') as f:
            content = f.read()
        
        # Extract project name from title
        title_match = re.search(r'^# Project Structure: (.+)$', content, re.MULTILINE)
        if not title_match:
            print("❌ Error: Not a full-content-markdown file (no project title found)")
            return 1
        
        project_name = title_match.group(1).strip()
        recovery_dir = output_dir / project_name
        
        print(f"📁 Creating recovery directory: {recovery_dir}")
        recovery_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all file content blocks
        file_pattern = re.compile(
            r'^### [^`]*`([^`]+)`.*?```(\w+)\n(.*?)^```',
            re.MULTILINE | re.DOTALL
        )
        
        recovered_count = 0
        for match in file_pattern.finditer(content):
            file_path_str = match.group(1)
            language = match.group(2)
            file_content = match.group(3)
            
            file_path = Path(file_path_str)
            full_path = recovery_dir / file_path
            
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(file_content.rstrip() + '\n')
            
            recovered_count += 1
            print(f"✅ Recovered: {file_path}")
        
        print(f"\n🎉 Successfully recovered {recovered_count} files!")
        print(f"📍 Location: {recovery_dir}")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def recover_from_legacy_html(html_path: Path, output_dir: Path) -> int:
    """Recover project from legacy-html format."""
    print(f"📄 Reading HTML file: {html_path}")
    
    try:
        with open(html_path, encoding='utf-8') as f:
            content = f.read()
        
        # Extract project name from title
        title_match = re.search(r'<title>Project Structure: ([^<]+)</title>', content)
        if not title_match:
            print("❌ Error: Not a legacy HTML file (no project title found)")
            return 1
        
        project_name = title_match.group(1).strip()
        recovery_dir = output_dir / project_name
        
        print(f"📁 Creating recovery directory: {recovery_dir}")
        recovery_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to parse HTML for file content
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            recovered_count = 0
            # Find all h3 elements with file paths, then look for following pre/code blocks
            for h3 in soup.find_all('h3'):
                code_tag = h3.find('code')
                if not code_tag:
                    continue
                
                file_path_str = code_tag.get_text().strip()
                
                # Find the next pre/code block
                next_elem = h3.find_next_sibling()
                while next_elem and next_elem.name != 'pre':
                    next_elem = next_elem.find_next_sibling()
                
                if next_elem and next_elem.code:
                    file_content = next_elem.code.get_text()
                    
                    file_path = Path(file_path_str)
                    full_path = recovery_dir / file_path
                    
                    # Create parent directories
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write file content
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(file_content.rstrip() + '\n')
                    
                    recovered_count += 1
                    print(f"✅ Recovered: {file_path}")
            
            print(f"\n🎉 Successfully recovered {recovered_count} files!")
            print(f"📍 Location: {recovery_dir}")
            return 0
            
        except ImportError:
            print("❌ Error: BeautifulSoup4 is required for HTML parsing")
            print("Install with: pip install beautifulsoup4")
            return 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


def detect_format(file_path: Path) -> str:
    """Detect the export format of a file."""
    if not file_path.exists():
        return "unknown"
    
    # Check by extension first
    ext = file_path.suffix.lower()
    if ext == '.json':
        try:
            with open(file_path, encoding='utf-8') as f:
                data = json.load(f)
            if data.get('format') == 'full-content-json':
                return 'full-content-json'
        except:
            pass
    elif ext == '.md':
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()
            if 'This report includes complete source code content' in content:
                return 'full-content-markdown'
        except:
            pass
    elif ext == '.html':
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()
            if 'Project Structure:' in content and '<pre><code>' in content:
                return 'legacy-html'
        except:
            pass
    
    return "unknown"


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("""
🔧 Enhanced Project Recovery Tool

Usage:
  python full_content_recover.py <export_file> [output_directory]

Supported formats:
  • full-content-json   - Complete JSON export with source code
  • full-content-markdown - Complete Markdown export with source code  
  • legacy-html         - HTML export with source code

Examples:
  python full_content_recover.py project_export.json
  python full_content_recover.py project_export.md ./recovered
  python full_content_recover.py project_export.html
        """)
        sys.exit(1)
    
    export_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "./recovered")
    
    if not export_file.exists():
        print(f"❌ Error: File not found: {export_file}")
        sys.exit(1)
    
    print(f"🔍 Detecting format of: {export_file}")
    format_type = detect_format(export_file)
    print(f"📋 Detected format: {format_type}")
    
    if format_type == "full-content-json":
        result = recover_from_full_content_json(export_file, output_dir)
    elif format_type == "full-content-markdown":
        result = recover_from_full_content_markdown(export_file, output_dir)
    elif format_type == "legacy-html":
        result = recover_from_legacy_html(export_file, output_dir)
    else:
        print(f"❌ Error: Unsupported or unrecognized format: {format_type}")
        print("This tool only supports full-content exports that include complete source code.")
        result = 1
    
    sys.exit(result)


if __name__ == "__main__":
    main()