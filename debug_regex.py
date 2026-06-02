import re
text = 'criar uma pasta chamada teste, dentro desta pasta crier um arquivo txt chamado de Leia-me'
pattern = r'(?:crie|criar|cria|gere|gerar|crier)\s+(?:uma\s+)?(?:pasta|diret[oó]rio)(?:\s+chamada|\s+chamado)?\s+['\"]?([^'\",\s]+)['\"]?(?:\s|$)'
match = re.search(pattern, text, flags=re.IGNORECASE)
if match:
    print('Match:', repr(match.group(0)))
    print('Group 1:', repr(match.group(1)))
else:
    print('No match')