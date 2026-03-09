import json
from typing import Any, AsyncIterator, Protocol

import httpx

from src.dify_client import AsyncChatClient

class DifyGatewayError(Exception):
    def __init__(self, *, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class DifyChatGateway(Protocol):
    async def create_blocking_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    async def open_stream_chat_message(self, payload: dict[str, Any]): ...


class StreamingDifyResponse:
    def __init__(self, *, client: AsyncChatClient, response: httpx.Response):
        self._client = client
        self._response = response

    @property
    def headers(self):
        return self._response.headers

    async def aiter_bytes(self, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_bytes(chunk_size=chunk_size):
            if chunk:
                yield chunk

    async def aclose(self) -> None:
        await self._response.aclose()
        await self._client.aclose()


class AsyncDifyChatGateway:
    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: int = 300):
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def create_blocking_chat_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with AsyncChatClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=float(self.timeout_seconds),
        ) as client:
            response = await client.create_chat_message(
                inputs=payload.get("inputs", {}),
                query=payload["query"],
                user=payload["user"],
                response_mode="blocking",
                conversation_id=payload.get("conversation_id"),
                files=payload.get("files"),
                auto_generate_name=payload.get("auto_generate_name"),
            )
        self._raise_for_error_response(response)
        return response.json()

    async def open_stream_chat_message(self, payload: dict[str, Any]) -> StreamingDifyResponse:
        client = AsyncChatClient(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=float(self.timeout_seconds),
        )
        try:
            response = await client.create_chat_message(
                inputs=payload.get("inputs", {}),
                query=payload["query"],
                user=payload["user"],
                response_mode="streaming",
                conversation_id=payload.get("conversation_id"),
                files=payload.get("files"),
                auto_generate_name=payload.get("auto_generate_name"),
            )
            self._raise_for_error_response(response)
            return StreamingDifyResponse(client=client, response=response)
        except Exception:
            await client.aclose()
            raise

    def _raise_for_error_response(self, response) -> None:
        if response.status_code < 400:
            return

        detail = _extract_error_detail(response)
        raise DifyGatewayError(status_code=response.status_code, detail=detail)


def _normalize_base_url(base_url: str) -> str:
    normalized_url = base_url.rstrip("/")
    if normalized_url.endswith("/v1"):
        return normalized_url
    return f"{normalized_url}/v1"


def _extract_error_detail(response) -> str:
    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError):
        return response.text or "Dify request failed"

    if isinstance(data, dict):
        return str(data.get("message") or data.get("detail") or data)

    return str(data)
