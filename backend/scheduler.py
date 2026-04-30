from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
import logging
import pandas as pd

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def create_screen_task(app):
    """创建筛选任务的工厂函数（避免循环导入）"""
    async def morning_screen():
        logger.info("========== 盘中筛选任务启动 (09:35) ==========")
        async with app.ctx.db_sessionmaker() as session:
            from services.pool_manager import PoolManager
            from services.data_fetcher import DataFetcher
            from services.factor_engine import FactorEngine
            from services.predictor import StockPredictor
            from config import get_settings

            settings = get_settings()
            fetcher = DataFetcher(settings.tushare_token)
            predictor = StockPredictor(settings.model_path)
            pm = PoolManager(session)

            today = datetime.now().strftime('%Y%m%d')
            prev_date = fetcher.get_previous_trade_date(today)
            logger.info(f"使用昨日数据: {prev_date}")

            try:
                daily_df = fetcher.get_market_daily(prev_date)

                if settings.exclude_st:
                    daily_df = daily_df[~daily_df['name'].str.contains('ST', na=False)]
                if settings.exclude_limit_up:
                    daily_df = daily_df[daily_df['pct_chg'] < 9.5]
                if settings.exclude_limit_down:
                    daily_df = daily_df[daily_df['pct_chg'] > -9.5]

                daily_df['return_5d'] = daily_df['pct_chg'] * 0.5
                daily_df['volatility_20d'] = daily_df['volume'] / daily_df['volume'].rolling(20).mean()
                daily_df['volume_ratio'] = daily_df['volume'] / daily_df['volume'].rolling(5).mean()
                daily_df = daily_df.dropna()

                result_df = predictor.predict_top_n(
                    daily_df, n=settings.top_n, prob_threshold=settings.prob_threshold
                )

                items = []
                for _, row in result_df.iterrows():
                    items.append({
                        'ts_code': row['ts_code'],
                        'name': row.get('name', row['ts_code']),
                        'industry': row.get('industry', ''),
                        'score': float(row['score']),
                        'proba': float(row['proba']),
                        'top_factor': predictor.top_factor(row),
                    })

                await pm.save_screen_result(prev_date, items)
                logger.info(f"盘中筛选完成: {len(items)} 只")

            except Exception as e:
                logger.error(f"盘中筛选失败: {e}")

    async def evening_screen():
        logger.info("========== 盘后筛选任务启动 (15:35) ==========")
        async with app.ctx.db_sessionmaker() as session:
            from services.pool_manager import PoolManager
            from services.data_fetcher import DataFetcher
            from services.factor_engine import FactorEngine
            from services.predictor import StockPredictor
            from config import get_settings

            settings = get_settings()
            fetcher = DataFetcher(settings.tushare_token)
            predictor = StockPredictor(settings.model_path)
            pm = PoolManager(session)

            today = datetime.now().strftime('%Y%m%d')

            try:
                # 盘后用当日数据
                daily_df = fetcher.get_market_daily(today)

                if settings.exclude_st:
                    daily_df = daily_df[~daily_df['name'].str.contains('ST', na=False)]
                if settings.exclude_limit_up:
                    daily_df = daily_df[daily_df['pct_chg'] < 9.5]
                if settings.exclude_limit_down:
                    daily_df = daily_df[daily_df['pct_chg'] > -9.5]

                daily_df['return_5d'] = daily_df['pct_chg'] * 0.5
                daily_df['volatility_20d'] = daily_df['volume'] / daily_df['volume'].rolling(20).mean()
                daily_df['volume_ratio'] = daily_df['volume'] / daily_df['volume'].rolling(5).mean()
                daily_df = daily_df.dropna()

                result_df = predictor.predict_top_n(
                    daily_df, n=settings.top_n, prob_threshold=settings.prob_threshold
                )

                items = []
                for _, row in result_df.iterrows():
                    items.append({
                        'ts_code': row['ts_code'],
                        'name': row.get('name', row['ts_code']),
                        'industry': row.get('industry', ''),
                        'score': float(row['score']),
                        'proba': float(row['proba']),
                        'top_factor': predictor.top_factor(row),
                    })

                await pm.save_screen_result(today, items)
                logger.info(f"盘后筛选完成: {len(items)} 只")

                # 更新股票池天数
                await pm.update_pool_days()
                removed = await pm.auto_remove_old(settings.max_days)
                logger.info(f"自动移出 {removed} 只超期股票")

            except Exception as e:
                logger.error(f"盘后筛选失败: {e}")

    return morning_screen, evening_screen


def init_scheduler(app):
    """初始化定时任务"""
    morning_job, evening_job = create_screen_task(app)

    # 盘中：每天 09:35
    scheduler.add_job(
        morning_job,
        CronTrigger(hour=9, minute=35),
        id="morning_screen",
        name="盘中预选",
        replace_existing=True,
    )

    # 盘后：每天 15:35
    scheduler.add_job(
        evening_job,
        CronTrigger(hour=15, minute=35),
        id="evening_screen",
        name="盘后确认",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("定时任务已启动: 09:35(盘中) / 15:35(盘后)")
