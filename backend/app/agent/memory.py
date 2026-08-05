"""
Investor persona memory — extracts and maintains per-user investor profiles.
Persona stored as both text (for LLM) and vector (for similarity matching).
"""
import asyncio
import json
import logging
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from app.models import User
from app.ingestion.embedder import embed_single
from app.config import get_settings
from app.agent.prompts import PERSONA_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()


def get_llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model="llama-3.1-8b-instant",
        temperature=0,
        max_tokens=300,
    )


async def extract_preferences_from_message(message: str) -> Optional[dict]:
    """Use LLM to extract investor preferences from a chat message."""
    try:
        llm = get_llm()
        prompt = PERSONA_EXTRACTION_PROMPT.format(message=message)
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm.invoke([HumanMessage(content=prompt)]).content,
        )
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            if data.get("no_preferences"):
                return None
            return data
    except Exception as e:
        logger.warning(f"Preference extraction failed: {e}")
    return None


def preferences_to_text(prefs: dict, existing: Optional[str] = None) -> str:
    """Convert extracted preferences to a human-readable persona string."""
    parts = []

    if prefs.get("risk_tolerance"):
        parts.append(f"Risk tolerance: {prefs['risk_tolerance']}")
    if prefs.get("investment_style"):
        parts.append(f"Investment style: {prefs['investment_style']}")
    if prefs.get("dividend_focus"):
        parts.append("Focused on dividend income")
    if prefs.get("avoid_high_debt"):
        parts.append("Avoids high-debt companies")
    if prefs.get("debt_preference") and prefs["debt_preference"] != "any":
        parts.append(f"Prefers {prefs['debt_preference']} debt companies")
    if prefs.get("time_horizon"):
        parts.append(f"Time horizon: {prefs['time_horizon']}-term")
    if prefs.get("sector_preferences"):
        parts.append(f"Prefers sectors: {', '.join(prefs['sector_preferences'])}")
    if prefs.get("sector_avoidances"):
        parts.append(f"Avoids sectors: {', '.join(prefs['sector_avoidances'])}")
    if prefs.get("other_preferences"):
        parts.append(prefs["other_preferences"])

    new_text = ". ".join(parts) + "."
    if existing:
        return f"{existing} Additionally: {new_text}"
    return new_text


async def update_user_persona(user: User, message: str, db: AsyncSession) -> bool:
    """
    Extract preferences from message and update user's persona vector + text.
    Returns True if persona was updated.
    """
    prefs = await extract_preferences_from_message(message)
    if not prefs:
        return False

    new_text = preferences_to_text(prefs, user.persona_text)
    new_vec = await asyncio.get_event_loop().run_in_executor(
        None, embed_single, new_text
    )

    user.persona_text = new_text
    user.persona_vec = new_vec

    logger.info(f"Updated persona for user {user.id}: {new_text[:100]}")
    return True


def extract_persona_filters(persona_text: Optional[str]) -> dict:
    """
    Parse persona text into filter rules for algorithmic stock screening.
    This is pure logic — no LLM involved.
    """
    if not persona_text:
        return {}

    text_lower = persona_text.lower()
    filters = {}

    # Debt preference
    if "avoid high-debt" in text_lower or "avoids high-debt" in text_lower or "low debt" in text_lower:
        filters["max_debt_to_equity"] = 1.0  # D/E < 1x
    elif "medium debt" in text_lower:
        filters["max_debt_to_equity"] = 2.0

    # Dividend focus
    if "dividend" in text_lower:
        filters["min_dividend_yield"] = 0.01  # At least 1%

    # PE filter by style
    if "value" in text_lower:
        filters["max_pe"] = 25.0
    elif "growth" in text_lower:
        filters["min_revenue_growth"] = 0.1  # 10%+ growth

    # Risk tolerance
    if "conservative" in text_lower:
        filters["max_beta"] = 1.0
        filters["min_roe"] = 0.10  # 10%+ ROE for quality
    elif "aggressive" in text_lower:
        filters["min_revenue_growth"] = filters.get("min_revenue_growth", 0.15)

    return filters
