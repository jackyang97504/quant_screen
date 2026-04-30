from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.schemas import (
    PoolResponse, PoolItem, ConfirmRequest, RejectRequest,
    MessageResponse, PendingScreenResponse, StockItem
)
from services.pool_manager import PoolManager
import logging

router = APIRouter(prefix="/api/pool", tags=["股票池"])
logger = logging.getLogger(__name__)


@router.get("", response_model=PoolResponse)
async def get_pool(
    status: str = "active",
    db: AsyncSession = Depends(get_db)
):
    """获取当前股票池"""
    pm = PoolManager(db)
    items = await pm.get_pool(status)
    return PoolResponse(total=len(items), items=[PoolItem(**item) for item in items])


@router.get("/pending", response_model=PendingScreenResponse)
async def get_pending(db: AsyncSession = Depends(get_db)):
    """获取待确认列表"""
    pm = PoolManager(db)
    items = await pm.get_pending_screen()
    return PendingScreenResponse(total=len(items), items=[StockItem(**item) for item in items])


@router.get("/stats")
async def get_pool_stats(db: AsyncSession = Depends(get_db)):
    """获取股票池统计"""
    pm = PoolManager(db)
    stats = await pm.get_pool_stats()
    return stats


@router.post("/confirm", response_model=MessageResponse)
async def confirm_stocks(
    req: ConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    """确认股票入选"""
    pm = PoolManager(db)
    count = await pm.confirm_stocks(req.codes, operator='manual')
    return MessageResponse(message=f"已确认 {count} 只股票", code=0)


@router.post("/reject", response_model=MessageResponse)
async def reject_stocks(
    req: RejectRequest,
    db: AsyncSession = Depends(get_db)
):
    """拒绝股票"""
    pm = PoolManager(db)
    count = await pm.reject_stocks(req.codes, operator='manual')
    return MessageResponse(message=f"已拒绝 {count} 只股票", code=0)


@router.post("/remove", response_model=MessageResponse)
async def remove_stocks(
    req: ConfirmRequest,  # 复用结构
    db: AsyncSession = Depends(get_db)
):
    """从股票池移出"""
    pm = PoolManager(db)
    count = await pm.remove_from_pool(req.codes, operator='manual')
    return MessageResponse(message=f"已移出 {count} 只股票", code=0)
