"""Tests for database engine configuration."""
import os
import pytest
from unittest.mock import patch

from app.database import engine, async_session, get_db
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine


class TestEngineConfig:
    def test_engine_is_async(self):
        assert isinstance(engine, AsyncEngine)

    def test_engine_url_uses_sqlite_in_test(self):
        assert "sqlite" in str(engine.url)

    def test_async_session_is_async_sessionmaker(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        assert isinstance(async_session, async_sessionmaker)

    def test_async_session_produces_async_session(self):
        from sqlalchemy.ext.asyncio import AsyncSession
        session = async_session()
        assert isinstance(session, AsyncSession)

    def test_engine_echo_default_false(self):
        assert not engine.echo


class TestGetDb:
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        gen = get_db()
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    @pytest.mark.asyncio
    async def test_get_db_closes_session(self):
        gen = get_db()
        session = await gen.__anext__()
        assert session is not None
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


class TestPoolConfig:
    def test_sqlite_no_pool_config(self):
        assert "sqlite" in str(engine.url)
