import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.auth.router import router as auth_router
from app.stocks.router import router as stocks_router
from app.chat.router import router as chat_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB tables, pgvector, embedding model, and scheduler."""
    logger.info("Starting up — initialising database...")
    await init_db()

    # Pre-load embedding model to avoid cold start on first request
    from app.ingestion.embedder import get_embedding_model
    import asyncio
    await asyncio.get_event_loop().run_in_executor(None, get_embedding_model)
    logger.info("Embedding model loaded ✓")

    # Start background scheduler (6-hour refresh + daily sentiment snapshot)
    from app.scheduler import start_scheduler
    start_scheduler()

    yield

    # Shutdown scheduler cleanly
    from app.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("Shutting down...")


app = FastAPI(
    title="Indian Equity Analyst API",
    description="RAG-powered personal equity research assistant for NSE/BSE stocks",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(stocks_router)
app.include_router(chat_router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "1.0.0",
    }
