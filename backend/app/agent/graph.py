"""
LangGraph state machine for the equity analyst agent.
Graph: classify → [retrieve|update_persona|screen] → generate
"""
from typing import TypedDict, Optional, Annotated
import operator
import logging

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.agent.nodes import (
    classify_intent,
    retrieve_documents,
    grade_documents,
    screen_and_score_stocks,
    generate_cited_response,
)
from app.agent.memory import update_user_persona
from app.ingestion.news import find_tickers_in_text

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State passed between nodes in the LangGraph."""
    message: str
    user_id: str
    intent: Optional[str]
    tickers_mentioned: list[str]
    retrieved_docs: list[dict]
    graded_docs: list[dict]
    scored_stocks: Optional[list[dict]]
    persona_updated: bool
    response: Optional[str]
    citations: list[dict]


async def run_agent(
    message: str,
    user: User,
    db: AsyncSession,
) -> tuple[str, list[dict], bool]:
    """
    Run the full agent graph for a user message.
    Returns: (response_text, citations, persona_was_updated)
    """
    # Step 1: Classify intent
    intent = await classify_intent(message)
    logger.info(f"Intent: {intent} | Message: {message[:50]}")

    # Step 2: Extract mentioned tickers
    tickers = find_tickers_in_text(message)

    persona_updated = False
    scored_stocks = None
    citations = []
    response = ""

    # Step 3: Always check and update user persona if preferences are mentioned in query
    persona_updated = await update_user_persona(user, message, db)
    if persona_updated:
        await db.flush()

    if intent == "PERSONA_UPDATE":
        # Still retrieve docs to ground the acknowledgement
        docs = await retrieve_documents(message, user, db, k=3)
        graded = grade_documents(docs, threshold=0.25)

        response, citations = await generate_cited_response(
            query=f"Acknowledge the investor preference update and provide any relevant insights: {message}",
            docs=graded,
            user=user,
            intent=intent,
        )
        return response, citations, persona_updated

    # Step 4: Retrieve documents
    docs = await retrieve_documents(
        query=message,
        user=user,
        db=db,
        k=10,
        ticker_filter=tickers if tickers else None,
    )
    graded = grade_documents(docs, threshold=0.25)
    logger.info(f"Retrieved {len(docs)} docs, {len(graded)} after grading")

    # Step 5: Screen stocks for recommendations
    if intent == "RECOMMENDATION":
        scored_stocks = await screen_and_score_stocks(user, db, query=message)

    # Step 6: Generate response
    response, citations = await generate_cited_response(
        query=message,
        docs=graded or docs[:5],  # Fallback to top docs if none graded
        user=user,
        intent=intent,
        scored_stocks=scored_stocks,
    )

    return response, citations, persona_updated
