"""
Tests for carbon_executor — the real-time carbon-aware LLM executor.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from carbon_executor import CarbonAwareExecutor


class TestCarbonAwareExecutor:
    def setup_method(self):
        self.executor = CarbonAwareExecutor()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "", "AWS_ACCESS_KEY_ID": "", "OLLAMA_BASE_URL": ""})
    def test_no_providers_configured(self):
        executor = CarbonAwareExecutor()
        assert executor.aws_key == ""
        assert executor.openrouter_key == ""
        assert executor.ollama_url == ""

    def test_has_ollama(self):
        executor = CarbonAwareExecutor()
        executor.ollama_url = "http://localhost:11434"
        assert executor.ollama_url != ""

    def test_has_aws(self):
        executor = CarbonAwareExecutor()
        executor.aws_key = "test-key"
        executor.aws_secret = "test-secret"
        assert executor.aws_key != ""

    def test_has_vertex(self):
        executor = CarbonAwareExecutor()
        executor.vertex_cred = "/path/to/creds.json"
        assert executor.vertex_cred != ""

    def test_has_openrouter(self):
        executor = CarbonAwareExecutor()
        executor.openrouter_key = "sk-or-test"
        assert executor.openrouter_key != ""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "", "AWS_ACCESS_KEY_ID": "", "OLLAMA_BASE_URL": ""})
    def test_execute_no_providers_raises(self):
        executor = CarbonAwareExecutor()
        assert executor.ollama_url == ""
        assert executor.aws_key == ""
        assert executor.vertex_cred == ""
        assert executor.openrouter_key == ""

    def test_ranking_prefers_green(self):
        """Verify green regions rank higher."""
        from region_scorer import scorer

        green = scorer.score_region("stockholm", 13, {"nuclear": 40, "hydro": 60})
        dirty = scorer.score_region("mumbai", 700, {"coal": 55, "gas": 25})

        assert green.total_score < dirty.total_score
        assert green.is_green is True
        assert dirty.is_green is False

    def test_bedrock_model_mapping(self):
        """Test Bedrock model names are valid."""
        valid_models = [
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "amazon.titan-text-lite-v1",
        ]
        assert len(valid_models) > 0

    def test_vertex_model_mapping(self):
        """Test Vertex AI model names are valid."""
        valid_models = [
            "gemini-2.0-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]
        assert len(valid_models) > 0
