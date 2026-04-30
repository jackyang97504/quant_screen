from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
import os
from dotenv import load_dotenv

# 加载 .env 文件
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_path,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Tushare token
    tushare_token: str = "YOUR_TUSHARE_TOKEN"

    # 数据源配置
    data_source_primary: str = "akshare"
    data_source_backup: str = "tushare"
    retry_times: int = 3
    retry_delay: int = 5

    # 股票池配置
    top_n: int = 50
    max_pool_size: int = 100
    max_days: int = 20
    prob_threshold: float = 0.50

    # 过滤规则
    min_volume_ma5: float = 5000  # 万元
    max_turnover: float = 30.0
    min_turnover: float = 0.5
    exclude_st: bool = True
    exclude_limit_up: bool = True
    exclude_limit_down: bool = True

    # 行业分散
    max_per_industry: int = 10

    # 定时配置
    morning_run_time: str = "09:35"
    evening_run_time: str = "15:35"

    # 模型路径
    model_path: str = "./models/lightgbm_stock_model.txt"

    # PostgreSQL 数据库
    database_url: str = "postgresql+asyncpg://jackyang@localhost:5432/quant_screen"
    database_url_sync: str = "postgresql://jackyang@localhost:5432/quant_screen"

    # 日志
    log_dir: str = "./logs"
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
