import unittest
from pathlib import Path
from unittest.mock import patch

from src.webapp.config import Settings
import src.startup as startup


class StartupTestCase(unittest.TestCase):
    @patch("src.startup.uvicorn.run")
    @patch("src.startup.get_settings")
    def test_main_runs_web_server_with_config_settings(self, mock_get_settings, mock_uvicorn_run):
        mock_get_settings.return_value = Settings(
            root_path="/",
            redis_url="redis://localhost:6379/0",
            default_dify_url="http://127.0.0.1:5001",
            default_dify_api_key="app-test",
            session_default_expire_seconds=1200,
            session_key_prefix="smart-assistant:session",
            server_host="127.0.0.1",
            server_port=9000,
            server_reload=False,
        )

        startup.main()

        expected_app_dir = str(Path(startup.__file__).resolve().parents[1])
        mock_uvicorn_run.assert_called_once_with(
            "src.webapp.assistant_app:app",
            host="127.0.0.1",
            port=9000,
            reload=False,
            app_dir=expected_app_dir,
        )


if __name__ == "__main__":
    unittest.main()
