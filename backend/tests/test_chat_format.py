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


def test_clean_response_enforces_plain_single_paragraph_limits():
    response = clean_response(
        "**Thermodynamics** is the study of energy.\n"
        "It examines heat and work. It applies to physical systems. "
        "It supports engineering. It explains engines. It informs design."
    )

    assert "**" not in response
    assert "\n" not in response
    assert len(response.split()) <= 60
    assert len(response.split(". ")) <= 4