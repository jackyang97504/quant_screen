import pandas as pd
import numpy as np
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class FactorEngine:
    """因子计算引擎 — 计算 30+ 个选股因子"""

    # 因子列表
    FACTOR_COLS = [
        # 动量
        'return_5d', 'return_10d', 'return_20d', 'return_60d',
        # 均线
        'price_ma5_ratio', 'price_ma20_ratio', 'price_ma60_ratio',
        'ma5_ma20_cross', 'ma10_ma20_cross', 'ma_bull',
        # 波动率
        'volatility_20d', 'volatility_60d',
        # RSI
        'rsi_14', 'rsi_28',
        # KDJ
        'kdj_k', 'kdj_d', 'kdj_j', 'kdj金叉', 'kdj超买',
        # MACD
        'macd', 'macd_signal', 'macd_hist',
        # 布林带
        'boll_position', 'boll_width',
        # 量价
        'volume_ratio', 'volume_ma5_ratio', 'volume_ma20_ratio',
        'amount_ratio', 'turnover_change',
        # 换手率
        'turnover', 'turnover_ma5',
        # 行业热度
        'industry_return_5d', 'industry_return_20d',
        'industry_money_flow_5d', 'industry_rel_strength',
        'industry_rsi_median', 'industry_volatility_median',
    ]

    def __init__(self):
        pass

    def compute(self, df: pd.DataFrame, use_today: bool = True) -> pd.DataFrame:
        """
        对单只股票计算所有因子
        df: 包含 open/high/low/close/vol/amount/turn 等列
        use_today: True=用当日数据, False=用昨日数据(盘中用)
        """
        if len(df) < 60:
            raise ValueError(f"数据不足，需要至少60条，当前{len(df)}条")

        df = df.sort_values('date').copy()
        c = df['close'].values
        v = df['volume'].values.astype(float)
        h = df['high'].values
        l = df['low'].values
        amount = df['amount'].values.astype(float)
        turnover = df['turnover'].values.astype(float)

        result = pd.DataFrame()
        result['date'] = df['date'].values

        # ===== 动量因子 =====
        result['return_5d']  = self._pct_change(c, 5)
        result['return_10d'] = self._pct_change(c, 10)
        result['return_20d'] = self._pct_change(c, 20)
        result['return_60d'] = self._pct_change(c, 60)

        # ===== 均线 =====
        ma5  = self._ma(c, 5)
        ma10 = self._ma(c, 10)
        ma20 = self._ma(c, 20)
        ma60 = self._ma(c, 60)
        result['price_ma5_ratio']  = c / ma5
        result['price_ma20_ratio'] = c / ma20
        result['price_ma60_ratio'] = c / ma60
        result['ma5_ma20_cross']   = (ma5 > ma20).astype(int)
        result['ma10_ma20_cross']  = (ma10 > ma20).astype(int)
        result['ma_bull'] = ((ma5 > ma10) & (ma10 > ma20)).astype(int)

        # ===== 波动率 =====
        returns = np.diff(c) / c[:-1]
        returns = np.insert(returns, 0, np.nan)
        result['volatility_20d'] = self._rolling_std(returns, 20) * np.sqrt(252)
        result['volatility_60d'] = self._rolling_std(returns, 60) * np.sqrt(252)

        # ===== RSI =====
        result['rsi_14'] = self._rsi(c, 14)
        result['rsi_28'] = self._rsi(c, 28)

        # ===== KDJ =====
        k, d = self._kdj(h, l, c, 9, 3, 3)
        result['kdj_k'] = k
        result['kdj_d'] = d
        result['kdj_j'] = 3 * k - 2 * d
        result['kdj金叉'] = self._cross(k, d).astype(int)
        result['kdj超买'] = (k > 85).astype(int)

        # ===== MACD =====
        ema12 = self._ema(c, 12)
        ema26 = self._ema(c, 26)
        macd_line = ema12 - ema26
        macd_signal = self._ema(macd_line, 9)
        result['macd'] = macd_line
        result['macd_signal'] = macd_signal
        result['macd_hist'] = macd_line - macd_signal

        # ===== 布林带 =====
        boll_mid = ma20
        boll_std = self._rolling_std(c, 20)
        boll_upper = boll_mid + 2 * boll_std
        boll_lower = boll_mid - 2 * boll_std
        result['boll_position'] = (c - boll_lower) / (boll_upper - boll_lower + 1e-10)
        result['boll_width'] = (boll_upper - boll_lower) / boll_mid

        # ===== 量价因子 =====
        vol_ma5 = self._ma(v, 5)
        vol_ma20 = self._ma(v, 20)
        amount_ma5 = self._ma(amount, 5)
        result['volume_ratio'] = v / vol_ma5
        result['volume_ma5_ratio'] = v / vol_ma5
        result['volume_ma20_ratio'] = v / vol_ma20
        result['amount_ratio'] = amount / amount_ma5
        result['turnover_change'] = np.diff(turnover, axis=0, prepend=np.nan)
        result['turnover'] = turnover
        result['turnover_ma5'] = self._ma(turnover, 5)

        # ===== 过滤异常值 =====
        result = self._winsorize(result)

        return result

    def compute_batch(self, daily_data: dict, use_today: bool = True) -> pd.DataFrame:
        """
        批量计算多只股票的因子
        daily_data: {ts_code: df} 字典
        返回: 合并的 DataFrame，带 ts_code 列
        """
        all_factors = []
        for ts_code, df in daily_data.items():
            try:
                factors = self.compute(df, use_today)
                factors['ts_code'] = ts_code
                all_factors.append(factors)
            except Exception as e:
                logger.warning(f"{ts_code} 因子计算失败: {e}")
                continue

        if not all_factors:
            raise ValueError("没有成功的因子计算结果")

        df = pd.concat(all_factors, ignore_index=True)
        # 计算行业因子
        df = self.compute_industry_factors(df)
        return df

    def compute_industry_factors(self, df: pd.DataFrame,
                                 industry_col: str = 'industry') -> pd.DataFrame:
        """
        在个股因子基础上计算行业聚合因子
        df: 包含 ts_code/industry/return_5d/return_20d/volume_ratio/rsi_14 等列
        需要先按 ts_code + date 排序
        """
        import pandas as pd
        df = df.copy()

        # 等权行业收益率
        ind_return_5d = df.groupby(industry_col)['return_5d'].transform('mean')
        ind_return_20d = df.groupby(industry_col)['return_20d'].transform('mean')

        # 行业资金流（用 amount_ratio 均值代理）
        if 'amount_ratio' in df.columns:
            ind_money_flow = df.groupby(industry_col)['amount_ratio'].transform('mean')
        else:
            ind_money_flow = df.groupby(industry_col)['volume_ratio'].transform('mean')

        # 行业RSI中位数
        ind_rsi = df.groupby(industry_col)['rsi_14'].transform('median')

        # 行业波动率中位数
        ind_vol = df.groupby(industry_col)['volatility_20d'].transform('median')

        # 行业相对强弱 = 行业5日收益率 / 市场(所有股票)等权收益率
        market_return_5d = df['return_5d'].mean()
        ind_rel_strength = ind_return_5d / (market_return_5d + 1e-10)

        df['industry_return_5d'] = ind_return_5d
        df['industry_return_20d'] = ind_return_20d
        df['industry_money_flow_5d'] = ind_money_flow
        df['industry_rel_strength'] = ind_rel_strength
        df['industry_rsi_median'] = ind_rsi
        df['industry_volatility_median'] = ind_vol

        return df

    @staticmethod
    def industry_neutralize(df: pd.DataFrame, factor_cols: List[str],
                            industry_col: str = 'industry') -> pd.DataFrame:
        """行业中性化：因子值减去行业均值"""
        df = df.copy()
        for col in factor_cols:
            if col in df.columns:
                ind_mean = df.groupby(industry_col)[col].transform('mean')
                df[f'{col}_ind_neutral'] = df[col] - ind_mean
        return df

    @staticmethod
    def standardize(df: pd.DataFrame, factor_cols: List[str]) -> pd.DataFrame:
        """Z-score 标准化"""
        df = df.copy()
        for col in factor_cols:
            if col in df.columns:
                mean = df[col].mean()
                std = df[col].std()
                df[f'{col}_zscore'] = (df[col] - mean) / (std + 1e-10)
        return df

    # ==================== 基础技术指标 ====================

    @staticmethod
    def _pct_change(arr: np.ndarray, n: int) -> np.ndarray:
        result = np.full_like(arr, np.nan, dtype=float)
        result[n:] = arr[n:] / arr[:-n] - 1
        return result

    @staticmethod
    def _ma(arr: np.ndarray, n: int) -> np.ndarray:
        result = np.full_like(arr, np.nan, dtype=float)
        result[n-1:] = np.convolve(arr, np.ones(n)/n, mode='valid')
        return result

    @staticmethod
    def _ema(arr: np.ndarray, n: int) -> np.ndarray:
        alpha = 2 / (n + 1)
        result = np.zeros_like(arr, dtype=float)
        result[0] = arr[0]
        for i in range(1, len(arr)):
            result[i] = alpha * arr[i] + (1 - alpha) * result[i-1]
        return result

    @staticmethod
    def _rolling_std(arr: np.ndarray, n: int) -> np.ndarray:
        result = np.full_like(arr, np.nan, dtype=float)
        for i in range(n-1, len(arr)):
            result[i] = np.std(arr[i-n+1:i+1])
        return result

    @staticmethod
    def _rsi(close: np.ndarray, n: int = 14) -> np.ndarray:
        delta = np.diff(close, prepend=np.nan)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = np.full_like(close, np.nan, dtype=float)
        avg_loss = np.full_like(close, np.nan, dtype=float)
        avg_gain[n] = np.mean(gain[1:n+1])
        avg_loss[n] = np.mean(loss[1:n+1])
        for i in range(n+1, len(close)):
            avg_gain[i] = (avg_gain[i-1] * (n-1) + gain[i]) / n
            avg_loss[i] = (avg_loss[i-1] * (n-1) + loss[i]) / n
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi[:n] = np.nan
        return rsi

    @staticmethod
    def _kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray,
             n: int = 9, k_n: int = 3, d_n: int = 3) -> tuple:
        lowest_low = np.array([np.min(low[max(0, i-n):i+1]) for i in range(len(low))])
        highest_high = np.array([np.max(high[max(0, i-n):i+1]) for i in range(len(high))])
        rsv = (close - lowest_low) / (highest_high - lowest_low + 1e-10) * 100
        k = np.full_like(close, np.nan, dtype=float)
        d = np.full_like(close, np.nan, dtype=float)
        k[n-1] = 50
        d[n-1] = 50
        for i in range(n, len(close)):
            k[i] = 2/3 * k[i-1] + 1/3 * rsv[i]
            d[i] = 2/3 * d[i-1] + 1/3 * k[i]
        return k, d

    @staticmethod
    def _cross(arr1: np.ndarray, arr2: np.ndarray) -> np.ndarray:
        cross = np.zeros(len(arr1), dtype=int)
        for i in range(1, len(arr1)):
            if not np.isnan(arr1[i-1]) and not np.isnan(arr2[i-1]):
                if arr1[i-1] <= arr2[i-1] and arr1[i] > arr2[i]:
                    cross[i] = 1
        return cross

    @staticmethod
    def _winsorize(df: pd.DataFrame, low: float = 0.01, high: float = 0.99) -> pd.DataFrame:
        """去极值"""
        df = df.copy()
        for col in df.columns:
            if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
                q1 = df[col].quantile(low)
                q99 = df[col].quantile(high)
                df[col] = df[col].clip(q1, q99)
        return df
