from typing import List, Literal, Optional
from pydantic import BaseModel
from datetime import datetime


class ChatRequest(BaseModel):
    class_id: int
    question: str
    document_ids: List[str]
    creativity_mode: Literal["strict", "expanded"] = "strict"
    detail_level: Literal["brief", "normal", "detailed"] = "normal"


class ChatSaveRequest(BaseModel):
    class_id: int
    question: str
    answer: str
    citations: Optional[List[dict]] = None


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime
    citations: Optional[List[dict]] = None
