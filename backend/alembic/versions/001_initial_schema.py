"""Initial database schema migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-05 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('picture', sa.Text(), nullable=True),
        sa.Column('google_id', sa.String(length=255), nullable=True),
        sa.Column('persona_text', sa.Text(), nullable=True),
        sa.Column('persona_vec', Vector(dim=384), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 3. Stocks table
    op.create_table(
        'stocks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('ticker_ns', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('exchange', sa.String(length=10), nullable=False, server_default='NSE'),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('market_cap', sa.Float(), nullable=True),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('pe_ratio', sa.Float(), nullable=True),
        sa.Column('pb_ratio', sa.Float(), nullable=True),
        sa.Column('dividend_yield', sa.Float(), nullable=True),
        sa.Column('debt_to_equity', sa.Float(), nullable=True),
        sa.Column('roe', sa.Float(), nullable=True),
        sa.Column('revenue', sa.Float(), nullable=True),
        sa.Column('net_profit', sa.Float(), nullable=True),
        sa.Column('eps', sa.Float(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fundamentals_json', sa.JSON(), nullable=True),
        sa.Column('last_ingested', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker')
    )
    op.create_index('ix_stocks_ticker', 'stocks', ['ticker'], unique=True)

    # 4. UserStock watchlist table
    op.create_table(
        'user_stocks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('stock_id', sa.String(length=36), nullable=False),
        sa.Column('followed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'stock_id', name='uq_user_stock')
    )

    # 5. Documents table (RAG vector store)
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('stock_id', sa.String(length=36), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('source_name', sa.String(length=100), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(dim=384), nullable=True),
        sa.Column('sentiment', sa.String(length=20), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=True),
        sa.Column('impact', sa.String(length=20), nullable=True),
        sa.Column('tickers_mentioned', sa.JSON(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_hash', 'chunk_index', name='uq_doc_chunk')
    )
    op.create_index('ix_documents_stock_id', 'documents', ['stock_id'])

    # 6. ChatMessages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('citations', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_thread_id', 'chat_messages', ['thread_id'])

    # 7. IngestionLocks table
    op.create_table(
        'ingestion_locks',
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('locked_by', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('ticker')
    )

    # 8. SentimentHistory table
    op.create_table(
        'sentiment_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('stock_id', sa.String(length=36), nullable=False),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('positive_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('negative_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('neutral_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('close_price', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_id', 'date', name='uq_sentiment_date')
    )
    op.create_index('ix_sentiment_stock_date', 'sentiment_history', ['stock_id', 'date'])


def downgrade() -> None:
    op.drop_table('sentiment_history')
    op.drop_table('ingestion_locks')
    op.drop_table('chat_messages')
    op.drop_table('documents')
    op.drop_table('user_stocks')
    op.drop_table('stocks')
    op.drop_table('users')
