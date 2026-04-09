import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repository import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["DB_PATH"] = str(db_path)
    database = Database()
    # Override engine to use tmp path
    database.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    database.session_factory = async_sessionmaker(database.engine, expire_on_commit=False)
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_log_prompt(db):
    entry = await db.log_prompt(
        user_id=123,
        username="testuser",
        model="test-model",
        prompt="Hello",
        response="Hi there!",
        tokens_used=10,
    )
    assert entry.id is not None
    assert entry.user_id == 123
    assert entry.prompt == "Hello"
    assert entry.response == "Hi there!"


@pytest.mark.asyncio
async def test_get_stats(db):
    await db.log_prompt(123, "user1", "model-a", "q1", "a1", 5)
    await db.log_prompt(123, "user1", "model-a", "q2", "a2", 5)
    await db.log_prompt(123, "user1", "model-b", "q3", "a3", 5)
    await db.log_prompt(456, "user2", "model-a", "q4", "a4", 5)

    stats = await db.get_stats(user_id=123)
    assert stats["total_prompts"] == 3
    assert stats["by_model"]["model-a"] == 2
    assert stats["by_model"]["model-b"] == 1

    all_stats = await db.get_stats()
    assert all_stats["total_prompts"] == 4


@pytest.mark.asyncio
async def test_get_recent_prompts(db):
    for i in range(5):
        await db.log_prompt(123, "user1", "model", f"q{i}", f"a{i}", 1)

    recent = await db.get_recent_prompts(user_id=123, limit=3)
    assert len(recent) == 3
