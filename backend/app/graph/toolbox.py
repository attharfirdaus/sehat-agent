"""Satu-satunya tempat node mengambil tools (memudahkan mock di test)."""

from app.risk.features import age_years, build_features
from app.schemas import DiabetesFeatures, LatestValues, Profile
from app.tools.analytics import compute_trends
from app.tools.charts import build_chart_payload
from app.tools.data import get_profile, query_history, save_daily_log, save_measurement, today
from app.tools.knowledge import retrieve_guidelines
from app.tools.nutrition import estimate_meal_from_image
from app.tools.plan import get_active_plan, save_plan
from app.tools.risk import framingham_nonlab, guideline_flags, predict_diabetes
from app.tools.safety import red_flag_rules


async def diabetes_features(
    user_id: int, profile: Profile, latest: LatestValues
) -> DiabetesFeatures | None:
    """Fitur BRFSS (8.3); butuh rata-rata tekanan darah 30 hari untuk HighBP."""
    bp = await query_history(user_id, ["systolic", "diastolic"], 30)
    return build_features(
        profile,
        latest,
        age_years(profile.birth_date, today()),
        [r.values["systolic"] for r in bp.rows if r.values["systolic"] is not None],
        [r.values["diastolic"] for r in bp.rows if r.values["diastolic"] is not None],
    )


__all__ = [
    "build_chart_payload",
    "compute_trends",
    "diabetes_features",
    "estimate_meal_from_image",
    "framingham_nonlab",
    "get_active_plan",
    "get_profile",
    "guideline_flags",
    "predict_diabetes",
    "query_history",
    "red_flag_rules",
    "retrieve_guidelines",
    "save_daily_log",
    "save_measurement",
    "save_plan",
]
