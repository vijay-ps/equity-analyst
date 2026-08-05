from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from app.models import User
from app.auth.dependencies import get_current_user
from app.stocks.schemas import FollowRequest, FollowResponse, StockOut
from app.stocks import service
from app.auth.schemas import UserOut

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.post("/follow", response_model=FollowResponse)
async def follow_stock(
    req: FollowRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a ticker. Triggers background news + fundamentals ingestion."""
    stock = await service.follow_stock(user, req.ticker, db)
    if not stock:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{req.ticker}' not found on NSE or BSE. Please verify the symbol.",
        )

    # Kick off background ingestion
    from app.ingestion.service import ingest_stock
    background_tasks.add_task(ingest_stock, stock.ticker)

    return FollowResponse(message=f"Now following {stock.ticker}", stock=StockOut.model_validate(stock))


@router.delete("/unfollow/{ticker}")
async def unfollow_stock(
    ticker: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    success = await service.unfollow_stock(user, ticker, db)
    if not success:
        raise HTTPException(status_code=404, detail="Stock not in your watchlist")
    return {"message": f"Unfollowed {ticker.upper()}"}


@router.get("/followed", response_model=list[StockOut])
async def get_followed(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stocks = await service.get_followed_stocks(user, db)
    return [StockOut.model_validate(s) for s in stocks]


@router.get("/search/{query}", response_model=list[dict])
async def search_stocks(query: str):
    """Quick search for NSE/BSE ticker symbols."""
    import yfinance as yf
    try:
        results = yf.Search(query, max_results=10)
        quotes = results.quotes
        indian = [q for q in quotes if q.get("exchange") in ("NSI", "BSE", "NSE")]
        return [{"ticker": q.get("symbol", ""), "name": q.get("longname") or q.get("shortname", "")} for q in indian[:5]]
    except Exception:
        return []


@router.get("/me", response_model=UserOut)
async def get_profile(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.get("/{ticker}/sentiment-history")
async def get_sentiment_history(
    ticker: str,
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return daily sentiment history for a ticker (default last 30 days).
    Used by the frontend sentiment trend chart.
    """
    from datetime import timedelta
    from sqlalchemy import select
    from app.models import Stock, SentimentHistory

    # Verify user follows this stock
    result = await db.execute(select(Stock).where(Stock.ticker == ticker.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    hist_result = await db.execute(
        select(SentimentHistory)
        .where(
            SentimentHistory.stock_id == stock.id,
            SentimentHistory.date >= cutoff,
        )
        .order_by(SentimentHistory.date)
    )
    rows = hist_result.scalars().all()

    return {
        "ticker": stock.ticker,
        "days": days,
        "data": [
            {
                "date": r.date.strftime("%Y-%m-%d"),
                "sentiment_score": round(r.sentiment_score or 0.0, 3),
                "positive_count": r.positive_count,
                "negative_count": r.negative_count,
                "neutral_count": r.neutral_count,
                "article_count": r.article_count,
                "close_price": r.close_price,
            }
            for r in rows
        ],
    }


@router.post("/{ticker}/refresh")
async def manual_refresh(
    ticker: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Manually trigger a fresh ingestion for a ticker."""
    from app.ingestion.service import ingest_stock
    background_tasks.add_task(ingest_stock, ticker.upper())
    return {"message": f"Refresh triggered for {ticker.upper()} — data will update in ~30 seconds"}

