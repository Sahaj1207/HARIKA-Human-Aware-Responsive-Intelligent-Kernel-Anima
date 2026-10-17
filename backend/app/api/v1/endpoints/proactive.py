"""Settings > General > Heads-up: what HARIKA may tell you about on its own."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.endpoints.llm_settings import local_only
from app.services.proactive import proactive_settings

router = APIRouter(dependencies=[Depends(local_only)])


class ProactiveUpdate(BaseModel):
    meetings: bool | None = None
    meeting_minutes: int | None = None
    birthdays: bool | None = None
    battery: bool | None = None
    battery_percent: int | None = None


@router.get("")
async def get_proactive_settings() -> dict:
    return proactive_settings.load()


@router.put("")
async def update_proactive_settings(update: ProactiveUpdate) -> dict:
    return proactive_settings.update(**update.model_dump(exclude_none=True))
