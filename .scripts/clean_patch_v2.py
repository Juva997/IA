from pathlib import Path
import re

src = Path('patches/clean-combined.patch')
if not src.exists():
    print('ERROR: source not found:', src)
    raise SystemExit(1)

bak = src.with_suffix('.patch.orig')
if not bak.exists():
    src.replace(bak)
    # restore original back to src
    bak.write_text(bak.read_text(encoding='utf-8', errors='replace'), encoding='utf-8')

s = src.read_text(encoding='utf-8', errors='replace')
lines = s.splitlines(keepends=True)
blocks = []
cur = []
for line in lines:
    if line.startswith('diff --git '):
        if cur:
            blocks.append(''.join(cur))
        cur = [line]
    else:
        cur.append(line)
if cur:
    blocks.append(''.join(cur))

keep = []
skipped = 0
for b in blocks:
    # detect binary indicators
    if 'GIT binary patch' in b or 'Binary files ' in b or re.search(r'^literal \d+', b, flags=re.M):
        skipped += 1
        continue
    keep.append(b)

out = Path('patches/clean-combined.v2.patch')
with out.open('w', encoding='utf-8', newline='\n') as f:
    f.write(''.join(keep))
print('wrote', out.stat().st_size, 'bytes; skipped blocks:', skipped)
