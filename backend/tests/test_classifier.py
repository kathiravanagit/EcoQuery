"""Tests for classifier.py — query tier classification logic."""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["ECO_QUERY_TESTING"] = "1"

import pytest
from classifier import classifier


def _classify_sync(msg: str):
    return asyncio.run(classifier.classify(msg))


def test_simple_query():
    result = _classify_sync("Hello")
    assert result["tier"] in ("simple", "medium", "complex")
    assert "confidence" in result
    assert "method" in result


def test_complex_query():
    result = _classify_sync("Write a detailed analysis of carbon emissions across different data center regions, considering grid intensity variations throughout the day")
    assert result["tier"] in ("simple", "medium", "complex")
    assert result["method"] in ("simple-rules", "heuristic")


def test_empty_query():
    result = _classify_sync("Hi")
    assert result["tier"] in ("simple", "medium", "complex")


def test_classifier_structure():
    result = _classify_sync("Test")
    expected_keys = {"tier", "confidence", "method"}
    assert expected_keys.issubset(result.keys())


def test_reasoning_query_detected():
    result = _classify_sync("Explain how quantum entanglement works and compare it to classical computing")
    assert result["tier"] in ("medium", "complex")


def test_code_query_detected():
    result = _classify_sync("Write a Python function that implements merge sort with O(n log n) complexity")
    assert result["tier"] in ("medium", "complex")


def test_very_long_query_is_complex():
    result = _classify_sync("word " * 100)
    assert result["tier"] == "complex"


def test_code_snippet_is_complex():
    result = _classify_sync("def fibonacci(n):\n    if n <= 1: return n\n    return fibonacci(n-1) + fibonacci(n-2)")
    assert result["tier"] == "complex"
    assert result["confidence"] in (0.8, 0.75)


def test_import_statement_detected():
    result = _classify_sync("import numpy as np; import pandas as pd")
    assert result["tier"] == "complex"


def test_math_symbols_detected():
    result = _classify_sync("Solve ∫x² dx from 0 to 1")
    assert result["tier"] == "complex"


def test_short_reasoning_query():
    result = _classify_sync("Why is the sky blue?")
    assert result["tier"] in ("medium", "complex")


def test_one_word_greeting():
    result = _classify_sync("hi")
    assert result["tier"] == "simple"
    assert result["confidence"] >= 0.7
