"""
deep scan H5: what THUTOra's AI costs, per school, this month (or another).

    python -m scripts.ai_costs              # this month
    python -m scripts.ai_costs --month 2026-11

Prices: app/services/ai_cost.py (update when Anthropic's prices change).
"""

import argparse
import asyncio
from datetime import datetime

from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.models import AiUsage, School
from app.services.ai_cost import cost_usd


async def main(month: str | None) -> None:
    start = datetime.strptime(month, "%Y-%m") if month else datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + (start.month == 12), month=start.month % 12 + 1)
    async with async_session_factory() as db:
        rows = (
            await db.execute(
                select(School.name, AiUsage.feature, AiUsage.model, func.count(),
                       func.sum(AiUsage.input_tokens), func.sum(AiUsage.output_tokens),
                       func.sum(AiUsage.cache_read_tokens), func.sum(AiUsage.cache_write_tokens))
                .join(School, School.id == AiUsage.school_id, isouter=True)
                .where(AiUsage.created_at >= start, AiUsage.created_at < end)
                .group_by(School.name, AiUsage.feature, AiUsage.model)
                .order_by(School.name)
            )
        ).all()
    total = 0.0
    print(f"AI use {start:%B %Y}")
    for name, feature, model, n, i, o, cr, cw in rows:
        c = cost_usd(model, i or 0, o or 0, cr or 0, cw or 0)
        total += c
        print(f"  {name or '(no school)':35} {feature:12} {model:20} {n:6} calls  ${c:9.2f}")
    print(f"  {'TOTAL':35} {'':12} {'':20} {'':6}        ${total:9.2f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--month", help="YYYY-MM (default: this month)")
    asyncio.run(main(p.parse_args().month))
