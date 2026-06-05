import os
import sys

import uvicorn

from interfaces.api import app as api_app
from interfaces.cli import run_cli, run_doctor
from utils import logger
from utils.config_loader import ConfigLoader

log = logger.get_logger("app")


def bootstrap():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    config = ConfigLoader(config_path)

    _prepare_directories(config)

    log.info(f"\n{config.get('app_name')} v{config.get('version')}")
    log.info("Modo inicializando...\n")

    return config


def _prepare_directories(config):
    paths = config.get("data_paths", {})

    for path in paths.values():
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            log.warning(f"erro ao criar pasta {path}: {e}")


def start_api(config=None):
    if config is None:
        config = ConfigLoader()

    host = config.get("server.host", "127.0.0.1")
    try:
        api_port = int(config.get("server.api_port", 8000))
    except Exception:
        api_port = 8000
    try:
        metrics_port = int(config.get("server.metrics_port", 8001))
    except Exception:
        metrics_port = 8001

    # SECURITY: if API key requirement is enabled, ensure API key exists before starting
    require_flag_env = os.environ.get("ASSISTENTE_REQUIRE_API_KEY", "1").strip().lower() in ("1", "true", "yes")
    if require_flag_env and not os.environ.get("ASSISTENTE_API_KEY"):
        log.error("ASSISTENTE_REQUIRE_API_KEY is set but ASSISTENTE_API_KEY is not configured. Aborting start.")
        raise SystemExit("Missing ASSISTENTE_API_KEY while require_api_key is enabled")

    log.info(f"Iniciando API REST em http://{host}:{api_port}")
    log.info(f"Docs: http://{host}:{api_port}/docs")
    log.info(f"Metricas: http://{host}:{metrics_port}")

    try:
        from monitor.metrics import Metrics

        metrics = Metrics()
        metrics.start_server(metrics_port)
    except ValueError:
        log.info("Metricas ja iniciadas")

    uvicorn.run(api_app, host=host, port=api_port)

# export `app` symbol for `uvicorn app:app` compatibility
app = api_app
def main():
    logger.configure_logging()
    config = bootstrap()

    mode = "ui"

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    # Prefer launcher (unificado). Fallback para comportamento legado se o
    # launcher não puder ser importado.
    try:
        from interfaces.launcher import launch  # type: ignore

        launch(mode)
        return
    except Exception:
        log.info("Launcher não disponível, usando comportamento legado")

    if mode == "cli":
        run_cli()
    elif mode == "ui":
        try:
            from interfaces.ui import start_ui
        except Exception as e:
            log.error("UI não disponível: %s", e)
            raise
        start_ui()
    elif mode == "voice":
        try:
            from interfaces.voice import start_voice
        except Exception as e:
            log.error("Voice interface não disponível: %s", e)
            raise
        start_voice()
    elif mode == "api":
        start_api(config)
    elif mode == "doctor":
        run_doctor()
    else:
        log.error("Modo invalido. Use: cli | ui | voice | api | doctor")


if __name__ == "__main__":
    main()
