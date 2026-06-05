#!/usr/bin/env python3
"""Extrai itens Crítico/Alto do relatório classificado e sugere cenários e remediações.
Gera: reports/triage_high_critical.json
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "reports" / "secret_report_classified.json"
OUT = ROOT / "reports" / "triage_high_critical.json"

CRIT_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
]


def load_report(p: Path):
    if not p.exists():
        raise SystemExit(f"Relatório não encontrado: {p}")
    with p.open('r', encoding='utf-8') as f:
        return json.load(f)


def detect_scenario_and_remediation(item: dict):
    match = str(item.get('match') or '')
    ctx = str(item.get('context') or item.get('example') or '')
    txt = (match + ' ' + ctx).lower()
    findings = []
    remediation = []

    # Private key
    for p in CRIT_PATTERNS:
        if p.search(match) or p.search(ctx):
            findings.append('Chave/Token crítico identificado: padrão provedor/privada')
            remediation.append('Rotacionar e revogar imediatamente no provedor; remover do histórico git com git filter-repo/BFG; invalidar credenciais; evitar reutilização.')
            break

    # SECRET_KEY default
    if 'secret_key' in txt:
        if 'change-me-secret' in txt or 'change me secret' in txt:
            findings.append('Default inseguro de SECRET_KEY encontrado no histórico')
            remediation.append('Remover default; exigir variável de ambiente `SECRET_KEY` e falhar na inicialização se ausente; rotacionar se usado em produção; limpar histórico ou tratar como audit item.')
        else:
            findings.append('SECRET_KEY hardcoded ou exposto')
            remediation.append('Rotacionar secret, remover do repo/history e mover para secret manager; usar env var em runtime.')

    # AWS key pattern
    if re.search(r'akia[0-9a-z]{16}', txt, re.I):
        findings.append('AWS Access Key ID detectada (AKIA...)')
        remediation.append('Rotacionar chaves AWS, revogar imediatamente, auditar uso via CloudTrail; mover para IAM role ou secret manager; remover do histórico git.')

    # Google API key
    if re.search(r'AIza[0-9A-Za-z_\-]{35}', txt):
        findings.append('Google API key detectada (AIza...)')
        remediation.append('Rotacionar a chave; restringir por IP/refs e ativar política de APIs; remover do histórico.')

    # GitHub PAT
    if re.search(r'ghp_[A-Za-z0-9]{36}', txt):
        findings.append('GitHub Personal Access Token detectado (ghp_)')
        remediation.append('Revogar token no GitHub, auditar repositórios acessados; remover do histórico e rotacionar credenciais afetadas.')

    # Slack / Slack-like tokens
    if re.search(r'xox[baprs]-', txt):
        findings.append('Token Slack-like detectado (xox...)')
        remediation.append('Revogar token na plataforma, rotacionar, e remover do histórico. Verificar integrações expostas.')

    # Generic API key/token/password assignment
    if re.search(r"(api[_\- ]?key|token|secret|password)\W{0,10}[:=]\W{0,10}['\"]?[A-Za-z0-9\-_=+/,]{8,200}['\"]?", txt, re.I):
        findings.append('Token/API key/password hardcoded detectado')
        remediation.append('Rotacionar e revogar onde aplicável; extrair para variáveis de ambiente ou secret manager; aplicar varredura pre-commit e CI para evitar re-submissões.')

    # If nothing matched specifically
    if not findings:
        findings.append('Possível segredo de alta entropia ou atribuição sensível — revisão manual necessária')
        remediation.append('Revisar manualmente; se for segredo, rotacionar e remover do histórico; introduzir controles de segurança (secret manager, env vars, policies).')

    # Standard remediation steps appended
    remediation_std = [
        'Adicionar proteção: pre-commit hook com gitleaks/git-secrets e CI scanning',
        'Adicionar logs/auditoria para uso de credenciais rotacionadas',
        'Considerar isolar chaves com menor privilégio (principle of least privilege)'
    ]
    remediation.extend(remediation_std)

    return {'findings': findings, 'remediation': remediation}


if __name__ == '__main__':
    data = load_report(IN)
    items = data.get('items', [])
    high = [it for it in items if it.get('severity') in ('Crítico', 'Alto')]

    triage = []
    by_file = {}
    for it in high:
        file = it.get('file') or ''
        by_file.setdefault(file, 0)
        by_file[file] += 1
        info = detect_scenario_and_remediation(it)
        tri = {
            'file': file,
            'line': it.get('line'),
            'match': it.get('match'),
            'context': it.get('context') or it.get('example'),
            'severity': it.get('severity'),
            'source_report': it.get('source_report'),
            'commit': it.get('commit'),
            'findings': info['findings'],
            'remediation': info['remediation'],
        }
        triage.append(tri)

    summary = {
        'root': str(ROOT),
        'total_high_critical': len(triage),
        'by_file_count_top10': sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:10],
    }

    out = {'summary': summary, 'items': triage}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {OUT} — total {len(triage)} itens (Crítico/Alto)')
