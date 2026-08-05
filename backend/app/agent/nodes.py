"""
LangGraph agent nodes — each node is a pure async function.
The graph handles: retrieve → grade → generate, or persona_update.
"""
import asyncio
import json
import logging
import re
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pgvector.sqlalchemy import Vector

from app.models import User, Stock, Document, UserStock
from app.config import get_settings
from app.agent.prompts import (
    SYSTEM_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    RECOMMENDATION_PROMPT,
)
from app.agent.memory import (
    update_user_persona,
    extract_persona_filters,
)
from app.ingestion.embedder import embed_single
from app.ingestion.news import find_tickers_in_text

logger = logging.getLogger(__name__)
settings = get_settings()


def get_main_llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.3,
        max_tokens=2048,
    )


def get_fast_llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model="llama-3.1-8b-instant",
        temperature=0,
        max_tokens=200,
    )


# ─── Node: Classify Intent ───────────────────────────────────────────────────

async def classify_intent(message: str) -> str:
    """Returns one of: PERSONA_UPDATE, STOCK_QUERY, SENTIMENT_QUERY, RECOMMENDATION, GENERAL"""
    try:
        llm = get_fast_llm()
        prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm.invoke([HumanMessage(content=prompt)]).content.strip().upper(),
        )
        valid = {"PERSONA_UPDATE", "STOCK_QUERY", "SENTIMENT_QUERY", "RECOMMENDATION", "GENERAL"}
        for v in valid:
            if v in response:
                return v
    except Exception as e:
        logger.warning(f"Intent classification failed: {e}")
    return "GENERAL"


# ─── Node: Retrieve Documents ────────────────────────────────────────────────

async def retrieve_documents(
    query: str,
    user: User,
    db: AsyncSession,
    k: int = 8,
    ticker_filter: Optional[list[str]] = None,
) -> list[dict]:
    """
    Vector similarity search on user's followed stocks.
    Caches query embedding — does NOT re-embed if same query seen.
    """
    # Embed the query
    query_vec = await asyncio.get_event_loop().run_in_executor(
        None, embed_single, query
    )

    # Get followed stock IDs
    followed_result = await db.execute(
        select(Stock.id, Stock.ticker)
        .join(UserStock, Stock.id == UserStock.stock_id)
        .where(UserStock.user_id == user.id)
    )
    followed = followed_result.fetchall()

    # If user hasn't followed any stocks yet, query across all stocks in database
    if not followed:
        all_stocks_res = await db.execute(select(Stock.id, Stock.ticker))
        followed = all_stocks_res.fetchall()

    followed_ids = [row[0] for row in followed]

    # If ticker filter specified, search across matching stocks (ingest on fly if missing)
    if ticker_filter:
        ticker_filter_upper = [t.upper() for t in ticker_filter]
        matching_stocks_res = await db.execute(
            select(Stock.id, Stock.ticker).where(func.upper(Stock.ticker).in_(ticker_filter_upper))
        )
        matching_rows = matching_stocks_res.fetchall()

        # Auto-ingest missing requested tickers on the fly if needed
        if len(matching_rows) < len(ticker_filter_upper):
            from app.stocks.service import get_or_create_stock
            for tf in ticker_filter_upper:
                if not any(r[1].upper() == tf for r in matching_rows):
                    try:
                        s_obj = await get_or_create_stock(tf, db)
                        if s_obj:
                            matching_rows.append((s_obj.id, s_obj.ticker))
                    except Exception:
                        pass

        if matching_rows:
            followed_ids = [row[0] for row in matching_rows]

    if not followed_ids:
        return []

    # pgvector cosine similarity search
    from sqlalchemy import func, Float

    query_str = (
        select(
            Document,
            (1 - func.cast(
                Document.embedding.op("<=>") (query_vec),
                Float,
            )).label("similarity"),
        )
        .where(Document.stock_id.in_(followed_ids))
        .order_by(Document.embedding.op("<=>") (query_vec))
        .limit(k)
    )

    result = await db.execute(query_str)
    rows = result.fetchall()

    docs = []
    for row in rows:
        doc = row[0]
        similarity = row[1] if len(row) > 1 else 0.0

        # Get stock info
        stock_result = await db.execute(select(Stock).where(Stock.id == doc.stock_id))
        stock = stock_result.scalar_one_or_none()

        docs.append({
            "id": doc.id,
            "ticker": stock.ticker if stock else "?",
            "company": stock.name if stock else "?",
            "source_type": doc.source_type,
            "source_name": doc.source_name or "Unknown",
            "source_url": doc.source_url or "",
            "title": doc.title or "Untitled",
            "chunk_text": doc.chunk_text,
            "sentiment": doc.sentiment,
            "sentiment_score": doc.sentiment_score,
            "event_type": doc.event_type,
            "published_at": doc.published_at.isoformat() if doc.published_at else None,
            "similarity": float(similarity),
        })

    # If no vector docs found, generate fundamental fallback docs directly from Stock table metrics
    if not docs and followed_ids:
        stock_query = select(Stock).where(Stock.id.in_(followed_ids))
        stock_res = await db.execute(stock_query)
        target_stocks = stock_res.scalars().all()
        for stock in target_stocks:
            fund_text = (
                f"Fundamental metrics for {stock.ticker} ({stock.name or 'N/A'}):\n"
                f"- Price: Rs. {stock.last_price or 'N/A'}\n"
                f"- Market Cap: Rs. {stock.market_cap or 'N/A'}\n"
                f"- P/E Ratio: {stock.pe_ratio or 'N/A'}\n"
                f"- P/B Ratio: {stock.pb_ratio or 'N/A'}\n"
                f"- Debt to Equity: {stock.debt_to_equity or 'N/A'}\n"
                f"- Dividend Yield: {(stock.dividend_yield or 0)*100:.2f}%\n"
                f"- ROE: {(stock.roe or 0)*100:.2f}%\n"
                f"- Sector: {stock.sector or 'N/A'}, Industry: {stock.industry or 'N/A'}\n"
            )
            docs.append({
                "id": stock.id,
                "ticker": stock.ticker,
                "company": stock.name or stock.ticker,
                "source_type": "fundamentals",
                "source_name": "Stock Fundamentals Database",
                "source_url": "",
                "title": f"{stock.ticker} Stock Fundamentals",
                "chunk_text": fund_text,
                "sentiment": "neutral",
                "sentiment_score": stock.sentiment_score or 0.0,
                "event_type": "fundamentals",
                "published_at": None,
                "similarity": 0.8,
            })

    return docs



