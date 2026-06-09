import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

DATABASE_URL_ENV_NAME = "SQLALCHEMY_DATABASE_URL"


def get_database_url() -> str:
    database_url = os.getenv(DATABASE_URL_ENV_NAME, "").strip()
    if not database_url:
        raise RuntimeError(f"{DATABASE_URL_ENV_NAME} is required for database access")

    return database_url


@lru_cache
def get_async_engine(database_url: str | None = None) -> AsyncEngine:
    return create_async_engine(
        database_url or get_database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )


@lru_cache
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_async_engine(), expire_on_commit=False, autoflush=False)


async def get_db_session():
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        yield session


def clear_db_connection_cache() -> None:
    get_async_session_factory.cache_clear()
    get_async_engine.cache_clear()
