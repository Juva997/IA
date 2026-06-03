"""Launcher unificado para iniciar API, UI, CLI e voz em combinações.

Use `launch(mode)` onde `mode` pode ser: 'api', 'ui', 'cli', 'voice',
combinações separadas por '+' ou ',' (ex: 'api+ui') ou 'all'.

O launcher inicia componentes que podem rodar em background (API/voice)
em threads, enquanto prioriza iniciar a UI no thread principal quando
solicitado.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import List

log = logging.getLogger(__name__)


def _parse_modes(mode_str: str) -> List[str]:
    if not mode_str:
        return []
    ms = mode_str.strip().lower()
    if ms == "all":
        return ["api", "ui", "voice", "cli"]
    parts = re.split(r"[,+\s]+", ms)
    modes: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if p not in modes:
            modes.append(p)
    return modes


def _start_in_thread(fn, name: str | None = None):
    th = threading.Thread(target=fn, daemon=True, name=name or getattr(fn, "__name__", "thread"))
    th.start()
    return th


def _safe_wrapper(fn, label: str):
    def _inner():
        try:
            fn()
        except Exception as e:
            log.exception("%s failed: %s", label, e)

    return _inner


# Import tools lazily but provide graceful fallbacks if imports fail.
# Prefer `app.start_api` (defined in the project entrypoint); fall back
# to other locations if needed.
try:
    from app import start_api  # type: ignore
except Exception:
    try:
        from interfaces.api import start_api  # type: ignore
    except Exception:
        def start_api(config=None):
            raise RuntimeError("start_api not available")

try:
    from interfaces.ui import start_ui  # type: ignore
except Exception:
    def start_ui():
        raise RuntimeError("start_ui not available")

try:
    from interfaces.cli import run_cli, run_doctor  # type: ignore
except Exception:
    def run_cli():
        raise RuntimeError("run_cli not available")

    def run_doctor():
        raise RuntimeError("run_doctor not available")

try:
    from interfaces.voice import start_voice  # type: ignore
except Exception:
    def start_voice():
        raise RuntimeError("start_voice not available")


def launch(mode: str | None = "ui"):
    """Inicia componentes conforme `mode`.

    Exemplos:
    - launch('ui') -> inicia apenas a UI (thread principal)
    - launch('api') -> inicia apenas a API (bloqueante)
    - launch('api+ui') -> inicia API em thread e UI no thread principal
    - launch('all') -> tenta iniciar api, ui, voice e cli
    """
    modes = _parse_modes(mode or "")
    if not modes:
        modes = ["ui"]

    # Componentes que podem rodar em background
    if "api" in modes:
        _start_in_thread(_safe_wrapper(start_api, "API"), "api")

    if "voice" in modes:
        _start_in_thread(_safe_wrapper(start_voice, "Voice"), "voice")

    # Priorizar UI no thread principal se solicitado
    if "ui" in modes:
        log.info("Launcher: iniciando UI no thread principal")
        try:
            start_ui()
        except Exception:
            log.exception("Falha ao iniciar UI; entrando em CLI de fallback")
            run_cli()
        return

    # Se UI não for solicitada, rodar CLI/doctor conforme pedido
    if "cli" in modes:
        log.info("Launcher: iniciando CLI no thread principal")
        run_cli()
        return

    if "doctor" in modes:
        run_doctor()
        return

    # Se nada mais, manter CLI por padrão
    run_cli()


def available_modes() -> List[str]:
    return ["api", "ui", "cli", "voice", "doctor", "all"]
