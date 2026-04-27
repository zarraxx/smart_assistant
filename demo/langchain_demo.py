import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_openai import ChatOpenAI

from src.http_debug import DebugHTTPClients, build_debug_http_clients


load_dotenv()

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OPEN_THINK_TAG = "<think>"
CLOSE_THINK_TAG = "</think>"


class ReasoningChatOpenAI(ChatOpenAI):
    """Preserve provider-specific reasoning deltas on LangChain stream chunks."""

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict[str, Any],
        default_chunk_class: type,
        base_generation_info: dict[str, Any] | None,
    ):
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation_chunk is None:
            return None

        choices = chunk.get("choices", []) or chunk.get("chunk", {}).get("choices", [])
        if not choices:
            return generation_chunk

        delta = choices[0].get("delta") or {}
        reasoning_content = delta.get("reasoning_content")
        if reasoning_content and isinstance(generation_chunk.message, AIMessageChunk):
            generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning_content

        return generation_chunk


@dataclass(slots=True)
class ThinkTagStreamParser:
    """Split streamed `<think>...</think>` text into reasoning and answer output."""

    phase: str = "initial"
    buffer: str = ""

    def consume(self, text: str) -> tuple[str, str]:
        if not text:
            return "", ""

        self.buffer += text
        reasoning_parts: list[str] = []
        answer_parts: list[str] = []

        while self.buffer:
            if self.phase == "answer":
                answer_parts.append(self.buffer)
                self.buffer = ""
                break

            marker = OPEN_THINK_TAG if self.phase == "initial" else CLOSE_THINK_TAG
            marker_index = self.buffer.find(marker)
            if marker_index >= 0:
                prefix = self.buffer[:marker_index]
                if self.phase == "thinking":
                    reasoning_parts.append(prefix)
                    self.phase = "answer"
                else:
                    answer_parts.append(prefix)
                    self.phase = "thinking"
                self.buffer = self.buffer[marker_index + len(marker) :]
                continue

            hold_back = _partial_tag_suffix_length(self.buffer, marker)
            emit_upto = len(self.buffer) - hold_back
            if emit_upto <= 0:
                break

            safe_text = self.buffer[:emit_upto]
            self.buffer = self.buffer[emit_upto:]
            if self.phase == "thinking":
                reasoning_parts.append(safe_text)
            else:
                answer_parts.append(safe_text)

        return "".join(reasoning_parts), "".join(answer_parts)

    def flush(self) -> tuple[str, str]:
        if not self.buffer:
            return "", ""

        leftover = self.buffer
        self.buffer = ""
        if self.phase == "thinking":
            return leftover, ""
        return "", leftover


def _partial_tag_suffix_length(text: str, marker: str) -> int:
    max_len = min(len(text), len(marker) - 1)
    for size in range(max_len, 0, -1):
        if marker.startswith(text[-size:]):
            return size
    return 0


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
                continue

            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)

        return "".join(text_parts)

    return ""


def _extract_display_segments(chunk: Any, parser: ThinkTagStreamParser) -> tuple[str, str]:
    if isinstance(chunk, tuple):
        reasoning_parts: list[str] = []
        answer_parts: list[str] = []
        for item in chunk:
            reasoning, answer = _extract_display_segments(item, parser)
            if reasoning:
                reasoning_parts.append(reasoning)
            if answer:
                answer_parts.append(answer)
        return "".join(reasoning_parts), "".join(answer_parts)

    if not isinstance(chunk, AIMessageChunk):
        return "", ""

    chunk_reasoning = chunk.additional_kwargs.get("reasoning_content")
    if isinstance(chunk_reasoning, str) and chunk_reasoning:
        return chunk_reasoning, _normalize_message_content(chunk.content)

    chunk_text = _normalize_message_content(chunk.content)
    return parser.consume(chunk_text)


def _print_section_text(*, text: str, title: str, section_started: bool) -> bool:
    if not text:
        return section_started

    if not section_started:
        print("\n" + "=" * 20 + title + "=" * 20)
    print(text, end="", flush=True)
    return True


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def main() -> None:
    debug_clients: DebugHTTPClients | None = None
    model_kwargs: dict[str, Any] = {}
    if _is_truthy_env(os.getenv("OPENAI_DEBUG_HTTP")):
        debug_clients = build_debug_http_clients(emit=logger.info)
        model_kwargs = {
            "http_client": debug_clients.http_client,
            "http_async_client": debug_clients.http_async_client,
        }

    llm = ReasoningChatOpenAI(
        model=os.getenv("OPENAI_MODEL"),
        timeout=300,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        stream_usage=True,
        extra_body={"enable_thinking": True},
        **model_kwargs,
    )

    parser = ThinkTagStreamParser()
    thinking_started = False
    answer_started = False

    try:
        async for chunk in llm.astream([HumanMessage(content="你是谁")]):
            reasoning, answer = _extract_display_segments(chunk, parser)
            thinking_started = _print_section_text(
                text=reasoning,
                title="思考过程",
                section_started=thinking_started,
            )
            answer_started = _print_section_text(
                text=answer,
                title="完整回复",
                section_started=answer_started,
            )

        reasoning, answer = parser.flush()
        thinking_started = _print_section_text(
            text=reasoning,
            title="思考过程",
            section_started=thinking_started,
        )
        answer_started = _print_section_text(
            text=answer,
            title="完整回复",
            section_started=answer_started,
        )

        if thinking_started or answer_started:
            print()
    finally:
        if debug_clients is not None:
            await debug_clients.aclose()


if __name__ == "__main__":
    asyncio.run(main())
