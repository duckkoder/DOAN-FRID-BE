import logging
from typing import AsyncGenerator, List

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG"])

_AI_BASE = settings.AI_SERVICE_URL.rstrip("/") + "/api/v1/rag"

# ---------------------------------------------------------------------------
# POST /rag/chat  – streaming proxy
# ---------------------------------------------------------------------------
from app.schemas.rag_schema import ChatRequest, ChatSaveRequest, ChatMessageResponse
from app.services.rag_service import RAGService
from app.services.document_service import DocumentService


@router.post("/chat")
async def proxy_chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Proxy SSE stream from AI Service back to the browser.
    """
    validated_document_ids = DocumentService.validate_rag_documents(
        db=db,
        current_user=current_user,
        class_id=body.class_id,
        document_ids=body.document_ids,
    )
    ai_payload = body.model_dump()
    ai_payload["document_ids"] = validated_document_ids

    async def _stream() -> AsyncGenerator[bytes, None]:
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{_AI_BASE}/chat",
                    headers={
                        "Content-Type": "application/json",
                    },
                    json=ai_payload,
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
# POST /rag/chat/save – Save chat history to Backend DB
# ---------------------------------------------------------------------------

@router.post("/chat/save")
async def save_chat_message(
    body: ChatSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a question-answer pair to the database."""
    session_id = RAGService.save_chat_message(db, current_user, body)
    return {"success": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# GET /rag/chat/history
# ---------------------------------------------------------------------------

@router.get("/chat/history", response_model=List[ChatMessageResponse])
async def get_chat_history(
    class_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chat history from Backend DB."""
    return RAGService.get_chat_history(db, current_user, class_id, limit)


# ---------------------------------------------------------------------------
# DELETE /rag/chat/history
# ---------------------------------------------------------------------------

@router.delete("/chat/history")
async def clear_chat_history(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear history by deleting the session."""
    RAGService.clear_chat_history(db, current_user, class_id)
    return {"success": True}
