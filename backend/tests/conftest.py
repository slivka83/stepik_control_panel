import os
os.environ["ENCRYPTION_KEY"] = "qlH5mDp3kj_nhcS3TKrZqjniP_on0n6eMg9sp8DQ2UQ="
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["STEPIK_CLIENT_ID"] = "test_client_id"
os.environ["STEPIK_CLIENT_SECRET"] = "test_client_secret"
os.environ["STEPIK_REDIRECT_URI"] = "http://localhost:8000/api/auth/callback"

import pytest


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def setup_db():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.database import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
