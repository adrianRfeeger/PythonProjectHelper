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

        # Try to detect the format and parse file content blocks
        # Markdown/Plaintext: look for headings like '### 📄 `path`' and code blocks
        md_file_blocks = list(re.finditer(r"^### [^`]*`([^`]+)`.*?^\*\*Size:.*?^```([\w]*)\n(.*?)^```", text, re.MULTILINE | re.DOTALL))
        # Try again with a more permissive regex for file paths (including spaces and special chars)
        if not md_file_blocks:
            md_file_blocks = list(re.finditer(r"^### [^`]*`(.+?)`.*?^\*\*Size:.*?^```([\w]*)\n(.*?)^```", text, re.MULTILINE | re.DOTALL))
        if md_file_blocks:
            print(f"[DEBUG] Found {len(md_file_blocks)} Markdown/plaintext file blocks.")
            for m in md_file_blocks:
                rel_path = m.group(1).strip()
                content = m.group(3)
                print(f"[DEBUG] Recovering Markdown file: {rel_path}")
                write_recovered_file(root_dir, rel_path, content)
            print(f"Recovered {len(md_file_blocks)} files from Markdown/plaintext report.")
            return

        # HTML: look for <h3> with file path and <pre><code> blocks after
        # Improved regex: non-greedy match between </h3> and <pre><code>, allows for newlines and extra HTML
        html_file_blocks = list(re.finditer(r'<h3>.*?`([^`]+)`.*?</h3>.*?<pre><code>(.*?)</code></pre>', text, re.DOTALL))
        # If not found, try a more robust version that allows for any content between </h3> and <pre><code>
        if not html_file_blocks:
            html_file_blocks = list(re.finditer(r'<h3>.*?`([^`]+)`.*?</h3>[\s\S]*?<pre><code>([\s\S]*?)</code></pre>', text))
        if html_file_blocks:
            print(f"[DEBUG] Found {len(html_file_blocks)} HTML file blocks.")
            for m in html_file_blocks:
                rel_path = m.group(1).strip()
                content = m.group(2)
                print(f"[DEBUG] Recovering HTML file: {rel_path}")
                write_recovered_file(root_dir, rel_path, content)
            print(f"Recovered {len(html_file_blocks)} files from HTML report.")
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
