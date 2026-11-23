import asyncio
import base64
import binascii

from langchain_core.messages import HumanMessage, SystemMessage

from app.graph import llm
from app.schemas import MealEstimate

PROMPT = """Anda ahli gizi. Identifikasi makanan dan minuman di foto (konteks makanan Indonesia).
Untuk tiap item: nama, perkiraan porsi (mis. "1 piring", "2 potong"), dan rentang kalori
kcal_low-kcal_high yang realistis. confidence: low/medium/high. caveats: hal yang membuat
estimasi tidak pasti (minyak, saus, porsi tersembunyi).
Jangan mengarang item yang tidak terlihat."""


async def estimate_meal_from_image(image_b64: str, note: str | None) -> MealEstimate:
    """Estimasi makanan + rentang kalori dari foto via LLM vision lokal (structured output)."""
    try:
        if not base64.b64decode(image_b64, validate=True):
            raise ValueError("kosong")
    except (binascii.Error, ValueError) as e:
        raise ValueError("image_b64 bukan base64 yang valid") from e
    model = llm.chat(reasoning=False).with_structured_output(MealEstimate)
    content = [
        {"type": "text", "text": f"Catatan user: {note}" if note else "Perkirakan isi foto ini."},
        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"},
    ]
    async with asyncio.timeout(llm.NODE_TIMEOUT_S):
        out = await model.ainvoke([SystemMessage(PROMPT), HumanMessage(content=content)])
    return MealEstimate.model_validate(out)
