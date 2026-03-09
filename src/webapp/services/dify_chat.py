from typing import Any, Iterator, Protocol

import requests


class DifyGatewayError(Exception):
    def __init__(self, *, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class DifyChatGateway(Protocol):
    def create_blocking_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def open_stream_chat_message(self, payload: dict[str, Any]): ...


class RequestsDifyChatGateway:
    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: int = 300):
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def create_blocking_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/chat-messages",
            json=payload,
            headers=self._build_headers(),
            timeout=self.timeout_seconds,
        )
        self._raise_for_error_response(response)
        return response.json()

    def open_stream_chat_message(self, payload: dict[str, Any]):
        response = requests.post(
            f"{self.base_url}/chat-messages",
            json=payload,
            headers=self._build_headers(),
            timeout=self.timeout_seconds,
            stream=True,
        )
        self._raise_for_error_response(response)
        return response

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _raise_for_error_response(self, response) -> None:
        if response.status_code < 400:
            return

        detail = _extract_error_detail(response)
        raise DifyGatewayError(status_code=response.status_code, detail=detail)


def iter_streaming_content(response, chunk_size: int = 8192) -> Iterator[bytes]:
    try:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                yield chunk
    finally:
        response.close()


def _normalize_base_url(base_url: str) -> str:
    normalized_url = base_url.rstrip("/")
    if normalized_url.endswith("/v1"):
        return normalized_url
    return f"{normalized_url}/v1"


def _extract_error_detail(response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text or "Dify request failed"

    if isinstance(data, dict):
        return str(data.get("message") or data.get("detail") or data)

    return str(data)
