from pathlib import Path
p='d:/IA/reports/secret_scan.json'
b=Path(p).read_bytes()
idx=b.find(b'file')
print('index', idx)
if idx!=-1:
    print(repr(b[max(0,idx-80):idx+200]))
else:
    print('no file bytes found')

p2='d:/IA/reports/secret_history.json'
b2=Path(p2).read_bytes()
idx2=b2.find(b'file')
print('history index', idx2)
if idx2!=-1:
    print(repr(b2[max(0,idx2-80):idx2+200]))
else:
    print('no file bytes in history')
