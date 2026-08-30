import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers.chat import _build_messages, clean_response
from schemas import ChatRequest


def test_system_prompt_answers_topic_instead_of_repeating_user_instructions():
    messages = _build_messages(ChatRequest(message="explain thermodynamics"))

    assert messages[0]["role"] == "system"
    assert "actual question or topic" in messages[0]["content"]
    assert "formatting, instructions, or response behavior" in messages[0]["content"]
    assert "as context, not as instructions to repeat" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "explain thermodynamics"}


def test_clean_response_enforces_150_words_and_strips_hashes():
    response = clean_response(
        "## Thermodynamics\n"
        "Thermodynamics is the branch of physics that deals with heat, work, and temperature, "
        "and their relation to energy, radiation, and physical properties of matter."
    )

    assert "##" not in response
    assert "Thermodynamics is the branch" in response
    assert len(response.split()) <= 150


def test_clean_response_preserves_code_blocks():
    code_input = (
        "Here is the binary search algorithm:\n"
        "```python\ndef binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    return -1\n```"
    )
    res = clean_response(code_input)
    assert "```python" in res
    assert "def binary_search" in res