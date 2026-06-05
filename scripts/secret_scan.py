#!/usr/bin/env python3
import os
import re
import json

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
exclude_dirs = {".git", "node_modules", "venv", "env", "__pycache__", "data", ".venv", "monitor"}

patterns = [
    ("aws_access_key_id", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("aws_secret_access_key", re.compile(r'(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])')),
    ("gcp_api_key", re.compile(r'AIza[0-9A-Za-z\-_]{35}')),
    ("google_oauth", re.compile(r'ya29\.[0-9A-Za-z\-_]+')),
    ("private_key_begin", re.compile(r'-----BEGIN (?:RSA |)PRIVATE KEY-----')),
    ("ssh_pubkey", re.compile(r'ssh-(?:rsa|ed25519|dss) [A-Za-z0-9+/=]{100,}')),
    ("hex_32_plus", re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])')),
    ("long_base64", re.compile(r'(?<![A-Za-z0-9+/=])[A-Za-z0-9+/=]{40,}')),
    ("generic_assignment", re.compile(r'(?i)(api[_-]?key|apikey|secret|client_secret|secret_key|access[_-]?token|auth[_-]?token|password|passwd|pwd)[\'\"\s:=]+([^\s\'\",;]+)')),
]

findings = []
for dirpath, dirnames, filenames in os.walk(root):
    # skip excluded dirs
    rel = os.path.relpath(dirpath, root)
    parts = set(rel.split(os.sep)) if rel != "." else set()
    if parts & exclude_dirs:
        continue

    for fname in filenames:
        path = os.path.join(dirpath, fname)

        # skip large files
        try:
            if os.path.getsize(path) > 1024 * 1024 * 5:
                continue
        except Exception:
            continue

        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception:
            continue

        for i, line in enumerate(lines, start=1):
            for name, pat in patterns:
                for m in pat.finditer(line):
                    matched = m.group(0)
                    if not matched or len(matched) < 8:
                        continue
                    findings.append({
                        "file": os.path.relpath(path, root).replace("\\", "/"),
                        "line": i,
                        "type": name,
                        "match": matched[:200],
                        "context": line.strip()[:300],
                    })

# Deduplicate
uniq = []
seen = set()
for f in findings:
    key = (f['file'], f['line'], f['type'], f['match'])
    if key in seen:
        continue
    seen.add(key)
    uniq.append(f)

output = {"root": root, "findings": uniq}
print(json.dumps(output, indent=2, ensure_ascii=False))
