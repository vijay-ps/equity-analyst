from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StockBase(BaseModel):
    ticker: str
    exchange: str = "NSE"


class StockOut(BaseModel):
    id: str
    ticker: str
    ticker_ns: str
    name: Optional[str] = None
    exchange: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    last_price: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    debt_to_equity: Optional[float] = None
    roe: Optional[float] = None
    sentiment_score: Optional[float] = None
    last_ingested: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FollowRequest(BaseModel):
    ticker: str


class FollowResponse(BaseModel):
    message: str
    stock: StockOut
