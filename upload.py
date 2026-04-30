#!/usr/bin/env python3
"""Upload files to GitHub repo via REST API."""
import base64
import json
import os
import subprocess
import sys

REPO = "seastarbot/agentflow"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_files():
    """Get all files to upload (excluding .git, __pycache__, .egg-info, .pytest_cache)."""
    skip = {".git", "__pycache__", "*.egg-info", ".pytest_cache", ".eggs"}
    files = []
    for root, dirs, filenames in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if not any(s in d for s in skip)]
        for f in filenames:
            if f.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, BASE_DIR)
            files.append(rel)
    return sorted(files)

def upload_file(path, content_b64, message="Add files"):
    """Upload a single file via GitHub API."""
    cmd = [
        "gh", "api", "-X", "PUT",
        f"repos/{REPO}/contents/{path}",
        "-f", f"message={message}",
        "-f", f"content={content_b64}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAIL {path}: {result.stderr.strip()[:100]}")
        return False
    print(f"  OK   {path}")
    return True

def main():
    files = get_files()
    print(f"Uploading {len(files)} files to {REPO}...")

    success = 0
    fail = 0
    for f in files:
        full = os.path.join(BASE_DIR, f)
        try:
            with open(full, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
        except Exception as e:
            print(f"  SKIP {f}: {e}")
            fail += 1
            continue

        if upload_file(f, b64, f"Add {f}"):
            success += 1
        else:
            fail += 1

    print(f"\nDone: {success} uploaded, {fail} failed")

if __name__ == "__main__":
    main()
