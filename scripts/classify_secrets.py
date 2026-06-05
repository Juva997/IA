#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "secret_report_classified.json"
INPUTS = [ROOT / "reports" / "secret_scan.json", ROOT / "reports" / "secret_history.json"]

# Patterns considered high-risk (private keys, common provider tokens/keys)
CRITICAL_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
]

# helper
def load_json_flexible(p: Path):
    if not p.exists():
        return {}
    # read bytes and detect common encodings (utf-8 or utf-16-LE/BE)
    b = p.read_bytes()
    enc = 'utf-8'
    if b.startswith(b'\xff\xfe') or b.startswith(b'\xfe\xff'):
        enc = 'utf-16'
    else:
        # heuristic: many null bytes likely indicate utf-16
        if b.count(b'\x00') > max(1, len(b) // 20):
            enc = 'utf-16'
    s = b.decode(enc, errors='ignore')
    # trim any leading non-json text
    idx = s.find('{')
    if idx > 0:
        s = s[idx:]
    try:
        return json.loads(s)
    except Exception:
        print(f"DEBUG: load_json_flexible failed to json.load {p}; length={len(s)}; detected_enc={enc}")
        print(s[:400].replace('\n', '\\n'))
        # Fallback: try to extract the "findings" array even if JSON is truncated
        key = '"findings"'
        kidx = s.find(key)
        if kidx == -1:
            return {}
        arr_start = s.find('[', kidx)
        if arr_start == -1:
            return {}
        # find matching closing bracket for the array
        depth = 0
        end = None
        for i in range(arr_start, len(s)):
            if s[i] == '[':
                depth += 1
            elif s[i] == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        arr_text = s[arr_start:end] if end else s[arr_start:]
        # attempt to close array if truncated
        if end is None:
            arr_text = arr_text + ']'
        try:
            findings = json.loads(arr_text)
            return {'findings': findings}
        except Exception:
            # Último recurso: tentar extrair objetos JSON individuais do texto
            objs = []
            pos = 0
            L = len(s)
            while True:
                idx = s.find('{', pos)
                if idx == -1:
                    break
                depth = 0
                end = None
                for i in range(idx, L):
                    if s[i] == '{':
                        depth += 1
                    elif s[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break
                if end is None:
                    break
                obj_text = s[idx:end]
                try:
                    obj = json.loads(obj_text)
                except Exception:
                    # tentar remover vírgula terminal inválida
                    try:
                        import re as _re
                        obj = json.loads(_re.sub(r',\s*\}$', '}', obj_text))
                    except Exception:
                        pos = idx + 1
                        continue
                if isinstance(obj, dict) and ('file' in obj or 'commit' in obj or 'match' in obj):
                    objs.append(obj)
                pos = end
            if objs:
                return {'findings': objs}
            # Último recurso: extrair campos via regex (mais tolerante a JSON inválido)
            def parse_findings_loose(text: str):
                res = []
                for m in re.finditer(r'"file"\s*:\s*"([^"]+)"', text):
                    file_val = m.group(1)
                    start = m.start()
                    # tentar extrair até o fim do objeto
                    end_pos = text.find('},', start)
                    if end_pos == -1:
                        end_pos = text.find('}', start)
                        if end_pos == -1:
                            end_pos = min(start + 3000, len(text) - 1)
                    snippet = text[start:end_pos+1]
                    mm = re.search(r'"match"\s*:\s*"([^\"]+)"', snippet)
                    match_val = mm.group(1) if mm else ''
                    ln = None
                    mm2 = re.search(r'"line"\s*:\s*(\d+)', snippet)
                    if mm2:
                        ln = int(mm2.group(1))
                    typ = None
                    mm3 = re.search(r'"type"\s*:\s*"([^\"]+)"', snippet)
                    if mm3:
                        typ = mm3.group(1)
                    commit = None
                    mm4 = re.search(r'"commit"\s*:\s*"([^\"]+)"', snippet)
                    if mm4:
                        commit = mm4.group(1)
                    ctx = ''
                    mm5 = re.search(r'"context"\s*:\s*"([^\"]+)"', snippet)
                    if mm5:
                        ctx = mm5.group(1)
                    res.append({
                        'file': file_val,
                        'match': match_val,
                        'line': ln,
                        'type': typ,
                        'commit': commit,
                        'context': ctx,
                    })
                # also try to extract objects that have 'commit' but not file
                for m in re.finditer(r'"commit"\s*:\s*"([^"]+)"', text):
                    # skip if we already captured this commit via file extraction
                    commit_val = m.group(1)
                    # if commit already present in res, skip
                    if any(it.get('commit') == commit_val for it in res):
                        continue
                    start = m.start()
                    end_pos = text.find('},', start)
                    if end_pos == -1:
                        end_pos = text.find('}', start)
                        if end_pos == -1:
                            end_pos = min(start + 3000, len(text) - 1)
                    snippet = text[start:end_pos+1]
                    mmf = re.search(r'"file"\s*:\s*"([^\"]+)"', snippet)
                    file_val = mmf.group(1) if mmf else ''
                    mm = re.search(r'"match"\s*:\s*"([^\"]+)"', snippet)
                    match_val = mm.group(1) if mm else ''
                    ln = None
                    mm2 = re.search(r'"line"\s*:\s*(\d+)', snippet)
                    if mm2:
                        ln = int(mm2.group(1))
                    typ = None
                    mm3 = re.search(r'"type"\s*:\s*"([^\"]+)"', snippet)
                    if mm3:
                        typ = mm3.group(1)
                    res.append({
                        'file': file_val,
                        'match': match_val,
                        'line': ln,
                        'type': typ,
                        'commit': commit_val,
                        'context': ''
                    })
                return res

            loose = parse_findings_loose(s)
            print('DEBUG: loose regex found', len(loose))
            print('DEBUG: file-key count', len(list(re.finditer(r'"file"\s*:\s*"([^\"]+)"', s))))
            if loose:
                return {'findings': loose}
            return {}


def classify_item(item):
    file = str(item.get('file') or item.get('path') or '')
    typ = str(item.get('type') or '')
    match = str(item.get('match') or '')
    line = str(item.get('line') or item.get('context') or '')
    src = str(item.get('source') or '')

    severity = 'Baixo'
    reasons = []

    # quick rules for obvious benigns
    if '.mypy_cache' in file or file.endswith('.db') or file.endswith('.pyc'):
        severity = 'Baixo'
        reasons.append('Arquivo de cache/binário — provavelmente falso positivo')
        return severity, reasons
    if 'package-lock.json' in file or 'integrity' in (match+line).lower():
        severity = 'Baixo'
        reasons.append('Hash de integridade de pacote (normalmente benigno)')
        return severity, reasons

    # test artifacts
    if 'audit_pytest_tmp' in file or '/test_' in file or file.startswith('test_'):
        severity = 'Médio'
        reasons.append('Artefato de teste — revisar se contém segredos reais')

    # insecure default secret
    if 'SECRET_KEY' in match or 'SECRET_KEY' in line:
        if 'change-me-secret' in (match+line):
            severity = 'Alto'
            reasons.append('Default inseguro de SECRET_KEY encontrado no histórico — não é segredo exposto mas é risco de segurança')
        else:
            severity = 'Crítico'
            reasons.append('Atribuição de SECRET_KEY detectada (possível segredo)')

    # generic credential-like assignments
    if re.search(r"password\W*[:=]\W*['\"]?\w+['\"]?", line, re.I):
        if severity != 'Crítico':
            severity = 'Alto'
            reasons.append('Senha hardcoded detectada')

    # explicit API key/token patterns
    if re.search(r"(api[_-]?key|token|secret)[\s\":=]{1,20}[A-Za-z0-9\-_.]{8,200}", (match+line), re.I):
        severity = 'Crítico'
        reasons.append('Token/API key detectada em contexto de atribuição')

    # check critical regexes
    for p in CRITICAL_PATTERNS:
        if p.search(match) or p.search(line):
            severity = 'Crítico'
            reasons.append('Padrão crítico encontrado (chave privada / token de provedor)')
            break

    # high-entropy strings outside known benign files
    if severity == 'Baixo' and typ in ('long_base64','hex_32_plus'):
        severity = 'Médio'
        reasons.append('String de alta entropia encontrada; revisar se é segredo')

    return severity, reasons


all_items = []
for inp in INPUTS:
    doc = load_json_flexible(inp)
    items = doc.get('findings') if isinstance(doc, dict) else []
    if items:
        for it in items:
            it['source_report'] = inp.name
            # normalize minimal fields
            it.setdefault('file', it.get('file', it.get('path', '')))
            severity, reasons = classify_item(it)
            it['severity'] = severity
            it['reasons'] = reasons
            # add short example snippet
            line = str(it.get('line') or it.get('context') or '')
            it['example'] = (line.strip()[:400] + '...') if line and len(line) > 400 else line
            all_items.append(it)

# counts
counts = {'Crítico':0,'Alto':0,'Médio':0,'Baixo':0}
for it in all_items:
    counts[it['severity']] = counts.get(it['severity'],0) + 1

out = {
    'root': str(ROOT),
    'counts': counts,
    'items': all_items,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote', OUT)
