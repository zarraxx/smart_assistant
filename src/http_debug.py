from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Iterable

import httpx


EmitFn = Callable[[str], None]
DEFAULT_MAX_BODY_CHARS = 16_384
DEFAULT_REDACTED_HEADERS = frozenset({"authorization"})


def _default_emit(message: str) -> None:
    logging.getLogger(__name__).info(message)


def _normalize_headers(
    headers: httpx.Headers,
    *,
    redacted_headers: Iterable[str],
) -> dict[str, str]:
    redacted = {header.lower() for header in redacted_headers}
    normalized: dict[str, str] = {}
    for key, value in headers.items():
        normalized[key] = "***REDACTED***" if key.lower() in redacted else value
    return normalized


def _format_body_preview(body: bytes, *, max_body_chars: int) -> str:
    text = body.decode("utf-8", errors="replace")
    if len(text) <= max_body_chars:
        return text
    return f"{text[:max_body_chars]}\n...<truncated {len(text) - max_body_chars} chars>"


class LoggingByteStream(httpx.SyncByteStream):
    def __init__(
        self,
        stream: httpx.SyncByteStream,
        *,
        emit: EmitFn,
        max_body_chars: int,
    ) -> None:
        self._stream = stream
        self._emit = emit
        self._max_body_chars = max_body_chars
        self._chunks: list[bytes] = []

    def __iter__(self):
        try:
            for chunk in self._stream:
                self._chunks.append(chunk)
                yield chunk
        finally:
            body = b"".join(self._chunks)
            self._emit(
                "HTTP response body:\n"
                f"{_format_body_preview(body, max_body_chars=self._max_body_chars)}"
            )

    def close(self) -> None:
        self._stream.close()


class LoggingAsyncByteStream(httpx.AsyncByteStream):
    def __init__(
        self,
        stream: httpx.AsyncByteStream,
        *,
        emit: EmitFn,
        max_body_chars: int,
    ) -> None:
        self._stream = stream
        self._emit = emit
        self._max_body_chars = max_body_chars
        self._chunks: list[bytes] = []

    async def __aiter__(self):
        try:
            async for chunk in self._stream:
                self._chunks.append(chunk)
                yield chunk
        finally:
            body = b"".join(self._chunks)
            self._emit(
                "HTTP response body:\n"
                f"{_format_body_preview(body, max_body_chars=self._max_body_chars)}"
            )

    async def aclose(self) -> None:
        await self._stream.aclose()


class DebugTransport(httpx.BaseTransport):
    def __init__(
        self,
        inner_transport: httpx.BaseTransport | None = None,
        *,
        emit: EmitFn | None = None,
        max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
        redacted_headers: Iterable[str] = DEFAULT_REDACTED_HEADERS,
    ) -> None:
        self._inner_transport = inner_transport or httpx.HTTPTransport()
        self._emit = emit or _default_emit
        self._max_body_chars = max_body_chars
        self._redacted_headers = tuple(redacted_headers)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request_body = request.read()
        self._emit(
            "HTTP request:\n"
            f"{request.method} {request.url}\n"
            f"headers={_normalize_headers(request.headers, redacted_headers=self._redacted_headers)}\n"
            f"body={_format_body_preview(request_body, max_body_chars=self._max_body_chars)}"
        )

        forwarded_request = httpx.Request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            content=request_body,
            extensions=request.extensions,
        )
        response = self._inner_transport.handle_request(forwarded_request)
        self._emit(
            "HTTP response:\n"
            f"status={response.status_code}\n"
            f"headers={dict(response.headers)}"
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            stream=LoggingByteStream(
                response.stream,
                emit=self._emit,
                max_body_chars=self._max_body_chars,
            ),
            extensions=response.extensions,
            request=forwarded_request,
        )

    def close(self) -> None:
        self._inner_transport.close()


class DebugAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        inner_transport: httpx.AsyncBaseTransport | None = None,
        *,
        emit: EmitFn | None = None,
        max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
        redacted_headers: Iterable[str] = DEFAULT_REDACTED_HEADERS,
    ) -> None:
        self._inner_transport = inner_transport or httpx.AsyncHTTPTransport()
        self._emit = emit or _default_emit
        self._max_body_chars = max_body_chars
        self._redacted_headers = tuple(redacted_headers)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request_body = await request.aread()
        self._emit(
            "HTTP request:\n"
            f"{request.method} {request.url}\n"
            f"headers={_normalize_headers(request.headers, redacted_headers=self._redacted_headers)}\n"
            f"body={_format_body_preview(request_body, max_body_chars=self._max_body_chars)}"
        )

        forwarded_request = httpx.Request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            content=request_body,
            extensions=request.extensions,
        )
        response = await self._inner_transport.handle_async_request(forwarded_request)
        self._emit(
            "HTTP response:\n"
            f"status={response.status_code}\n"
            f"headers={dict(response.headers)}"
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            stream=LoggingAsyncByteStream(
                response.stream,
                emit=self._emit,
                max_body_chars=self._max_body_chars,
            ),
            extensions=response.extensions,
            request=forwarded_request,
        )

    async def aclose(self) -> None:
        await self._inner_transport.aclose()


@dataclass(slots=True)
class DebugHTTPClients:
    http_client: httpx.Client
    http_async_client: httpx.AsyncClient

    async def aclose(self) -> None:
        await self.http_async_client.aclose()
        self.http_client.close()


def build_debug_http_clients(
    *,
    emit: EmitFn | None = None,
    max_body_chars: int = DEFAULT_MAX_BODY_CHARS,
    redacted_headers: Iterable[str] = DEFAULT_REDACTED_HEADERS,
) -> DebugHTTPClients:
    return DebugHTTPClients(
        http_client=httpx.Client(
            transport=DebugTransport(
                emit=emit,
                max_body_chars=max_body_chars,
                redacted_headers=redacted_headers,
            )
        ),
        http_async_client=httpx.AsyncClient(
            transport=DebugAsyncTransport(
                emit=emit,
                max_body_chars=max_body_chars,
                redacted_headers=redacted_headers,
            )
        ),
    )
