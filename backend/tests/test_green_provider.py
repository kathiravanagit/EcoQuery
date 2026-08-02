"""
Tests for green_provider — miniature Bedrock/Vertex region selection.
"""

import pytest
from green_provider import GreenProviderRouter, PROVIDER_REGIONS


class TestGreenProviderRouter:
    def setup_method(self):
        self.router = GreenProviderRouter()

    def test_all_providers_have_regions(self):
        for pid, info in PROVIDER_REGIONS.items():
            assert "regions" in info
            assert len(info["regions"]) > 0

    def test_all_providers_have_greenest(self):
        for pid, info in PROVIDER_REGIONS.items():
            assert "greenest_region" in info
            assert info["greenest_region"] in info["regions"]

    def test_anthropic_greenest_is_us_west(self):
        assert PROVIDER_REGIONS["anthropic"]["greenest_region"] == "gcp-us-west1"

    def test_google_greenest_is_europe(self):
        assert PROVIDER_REGIONS["google"]["greenest_region"] == "gcp-europe-west1"

    def test_microsoft_greenest_is_us_west(self):
        assert PROVIDER_REGIONS["microsoft"]["greenest_region"] == "azure-westus2"

    def test_amazon_greenest_is_us_west(self):
        assert PROVIDER_REGIONS["amazon"]["greenest_region"] == "aws-us-west-2"

    def test_carbon_neutral_providers(self):
        neutral = [pid for pid, info in PROVIDER_REGIONS.items() if info["carbon_neutral"]]
        assert len(neutral) >= 4

    def test_renewable_pct_ranges(self):
        for pid, info in PROVIDER_REGIONS.items():
            assert 0 <= info["renewable_energy_pct"] <= 100

    def test_get_all_providers(self):
        providers = self.router.get_all_providers()
        assert len(providers) >= 8
        assert all("id" in p for p in providers)

    def test_green_model_exists(self):
        assert callable(self.router.get_green_model)
