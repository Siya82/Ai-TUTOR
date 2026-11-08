"""
RECOVERY NOTE: this file was NEVER read verbatim — only described in
docs/BUILD_LOG.md as "async SQLAlchemy engine/session (asyncpg), so DB
calls don't block while the API is also awaiting Claude API calls in the
same request". This is a best-effort RECONSTRUCTION, not recovered code.

Per later project memory, a Windows-specific fix was added here: a
`sys.modules` check that scopes `NullPool` to pytest specifically (paired
with a `WindowsSelectorEventLoopPolicy` enforced in `conftest.py`) to work
around an asyncpg-on-Windows event-loop issue under test. That fix is
sketched below but should be verified/corrected against your own memory
of the actual implementation.
"""

import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine_kwargs = {}
if "pytest" in sys.modules:
    # Windows + asyncpg + the default pool can deadlock under pytest-asyncio's
    # event loop handling — NullPool sidesteps connection reuse across loops.
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with async_session_factory() as session:
        yield session
