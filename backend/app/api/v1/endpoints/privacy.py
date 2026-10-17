"""Settings > Privacy."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.v1.endpoints.llm_settings import local_only
from app.core.privacy import privacy_settings

router = APIRouter(dependencies=[Depends(local_only)])


class PrivacyUpdate(BaseModel):
    screen_images: bool | None = None


@router.get("")
async def get_privacy() -> dict:
    from app.vision.screen import vision_chain
    return {**privacy_settings.load(), "vision_services": [c["service"] for c in vision_chain()]}


@router.put("")
async def update_privacy(update: PrivacyUpdate) -> dict:
    privacy_settings.update(**update.model_dump(exclude_none=True))
    return await get_privacy()
