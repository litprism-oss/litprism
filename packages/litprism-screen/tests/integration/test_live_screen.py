"""Integration tests — require a real LLM API key in the environment.

Run with:
    uv run pytest packages/litprism-screen/tests/integration/ -v -m integration
"""

import pytest

pytestmark = pytest.mark.integration
