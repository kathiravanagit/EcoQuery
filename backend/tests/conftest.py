"""Pytest configuration — patches server warmup so verifier tests are deterministic."""

import time
import verifier

# Bump time past the 30s warmup so verification tests work deterministically
verifier.SERVER_START_TIME = time.time() - 60
