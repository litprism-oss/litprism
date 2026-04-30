import pytest
from httpx import AsyncClient


@pytest.fixture
async def client():
    """HTTP client pointed at the live backend (http://localhost:8000)."""
    async with AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        yield c
