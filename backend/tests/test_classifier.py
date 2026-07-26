import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["ECO_QUERY_TESTING"] = "1"

import pytest
from unittest.mock import patch
from classifier import classifier

@pytest.fixture(autouse=True)
def prevent_model_load():
    with patch.object(classifier, "_load_model", return_value=None):
        classifier._pipeline = None
        yield

def test_simple_query():
    result = classifier.classify("Hello")
    assert result["tier"] in ("simple", "medium", "complex")
    assert "confidence" in result
    assert "method" in result

def test_complex_query():
    result = classifier.classify("Write a detailed analysis of carbon emissions across different data center regions, considering grid intensity variations throughout the day")
    assert result["tier"] in ("simple", "medium", "complex")
    assert result["method"] in ("distil-bert", "heuristic")

def test_empty_query():
    result = classifier.classify("Hi")
    assert result["tier"] in ("simple", "medium", "complex")

def test_classifier_structure():
    result = classifier.classify("Test")
    expected_keys = {"tier", "confidence", "method"}
    assert expected_keys.issubset(result.keys())
