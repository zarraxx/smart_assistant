import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.http_debug import DebugHTTPClients, build_debug_http_clients


load_dotenv()

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    debug_clients: DebugHTTPClients | None = None
    client_kwargs: dict[str, object] = {}
    if _is_truthy_env(os.getenv("OPENAI_DEBUG_HTTP")):
        debug_clients = build_debug_http_clients(emit=logger.info)
        client_kwargs["http_client"] = debug_clients.http_client

    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        **client_kwargs,
    )

    messages = [{"content":"","role":"system"},{"role": "user", "content": "\u4f60\u662f\u8c01"}]
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL"),
        messages=messages,
        extra_body={"enable_thinking": True},
        stream=True,
        stream_options={"include_usage": True},
    )

    is_answering = False
    try:
        print("\n" + "=" * 20 + "\u601d\u8003\u8fc7\u7a0b" + "=" * 20)
        for chunk in completion:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                    if not is_answering:
                        print(delta.reasoning_content, end="", flush=True)
                if hasattr(delta, "content") and delta.content:
                    if not is_answering:
                        print("\n" + "=" * 20 + "\u5b8c\u6574\u56de\u590d" + "=" * 20)
                        is_answering = True
                    print(delta.content, end="", flush=True)
        print()
    finally:
        client.close()


if __name__ == "__main__":
    main()
