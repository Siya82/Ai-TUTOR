"""
NEW 20 Nov 2026 (deep scan H4). The frontend reports screen crashes here so
they reach the server log (and Cloud Error Reporting) instead of dying in a
learner's browser console. No login needed -- a crash can happen before
sign-in -- so it's limited per address and per day, and only the error text
and component stack are kept (never page content or learner input).
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import rate_limit

router = APIRouter()
log = logging.getLogger("thutora.client")


class ClientErrorIn(BaseModel):
    message: str = Field(max_length=500)
    stack: str = Field(default="", max_length=4000)
    path: str = Field(default="", max_length=200)


@router.post("/client-errors", status_code=204)
async def report_client_error(body: ClientErrorIn, request: Request, db: AsyncSession = Depends(get_db)) -> None:
    ip = request.client.host if request.client else "-"
    key = f"client-error:{ip}"
    if await rate_limit.too_many(db, key, limit=20, window_seconds=3600):
        return None  # quietly drop: a crash loop shouldn't flood the log
    await rate_limit.hit(db, key)
    await db.commit()
    log.error("Frontend error on %s: %s\n%s", body.path, body.message, body.stack)
    return None
