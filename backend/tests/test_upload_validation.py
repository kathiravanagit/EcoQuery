import base64

import pytest
from pydantic import ValidationError

from schemas import ChatRequest


def _encoded(value: bytes) -> str:
    return base64.b64encode(value).decode()


def test_chat_accepts_supported_image_signatures():
    for image in (
        b"\x89PNG\r\n\x1a\npayload",
        b"\xff\xd8\xffpayload",
        b"RIFFsizeWEBPpayload",
    ):
        request = ChatRequest(message="describe", images=[_encoded(image)])
        assert request.images


def test_chat_rejects_non_image_upload_data():
    with pytest.raises(ValidationError, match="Only PNG"):
        ChatRequest(message="describe", images=[_encoded(b"not an executable")])


def test_chat_rejects_malformed_base64():
    with pytest.raises(ValidationError, match="base64"):
        ChatRequest(message="describe", images=["not base64!"])
