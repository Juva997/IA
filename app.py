import os
import sys

import uvicorn

from interfaces.api import app as api_app
from interfaces.cli import run_cli, run_doctor
from interfaces.ui import start_ui
from interfaces.voice import start_voice
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


def start_api():
    log.info("Iniciando API REST em http://localhost:8000")
    log.info("Docs: http://localhost:8000/docs")
    log.info("Metricas: http://localhost:8001")

    try:
        from monitor.metrics import Metrics

        metrics = Metrics()
        metrics.start_server(8001)
    except ValueError:
        log.info("Metricas ja iniciadas")

    uvicorn.run(api_app, host="127.0.0.1", port=8000)


def main():
    logger.configure_logging()
    bootstrap()

    mode = "ui"

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    if mode == "cli":
        run_cli()
    elif mode == "ui":
        start_ui()
    elif mode == "voice":
        start_voice()
    elif mode == "api":
        start_api()
    elif mode == "doctor":
        run_doctor()
    else:
        log.error("Modo invalido. Use: cli | ui | voice | api | doctor")


if __name__ == "__main__":
    main()
