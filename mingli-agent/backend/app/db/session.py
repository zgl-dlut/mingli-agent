from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_recycle=1800,     # 30分钟回收连接，小于MySQL默认wait_timeout=28800(8h)
    pool_pre_ping=True,    # 每次使用前ping，断连自动重连
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