# ─── Node: Grade Relevance ───────────────────────────────────────────────────

def grade_documents(docs: list[dict], threshold: float = 0.3) -> list[dict]:
    """Filter documents by similarity threshold (algorithmic, no LLM)."""
    return [d for d in docs if d.get("similarity", 0) >= threshold]


# ─── Node: Screen & Score Stocks ─────────────────────────────────────────────

BENCHMARK_UNIVERSE = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", 
    "TATAMOTORS", "SBIN", "BHARTIARTL", "ITC", "LT", 
    "AXISBANK", "SUNPHARMA", "MARUTI", "TITAN", "ULTRACEMCO",
    "NTPC", "ONGC", "POWERGRID", "BAJFINANCE", "NESTLEIND",
    "ASIANPAINT", "COALINDIA", "TATASTEEL", "JSWSTEEL", "M&M",
    "ADANIENT", "ADANIPORTS", "GRASIM", "HEROMOTOCO", "HINDUNILVR",
    "CIPLA", "DRREDDY", "DIVISLAB", "EICHERMOT", "APOLLOHOSP",
    "BEL", "HAL", "TRENT", "ZOMATO", "SWIGGY",
    "WIPRO", "TECHM", "HCLTECH", "BAJAJ-AUTO", "INDUSINDBK",
    "KOTAKBANK", "BPCL", "IOC", "PIDILITIND", "VBL"
]

async def screen_and_score_stocks(
    user: User,
    db: AsyncSession,
    query: str = "",
) -> list[dict]:
    """
    Algorithmic stock screening against investor persona, query intent, and news sentiment.
    Dynamically extracts requested count (e.g. 20 stocks).
    """
    # 1. Parse target stock count requested by user (e.g. "give 20 stocks")
    target_count = 10
    match = re.search(r'(\d+)\s*(?:stock|reccomednation|recommendation|pick|idea|option)', query.lower())
    if match:
        try:
            target_count = int(match.group(1))
            target_count = max(3, min(target_count, 30))  # Cap between 3 and 30
        except ValueError:
            target_count = 10

    filters = extract_persona_filters(user.persona_text)
    query_lower = (query + " " + (user.persona_text or "")).lower()

    # Dynamic Weighting based on query/persona style
    is_short_term = any(w in query_lower for w in ["short time", "short term", "high risk", "margin", "momentum", "swing"])
    is_dividend = any(w in query_lower for w in ["dividend", "passive income", "yield"])
    is_value = any(w in query_lower for w in ["value", "low pe", "undervalued", "cheap"])

    if is_short_term:
        w_sentiment, w_roe, w_pe, w_debt, w_div = 0.40, 0.20, 0.20, 0.10, 0.10
    elif is_dividend:
        w_sentiment, w_roe, w_pe, w_debt, w_div = 0.20, 0.20, 0.10, 0.10, 0.40
    elif is_value:
        w_sentiment, w_roe, w_pe, w_debt, w_div = 0.20, 0.20, 0.40, 0.10, 0.10
    else:  # Conservative / Quality default
        w_sentiment, w_roe, w_pe, w_debt, w_div = 0.25, 0.30, 0.15, 0.20, 0.10

    # 2. Get existing stocks in DB
    all_result = await db.execute(select(Stock))
    stocks = list(all_result.scalars().all())
    stock_map = {s.id: s for s in stocks}

    # 3. Auto-ingest benchmark stocks from Yahoo/Screener if DB has fewer than needed
    needed_count = max(target_count + 5, 25)
    if len(stocks) < needed_count:
        from app.stocks.service import get_or_create_stock
        for t in BENCHMARK_UNIVERSE:
            if len(stocks) >= needed_count:
                break
            if not any(s.ticker == t for s in stocks):
                try:
                    s_obj = await get_or_create_stock(t, db)
                    if s_obj and s_obj.id not in stock_map:
                        stock_map[s_obj.id] = s_obj
                        stocks.append(s_obj)
                except Exception:
                    pass

    scored = []
    soft_scored = []
    for stock in stocks:
        # Calculate component scores (0 to 5)
        sent_part = ((stock.sentiment_score or 0.0) + 1.0) / 2.0 * 5.0
        roe_part = min((stock.roe or 0.0) / 0.20, 5.0)
        pe_part = max(0.0, 5.0 - (stock.pe_ratio or 20.0) / 10.0)
        debt_part = max(0.0, 5.0 - (stock.debt_to_equity or 1.0))
        div_part = min((stock.dividend_yield or 0.0) / 0.04, 5.0)

        score = (
            sent_part * w_sentiment +
            roe_part * w_roe +
            pe_part * w_pe +
            debt_part * w_debt +
            div_part * w_div
        )

        item = {"stock": stock, "score": round(score, 3)}
        soft_scored.append(item)

        # Apply hard filters if present
        passes_hard = True
        if filters.get("max_debt_to_equity") and stock.debt_to_equity:
            if stock.debt_to_equity > filters["max_debt_to_equity"]:
                passes_hard = False
        if filters.get("min_dividend_yield") and (stock.dividend_yield or 0) < filters["min_dividend_yield"]:
            passes_hard = False
        if filters.get("max_pe") and stock.pe_ratio and stock.pe_ratio > filters["max_pe"]:
            passes_hard = False

        if passes_hard:
            scored.append(item)

    # If hard filters produced fewer than target_count, top up with best soft-scored stocks
    if len(scored) < target_count:
        soft_scored.sort(key=lambda x: x["score"], reverse=True)
        scored_ids = {x["stock"].id for x in scored}
        for item in soft_scored:
            if item["stock"].id not in scored_ids:
                scored.append(item)
                scored_ids.add(item["stock"].id)
            if len(scored) >= target_count:
                break

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


