#!/usr/bin/env python3
import os
import re
import json
import subprocess

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
patterns = [
    ("aws_access_key_id", re.compile(r'AKIA[0-9A-Z]{16}')),
    ("aws_secret_access_key", re.compile(r'(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])')),
    ("gcp_api_key", re.compile(r'AIza[0-9A-Za-z\-_]{35}')),
    ("google_oauth", re.compile(r'ya29\.[0-9A-Za-z\-_]+')),
    ("private_key_begin", re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----')),
    ("ssh_pubkey", re.compile(r'ssh-(?:rsa|ed25519|dss) [A-Za-z0-9+/=]{100,}')),
    ("hex_32_plus", re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])')),
    ("long_base64", re.compile(r'(?<![A-Za-z0-9+/=])[A-Za-z0-9+/=]{40,}')),
    ("generic_assignment", re.compile(r'(?i)(api[_-]?key|apikey|secret|client_secret|secret_key|access[_-]?token|auth[_-]?token|password|passwd|pwd)[\'\"\s:=]+([^\s\'\",;]+)')),
]

print("Scanning git history (this may take a while)...")
try:
    proc = subprocess.run(["git", "log", "-p", "--all", "--pretty=format:COMMIT:%H"], capture_output=True, text=False, cwd=root, timeout=600)
    # decode bytes defensively
    try:
        text = proc.stdout.decode("utf-8", errors="replace") if proc.stdout is not None else ""
    except Exception:
        text = str(proc.stdout)
except Exception as e:
    print(json.dumps({"error": str(e)}))
    raise

findings = []
current_commit = None
current_file = None
for line in text.splitlines():
    if line.startswith("COMMIT:"):
        current_commit = line.split("COMMIT:", 1)[1].strip()
        current_file = None
        continue
    # file markers
    if line.startswith("+++ b/"):
        current_file = line[6:].strip()
        continue
    if line.startswith("diff --git"):
        # try to extract filename
        m = re.search(r"a/(\S+) b/(\S+)", line)
        if m:
            current_file = m.group(2)
        continue
    if not line:
        continue
    sign = None
    content = line
    if line.startswith("+") and not line.startswith("+++"):
        sign = "added"
        content = line[1:]
    elif line.startswith("-") and not line.startswith("---"):
        sign = "removed"
        content = line[1:]
    else:
        # context or metadata
        continue

    for name, pat in patterns:
        for m in pat.finditer(content):
            matched = m.group(0)
            if not matched or len(matched) < 8:
                continue
            findings.append({
                "commit": current_commit,
                "file": current_file or "",
                "change": sign,
                "type": name,
                "match": matched[:200],
                "line": content.strip()[:300],
            })

# Deduplicate
uniq = []
seen = set()
for f in findings:
    key = (f.get('commit'), f.get('file'), f.get('change'), f.get('type'), f.get('match'))
    if key in seen:
        continue
    seen.add(key)
    uniq.append(f)

output = {"root": root, "findings": uniq}
print(json.dumps(output, indent=2, ensure_ascii=False))
