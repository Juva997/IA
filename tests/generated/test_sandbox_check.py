from actions.tools.python_tools import run_python_code
with open("test_local_module.py","w",encoding="utf-8") as f:
    f.write("def main():\n    print(42)\n")
res = run_python_code({"code": "from test_local_module import main\nmain()"})
print(res)
