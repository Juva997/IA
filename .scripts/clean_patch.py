from pathlib import Path
import shutil

p = Path('patches/clean-combined.patch')
if not p.exists():
    print('ERROR: source patch not found:', p)
    raise SystemExit(1)

# backup original
bak = p.parent / (p.name + '.orig')
shutil.copy2(p, bak)

s = p.read_text(encoding='utf-8', errors='replace')
parts = s.split('\ndiff --git ')
keep = []
for part in parts:
    if not part.strip():
        continue
    block = 'diff --git ' + part
    if 'GIT binary patch' in block or 'Binary files ' in block:
        continue
    keep.append(block)

out = p
out.write_text('\n'.join(keep), encoding='utf-8')
print('wrote', out.stat().st_size)
