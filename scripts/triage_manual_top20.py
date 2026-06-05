#!/usr/bin/env python3
"""Gera um relatório com os top-20 itens Crítico/Alto com contexto extraído dos arquivos.
Saída: reports/triage_manual_top20.json
"""
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / 'reports' / 'triage_high_critical.json'
OUT = ROOT / 'reports' / 'triage_manual_top20.json'
GITLEAKS = ROOT / 'reports' / 'gitleaks-report.json'


def load(p: Path):
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding='utf-8', errors='ignore'))


def read_snippet(file_path: Path, line_no, ctx=5):
    try:
        text = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return {'exists': False, 'snippet': ''}
    lines = text.splitlines()
    if isinstance(line_no, int) and 1 <= line_no <= len(lines):
        start = max(0, line_no-1-ctx)
        end = min(len(lines), line_no-1+ctx+1)
        snippet = '\n'.join(lines[start:end])
        return {'exists': True, 'snippet': snippet, 'start_line': start+1, 'end_line': end}
    # fallback: return head
    return {'exists': True, 'snippet': '\n'.join(lines[:min(40,len(lines))]), 'start_line':1,'end_line':min(40,len(lines))}


if __name__ == '__main__':
    data = load(IN)
    if not data:
        raise SystemExit('triage_high_critical.json not found')
    items = data.get('items', [])
    # integrate gitleaks
    gdata = load(GITLEAKS)
    gcount = len(gdata) if isinstance(gdata, list) else 0

    # compute file frequencies
    files = [it.get('file') or '' for it in items]
    freq = Counter(files)

    # filter only Crítico/Alto and sort
    filtered = [it for it in items if it.get('severity') in ('Crítico','Alto')]
    # sort by severity then by file frequency
    sev_rank = {'Crítico': 0, 'Alto': 1}
    filtered.sort(key=lambda x: (sev_rank.get(x.get('severity'), 2), -freq.get(x.get('file') or '')))

    top = filtered[:20]
    out_items = []
    for it in top:
        f = it.get('file') or ''
        line = it.get('line')
        # resolve file on disk
        file_path = ROOT / f
        if not file_path.exists():
            # try without leading slash
            file_path = ROOT.joinpath(f.lstrip('/'))
        snippet_info = read_snippet(file_path, int(line) if isinstance(line, (int,str)) and str(line).isdigit() else None)
        merged = {
            'file': f,
            'file_exists': snippet_info.get('exists', False),
            'path': str(file_path) if snippet_info.get('exists', False) else None,
            'line': line,
            'severity': it.get('severity'),
            'match': it.get('match'),
            'context': it.get('context') or it.get('example'),
            'snippet': snippet_info.get('snippet',''),
            'source_report': it.get('source_report'),
            'commit': it.get('commit'),
        }
        # quick per-item suggested remediation templates
        rem = []
        txt = (str(it.get('match') or '') + ' ' + str(it.get('context') or '')).lower()
        if 'secret_key' in txt:
            rem.append('Remover default e exigir variável de ambiente `SECRET_KEY` (ex.: SECRET_KEY = os.environ["SECRET_KEY"])')
            rem.append('Se já foi usado em produção, rotacionar secret e invalidar onde aplicável')
            rem.append('Remover da história com `git filter-repo --replace-text` ou BFG; consulte team SOP')
        if 'ghp_' in txt or 'github' in txt:
            rem.append('Revogar token GitHub imediatamente e fazer scan de repositórios acessados')
        if 'akia' in txt:
            rem.append('Rotacionar chaves AWS e revogar; auditar uso via CloudTrail')
        if '-----begin' in txt:
            rem.append('Tratar como chave privada: remover, rotacionar e revogar onde for possível; considerar compromisso da conta')
        if not rem:
            rem.append('Revisão manual necessária; se confirmado, rotacionar e remover da história; adicionar pre-commit e CI scanning')
        merged['recommended_remediation'] = rem
        out_items.append(merged)

    out = {
        'root': str(ROOT),
        'gitleaks_count': gcount,
        'total_high_critical_found': len(filtered),
        'top_count': len(out_items),
        'top_items': out_items,
        'file_frequency_top10': freq.most_common(10)
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Wrote', OUT)
