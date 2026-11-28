"""AI agriculture assistant: grounded answers in Urdu or English (see services/assistant.py)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_assistant
from app.services.assistant import MAX_CHARS, MAX_HISTORY, Assistant

router = APIRouter(tags=["assistant"])

PRIVACY = {
    "en": "When the AI assistant is on, your question is sent to an AI service (Anthropic) to write the answer. "
    "Do not include names, phone numbers or other personal details.",
    "ur": "جب اے آئی اسسٹنٹ آن ہو تو جواب لکھنے کے لیے آپ کا سوال ایک اے آئی سروس (اینتھروپک) کو بھیجا جاتا ہے۔ "
    "نام، فون نمبر یا دوسری ذاتی معلومات نہ لکھیں۔",
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_CHARS)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=MAX_HISTORY)
    class_id: str | None = Field(None, description="Disease from a scan result, to pin its knowledge first.")

    @field_validator("messages")
    @classmethod
    def last_is_user(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        if messages[-1].role != "user":
            raise ValueError("the last message must come from the user")
        return messages


class RelatedItem(BaseModel):
    kind: str
    id: str
    title: dict[str, str]


class ChatResponse(BaseModel):
    reply: str
    language: Literal["en", "ur"]
    mode: Literal["ai", "knowledge_base"]
    model: str | None = None
    notice: str | None = Field(
        None, description="ai_not_configured | ai_unavailable (knowledge-base mode only)"
    )
    related: list[RelatedItem] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    disclaimer: str = "General guidance only, not a diagnosis. Please consult an agriculture expert."


@router.get("/assistant/status")
def status(assistant: Assistant = Depends(get_assistant)) -> dict:
    return {
        "ai_available": assistant.config.ai_available,
        "model": assistant.config.model if assistant.config.ai_available else None,
        "privacy": PRIVACY,
    }


@router.post("/assistant/chat", response_model=ChatResponse)
def chat(body: ChatRequest, assistant: Assistant = Depends(get_assistant)) -> ChatResponse:
    """Answer the farmer's latest message. Without an AI credential, verified knowledge-base passages are returned."""
    result = assistant.answer([m.model_dump() for m in body.messages], class_id=body.class_id)
    return ChatResponse(**result)
