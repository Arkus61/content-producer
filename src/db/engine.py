"""Async SQLAlchemy engine setup."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from .models import Base
from ..config import settings

db_url = settings.database_url
if db_url.startswith("postgresql") and "+" not in db_url.split(":")[0]:
    db_url = "postgresql+asyncpg://" + db_url.split("://")[1] if "://" in db_url else db_url

async_engine = create_async_engine(db_url, echo=settings.debug)

async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session():
    """Yield an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
