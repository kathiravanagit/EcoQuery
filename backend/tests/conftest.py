"""Pytest configuration — patches server warmup so verifier tests are deterministic."""

import time
import os
import verifier

os.environ.setdefault("PUBLIC_DEMO_MODE", "true")

# Bump time past the 30s warmup so verification tests work deterministically
verifier.SERVER_START_TIME = time.time() - 60
