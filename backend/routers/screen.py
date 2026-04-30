from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.schemas import ScreenResultResponse, StockItem, MessageResponse, ManualRunRequest
from services.pool_manager import PoolManager
from services.predictor import StockPredictor
from services.factor_engine import FactorEngine
from services.data_fetcher import DataFetcher
from config import get_settings
import logging

router = APIRouter(prefix="/api/screen", tags=["筛选"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _compute_screening_detail(row) -> str:
    """
    生成单只股票的详细筛选依据（JSON格式），供人工辅助判断
    """
    import json
    import numpy as np

    def _fmt(v, decimals=3):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return round(float(v), decimals)

    def _has(v):
        return v is not None

    def _label(val, thresholds, labels):
        for t, l in zip(thresholds, labels):
            if val is not None and val <= t:
                return l
        return labels[-1]

    try:
        r5 = _fmt(row.get('return_5d'))
        r20 = _fmt(row.get('return_20d'))
        r60 = _fmt(row.get('return_60d'))
        vol20 = _fmt(row.get('volatility_20d'))
        rsi14 = _fmt(row.get('rsi_14'))
        kdj_k = _fmt(row.get('kdj_k'))
        kdj_d = _fmt(row.get('kdj_d'))
        boll_pos = _fmt(row.get('boll_position'))
        turnover = _fmt(row.get('turnover'))
        macd_hist = _fmt(row.get('macd_hist'))

        # 行业因子
        ind_ret5 = _fmt(row.get('industry_return_5d'))
        ind_ret20 = _fmt(row.get('industry_return_20d'))
        ind_rel = _fmt(row.get('industry_rel_strength'))
        ind_vol = _fmt(row.get('industry_volatility_median'))
        ind_rsi = _fmt(row.get('industry_rsi_median'))

        # ===== 正面信号 =====
        positives = []
        negatives = []
        warnings = []

        # 动量
        if _has(r5) and r5 > 0.03:
            positives.append(f"短期动量强劲(5日+{r5:.1%})")
        elif _has(r5) and r5 < -0.05:
            negatives.append(f"短期回调({r5:.1%})")

        if _has(ind_ret5) and ind_ret5 > 0.02:
            positives.append(f"行业短期强势(行业5日+{ind_ret5:.1%})")

        if _has(ind_rel) and ind_rel > 1.1:
            positives.append(f"行业相对强势(相对强弱={ind_rel:.2f})")
        elif _has(ind_rel) and ind_rel < 0.9:
            negatives.append(f"行业相对弱势(相对强弱={ind_rel:.2f})")

        # 超买超卖
        if _has(rsi14):
            if rsi14 < 30:
                positives.append(f"RSI超卖({rsi14:.0f})，反弹概率大")
            elif rsi14 > 70:
                warnings.append(f"RSI超买({rsi14:.0f})，注意回调风险")

        # KDJ
        if _has(kdj_k) and _has(kdj_d):
            if kdj_k < 20:
                positives.append(f"KDJ超卖(K={kdj_k:.0f})")
            elif kdj_k > 80:
                warnings.append(f"KDJ超买(K={kdj_k:.0f})")

        # MACD
        if macd_hist is not None and macd_hist > 0.05:
            positives.append(f"MACD红柱扩张({macd_hist:.3f})")
        elif macd_hist is not None and macd_hist < -0.05:
            negatives.append(f"MACD绿柱({macd_hist:.3f})")

        # 布林带
        if boll_pos is not None:
            if boll_pos < 0.2:
                positives.append(f"布林下轨支撑(位置={boll_pos:.2f})")
            elif boll_pos > 0.85:
                warnings.append(f"布林上轨压力(位置={boll_pos:.2f})")

        # 换手率
        if _has(turnover):
            if turnover > 10:
                positives.append(f"高换手({turnover:.1f}%)，资金活跃")
            elif turnover < 1:
                warnings.append(f"换手率极低({turnover:.1f}%)，关注流动性")

        # 行业波动率
        if _has(ind_vol) and ind_vol > 0.35:
            warnings.append(f"行业高波动(行业波动率={ind_vol:.1%})")

        # ===== 风险等级 =====
        risk_level = "低"
        risk_score = 0
        if _has(rsi14) and rsi14 > 75:
            risk_score += 2
        if _has(turnover) and turnover > 15:
            risk_score += 1
        if _has(vol20) and vol20 > 0.5:
            risk_score += 1
        if _has(ind_vol) and ind_vol > 0.4:
            risk_score += 1
        if risk_score >= 3:
            risk_level = "高"
        elif risk_score >= 1:
            risk_level = "中"

        detail = {
            "prob": _fmt(row.get('proba')),
            "industry": row.get('industry', ''),
            "risk_level": risk_level,
            "positive_signals": positives[:4],
            "negative_signals": negatives[:3],
            "warnings": warnings[:3],
            "key_indicators": {
                "5日收益率": f"{r5:.2%}" if _has(r5) else "N/A",
                "20日收益率": f"{r20:.2%}" if _has(r20) else "N/A",
                "60日收益率": f"{r60:.2%}" if _has(r60) else "N/A",
                "波动率(20日)": f"{vol20:.2%}" if _has(vol20) else "N/A",
                "RSI(14)": f"{rsi14:.1f}" if _has(rsi14) else "N/A",
                "KDJ-K": f"{kdj_k:.1f}" if _has(kdj_k) else "N/A",
                "布林位置": f"{boll_pos:.2f}" if boll_pos is not None else "N/A",
                "换手率": f"{turnover:.2f}%" if _has(turnover) else "N/A",
            },
            "industry_context": {
                "行业5日动量": f"{ind_ret5:.2%}" if _has(ind_ret5) else "N/A",
                "行业20日动量": f"{ind_ret20:.2%}" if _has(ind_ret20) else "N/A",
                "行业相对强弱": f"{ind_rel:.2f}" if _has(ind_rel) else "N/A",
                "行业波动率": f"{ind_vol:.2%}" if _has(ind_vol) else "N/A",
            }
        }

        return json.dumps(detail, ensure_ascii=False, indent=2)

    except Exception:
        return "{}"


def create_screen_result(trade_date: str, items: list) -> ScreenResultResponse:
    return ScreenResultResponse(
        trade_date=trade_date,
        total=len(items),
        items=[StockItem(**item) for item in items]
    )


@router.get("/today", response_model=ScreenResultResponse)
async def get_today_screen(trade_date: str, db: AsyncSession = Depends(get_db)):
    """获取当日筛选结果"""
    pm = PoolManager(db)
    items = await pm.get_today_screen(trade_date)
    if not items:
        raise HTTPException(status_code=404, detail=f"无 {trade_date} 的筛选结果")
    return create_screen_result(trade_date, items)


@router.get("/history", response_model=ScreenResultResponse)
async def get_history_screen(trade_date: str, db: AsyncSession = Depends(get_db)):
    """获取历史筛选结果"""
    pm = PoolManager(db)
    items = await pm.get_history(trade_date)
    return create_screen_result(trade_date, items)


@router.post("/run", response_model=MessageResponse)
async def run_screen(
    req: ManualRunRequest,
    background: BackgroundTasks,
):
    """手动触发一次筛选（后台运行）"""
    # 后台任务应自行创建数据库会话，避免复用请求生命周期中的 session
    background.add_task(run_screen_task, req.trade_date)
    return MessageResponse(message="筛选任务已启动", code=0)


async def run_screen_task(trade_date: str):
    """实际执行筛选的后台任务 — 两步法：快速预筛选 + 完整因子预测"""
    from database import init_db
    import pandas as pd
    import tushare as ts
    import time
    from database import AsyncSessionLocal

    logger.info(f"开始筛选任务: {trade_date}")

    try:
        init_db()
    except Exception as e:
        logger.warning(f"表已存在或创建失败: {e}")

    fetcher = DataFetcher(settings.tushare_token)
    predictor = StockPredictor(settings.model_path)

    # 获取上一交易日
    if not trade_date:
        today = pd.Timestamp.now().strftime('%Y%m%d')
        trade_date = fetcher.get_previous_trade_date(today)

    try:
        daily_df = fetcher.get_market_daily(trade_date)
    except Exception as e:
        logger.error(f"数据获取失败: {e}")
        return

    if daily_df is None or len(daily_df) == 0:
        logger.error("无市场数据")
        return

    try:
        # ===== 过滤基础垃圾股 =====
        if settings.exclude_st:
            daily_df = daily_df[~daily_df['name'].str.contains('ST', na=False)]
        if settings.exclude_limit_up:
            daily_df = daily_df[daily_df['pct_chg'] < 9.5]
        if settings.exclude_limit_down:
            daily_df = daily_df[daily_df['pct_chg'] > -9.5]

        # ===== 预筛选：Top 300 只股票（用单日数据 + 简化因子）=====
        # 只保留沪市(6开头)和深市(0开头)，排除北交所(9开头.BJ)
        daily_df = daily_df[daily_df['ts_code'].str.match(r'^(0|6)\d{5}\.(SH|SZ)$')]

        daily_df['return_5d'] = daily_df['pct_chg'] * 0.5
        daily_df['volume_ratio'] = daily_df['volume'] / (daily_df['volume'].rolling(5).mean() + 1)
        daily_df['amount_ratio'] = daily_df['amount'] / (daily_df['amount'].rolling(5).mean() + 1)
        daily_df['score_simple'] = (
            daily_df['pct_chg'].abs() * 0.3 +
            daily_df['volume_ratio'] * 0.3 +
            daily_df['amount_ratio'] * 0.4
        )
        pre_stocks = daily_df.nlargest(300, 'score_simple')[['ts_code', 'name', 'industry', 'trade_date']].copy()
        pre_codes = pre_stocks['ts_code'].tolist()
        logger.info(f"预筛选完成: {len(pre_codes)} 只候选")

        # ===== 逐只获取历史数据并计算完整因子 =====
        pro = ts.pro_api(settings.tushare_token)
        all_factors = []
        lookback = 120  # 日历天，涵盖70+交易日（去除停牌/节假日）

        for i, code in enumerate(pre_codes):
            if i % 50 == 0:
                logger.info(f"  计算因子进度: {i}/{len(pre_codes)}")
            try:
                hist = pro.daily(ts_code=code, start_date='20251001', end_date=trade_date)
                if hist is None or len(hist) < 60:
                    continue
                hist = hist.head(70)  # 取最近70条（API返回降序，最新在前）
                if len(hist) < 60:
                    continue
                hist.rename(columns={'vol': 'volume'}, inplace=True)
                hist['amount'] = hist['amount'] * 10000
                hist['turnover'] = hist['amount'] / (hist['close'] * 100 + 1e-10)
                hist['date'] = pd.to_datetime(hist['trade_date'])
                # 添加industry
                ind = pre_stocks[pre_stocks['ts_code'] == code]['industry'].values
                industry_val = ind[0] if len(ind) > 0 else '未知'
                hist['industry'] = industry_val

                # 计算完整因子
                fe = FactorEngine()
                factors = fe.compute(hist[['date', 'close', 'high', 'low', 'volume', 'amount', 'turnover']].copy(),
                                     use_today=True)
                factors['ts_code'] = code
                factors['trade_date'] = factors['date'].dt.strftime('%Y%m%d')  # 从已排序的date列转换
                factors['industry'] = industry_val  # 保留行业信息
                all_factors.append(factors)
            except Exception as e:
                if i < 5:
                    logger.warning(f"  股票 {code} 计算因子失败: {e}")
                continue
            time.sleep(0.05)  # 避免频率限制

        if not all_factors:
            logger.error("没有计算出有效因子")
            import traceback
            traceback.print_exc()
            return

        df = pd.concat(all_factors, ignore_index=True)
        logger.info(f"  合并后 df 大小: {df.shape}")

        # ===== 计算行业因子 =====
        df['industry_return_5d'] = df.groupby(['trade_date', 'industry'])['return_5d'].transform('mean')
        df['industry_return_20d'] = df.groupby(['trade_date', 'industry'])['return_20d'].transform('mean')
        df['industry_money_flow_5d'] = df.groupby(['trade_date', 'industry'])['amount_ratio'].transform('mean')
        df['industry_rsi_median'] = df.groupby(['trade_date', 'industry'])['rsi_14'].transform('median')
        df['industry_volatility_median'] = df.groupby(['trade_date', 'industry'])['volatility_20d'].transform('median')
        market_ret = df.groupby('trade_date')['return_5d'].transform('mean')
        df['industry_rel_strength'] = df['industry_return_5d'] / (market_ret + 1e-10)

        # 只保留最新一天
        latest_date = df['trade_date'].max()
        df = df[df['trade_date'] == latest_date].copy()
        logger.info(f"  过滤到最新一天后: {len(df)} 条, date={latest_date}")

        # 调试：检查关键列的空值
        for col in ['return_5d', 'volatility_20d', 'rsi_14', 'industry_return_5d']:
            nulls = df[col].isna().sum()
            logger.info(f"    {col}: 空值 {nulls}/{len(df)}")

        # 行业因子去空
        for col in ['industry_return_5d', 'industry_return_20d',
                    'industry_money_flow_5d', 'industry_rel_strength',
                    'industry_rsi_median', 'industry_volatility_median']:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # 只对关键特征列 dropna
        key_cols = ['return_5d', 'volatility_20d', 'rsi_14']
        df = df.dropna(subset=key_cols)
        logger.info(f"  有效因子数据: {len(df)} 条")

        # ===== 预测 =====
        result_df = predictor.predict_top_n(
            df,
            n=settings.top_n,
            prob_threshold=settings.prob_threshold
        )

        # 合并名称和行业
        name_map = pre_stocks.set_index('ts_code')[['name', 'industry']].to_dict('index')

        items = []
        for _, row in result_df.iterrows():
            ts_code = row['ts_code']
            info = name_map.get(ts_code, {})
            detail = _compute_screening_detail(row)
            items.append({
                'ts_code': ts_code,
                'name': info.get('name', ts_code),
                'industry': info.get('industry', ''),
                'score': float(row['score']),
                'proba': float(row['proba']),
                'top_factor': predictor.top_factor(row),
                'screening_detail': detail,
            })

        async with AsyncSessionLocal() as db:
            pm = PoolManager(db)
            await pm.save_screen_result(trade_date, items)
        logger.info(f"筛选完成: {len(items)} 只股票")

    except Exception as e:
        logger.error(f"筛选失败: {e}")
        import traceback
        traceback.print_exc()
