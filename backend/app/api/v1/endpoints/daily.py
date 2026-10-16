"""Settings > General > Daily: home city for weather and the morning briefing."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.endpoints.llm_settings import local_only
from app.core.daily_settings import daily_settings

router = APIRouter(dependencies=[Depends(local_only)])


class DailySettingsUpdate(BaseModel):
    home: str | None = None
    briefing_enabled: bool | None = None
    briefing_time: str | None = None


@router.get("")
async def get_daily_settings() -> dict:
    return daily_settings.load()


@router.put("")
async def update_daily_settings(update: DailySettingsUpdate) -> dict:
    try:
        return daily_settings.update(**update.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
