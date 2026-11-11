from dependencies import get_current_user
from fastapi import APIRouter, Depends

# Stub. Authenticated from the start so it isn't open when it gets built.
router = APIRouter(dependencies=[Depends(get_current_user)])
