# file: recover.py
"""Recover files and directories from project report outputs (txt, md, html, json)."""
import re
import os
from pathlib import Path
from typing import Optional

def recover_from_report(report_path: str, output_dir: Path = Path("recovered_project")) -> None:
    print("[DEBUG] Starting recovery...")
    print(f"[DEBUG] report_path: {report_path}")
    print(f"[DEBUG] output_dir: {output_dir}")
    try:
        if not isinstance(output_dir, Path):
            output_dir = Path(output_dir)

        with open(report_path, encoding="utf-8") as f:
            text = f.read()

        # Try to extract the project root name from the report (HTML, Markdown, or JSON)
        project_root = None
        # Markdown: # Project Structure: NAME
        m = re.search(r"^# Project Structure: (.+)$", text, re.MULTILINE)
        if m:
            project_root = m.group(1).strip()
        # HTML: <title>Project Structure: NAME</title>
        if not project_root:
            m = re.search(r"<title>Project Structure: (.+?)</title>", text)
            if m:
                project_root = m.group(1).strip()
        # JSON: 'root' property
        if not project_root and '"root":' in text:
            m = re.search(r'"root"\s*:\s*"([^"]+)"', text)
            if m:
                # Use only the last part of the path
                project_root = Path(m.group(1)).name
        if not project_root:
            project_root = "project_root"

        print(f"[DEBUG] project_root: {project_root}")
        # Create the root folder inside the output directory
        root_dir = output_dir / project_root
        root_dir.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG] root_dir: {root_dir}")

        # Detect if this is an HTML report (look for <!DOCTYPE html> or <html)
        is_html = text.lstrip().lower().startswith("<!doctype html") or "<html" in text[:500].lower()
        html_file_blocks = []
        if is_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(text, "html.parser")
                file_blocks = []
                # Find all <h3> with <code> (file path), then next <pre><code> (file content)
                for h3 in soup.find_all("h3"):
                    code = h3.find("code")
                    if not code:
                        continue
                    rel_path = code.get_text(strip=True)
                    # Find the next <pre><code> sibling (may be separated by <div> etc)
                    pre = h3.find_next_sibling()
                    while pre and (pre.name != "pre" or not pre.code):
                        pre = pre.find_next_sibling()
                    if pre and pre.code:
                        content = pre.code.get_text()
                        file_blocks.append((rel_path, content))
                if file_blocks:
                    print(f"[DEBUG] Found {len(file_blocks)} HTML file blocks (via BeautifulSoup).")
                    recovered_files = []
                    for rel_path, content in file_blocks:
                        print(f"[DEBUG] Recovering HTML file: {rel_path}")
                        write_recovered_file(root_dir, rel_path, content)
                        recovered_files.append(rel_path)
                    print(f"Recovered {len(file_blocks)} files from HTML report.")
                    suspicious = [f for f in recovered_files if f == '{report.root}']
                    subfolder_files = [f for f in recovered_files if '/' in f or '\\' in f]
                    if suspicious:
                        print("[WARNING] File named '{report.root}' was created. This indicates a likely extraction failure.")
                    if not subfolder_files:
                        print("[WARNING] No subfolder files were extracted. This may indicate a parsing issue.")
                    if suspicious or not subfolder_files:
                        print("[INFO] Retrying extraction using Markdown/plaintext parser as fallback...")
                        # Fallback to Markdown logic below
                    else:
                        return
                else:
                    print("[WARNING] No file blocks found in HTML report using BeautifulSoup.")
            except Exception as e:
                print(f"[ERROR] BeautifulSoup HTML parsing failed: {e}")
        # Otherwise, try Markdown/Plaintext
        md_file_blocks = list(re.finditer(r"^### [^`]*`([^`]+)`.*?^\*\*Size:.*?^```([\w]*)\n(.*?)^```", text, re.MULTILINE | re.DOTALL))
        if not md_file_blocks:
            md_file_blocks = list(re.finditer(r"^### [^`]*`(.+?)`.*?^\*\*Size:.*?^```([\w]*)\n(.*?)^```", text, re.MULTILINE | re.DOTALL))
        if md_file_blocks:
            print(f"[DEBUG] Found {len(md_file_blocks)} Markdown/plaintext file blocks.")
            recovered_files = []
            for m in md_file_blocks:
                rel_path = m.group(1).strip()
                content = m.group(3)
                print(f"[DEBUG] Recovering Markdown file: {rel_path}")
                write_recovered_file(root_dir, rel_path, content)
                recovered_files.append(rel_path)
            print(f"Recovered {len(md_file_blocks)} files from Markdown/plaintext report.")
            suspicious = [f for f in recovered_files if f == '{report.root}']
            subfolder_files = [f for f in recovered_files if '/' in f or '\\' in f]
            if suspicious:
                print("[WARNING] File named '{report.root}' was created. This indicates a likely extraction failure.")
            if not subfolder_files:
                print("[WARNING] No subfolder files were extracted. This may indicate a parsing issue.")
            return

        # JSON: look for a 'files' array with 'path' and 'content'
        if '"files":' in text:
            import json
            data = json.loads(text)
            count = 0
            for f in data.get("files", []):
                if f.get("content") is not None:
                    print(f"[DEBUG] Recovering JSON file: {f['path']}")
                    write_recovered_file(root_dir, f["path"], f["content"])
                    count += 1
            print(f"Recovered {count} files from JSON report.")
            return

        print("Could not detect a supported report format or no file contents found.")
    except Exception as e:
        import traceback
        print("[ERROR] Exception during recovery:")
        traceback.print_exc()

def write_recovered_file(base_dir: Path, rel_path: str, content: str) -> None:
    """Write a recovered file to disk, creating directories as needed."""
    out_path = base_dir / rel_path
    print(f"[DEBUG] rel_path: {rel_path}")
    print(f"[DEBUG] out_path: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content.strip("\n") + "\n")
    print(f"Recovered: {out_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python recover.py <report_file> [output_dir]")
    elif len(sys.argv) == 2:
        recover_from_report(sys.argv[1])
    else:
        recover_from_report(sys.argv[1], Path(sys.argv[2]))
