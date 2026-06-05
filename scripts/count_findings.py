from pathlib import Path
paths = ['d:/IA/reports/secret_scan.json','d:/IA/reports/secret_history.json']
for p in paths:
    try:
        s = Path(p).read_bytes().decode('utf-8','ignore')
        print(p)
        print('  len=', len(s))
        print('  "file" count=', s.count('"file"'))
        print('  "commit" count=', s.count('"commit"'))
        print('  "match" count=', s.count('"match"'))
    except Exception as e:
        print('error reading', p, e)
