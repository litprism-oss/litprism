from db.models import SearchRun
from sqlalchemy.ext.asyncio import AsyncSession


async def run_search(search_run: SearchRun, db: AsyncSession) -> None:
    """Execute all source queries for a search run and persist results."""
    raise NotImplementedError
