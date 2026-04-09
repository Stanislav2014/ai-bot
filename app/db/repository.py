from pathlib import Path

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base, PromptLog

logger = structlog.get_logger()


class Database:
    def __init__(self) -> None:
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_initialized", path=settings.db_path)

    async def close(self) -> None:
        await self.engine.dispose()

    async def log_prompt(
        self,
        user_id: int,
        username: str | None,
        model: str,
        prompt: str,
        response: str | None,
        tokens_used: int | None,
    ) -> PromptLog:
        async with self.session_factory() as session:
            entry = PromptLog(
                user_id=user_id,
                username=username,
                model=model,
                prompt=prompt,
                response=response,
                tokens_used=tokens_used,
            )
            session.add(entry)
            await session.commit()
            logger.info(
                "prompt_logged",
                user_id=user_id,
                username=username,
                model=model,
                prompt_length=len(prompt),
            )
            return entry

    async def get_stats(self, user_id: int | None = None) -> dict:
        async with self.session_factory() as session:
            query = select(func.count(PromptLog.id))
            if user_id is not None:
                query = query.where(PromptLog.user_id == user_id)
            total = (await session.execute(query)).scalar() or 0

            model_query = select(
                PromptLog.model, func.count(PromptLog.id)
            ).group_by(PromptLog.model)
            if user_id is not None:
                model_query = model_query.where(PromptLog.user_id == user_id)
            model_rows = (await session.execute(model_query)).all()

            return {
                "total_prompts": total,
                "by_model": {row[0]: row[1] for row in model_rows},
            }

    async def get_recent_prompts(
        self, user_id: int, limit: int = 20
    ) -> list[PromptLog]:
        async with self.session_factory() as session:
            query = (
                select(PromptLog)
                .where(PromptLog.user_id == user_id)
                .order_by(PromptLog.created_at.desc())
                .limit(limit)
            )
            result = await session.execute(query)
            return list(result.scalars().all())
