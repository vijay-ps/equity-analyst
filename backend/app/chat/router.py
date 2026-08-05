import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, ChatMessage
from app.auth.dependencies import get_current_user
from app.agent.graph import run_agent
from app.chat.schemas import ChatMessageIn, ChatMessageOut, ChatHistoryOut, CitationOut

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/send", response_model=ChatMessageOut)
async def send_message(
    req: ChatMessageIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message to the equity analyst agent. Returns cited response."""
    thread_id = req.thread_id or str(uuid.uuid4())

    # Save user message
    user_msg = ChatMessage(
        user_id=user.id,
        thread_id=thread_id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    await db.flush()

    try:
        # Run agent
        response_text, citations, persona_updated = await run_agent(
            message=req.message,
            user=user,
            db=db,
        )
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        response_text = "I encountered an error processing your request. Please try again."
        citations = []
        persona_updated = False

    # Save assistant message
    assistant_msg = ChatMessage(
        user_id=user.id,
        thread_id=thread_id,
        role="assistant",
        content=response_text,
        citations=citations,
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    return ChatMessageOut(
        id=assistant_msg.id,
        role="assistant",
        content=response_text,
        citations=[CitationOut(**c) for c in citations] if citations else None,
        created_at=assistant_msg.created_at,
        thread_id=thread_id,
    )


@router.post("/new")
async def new_thread(user: User = Depends(get_current_user)):
    """Create a new chat thread."""
    return {"thread_id": str(uuid.uuid4())}


@router.get("/history/{thread_id}", response_model=ChatHistoryOut)
async def get_history(
    thread_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user.id, ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()

    return ChatHistoryOut(
        thread_id=thread_id,
        messages=[
            ChatMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=[CitationOut(**c) for c in (m.citations or [])],
                created_at=m.created_at,
                thread_id=thread_id,
            )
            for m in messages
        ],
    )


@router.get("/threads")
async def list_threads(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all chat threads for the user (latest message per thread)."""
    result = await db.execute(
        select(ChatMessage.thread_id, ChatMessage.content, ChatMessage.created_at)
        .where(ChatMessage.user_id == user.id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc())
    )
    rows = result.fetchall()

    # Deduplicate by thread_id (latest only)
    seen = set()
    threads = []
    for row in rows:
        tid = row[0]
        if tid not in seen:
            seen.add(tid)
            threads.append({
                "thread_id": tid,
                "preview": row[1][:80] + "..." if len(row[1]) > 80 else row[1],
                "last_message_at": row[2].isoformat(),
            })

    return threads
