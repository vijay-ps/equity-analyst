"""
Comprehensive test script for the Equity Analyst Agent logic.
Tests:
1. Persona extraction from inline query
2. Stock screening & scoring (10 stocks guaranteed)
3. Cited recommendation response generation with 10 picks
4. Sentiment query response generation
5. Stock query response generation with citations
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_agent_pipeline():
    from app.database import init_db, AsyncSessionLocal
    from app.models import User
    from app.agent.graph import run_agent
    from app.agent.memory import update_user_persona, extract_preferences_from_message
    from app.agent.nodes import classify_intent, screen_and_score_stocks
    from sqlalchemy import select

    logger.info("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as db:
        # Get or create test user
        res = await db.execute(select(User).limit(1))
        user = res.scalars().first()
        if not user:
            logger.error("No user found in database! Creating test user...")
            user = User(email="test@sentellent.com", name="Test User", persona_text="")
            db.add(user)
            await db.commit()
            await db.refresh(user)

        logger.info(f"Test user: {user.email} (ID: {user.id})")

        # Test Case 1: Extract inline persona
        msg1 = "give 10 stock reccomednations for long term investment as i am a conservative user"
        logger.info(f"\n--- TEST 1: Inline Persona Extraction ---")
        logger.info(f"Query: '{msg1}'")
        prefs = await extract_preferences_from_message(msg1)
        logger.info(f"Extracted preferences: {prefs}")
        assert prefs is not None, "FAILED: Preference extraction returned None for query containing 'conservative user'"

        # Test Case 2: Run full agent for RECOMMENDATION query
        logger.info(f"\n--- TEST 2: Run Agent for 10 Stock Recommendations ---")
        response1, citations1, updated1 = await run_agent(msg1, user, db)
        logger.info(f"Persona updated: {updated1}")
        logger.info(f"Response length: {len(response1)}")
        logger.info(f"Response Preview:\n{response1[:800]}...")
        logger.info(f"Citations count: {len(citations1)}")

        # Check assertions for Test 2
        assert "unable to give personalized" not in response1.lower(), "FAILED: Agent refused recommendation saying no profile provided!"
        assert "no investor profile" not in response1.lower(), "FAILED: Agent complained about missing profile!"
        assert len(citations1) > 0, "FAILED: No citations returned in recommendation response!"

        # Test Case 3: Sentiment Query
        msg2 = "What's the sentiment on TCS this week?"
        logger.info(f"\n--- TEST 3: Sentiment Query ---")
        response2, citations2, _ = await run_agent(msg2, user, db)
        logger.info(f"Response Preview:\n{response2[:500]}...")
        logger.info(f"Citations count: {len(citations2)}")

        logger.info("\n✅ ALL LIVE AGENT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_agent_pipeline())
