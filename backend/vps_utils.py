"""
Shared utilities for EcoQuery backend.
"""

import os


def parse_vps_endpoints() -> list:
    """Parse OLLAMA_ENDPOINTS env var into list of {url, region} dicts.
    
    Format: http://ip1:11434:region1,http://ip2:11434:region2
    Example: http://1.2.3.4:11434:eu-north-1,http://5.6.7.8:11434:eu-west-3
    
    Falls back to OLLAMA_BASE_URL + OLLAMA_REGION if OLLAMA_ENDPOINTS is not set.
    """
    raw = os.getenv("OLLAMA_ENDPOINTS", "")
    if not raw:
        url = os.getenv("OLLAMA_BASE_URL", "")
        region = os.getenv("OLLAMA_REGION", "eu-north-1")
        if url:
            return [{"url": url.rstrip("/"), "region": region}]
        return []

    endpoints = []
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            parts = part.rsplit(":", 1)
            if len(parts) == 2:
                url, region = parts
                endpoints.append({"url": url.rstrip("/"), "region": region})
    return endpoints
