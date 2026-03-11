import os
from dataclasses import dataclass
from functools import lru_cache


DEFAULT_SESSION_EXPIRE_SECONDS = 20 * 60


@dataclass(frozen=True)
class Settings:
    root_path: str
    redis_url: str
    default_dify_url: str
    default_dify_api_key: str
    session_default_expire_seconds: int
    session_key_prefix: str
    server_host: str
    server_port: int
    server_reload: bool
    openai_base_url: str
    openai_api_key: str
    openai_model:str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        root_path=os.getenv("ROOT_PATH", "/smart_assistant"),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        default_dify_url=os.getenv("DEFAULT_DIFY_URL", "http://127.0.0.1:5001"),
        default_dify_api_key=os.getenv("DEFAULT_DIFY_API_KEY", ""),
        session_default_expire_seconds=int(
            os.getenv("SESSION_DEFAULT_EXPIRE_SECONDS", str(DEFAULT_SESSION_EXPIRE_SECONDS))
        ),
        session_key_prefix=os.getenv("SESSION_KEY_PREFIX", "smart-assistant:session"),
        server_host=os.getenv("SERVER_HOST", "0.0.0.0"),
        server_port=int(os.getenv("SERVER_PORT", "8000")),
        server_reload=_get_bool_env("SERVER_RELOAD", True),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "deepseek-v3"),
    )


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}
