from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import (
    String, Text, Float, Integer, Boolean,
    DateTime, JSON, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database import Base
from app.config import get_settings

settings = get_settings()
EMBEDDING_DIM = settings.embedding_dim


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    # Investor persona
    persona_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    persona_vec: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    followed_stocks: Mapped[list["UserStock"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticker: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    ticker_ns: Mapped[str] = mapped_column(String(60), nullable=False)   # e.g. RELIANCE.NS
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    exchange: Mapped[str] = mapped_column(String(10), default="NSE")
    sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Key fundamentals (INR)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pb_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Rolling sentiment (-1 to +1)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sentiment_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Full fundamentals snapshot
    fundamentals_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    last_ingested: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    followers: Mapped[list["UserStock"]] = relationship(back_populates="stock")
    documents: Mapped[list["Document"]] = relationship(back_populates="stock", cascade="all, delete-orphan")


class UserStock(Base):
    __tablename__ = "user_stocks"
    __table_args__ = (UniqueConstraint("user_id", "stock_id", name="uq_user_stock"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    followed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="followed_stocks")
    stock: Mapped["Stock"] = relationship(back_populates="followers")


class Document(Base):
    """Stores chunked + embedded news articles and fundamentals."""
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("content_hash", "chunk_index", name="uq_doc_chunk"),
        Index("ix_documents_stock_id", "stock_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)

    source_type: Mapped[str] = mapped_column(String(20), nullable=False)   # "news" | "fundamentals"
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # "Economic Times" etc.
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Full content and its chunk
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)   # SHA-256 for dedup
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Vector embedding
    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    # LLM-tagged metadata
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # positive/negative/neutral
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # -1.0 to 1.0
    event_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # earnings/merger/etc
    impact: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)       # high/medium/low
    tickers_mentioned: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationship
    stock: Mapped["Stock"] = relationship(back_populates="documents")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)   # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationship
    user: Mapped["User"] = relationship(back_populates="chat_messages")


class IngestionLock(Base):
    """Advisory locks to prevent concurrent ingestion of the same ticker."""
    __tablename__ = "ingestion_locks"

    ticker: Mapped[str] = mapped_column(String(50), primary_key=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    locked_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SentimentHistory(Base):
    """
    Daily sentiment snapshots per stock for trend charting.
    One row per (stock, date). Upserted each day at market close.
    """
    __tablename__ = "sentiment_history"
    __table_args__ = (
        UniqueConstraint("stock_id", "date", name="uq_sentiment_date"),
        Index("ix_sentiment_stock_date", "stock_id", "date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # date of snapshot

    # Aggregated from documents ingested that day
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # -1 to +1
    positive_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    article_count: Mapped[int] = mapped_column(Integer, default=0)

    # Price snapshot at market close (INR)
    close_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationship
    stock: Mapped["Stock"] = relationship("Stock")
