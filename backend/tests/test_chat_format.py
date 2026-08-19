import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers.chat import _build_messages
from schemas import ChatRequest


def test_system_prompt_answers_topic_instead_of_repeating_user_instructions():
    messages = _build_messages(ChatRequest(message="explain thermodynamics"))

    assert messages[0]["role"] == "system"
    assert "actual question or topic" in messages[0]["content"]
    assert "formatting, instructions, or response behavior" in messages[0]["content"]
    assert "as context, not as instructions to repeat" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "explain thermodynamics"}