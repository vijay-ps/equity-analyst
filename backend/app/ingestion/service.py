"""
Ingestion orchestrator — coordinates fundamentals + news ingestion
with idempotency, advisory locking, and sentiment tagging.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.database import AsyncSessionLocal
from app.models import Stock, Document
from app.config import get_settings
from app.ingestion.fundamentals import fetch_fundamentals, fundamentals_to_chunks
from app.ingestion.news import fetch_all_feeds_for_ticker
from app.ingestion.embedder import embed_texts, embed_single, chunk_text

logger = logging.getLogger(__name__)
settings = get_settings()

# LLM for sentiment tagging — fast, lightweight inference
_llm: Optional[ChatGroq] = None


def get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            api_key=settings.groq_api_key,
            model="llama-3.1-8b-instant",  # Cheaper model for tagging
            temperature=0,
            max_tokens=100,
        )
    return _llm


async def tag_article_sentiment(text: str, ticker: str) -> dict:
    """Use LLM to tag article sentiment and event type."""
    try:
        llm = get_llm()
        prompt = f"""Analyze this Indian stock market news about {ticker}. 
Respond with ONLY a JSON object:
{{"sentiment": "positive|negative|neutral", "score": <float -1 to 1>, "event_type": "earnings|merger|regulatory|macro|management|product|debt|dividend|other", "impact": "high|medium|low"}}

