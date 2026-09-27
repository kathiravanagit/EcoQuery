"""Pytest configuration — patches server warmup so verifier tests are deterministic."""

import time
import verifier
from unittest.mock import AsyncMock, patch
import pytest

# Bump time past the 30s warmup so verification tests work deterministically
verifier.SERVER_START_TIME = time.time() - 60


@pytest.fixture(autouse=True)
def mock_external_providers():
    provider_response = {
        "content": "Test provider response",
        "usage": {"prompt_tokens": 5, "completion_tokens": 4},
        "provider_lineage": {
            "requested_provider": "test",
            "requested_model": "test-model",
            "attempted_providers": [{"provider": "test", "model": "test-model", "status": "success"}],
            "final_provider": "test",
            "final_model": "test-model",
            "fallback_reason": None,
            "success": True,
        },
    }

    async def mock_stream(*args, **kwargs):
        yield {"token": "Test provider response"}
        yield {"provider_lineage": provider_response["provider_lineage"]}

    with patch("providers.provider_router.chat_completion", new=AsyncMock(return_value=provider_response)), \
         patch("providers.provider_router.stream_completion", new=mock_stream):
        yield
