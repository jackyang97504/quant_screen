from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine, text
from config import get_settings

settings = get_settings()

# 异步引擎（用于 FastAPI）
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 同步引擎（用于定时任务、初始化）
sync_engine = create_engine(
    settings.database_url_sync,
    echo=False,
    pool_size=5,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db():
    """初始化数据库表（同步调用）"""
    with sync_engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS screen_results (
                id SERIAL PRIMARY KEY,
                trade_date DATE NOT NULL,
                ts_code VARCHAR(10) NOT NULL,
                name VARCHAR(50),
                industry VARCHAR(50),
                score REAL,
                proba REAL,
                top_factor TEXT,
                screening_detail TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(trade_date, ts_code)
            )
        """))
        # 兼容旧库：补齐历史表缺失字段
        conn.execute(text("""
            ALTER TABLE screen_results
            ADD COLUMN IF NOT EXISTS screening_detail TEXT
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_pool (
                id SERIAL PRIMARY KEY,
                ts_code VARCHAR(10) UNIQUE NOT NULL,
                name VARCHAR(50),
                industry VARCHAR(50),
                first_seen DATE,
                last_seen DATE,
                hit_count INTEGER DEFAULT 1,
                days_in_pool INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                ts_code VARCHAR(10),
                action VARCHAR(20),
                operator VARCHAR(20),
                trade_date DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS factor_snapshot (
                id SERIAL PRIMARY KEY,
                trade_date DATE NOT NULL,
                ts_code VARCHAR(10) NOT NULL,
                factor_data JSONB,
                UNIQUE(trade_date, ts_code)
            )
        """))
        # 索引
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_screen_date ON screen_results(trade_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pool_status ON stock_pool(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_factor_date ON factor_snapshot(trade_date)"))
        conn.commit()
