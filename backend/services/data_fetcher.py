import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DataFetcher:
    """数据获取层：仅使用 tushare（akshare 因网络代理问题暂不可用）"""

    def __init__(self, tushare_token: str):
        self.tushare_token = tushare_token
        self.pro = ts.pro_api(tushare_token)
        self._basic_cache: Optional[pd.DataFrame] = None

    def get_market_daily(self, trade_date: str) -> pd.DataFrame:
        """
        获取全市场日线数据
        trade_date: YYYYMMDD 格式
        """
        try:
            df = self._fetch_tushare_daily(trade_date)
            if df is not None and len(df) > 100:
                return df
        except Exception as e:
            logger.error(f"tushare 日线获取失败: {e}")

        raise ValueError(f"无法获取 {trade_date} 的市场数据")

    def get_stock_basic(self) -> pd.DataFrame:
        """获取全市场股票基本信息（带缓存）"""
        if self._basic_cache is not None:
            return self._basic_cache

        try:
            df = self.pro.stock_basic(
                exchange='', list_status='L',
                fields='ts_code,name,industry'
            )
            self._basic_cache = df
            logger.info(f"股票基本信息缓存完成: {len(df)} 只")
            return df
        except Exception as e:
            logger.error(f"股票基本信息获取失败: {e}")
            return pd.DataFrame(columns=['ts_code', 'name', 'industry'])

    def _fetch_tushare_daily(self, trade_date: str) -> pd.DataFrame:
        """tushare 获取全市场日线"""
        df = self.pro.daily(trade_date=trade_date)
        basic = self.get_stock_basic()
        df = df.merge(basic[['ts_code', 'name', 'industry']], on='ts_code', how='left')
        # tushare daily: vol=成交量(手/100股), amount=成交额(万元)
        # vol -> volume (换手率需要 volume 和 amount)
        df.rename(columns={'vol': 'volume'}, inplace=True)
        df['amount'] = df['amount'] * 10000  # 万元->元
        # 换手率(%) = 成交额/收盘价/100 = amount/(close*100)
        df['turnover'] = df['amount'] / (df['close'] * 100 + 1e-10)
        # 涨跌停标记
        df['limit_up'] = df['pct_chg'] >= 9.5
        df['limit_down'] = df['pct_chg'] <= -9.5
        # 只保留沪市(6)和深市(0)，排除北交所(9开头.BJ)
        df = df[df['ts_code'].str.match(r'^(0|6)\d{5}\.(SH|SZ)$')]
        return df

    def get_previous_trade_date(self, trade_date: str) -> str:
        """获取指定日期的上一个交易日"""
        df = self.pro.trade_cal(
            exchange='SSE',
            start_date=self._date_add_days(trade_date, -10),
            end_date=trade_date
        )
        df = df[df['is_open'] == 1].sort_values('cal_date')
        prev_df = df[df['cal_date'] < trade_date]
        if prev_df.empty:
            raise ValueError(f"无法找到 {trade_date} 之前的交易日")
        prev = prev_df['cal_date'].iloc[-1]
        return prev

    def get_trade_dates(self, start_date: str, end_date: str) -> list:
        """获取交易日列表"""
        df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
        df = df[df['is_open'] == 1]
        return df['cal_date'].tolist()

    @staticmethod
    def _date_add_days(date_str: str, days: int) -> str:
        """日期加减天数"""
        d = datetime.strptime(date_str, '%Y%m%d') + timedelta(days=days)
        return d.strftime('%Y%m%d')
