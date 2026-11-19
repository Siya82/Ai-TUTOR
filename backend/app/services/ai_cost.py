"""
NEW 20 Nov 2026 (deep scan H5). What AI use costs, from the token counts in
ai_usage. Prices are US dollars per million tokens (input, output, cache
read, cache write) -- update this table when Anthropic's prices change.
Checked 20 Nov 2026: Sonnet 4.6 $3 / $15, cached input $0.30, 5-minute
cache write $3.75; Haiku 4.5 $1 / $5.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.models import AiUsage

PRICES = {
    "claude-sonnet-4-6": (3.00, 15.00, 0.30, 3.75),
    "claude-haiku-4-5": (1.00, 5.00, 0.10, 1.25),
}
DEFAULT_PRICE = PRICES["claude-sonnet-4-6"]  # unknown model: assume the dearer one


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    p_in, p_out, p_read, p_write = PRICES.get(model, DEFAULT_PRICE)
    return (input_tokens * p_in + output_tokens * p_out + cache_read * p_read + cache_write * p_write) / 1_000_000


def month_start(now: datetime | None = None) -> datetime:
    now = now or utcnow_naive()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def school_month(db: AsyncSession, school_id: uuid.UUID, now: datetime | None = None) -> dict:
    """This month's AI use for one school: calls, tokens and cost, by feature."""
    rows = (
        await db.execute(
            select(
                AiUsage.feature,
                AiUsage.model,
                func.count(),
                func.sum(AiUsage.input_tokens),
                func.sum(AiUsage.output_tokens),
                func.sum(AiUsage.cache_read_tokens),
                func.sum(AiUsage.cache_write_tokens),
            )
            .where(AiUsage.school_id == school_id, AiUsage.created_at >= month_start(now))
            .group_by(AiUsage.feature, AiUsage.model)
        )
    ).all()
    by_feature: dict[str, dict] = {}
    total = 0.0
    for feature, model, n, i, o, cr, cw in rows:
        c = cost_usd(model, i or 0, o or 0, cr or 0, cw or 0)
        f = by_feature.setdefault(feature, {"calls": 0, "cost_usd": 0.0})
        f["calls"] += n
        f["cost_usd"] += c
        total += c
    for f in by_feature.values():
        f["cost_usd"] = round(f["cost_usd"], 4)
    return {"since": month_start(now).isoformat(), "by_feature": by_feature, "cost_usd": round(total, 4)}


def usage_recorder(db: AsyncSession, *, school_id, user_id, feature: str):
    """An on_usage callback for TutorClient.ask that adds an AiUsage row to `db`."""

    def record(u: dict) -> None:
        db.add(
            AiUsage(
                school_id=school_id,
                user_id=user_id,
                feature=feature,
                model=u["model"],
                input_tokens=u["input_tokens"],
                output_tokens=u["output_tokens"],
                cache_read_tokens=u["cache_read_tokens"],
                cache_write_tokens=u["cache_write_tokens"],
            )
        )

    return record
