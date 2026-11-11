from dataclasses import asdict

from dependencies import CurrentUser
from fastapi import APIRouter

from api.schemas import MeOut

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
async def get_me(user: CurrentUser) -> MeOut:
    return MeOut(**asdict(user))
