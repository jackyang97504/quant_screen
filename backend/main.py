from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

# 日志目录（必须在 logging 之前创建）
os.makedirs('./logs', exist_ok=True)

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('./logs/quant_screen.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

from database import async_engine, AsyncSessionLocal, init_db
from routers import screen, pool, history
from scheduler import init_scheduler, scheduler as ap_scheduler
from config import get_settings

settings = get_settings()


class AppContext:
    db_sessionmaker = AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    logger.info("量化选股系统启动...")
    os.makedirs('./logs', exist_ok=True)

    # 初始化数据库表
    try:
        init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    app.ctx = AppContext()
    app.ctx.db_sessionmaker = AsyncSessionLocal

    # 启动定时任务（非阻塞）
    try:
        init_scheduler(app)
    except Exception as e:
        logger.error(f"定时任务启动失败: {e}")

    yield

    # 关闭时
    ap_scheduler.shutdown(wait=False)
    await async_engine.dispose()
    logger.info("量化选股系统关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="量化选股系统",
    description="每日量化选股筛选 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(screen.router)
app.include_router(pool.router)
app.include_router(history.router)


@app.get("/")
async def root():
    return {"message": "量化选股系统 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def health_with_api_prefix():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
