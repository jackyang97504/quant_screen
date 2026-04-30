import pandas as pd
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class PoolManager:
    """股票池管理器 — 管理 pending/confirmed/rejected 三种状态"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    # ========== 筛选结果管理 ==========

    @staticmethod
    def _parse_date(d: str) -> date:
        """将 YYYYMMDD 或 YYYY-MM-DD 字符串转为 date 对象"""
        d = d.replace('-', '')
        return datetime.strptime(d, '%Y%m%d').date()

    async def save_screen_result(self, trade_date: str, items: List[dict]) -> int:
        """保存当日筛选结果（写入 pending 表，先删除当日旧数据）"""
        td = self._parse_date(trade_date)
        # 先删除该交易日的历史记录（避免重复累积）
        await self.db.execute(
            text("DELETE FROM screen_results WHERE trade_date = :trade_date"),
            {'trade_date': td}
        )
        inserted = 0
        for item in items:
            stmt = text("""
                INSERT INTO screen_results (trade_date, ts_code, name, industry,
                                           score, proba, top_factor, screening_detail, status, created_at)
                VALUES (:trade_date, :ts_code, :name, :industry,
                        :score, :proba, :top_factor, :screening_detail, 'pending', NOW())
                ON CONFLICT (trade_date, ts_code)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    proba = EXCLUDED.proba,
                    top_factor = EXCLUDED.top_factor,
                    screening_detail = EXCLUDED.screening_detail,
                    status = 'pending'
            """)
            await self.db.execute(stmt, {
                'trade_date': td,
                'ts_code': item['ts_code'],
                'name': item.get('name', ''),
                'industry': item.get('industry', ''),
                'score': item['score'],
                'proba': item['proba'],
                'top_factor': item.get('top_factor', ''),
                'screening_detail': item.get('screening_detail', ''),
            })
            inserted += 1
        await self.db.commit()
        return inserted

    async def get_today_screen(self, trade_date: str) -> List[dict]:
        """获取当日筛选结果"""
        td = self._parse_date(trade_date)
        stmt = text("""
            SELECT ts_code, name, industry, score, proba, top_factor, screening_detail, status, created_at
            FROM screen_results
            WHERE trade_date = :trade_date
            ORDER BY score DESC
        """)
        result = await self.db.execute(stmt, {'trade_date': td})
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]

    async def get_pending_screen(self) -> List[dict]:
        """获取所有待确认结果"""
        stmt = text("""
            SELECT ts_code, name, industry, score, proba, top_factor, screening_detail,
                   trade_date, created_at
            FROM screen_results
            WHERE status = 'pending'
            ORDER BY trade_date DESC, score DESC
        """)
        result = await self.db.execute(stmt)
        return [dict(r._mapping) for r in result.fetchall()]

    # ========== 股票池管理 ==========

    async def confirm_stocks(self, codes: List[str], operator: str = 'manual') -> int:
        """确认股票入选股票池"""
        today = date.today()
        confirmed = 0

        for code in codes:
            # 查找该股票最新的筛选记录
            stmt = text("""
                SELECT name, industry, score, proba, trade_date
                FROM screen_results
                WHERE ts_code = :code AND status = 'pending'
                ORDER BY trade_date DESC LIMIT 1
            """)
            result = await self.db.execute(stmt, {'code': code})
            row = result.fetchone()

            if row is None:
                logger.warning(f"股票 {code} 无待确认记录")
                continue
            row_data = dict(row._mapping)

            # upsert 到 stock_pool
            upsert_stmt = text("""
                INSERT INTO stock_pool (ts_code, name, industry, first_seen, last_seen,
                                       hit_count, days_in_pool, status, updated_at)
                VALUES (:ts_code, :name, :industry, :today, :today, 1, 0, 'active', NOW())
                ON CONFLICT (ts_code) DO UPDATE SET
                    name = EXCLUDED.name,
                    industry = EXCLUDED.industry,
                    last_seen = :today,
                    hit_count = stock_pool.hit_count + 1,
                    days_in_pool = 0,
                    status = 'active',
                    updated_at = NOW()
            """)
            await self.db.execute(upsert_stmt, {
                'ts_code': code,
                'name': row_data.get('name', ''),
                'industry': row_data.get('industry', ''),
                'today': today,
            })

            # 更新筛选记录状态
            await self.db.execute(
                text("UPDATE screen_results SET status = 'confirmed' WHERE ts_code = :code AND trade_date = :trade_date"),
                {'code': code, 'trade_date': row_data.get('trade_date')}
            )

            # 写审计日志
            await self.db.execute(
                text("""
                    INSERT INTO audit_log (ts_code, action, operator, trade_date, created_at)
                    VALUES (:code, 'confirm', :operator, :trade_date, NOW())
                """),
                {'code': code, 'operator': operator, 'trade_date': today}
            )
            confirmed += 1

        await self.db.commit()
        return confirmed

    async def reject_stocks(self, codes: List[str], operator: str = 'manual') -> int:
        """拒绝股票（标记为 rejected）"""
        stmt = text("""
            UPDATE screen_results
            SET status = 'rejected'
            WHERE ts_code = ANY(:codes) AND status = 'pending'
        """)
        result = await self.db.execute(stmt, {'codes': codes})
        await self.db.commit()
        return result.rowcount if result.rowcount else 0

    async def remove_from_pool(self, codes: List[str], operator: str = 'manual') -> int:
        """从股票池中移出"""
        stmt = text("""
            UPDATE stock_pool
            SET status = 'removed', updated_at = NOW()
            WHERE ts_code = ANY(:codes) AND status = 'active'
        """)
        result = await self.db.execute(stmt, {'codes': codes})
        await self.db.commit()
        # 写审计日志
        today = date.today()
        for code in codes:
            await self.db.execute(
                text("""
                    INSERT INTO audit_log (ts_code, action, operator, trade_date, created_at)
                    VALUES (:code, 'remove', :operator, :trade_date, NOW())
                """),
                {'code': code, 'operator': operator, 'trade_date': today}
            )
        await self.db.commit()
        return result.rowcount

    async def get_pool(self, status: str = 'active') -> List[dict]:
        """获取当前股票池"""
        stmt = text("""
            SELECT ts_code, name, industry, first_seen, last_seen,
                   hit_count, days_in_pool, status, created_at
            FROM stock_pool
            WHERE status = :status
            ORDER BY hit_count DESC
        """)
        result = await self.db.execute(stmt, {'status': status})
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]

    async def auto_remove_old(self, max_days: int = 20) -> int:
        """自动移出超期股票"""
        cutoff = date.today() - timedelta(days=max_days)
        stmt = text("""
            UPDATE stock_pool
            SET status = 'expired', updated_at = NOW()
            WHERE status = 'active'
              AND last_seen < :cutoff
        """)
        result = await self.db.execute(stmt, {'cutoff': cutoff})
        await self.db.commit()
        return result.rowcount

    async def update_pool_days(self) -> int:
        """每日更新在池天数"""
        stmt = text("""
            UPDATE stock_pool
            SET days_in_pool = days_in_pool + 1,
                updated_at = NOW()
            WHERE status = 'active'
        """)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    # ========== 历史查询 ==========

    async def get_history(self, trade_date: str) -> List[dict]:
        """获取指定日期的筛选结果"""
        td = self._parse_date(trade_date)
        stmt = text("""
            SELECT ts_code, name, industry, score, proba, top_factor, screening_detail, status
            FROM screen_results
            WHERE trade_date = :trade_date
            ORDER BY score DESC
        """)
        result = await self.db.execute(stmt, {'trade_date': td})
        return [dict(r._mapping) for r in result.fetchall()]

    async def get_pool_stats(self) -> dict:
        """获取股票池统计"""
        stmt = text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'active') as active_count,
                COUNT(*) FILTER (WHERE status = 'removed') as removed_count,
                AVG(hit_count) FILTER (WHERE status = 'active') as avg_hit_count,
                MAX(hit_count) FILTER (WHERE status = 'active') as max_hit_count
            FROM stock_pool
        """)
        result = await self.db.execute(stmt)
        row = result.fetchone()
        return dict(row._mapping) if row else {}
