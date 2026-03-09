from pathlib import Path

import uvicorn

from src.webapp.config import Settings, get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_IMPORT_PATH = "src.webapp.assistant_app:app"


def run_web_server(settings: Settings | None = None) -> None:
    active_settings = settings or get_settings()
    uvicorn.run(
        APP_IMPORT_PATH,
        host=active_settings.server_host,
        port=active_settings.server_port,
        reload=active_settings.server_reload,
        app_dir=str(PROJECT_ROOT),
    )


def main() -> None:
    run_web_server()


if __name__ == "__main__":
    main()
