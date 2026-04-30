from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


# ========== 筛选结果 ==========
class StockItem(BaseModel):
    ts_code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    industry: Optional[str] = Field(None, description="行业")
    score: float = Field(..., description="模型评分")
    proba: float = Field(..., description="上涨概率")
    top_factor: Optional[str] = Field(None, description="主要入选因子（简述）")
    screening_detail: Optional[str] = Field(None, description="详细筛选依据（JSON字符串）")
    status: str = Field(default="pending", description="状态: pending/confirmed/rejected")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScreenResultResponse(BaseModel):
    trade_date: str
    total: int
    items: List[StockItem]


class PendingScreenResponse(BaseModel):
    total: int
    items: List[StockItem]


# ========== 股票池 ==========
class PoolItem(BaseModel):
    ts_code: str
    name: str
    industry: Optional[str] = None
    first_seen: Optional[date] = None
    last_seen: Optional[date] = None
    hit_count: int = 1
    days_in_pool: int = 0
    status: str = "active"
    avg_score: Optional[float] = None

    class Config:
        from_attributes = True


class PoolResponse(BaseModel):
    total: int
    items: List[PoolItem]


# ========== API 请求 ==========
class ConfirmRequest(BaseModel):
    codes: List[str] = Field(..., description="股票代码列表")


class RejectRequest(BaseModel):
    codes: List[str] = Field(..., description="股票代码列表")


class ManualRunRequest(BaseModel):
    trade_date: Optional[str] = Field(None, description="指定日期，默认为上一交易日")


# ========== 通用响应 ==========
class MessageResponse(BaseModel):
    message: str
    code: int = 0


class HistoryQuery(BaseModel):
    trade_date: str
    items: List[StockItem]
    total: int
