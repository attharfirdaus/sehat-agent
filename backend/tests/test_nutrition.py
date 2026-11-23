import base64
from typing import Any

import pytest

from app.graph import llm
from app.schemas import MealEstimate
from app.tools import mocks, nutrition


class FakeVision:
    """Pengganti ChatOllama: merekam pesan dan mengembalikan estimasi contoh."""

    def __init__(self) -> None:
        self.messages: list[Any] = []

    def with_structured_output(self, schema: type) -> "FakeVision":
        assert schema is MealEstimate
        return self

    async def ainvoke(self, messages: list[Any]) -> MealEstimate:
        self.messages = messages
        return await mocks.estimate_meal_from_image("", None)


def test_estimate_meal_sends_image(monkeypatch: pytest.MonkeyPatch, run: Any) -> None:
    fake = FakeVision()
    monkeypatch.setattr(llm, "chat", lambda reasoning: fake)
    image = base64.b64encode(b"\xff\xd8jpeg").decode()
    out = run(nutrition.estimate_meal_from_image, image, "nasi padang")
    assert out.items[0].name == "nasi putih"
    blocks = fake.messages[1].content
    assert blocks[0]["text"] == "Catatan user: nasi padang"
    assert blocks[1]["image_url"] == f"data:image/jpeg;base64,{image}"


def test_estimate_meal_rejects_invalid_base64(run: Any) -> None:
    with pytest.raises(ValueError, match="base64"):
        run(nutrition.estimate_meal_from_image, "bukan base64!!", None)
