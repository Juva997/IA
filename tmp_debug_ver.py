from benchmark.verification import apply_setup, run_verifications
from pathlib import Path
import json
import shutil
root = Path('tmp_ver_test')
if root.exists():
    shutil.rmtree(root)
root.mkdir()
apply_setup(
    root,
    {
        'files': [
            {'path':'data.json','json':{'ok':True,'count':2}},
            {'path':'script.py','content':"print('script_ok')\n"},
            {'path':'test_sample.py','content':"def test_sample():\n    assert 2 + 2 == 4\n"}
        ]
    }
)
results = run_verifications(
    root,
    [
        {'type':'file_exists','path':'script.py','kind':'file'},
        {'type':'json_equals','path':'data.json','equals':{'ok':True,'count':2}},
        {'type':'python_file','path':'script.py','stdout_contains':'script_ok'},
        {'type':'pytest','path':'test_sample.py','args':['-q'],'timeout':20}
    ]
)
print(json.dumps(results, indent=2, ensure_ascii=False))
