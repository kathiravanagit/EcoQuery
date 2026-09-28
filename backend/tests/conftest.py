"""Pytest configuration — patches server warmup so verifier tests are deterministic."""

import os
import time
import verifier
from unittest.mock import AsyncMock, patch
import pytest
from rate_limit import rate_limiter

# /api/chat requires auth by default (DEFAULT_ALLOW_ANONYMOUS_CHAT is False).
# The handler/routing/cache suites below post to it anonymously because they
# are testing response behaviour, not the auth gate — so permit anonymous
# access for the whole run. The gate itself is asserted explicitly in
# test_chat_access_policy.py. Must be set before `from main import app`
# happens, since routers.chat reads it at import time.
os.environ.setdefault("ALLOW_ANONYMOUS_CHAT", "true")

# Bump time past the 30s warmup so verification tests work deterministically
verifier.SERVER_START_TIME = time.time() - 60


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.local.clear()
    yield
    rate_limiter.local.clear()


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
