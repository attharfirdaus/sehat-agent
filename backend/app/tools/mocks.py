"""Mock tools dengan signature identik dengan app/tools/*. Data contoh, bukan hasil klinis.

Dipakai track lain selama tool asli belum ada (bagian 16). Test memastikan signature tetap sama.
"""

import base64
from datetime import UTC, date, datetime, timedelta

from app.schemas import (
    ChartPayload,
    DailyLogIn,
    DailyLogOut,
    DiabetesFeatures,
    DiabetesPrediction,
    Flag,
    FoodItem,
    FraminghamResult,
    HistoryRow,
    HistoryTable,
    LatestValues,
    MealEstimate,
    MeasurementIn,
    MeasurementOut,
    MeasurementValue,
    Metric,
    MetricTrend,
    Passage,
    Plan,
    PlanAction,
    PlanContent,
    PlanIn,
    PlanTarget,
    PlanWeek,
    Profile,
    RedFlag,
    SeriesPoint,
    ShapFactor,
    TrendReport,
)

_NOW = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
_TODAY = _NOW.date()
# PNG 1x1 transparan
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

SAMPLE_PROFILE = Profile(
    user_id=1,
    birth_date=date(2002, 5, 14),
    sex="male",
    height_cm=170.0,
    family_history_cvd=False,
    family_history_diabetes=True,
    dx_hypertension=False,
    dx_high_chol=False,
    dx_diabetes=False,
    bp_treated=False,
    smoker_lifetime_100=False,
    phys_activity_30d=True,
    fruits_daily=False,
    veggies_daily=True,
    heavy_alcohol=False,
    gen_health=2,
    diff_walk=False,
)

SAMPLE_FEATURES = DiabetesFeatures(
    HighBP=1,
    HighChol=0,
    BMI=26.5,
    Smoker=0,
    PhysActivity=1,
    Fruits=0,
    Veggies=1,
    HvyAlcoholConsump=0,
    GenHlth=2,
    DiffWalk=0,
    Sex=1,
    Age=3,
)

SAMPLE_LATEST = LatestValues(
    weight_kg=MeasurementValue(value=72.0, measured_at=_NOW - timedelta(days=3)),
    systolic=MeasurementValue(value=132.0, measured_at=_NOW - timedelta(days=1)),
    diastolic=MeasurementValue(value=84.0, measured_at=_NOW - timedelta(days=1)),
    resting_hr=MeasurementValue(value=78.0, measured_at=_NOW - timedelta(days=1)),
    avg_steps_7d=5200.0,
    avg_sleep_7d=5.8,
    smoked_days_7d=0,
)

SAMPLE_PLAN_CONTENT = PlanContent(
    weeks=[
        PlanWeek(
            range=f"minggu {i}",
            targets=[PlanTarget(metric="steps", target=6000 + 1000 * i)],
            actions=[
                PlanAction(
                    text="Jalan kaki 20 menit setelah makan siang.", citations=["WHO-PA-2020"]
                )
            ],
        )
        for i in range(1, 5)
    ]
)


def _trend(days: int) -> TrendReport:
    start = _TODAY - timedelta(days=days - 1)
    series = [
        SeriesPoint(date=start + timedelta(days=i), value=5000 + 100 * i) for i in range(days)
    ]
    return TrendReport(
        days=days,
        start=start,
        end=_TODAY,
        metrics={
            "steps": MetricTrend(
                mean=5300,
                min=5000,
                max=5600,
                delta=400,
                slope_per_day=100,
                n_obs=days,
                adherence_pct=57.0,
                series=series,
            ),
            "sleep_hours": MetricTrend(
                mean=5.8, min=5.0, max=6.5, delta=-0.6, slope_per_day=-0.1, n_obs=days
            ),
        },
    )


async def save_daily_log(user_id: int, log: DailyLogIn) -> DailyLogOut:
    return DailyLogOut(**log.model_dump(), id=1, user_id=user_id, created_at=_NOW)


