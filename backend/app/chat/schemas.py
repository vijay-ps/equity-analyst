from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ChatMessageIn(BaseModel):
    message: str
    thread_id: Optional[str] = None


class CitationOut(BaseModel):
    index: int
    ticker: str
    title: str
    source: str
    url: Optional[str] = None
    published_at: Optional[str] = None
    sentiment: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[list[CitationOut]] = None
    created_at: datetime
    thread_id: str

    model_config = {"from_attributes": True}


class ChatHistoryOut(BaseModel):
    thread_id: str
    messages: list[ChatMessageOut]
