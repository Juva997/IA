from actions.tools.python_tools import run_python_code


code = (
    "import math\n"
    "def fatorial(n):\n"
    "    return math.factorial(n)\n"
    "print('Fatorial de 5:', fatorial(5))"
)

result = run_python_code({"code": code})
print("RESULT:", result)
