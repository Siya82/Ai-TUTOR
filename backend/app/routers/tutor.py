"""
STEP-2 PLACEHOLDER -- not the real tutor router.

app/main.py imports `app.routers.tutor`, but the real tutor.py /
tutor_orchestration.py / personalization.py / diagnosis.py modules are
scheduled to be rebuilt from REBUILD_SPEC.md Section 1 in the NEXT phase
of this rebuild (step 2), not this one. This stub exists only so the app
can import cleanly and boot far enough for /health to prove the database
connection works. Replace this file entirely in step 2 -- nothing here
should be mistaken for recovered or real logic.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping() -> dict:
    return {"status": "placeholder -- real tutor router not yet rebuilt (see REBUILD_SPEC.md)"}
