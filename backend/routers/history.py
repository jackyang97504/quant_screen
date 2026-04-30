from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.schemas import ScreenResultResponse, StockItem
from services.pool_manager import PoolManager

router = APIRouter(prefix="/api/history", tags=["历史"])


@router.get("", response_model=ScreenResultResponse)
async def query_history(
    trade_date: str = Query(..., description="交易日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """按日期查询筛选结果"""
    pm = PoolManager(db)
    items = await pm.get_history(trade_date)
    return ScreenResultResponse(
        trade_date=trade_date,
        total=len(items),
        items=[StockItem(**item) for item in items]
    )


@router.get("/dates")
async def get_available_dates(
    limit: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """获取有筛选结果的日期列表"""
    from sqlalchemy import text
    stmt = text("""
        SELECT DISTINCT trade_date
        FROM screen_results
        ORDER BY trade_date DESC
        LIMIT :limit
    """)
    result = await db.execute(stmt, {'limit': limit})
    dates = [r[0] for r in result.fetchall()]
    return {"dates": dates, "total": len(dates)}
