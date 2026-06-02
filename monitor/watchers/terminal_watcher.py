import re


class TerminalWatcher:
    """
    Analisa textos de terminal para detectar:
    - erros
    - traceback
    - falhas comuns
    """

    ERROR_PATTERNS = [
        r"traceback",
        r"error",
        r"exception",
        r"module not found",
        r"no module named",
        r"syntaxerror",
        r"indentationerror",
        r"filenotfounderror",
        r"permissionerror",
        r"nameerror",
        r"typeerror",
        r"valueerror",
        r"keyerror",
        r"indexerror",
        r"attributeerror",
        r"falha",
        r"erro",
    ]

    def analyze(self, text: str) -> dict:
        text = text or ""
        lowered = text.lower()

        matches = []
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                matches.append(pattern)

        return {
            "has_error": len(matches) > 0,
            "matches": matches,
            "summary": self._build_summary(lowered, matches),
        }

    def _build_summary(self, text: str, matches: list[str]) -> str:
        if not matches:
            return "Nenhum erro evidente detectado."

        if "traceback" in matches:
            return "Traceback detectado no terminal."

        if "module not found" in matches or "no module named" in matches:
            return "Dependência ausente detectada."

        if "syntaxerror" in matches:
            return "Erro de sintaxe detectado."

        if "filenotfounderror" in matches:
            return "Arquivo não encontrado detectado."

        return "Possível erro detectado no terminal."
