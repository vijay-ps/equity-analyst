"""
Scheduled ingestion — APScheduler-based background job runner.
Runs every 6 hours to refresh news + prices for all followed stocks.
Uses AsyncIOScheduler so it integrates with FastAPI's event loop.
"""
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Stock, UserStock
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def refresh_all_followed_stocks():
    """
    Periodic job: ingest fresh news + fundamentals for every
    stock that at least one user is following.
    Runs idempotently — duplicate articles are skipped by content hash.
    """
    logger.info("⏰ Scheduled refresh starting...")

    async with AsyncSessionLocal() as db:
        # Get all unique stocks that have at least one follower
        result = await db.execute(
            select(Stock.ticker)
            .join(UserStock, Stock.id == UserStock.stock_id)
            .distinct()
        )
        tickers = [row[0] for row in result.fetchall()]

    if not tickers:
        logger.info("No followed stocks — skipping refresh")
        return

    logger.info(f"Refreshing {len(tickers)} stocks: {', '.join(tickers)}")

    from app.ingestion.service import ingest_stock

    # Ingest up to 3 stocks concurrently (avoid hammering external APIs)
    sem = asyncio.Semaphore(3)

    async def ingest_with_sem(ticker: str):
        async with sem:
            try:
                await ingest_stock(ticker)
                logger.info(f"✅ Refreshed {ticker}")
            except Exception as e:
                logger.error(f"❌ Failed to refresh {ticker}: {e}")

    await asyncio.gather(*[ingest_with_sem(t) for t in tickers])
    logger.info(f"⏰ Scheduled refresh complete — {len(tickers)} stocks processed")


async def record_daily_sentiment():
    """
    Snapshot today's sentiment scores into sentiment_history table.
    Called daily at market close (15:30 IST).
    """
    logger.info("📊 Recording daily sentiment snapshots...")
    from app.ingestion.service import snapshot_sentiment
    await snapshot_sentiment()


def start_scheduler():
    """Register all jobs and start the scheduler."""

    # News + fundamentals refresh — every 6 hours
    scheduler.add_job(
        refresh_all_followed_stocks,
        trigger=IntervalTrigger(hours=settings.news_refresh_hours),
        id="refresh_all_stocks",
        name="Refresh all followed stocks",
        replace_existing=True,
        misfire_grace_time=300,  # 5-min grace if server was down
    )

    # Daily sentiment snapshot — every day at 15:35 IST (market close)
    scheduler.add_job(
        record_daily_sentiment,
        trigger="cron",
        hour=15,
        minute=35,
        timezone="Asia/Kolkata",
        id="daily_sentiment_snapshot",
        name="Daily sentiment snapshot",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        f"✅ Scheduler started — refresh every {settings.news_refresh_hours}h, "
        "daily sentiment snapshot at 15:35 IST"
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