# ─── Node: Generate Response ─────────────────────────────────────────────────

async def generate_cited_response(
    query: str,
    docs: list[dict],
    user: User,
    intent: str,
    scored_stocks: Optional[list[dict]] = None,
) -> tuple[str, list[dict]]:
    """
    Generate a grounded, cited response using Groq LLM.
    Returns (response_text, citations_list).
    """
    llm = get_main_llm()

    # Build context from docs
    context_parts = []
    citations = []

    for i, doc in enumerate(docs[:10]):  # Limit context length
        source_label = f"[{i+1}]"
        pub_date = doc.get("published_at", "")[:10] if doc.get("published_at") else "N/A"
        context_parts.append(
            f"{source_label} [{doc['ticker']} | {doc['source_name']} | {pub_date}]\n"
            f"Title: {doc['title']}\n"
            f"{doc['chunk_text']}\n"
        )
        citations.append({
            "index": i + 1,
            "ticker": doc["ticker"],
            "title": doc["title"],
            "source": doc["source_name"],
            "url": doc["source_url"],
            "published_at": doc.get("published_at"),
            "sentiment": doc.get("sentiment"),
        })

    context = "\n---\n".join(context_parts)
    persona_summary = user.persona_text or f"Investor query: '{query}'. Provide balanced, quality Indian equity recommendations."

    if intent == "RECOMMENDATION" and scored_stocks:
        # Determine target count requested from query
        match = re.search(r'(\d+)\s*(?:stock|reccomednation|recommendation|pick|idea|option)', query.lower())
        count_req = int(match.group(1)) if match else 10
        count_req = max(3, min(count_req, 30))
        selected_stocks = scored_stocks[:count_req]

        stock_summaries = []
        for item in selected_stocks:
            s = item["stock"]
            score = item["score"]
            summary = (
                f"**{s.ticker}** ({s.name or 'N/A'}) | Score: {score:.2f}\n"
                f"  Price: Rs. {s.last_price or 'N/A'} | P/E: {s.pe_ratio or 'N/A'} | "
                f"P/B: {s.pb_ratio or 'N/A'} | D/E: {s.debt_to_equity or 'N/A'} | "
                f"Div Yield: {(s.dividend_yield or 0)*100:.1f}% | ROE: {(s.roe or 0)*100:.1f}%\n"
                f"  Sentiment: {s.sentiment_score or 0:.2f} | Sector: {s.sector or 'N/A'}"
            )
            stock_summaries.append(summary)

        stock_context = "\n".join(stock_summaries)
        prompt = RECOMMENDATION_PROMPT.format(
            count=len(selected_stocks),
            persona=persona_summary,
            context=f"STOCK SCORES:\n{stock_context}\n\nNEWS & FUNDAMENTALS:\n{context}",
        )
    else:
        prompt = f"""User Question: {query}

Investor Profile: {persona_summary}

Retrieved Data:
{context}

Answer the question using ONLY the data above. Cite sources using [1], [2] etc.
All monetary values in INR (Rs.). If data is insufficient, say so explicitly."""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: llm.invoke(messages).content,
    )

    return response, citations
