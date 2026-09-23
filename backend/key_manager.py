"""Provider-key access without persisting provider secrets locally.

Provider credentials are supplied through environment variables only. Runtime
state such as disabled keys is intentionally process-local and disposable.
"""

import logging
import os
import uuid

logger = logging.getLogger("EcoQuery.key_manager")


class KeyManager:
    def __init__(self):
        self._inactive: set[str] = set()

    def _configured_keys(self) -> list[dict]:
        values = {
            "openrouter": [os.getenv("OPENROUTER_API_KEY", ""), os.getenv("OPENROUTER_API_KEY_2", "")],
            "grok": [os.getenv("GROK_API_KEY", "")],
            "google": [os.getenv("GOOGLE_API_KEY", "")],
        }
        keys = []
        for provider, provider_keys in values.items():
            for value in provider_keys:
                if value:
                    key_id = f"{provider}:{uuid.uuid5(uuid.NAMESPACE_URL, value)}"
                    if key_id not in self._inactive:
                        keys.append({"id": key_id, "key_value": value, "provider": provider})
        return keys

    def get_active_keys(self, provider: str | None = None) -> list[dict]:
        return [k for k in self._configured_keys() if provider is None or k["provider"] == provider]

    def get_all_providers_keys(self) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = {}
        for key in self.get_active_keys():
            grouped.setdefault(key["provider"], []).append(key)
        return grouped

    def mark_key_inactive(self, key_id: str):
        self._inactive.add(key_id)

    def log_usage(self, key_id: str, provider: str, model: str, tokens: int, status: str):
        logger.info("provider=%s model=%s key=%s status=%s tokens=%s", provider, model, key_id[:12], status, tokens)


key_manager = KeyManager()
