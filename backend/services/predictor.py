import lightgbm as lgb
import numpy as np
import pandas as pd
from typing import List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class StockPredictor:
    """LightGBM 选股预测引擎"""

    FEATURE_COLS = [
        'return_5d', 'return_10d', 'return_20d', 'return_60d',
        'price_ma5_ratio', 'price_ma20_ratio', 'price_ma60_ratio',
        'ma5_ma20_cross', 'ma10_ma20_cross', 'ma_bull',
        'volatility_20d', 'volatility_60d',
        'rsi_14', 'rsi_28',
        'kdj_k', 'kdj_d', 'kdj_j', 'kdj金叉', 'kdj超买',
        'macd', 'macd_signal', 'macd_hist',
        'boll_position', 'boll_width',
        'volume_ratio', 'volume_ma5_ratio', 'volume_ma20_ratio',
        'amount_ratio', 'turnover_change', 'turnover', 'turnover_ma5',
    ]

    def __init__(self, model_path: str = "./models/lightgbm_stock_model.txt"):
        self.model_path = model_path
        self.model: Optional[lgb.Booster] = None
        self.feature_names: list = []
        self._load_model()

    def _load_model(self):
        """加载模型，如果不存在则创建默认模型"""
        if os.path.exists(self.model_path):
            self.model = lgb.Booster(model_file=self.model_path)
            self.feature_names = self.model.feature_name()
            logger.info(f"模型加载成功: {self.model_path} ({len(self.feature_names)} 个特征)")
        else:
            logger.warning(f"模型文件不存在: {self.model_path}，将创建默认模型")
            self.model = self._create_default_model()
            self.feature_names = self.FEATURE_COLS
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            self.model.save_model(self.model_path)

    def _create_default_model(self) -> lgb.Booster:
        """创建一个默认的 LightGBM 模型（用于无预训练模型时）"""
        params = {
            'objective': 'binary',
            'metric': 'auc',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'min_child_samples': 50,
            'max_depth': 6,
            'verbose': -1,
            'n_jobs': -1,
            'is_unbalance': True,
        }
        # 创建一个空数据集用于初始化
        dummy_data = lgb.Dataset(
            np.random.randn(100, len(self.FEATURE_COLS)),
            label=np.random.randint(0, 2, 100),
            feature_name=self.FEATURE_COLS
        )
        model = lgb.train(params, dummy_data, num_boost_round=10)
        return model

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        对 DataFrame 中的股票进行预测
        df: 必须包含 FEATURE_COLS 中的所有列
        返回: 添加了 score 和 proba 列的 DataFrame
        """
        if self.model is None:
            raise ValueError("模型未加载")

        # 只保留有特征的股票
        missing_cols = set(self.feature_names) - set(df.columns)
        if missing_cols:
            logger.warning(f"缺失列: {missing_cols}，将填充0")
            for col in missing_cols:
                df[col] = 0

        # 填充缺失值
        X = df[self.feature_names].fillna(0).values

        # 预测概率
        proba = self.model.predict(X)
        df['score'] = proba
        df['proba'] = proba

        return df.sort_values('score', ascending=False)

    def predict_top_n(self, df: pd.DataFrame, n: int = 50,
                      prob_threshold: float = 0.55) -> pd.DataFrame:
        """
        预测并返回 Top N
        """
        df = self.predict(df)
        # 阈值过滤
        df = df[df['proba'] >= prob_threshold]
        return df.head(n)

    def get_feature_importance(self) -> pd.DataFrame:
        """返回特征重要性"""
        if self.model is None:
            return pd.DataFrame()
        importance = self.model.feature_importance(importance_type='gain')
        return pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

    def top_factor(self, row: pd.Series) -> str:
        """返回单只股票的主要入选因子"""
        importance = self.get_feature_importance()
        factors = []
        for _, imp_row in importance.head(5).iterrows():
            feat = imp_row['feature']
            if feat in row and pd.notna(row[feat]) and row[feat] != 0:
                factors.append(f"{feat}={row[feat]:.3f}")
        return "; ".join(factors[:3])


def create_default_model_file(model_path: str = "./models/lightgbm_stock_model.txt"):
    """创建默认模型文件"""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    predictor = StockPredictor(model_path)
    return predictor
