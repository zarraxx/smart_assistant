from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    title: str | None = Field(default=None, description="Session title")
    expire_seconds: int | None = Field(default=None, ge=1, description="Session TTL in seconds")
    client_capabilities: list[str] = Field(default_factory=list, description="Client capability list")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata")

    @field_validator("client_capabilities")
    @classmethod
    def normalize_client_capabilities(cls, value: list[str]) -> list[str]:
        normalized_capabilities: list[str] = []
        seen_capabilities: set[str] = set()

        for capability in value:
            normalized_capability = capability.strip()
            if not normalized_capability or normalized_capability in seen_capabilities:
                continue

            normalized_capabilities.append(normalized_capability)
            seen_capabilities.add(normalized_capability)

        return normalized_capabilities


class CreateChatResponseData(BaseModel):
    session_id: str
    user_id: str
    title: str | None = None
    expire_seconds: int
    client_capabilities: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class CreateChatResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: CreateChatResponseData


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, description="Chat session id")
    inputs: dict[str, Any] = Field(default_factory=dict, description="App variable input")
    query: str = Field(..., min_length=1, description="User query")
    user: str = Field(..., min_length=1, description="User identifier")
    response_mode: Literal["blocking", "streaming"] = Field(
        default="streaming",
        description="Response mode",
    )
    files: list[dict[str, Any]] | None = Field(default=None, description="Uploaded file list")
    auto_generate_name: bool | None = Field(default=None, description="Whether to auto-generate a title")
