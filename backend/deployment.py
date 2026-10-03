"""Deployment metadata shared by health checks and observability."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _git_version() -> str:
    try:
        repo = Path(__file__).resolve().parent
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        revision = result.stdout.strip()
        if result.returncode == 0 and revision:
            return revision
    except (OSError, subprocess.SubprocessError):
        pass
    return "unavailable"


def deployment_version() -> str:
    """Return a stable source revision, never a misleading ``dev`` in prod."""
    configured = (os.getenv("APP_VERSION") or "").strip()
    if configured and configured.lower() not in {"dev", "development", "unknown"}:
        return configured

    for name in ("RENDER_GIT_COMMIT", "RENDER_GIT_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value

    return _git_version()