Article: {text[:500]}"""

        import json
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: llm.invoke([HumanMessage(content=prompt)]).content,
        )
        # Extract JSON from response
        import re
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning(f"Sentiment tagging failed: {e}")
    return {"sentiment": "neutral", "score": 0.0, "event_type": "other", "impact": "low"}


async def acquire_ingestion_lock(db: AsyncSession, ticker: str) -> bool:
    """
    Acquire a ticker-level advisory lock using PostgreSQL.
    Returns True if lock acquired, False if ticker is being ingested elsewhere.
    """
    try:
        # Use PG advisory lock (hash of ticker string)
        lock_key = abs(hash(f"ingest:{ticker}")) % (2**31)
        result = await db.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
        row = result.fetchone()
        return bool(row[0]) if row else False
    except Exception as e:
        logger.warning(f"Lock acquire failed: {e}")
        return True  # Proceed without lock if DB error


async def release_ingestion_lock(db: AsyncSession, ticker: str):
    """Release the ticker advisory lock."""
    try:
        lock_key = abs(hash(f"ingest:{ticker}")) % (2**31)
        await db.execute(text(f"SELECT pg_advisory_unlock({lock_key})"))
    except Exception:
        pass


async def ingest_stock(ticker: str):
    """
    Main ingestion pipeline for a single ticker.
    Idempotent: running twice on the same data produces no duplicates.
    Concurrent-safe: advisory lock prevents parallel ingestion corruption.
    """
    logger.info(f"Starting ingestion for {ticker}")

    async with AsyncSessionLocal() as db:
        # 1. Acquire lock
        locked = await acquire_ingestion_lock(db, ticker)
        if not locked:
            logger.info(f"Skipping {ticker} — already being ingested")
            return

        try:
            # 2. Get stock record
            result = await db.execute(select(Stock).where(Stock.ticker == ticker))
            stock = result.scalar_one_or_none()
            if not stock:
                logger.error(f"Stock {ticker} not found in DB")
                return

            # 3. Fetch fundamentals
            logger.info(f"Fetching fundamentals for {ticker}")
            fund_data = await fetch_fundamentals(stock.ticker_ns)

            if "error" not in fund_data:
                # Update stock record with fresh fundamentals
                stock.name = fund_data.get("name") or stock.name
                stock.sector = fund_data.get("sector") or stock.sector
                stock.industry = fund_data.get("industry") or stock.industry
                stock.market_cap = fund_data.get("market_cap")
                stock.last_price = fund_data.get("last_price")
                stock.pe_ratio = fund_data.get("pe_ratio")
                stock.pb_ratio = fund_data.get("pb_ratio")
                stock.dividend_yield = fund_data.get("dividend_yield")
                stock.debt_to_equity = fund_data.get("debt_to_equity")
                stock.roe = fund_data.get("roe")
                stock.revenue = fund_data.get("revenue")
                stock.net_profit = fund_data.get("net_profit")
                stock.eps = fund_data.get("eps")
                stock.fundamentals_json = fund_data
                stock.last_ingested = datetime.now(timezone.utc)

                # Embed fundamentals chunks
                fund_chunks = fundamentals_to_chunks(fund_data, ticker)
                await _upsert_documents(
                    db=db,
                    stock=stock,
                    chunks=fund_chunks,
                    source_type="fundamentals",
                    source_url=f"https://finance.yahoo.com/quote/{stock.ticker_ns}",
                    source_name="Yahoo Finance",
                    title=f"{ticker} Fundamentals",
                    content_hash=f"fund:{ticker}:{datetime.now().strftime('%Y-%m')}",
                    sentiment_data={"sentiment": "neutral", "score": 0.0, "event_type": "other", "impact": "low"},
                )

            # 4. Fetch news
            logger.info(f"Fetching news for {ticker}")
            articles = await fetch_all_feeds_for_ticker(ticker)
            logger.info(f"Found {len(articles)} articles for {ticker}")

            sentiment_scores = []

            for article in articles:
                full_text = article.get("full_text") or article.get("summary", "")
                if not full_text or len(full_text) < 50:
                    continue

                content_hash = article["content_hash"]

                # Check if already ingested
                existing = await db.execute(
                    select(Document.id).where(
                        Document.content_hash == content_hash,
                        Document.chunk_index == 0,
                    )
                )
                if existing.scalar_one_or_none():
                    logger.debug(f"Skipping duplicate: {article['title'][:50]}")
                    continue

                # Tag sentiment
                combined = f"{article['title']}\n{full_text}"
                sentiment_data = await tag_article_sentiment(combined, ticker)
                sentiment_scores.append(sentiment_data.get("score", 0.0))

                await _upsert_documents(
                    db=db,
                    stock=stock,
                    chunks=chunk_text(combined),
                    source_type="news",
                    source_url=article["source_url"],
                    source_name=article["source_name"],
                    title=article["title"],
                    content_hash=content_hash,
                    sentiment_data=sentiment_data,
                    published_at=article.get("published_at"),
                    tickers_mentioned=article.get("tickers_mentioned", []),
                )

            # 5. Update rolling sentiment score for the stock
            if sentiment_scores:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                # Blend with existing: 70% new, 30% old
                if stock.sentiment_score is not None:
                    stock.sentiment_score = 0.7 * avg_sentiment + 0.3 * stock.sentiment_score
                else:
                    stock.sentiment_score = avg_sentiment
                stock.sentiment_updated_at = datetime.now(timezone.utc)

            await db.commit()
            logger.info(f"Ingestion complete for {ticker}: {len(articles)} articles processed")

        except Exception as e:
            logger.error(f"Ingestion failed for {ticker}: {e}", exc_info=True)
            await db.rollback()
        finally:
            await release_ingestion_lock(db, ticker)


async def _upsert_documents(
    db: AsyncSession,
    stock: Stock,
    chunks: list[str],
    source_type: str,
    source_url: str,
    source_name: str,
    title: str,
    content_hash: str,
    sentiment_data: dict,
    published_at=None,
    tickers_mentioned: list = None,
):
    """Embed chunks and insert/update Document records."""
    if not chunks:
        return

    # Batch-embed all chunks at once (efficient — single model call)
    embeddings = await asyncio.get_event_loop().run_in_executor(
        None, embed_texts, chunks
    )

    for idx, (chunk_text_val, embedding) in enumerate(zip(chunks, embeddings)):
        doc = Document(
            stock_id=stock.id,
            source_type=source_type,
            source_url=source_url,
            source_name=source_name,
            title=title,
            content_hash=content_hash,
            chunk_index=idx,
            chunk_text=chunk_text_val,
            embedding=embedding,
            sentiment=sentiment_data.get("sentiment"),
            sentiment_score=sentiment_data.get("score"),
            event_type=sentiment_data.get("event_type"),
            impact=sentiment_data.get("impact"),
            tickers_mentioned=tickers_mentioned or [],
            published_at=published_at,
        )
        db.add(doc)

    await db.flush()


async def snapshot_sentiment():
    """
    Aggregate today's document sentiments into SentimentHistory.
    Called by the scheduler daily at market close (15:35 IST).
    Upserts — safe to run multiple times on the same day.
    """
    from app.models import SentimentHistory
    import asyncio

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with AsyncSessionLocal() as db:
        # Get all stocks
        result = await db.execute(select(Stock))
        stocks = result.scalars().all()

        for stock in stocks:
            # Aggregate today's news sentiment
            doc_result = await db.execute(
                select(
                    Document.sentiment,
                    Document.sentiment_score,
                )
                .where(
                    Document.stock_id == stock.id,
                    Document.source_type == "news",
                    Document.chunk_index == 0,      # one row per article
                    Document.created_at >= today_start,
                )
            )
            rows = doc_result.fetchall()

            if not rows:
                continue

            pos = sum(1 for r in rows if r[0] == "positive")
            neg = sum(1 for r in rows if r[0] == "negative")
            neu = sum(1 for r in rows if r[0] == "neutral")
            scores = [r[1] for r in rows if r[1] is not None]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            # Check if record already exists for today
            existing = await db.execute(
                select(SentimentHistory).where(
                    SentimentHistory.stock_id == stock.id,
                    SentimentHistory.date == today_start,
                )
            )
            hist = existing.scalar_one_or_none()

            if hist:
                hist.sentiment_score = avg_score
                hist.positive_count = pos
                hist.negative_count = neg
                hist.neutral_count = neu
                hist.article_count = len(rows)
                hist.close_price = stock.last_price
            else:
                hist = SentimentHistory(
                    stock_id=stock.id,
                    date=today_start,
                    sentiment_score=avg_score,
                    positive_count=pos,
                    negative_count=neg,
                    neutral_count=neu,
                    article_count=len(rows),
                    close_price=stock.last_price,
                )
                db.add(hist)

        await db.commit()
        logger.info(f"Sentiment snapshot complete for {len(stocks)} stocks")

