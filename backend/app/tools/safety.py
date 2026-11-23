from app.safety.rules import evaluate
from app.schemas import LatestValues, RedFlag


async def red_flag_rules(latest: LatestValues, user_text: str) -> list[RedFlag]:
    """Deteksi red flag deterministik: ambang angka + keyword gejala (bagian 13). Tanpa LLM."""
    return evaluate(latest, user_text)
