from typing import Optional
import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

from app.models import Stock, UserStock, User
from app.config import get_settings

settings = get_settings()

# Mapping common names → NSE tickers
TICKER_ALIASES = {
    "RELIANCE INDUSTRIES": "RELIANCE",
    "TATA CONSULTANCY": "TCS",
    "HDFC BANK": "HDFCBANK",
    "INFOSYS": "INFY",
}


def normalize_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    return TICKER_ALIASES.get(t, t)


def fetch_yf_info(ticker_ns: str) -> dict:
    """Synchronous yfinance fetch — run in thread pool."""
    try:
        stock = yf.Ticker(ticker_ns)
        info = stock.info
        if not info or info.get("quoteType") is None:
            return {}
        return info
    except Exception:
        return {}


async def get_or_create_stock(
    ticker: str,
    db: AsyncSession,
) -> Optional[Stock]:
    """
    Fetch or create a Stock record.
    Returns None if ticker doesn't exist on NSE/BSE.
    """
    ticker_clean = normalize_ticker(ticker)
    ticker_ns = f"{ticker_clean}.NS"

    # Check if already exists
    result = await db.execute(select(Stock).where(Stock.ticker == ticker_clean))
    stock = result.scalar_one_or_none()

    if not stock:
        # Validate by fetching from yfinance (in thread pool to avoid blocking)
        info = await asyncio.get_event_loop().run_in_executor(
            None, fetch_yf_info, ticker_ns
        )
        if not info:
            # Try BSE
            ticker_bo = f"{ticker_clean}.BO"
            info = await asyncio.get_event_loop().run_in_executor(
                None, fetch_yf_info, ticker_bo
            )
            if not info:
                return None
            ticker_ns = ticker_bo
            exchange = "BSE"
        else:
            exchange = "NSE"

        stock = Stock(
            ticker=ticker_clean,
            ticker_ns=ticker_ns,
            name=info.get("longName") or info.get("shortName") or ticker_clean,
            exchange=exchange,
            sector=info.get("sector"),
            industry=info.get("industry"),
            market_cap=info.get("marketCap"),
            last_price=info.get("currentPrice") or info.get("regularMarketPrice"),
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
            dividend_yield=info.get("dividendYield"),
            debt_to_equity=info.get("debtToEquity"),
            roe=info.get("returnOnEquity"),
            fundamentals_json=info,
        )
        db.add(stock)
        await db.flush()
        await db.refresh(stock)

    return stock


async def follow_stock(user: User, ticker: str, db: AsyncSession) -> Optional[Stock]:
    """Follow a stock ticker. Triggers background ingestion."""
    stock = await get_or_create_stock(ticker, db)
    if not stock:
        return None

    # Check not already followed
    result = await db.execute(
        select(UserStock).where(
            UserStock.user_id == user.id,
            UserStock.stock_id == stock.id,
        )
    )
    if not result.scalar_one_or_none():
        user_stock = UserStock(user_id=user.id, stock_id=stock.id)
        db.add(user_stock)
        await db.flush()

    # Trigger background news ingestion with advisory lock
    from app.ingestion.news import acquire_ticker_advisory_lock, release_ticker_advisory_lock, fetch_all_feeds_for_ticker
    from app.ingestion.embedder import embed_documents
    from app.ingestion.chunker import chunk_text
    from app.models import Document

    async def _ingest_news_bg():
        try:
            got_lock = await acquire_ticker_advisory_lock(stock.ticker, db)
            if not got_lock:
                return
            articles = await fetch_all_feeds_for_ticker(stock.ticker)
            if not articles:
                return
            
            # Write news chunks to database
            for art in articles[:10]:
                content_text = art.get("full_text") or art.get("summary") or art.get("title")
                chunks = chunk_text(content_text, chunk_size=500, overlap=50)
                if not chunks:
                    continue
                
                # Check hash for deduplication
                existing = await db.execute(
                    select(Document).where(Document.content_hash == art["content_hash"])
                )
                if existing.scalar_one_or_none():
                    continue

                for c in chunks:
                    doc = Document(
                        stock_id=stock.id,
                        source_type="rss",
                        source_name=art["source_name"],
                        source_url=art["source_url"],
                        title=art["title"],
                        chunk_text=c,
                        content_hash=art["content_hash"],
                        published_at=art.get("published_at"),
                    )
                    db.add(doc)
            await db.commit()
        except Exception:
            pass
        finally:
            await release_ticker_advisory_lock(stock.ticker, db)

    asyncio.create_task(_ingest_news_bg())
    return stock


async def unfollow_stock(user: User, ticker: str, db: AsyncSession) -> bool:
    ticker_clean = normalize_ticker(ticker)
    result = await db.execute(
        select(UserStock)
        .join(Stock, UserStock.stock_id == Stock.id)
        .where(UserStock.user_id == user.id, Stock.ticker == ticker_clean)
    )
    user_stock = result.scalar_one_or_none()
    if user_stock:
        await db.delete(user_stock)
        await db.flush()
        return True
    return False


async def get_followed_stocks(user: User, db: AsyncSession) -> list[Stock]:
    result = await db.execute(
        select(Stock)
        .join(UserStock, Stock.id == UserStock.stock_id)
        .where(UserStock.user_id == user.id)
    )
    return list(result.scalars().all())
