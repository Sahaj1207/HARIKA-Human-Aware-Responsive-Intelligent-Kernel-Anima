"""Settings > Activity: what HARIKA did, whether it needed a yes, and how it went."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.memory.activity import KEEP_DAYS, activity_log

router = APIRouter()


class ActivitySettings(BaseModel):
    keep: Optional[bool] = None


def _overview(days: int = 7, needed_approval: bool = False) -> dict:
    return {"keep": activity_log.keeping(), "keep_days": KEEP_DAYS,
            "entries": activity_log.entries(min(max(days, 1), KEEP_DAYS), needed_approval)}


@router.get("")
async def activity(days: int = 7, needed_approval: bool = False):
    return _overview(days, needed_approval)


@router.put("/settings")
async def update_activity_settings(settings: ActivitySettings):
    if settings.keep is not None:
        activity_log.set_keeping(settings.keep)
    return _overview()


@router.post("/clear")
async def clear_activity():
    activity_log.clear()
    return _overview()