async def save_measurement(user_id: int, m: MeasurementIn) -> MeasurementOut:
    return MeasurementOut(**m.model_dump(), id=1, user_id=user_id)


async def get_profile(user_id: int) -> Profile:
    return SAMPLE_PROFILE.model_copy(update={"user_id": user_id})


async def query_history(user_id: int, metrics: list[Metric], days: int = 7) -> HistoryTable:
    rows = [
        HistoryRow(
            date=_TODAY - timedelta(days=i),
            values={m: 6000.0 if m == "steps" else None for m in metrics},
        )
        for i in range(days)
    ]
    return HistoryTable(metrics=metrics, days=days, rows=rows)


async def compute_trends(user_id: int, days: int = 7) -> TrendReport:
    return _trend(days)


async def guideline_flags(profile: Profile, latest: LatestValues) -> list[Flag]:
    return [
        Flag(
            code="BP_STAGE1",
            severity="warn",
            metric="blood_pressure",
            value="132/84",
            threshold="130-139/80-89",
            source_id=None,
        ),
        Flag(
            code="SLEEP_SHORT",
            severity="info",
            metric="sleep_hours",
            value=5.8,
            threshold="<7",
            source_id=None,
        ),
    ]


async def framingham_nonlab(profile: Profile, latest: LatestValues) -> FraminghamResult:
    return FraminghamResult(applicable=False, reason="age_out_of_range")


async def predict_diabetes(features: DiabetesFeatures) -> DiabetesPrediction:
    return DiabetesPrediction(
        prob=0.18,
        band="moderate",
        top_factors=[
            ShapFactor(feature="BMI", value=features.BMI, shap=0.42, direction="increase"),
            ShapFactor(feature="HighBP", value=features.HighBP, shap=0.31, direction="increase"),
            ShapFactor(
                feature="PhysActivity",
                value=features.PhysActivity,
                shap=-0.12,
                direction="decrease",
            ),
        ],
        model_version="mock",
    )


async def retrieve_guidelines(query: str, k: int = 5, lang: str | None = None) -> list[Passage]:
    return [
        Passage(
            source_id="WHO-PA-2020",
            chunk_id=1,
            title="WHO guidelines on physical activity and sedentary behaviour",
            url="https://www.who.int/publications/i/item/9789240015128",
            publisher="WHO",
            year=2020,
            text="Contoh passage (mock).",
            score=0.82,
        )
    ][:k]


async def get_active_plan(user_id: int) -> Plan | None:
    return Plan(
        id=1,
        user_id=user_id,
        status="active",
        content=SAMPLE_PLAN_CONTENT,
        starts_on=_TODAY,
        created_at=_NOW,
    )


async def save_plan(user_id: int, plan: PlanIn) -> Plan:
    return Plan(**plan.model_dump(), id=1, user_id=user_id, created_at=_NOW)


async def estimate_meal_from_image(image_b64: str, note: str | None) -> MealEstimate:
    return MealEstimate(
        items=[
            FoodItem(name="nasi putih", portion="1 piring", kcal_low=180, kcal_high=260),
            FoodItem(name="ayam goreng", portion="1 potong paha", kcal_low=220, kcal_high=320),
        ],
        confidence="medium",
        caveats=["Minyak goreng tidak terlihat di foto."],
    )


async def red_flag_rules(latest: LatestValues, user_text: str) -> list[RedFlag]:
    return []


async def build_chart_payload(trends: TrendReport) -> ChartPayload:
    rows: dict[str, dict[str, float | str | None]] = {}
    for metric, t in trends.metrics.items():
        for p in t.series:
            rows.setdefault(p.date.isoformat(), {"date": p.date.isoformat()})[metric] = p.value
    return ChartPayload(series=list(trends.metrics), data=list(rows.values()))


async def render_chart_png(trends: TrendReport) -> bytes:
    return _PNG
