"""
RAG Chat Proxy – Backend router
Forwards /rag/chat (SSE stream) and /rag/chat/history to AI Service.
Frontend talks to Backend; Backend forwards with the internal callback secret.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG"])

_AI_BASE = settings.AI_SERVICE_URL.rstrip("/") + "/api/v1/rag"


def _ai_headers(token: str) -> dict:
    """Headers passed to AI Service: Backend JWT for auth + callback secret."""
    return {
        "Authorization": f"Bearer {token}",
        "X-Callback-Secret": settings.AI_SERVICE_SECRET,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# POST /rag/chat  – streaming proxy
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    class_id: int
    question: str
    document_ids: list[str]


@router.post("/chat")
async def proxy_chat(
    body: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Proxy SSE stream from AI Service back to the browser.
    Re-uses the user's JWT from the Authorization header.
    """
    # Forward the original Bearer token to AI Service so it can decode user_id
    auth_header = request.headers.get("Authorization", "")

    async def _stream() -> AsyncGenerator[bytes, None]:
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{_AI_BASE}/chat",
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                    },
                    json=body.model_dump(),
                ) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        logger.error(f"AI Service error {resp.status_code}: {error_text}")
                        yield f"data: [ERROR] AI Service returned {resp.status_code}\n\n".encode()
                        yield b"data: [DONE]\n\n"
                        return
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            except Exception as e:
                logger.error(f"Proxy stream error: {e}")
                yield f"data: [ERROR] {e}\n\n".encode()
                yield b"data: [DONE]\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /rag/chat/history
# ---------------------------------------------------------------------------

@router.get("/chat/history")
async def proxy_history(
    class_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    auth_header = request.headers.get("Authorization", "")
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{_AI_BASE}/chat/history",
                params={"class_id": class_id},
                headers={"Authorization": auth_header},
            )
            return resp.json()
        except Exception as e:
            logger.error(f"History proxy error: {e}")
            raise HTTPException(status_code=502, detail="Could not reach AI Service")


# ---------------------------------------------------------------------------
# DELETE /rag/chat/history
# ---------------------------------------------------------------------------

@router.delete("/chat/history")
async def proxy_clear_history(
    class_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    auth_header = request.headers.get("Authorization", "")
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.delete(
                f"{_AI_BASE}/chat/history",
                params={"class_id": class_id},
                headers={"Authorization": auth_header},
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Clear history proxy error: {e}")
            raise HTTPException(status_code=502, detail="Could not reach AI Service")
