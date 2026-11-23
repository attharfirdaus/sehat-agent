import asyncio
import inspect
from datetime import UTC, date, datetime

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.schemas import (
    Assessment,
    ClarifyPayload,
    ClinicianDecision,
    ClinicianReviewPayload,
    ConfirmLogPayload,
    ConfirmLogResume,
    ConfirmMealPayload,
    ConfirmMealResume,
    DailyLogIn,
    DiabetesFeatures,
    FoodItem,
    InterruptPayload,
    MeasurementIn,
    PlanIn,
)
from app.tools import analytics, charts, data, knowledge, mocks, nutrition, plan, risk, safety

TOOL_MODULES = [data, analytics, risk, knowledge, plan, nutrition, safety, charts]
TOOLS = [
    f
    for m in TOOL_MODULES
    for _, f in inspect.getmembers(m, inspect.iscoroutinefunction)
    if f.__module__ == m.__name__
]

LOG = DailyLogIn(log_date=date(2026, 11, 17), steps=6000, sleep_hours=5.0, source="web")
MEAS = MeasurementIn(kind="systolic", value=128, measured_at=datetime(2026, 11, 17, tzinfo=UTC))
FEAT = DiabetesFeatures(
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


def roundtrip(obj: object) -> None:
    if isinstance(obj, list):
        for o in obj:
            roundtrip(o)
    elif isinstance(obj, BaseModel):
        assert type(obj).model_validate_json(obj.model_dump_json()) == obj


def test_every_tool_has_mock_with_same_signature() -> None:
    assert len(TOOLS) == 15  # jumlah tool di PRD bagian 7
    for f in TOOLS:
        mock = getattr(mocks, f.__name__)
        assert inspect.signature(mock) == inspect.signature(f), f.__name__
        assert f.__doc__


def test_stubs_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        asyncio.run(charts.render_chart_png(asyncio.run(mocks.compute_trends(1))))


def test_mock_outputs_roundtrip() -> None:
    async def run() -> list[object]:
        profile = await mocks.get_profile(1)
        latest = mocks.SAMPLE_LATEST
        trends = await mocks.compute_trends(1, 7)
        return [
            await mocks.save_daily_log(1, LOG),
            await mocks.save_measurement(1, MEAS),
            profile,
            await mocks.query_history(1, ["steps", "smoked"], 7),
            trends,
            await mocks.guideline_flags(profile, latest),
            await mocks.framingham_nonlab(profile, latest),
            await mocks.predict_diabetes(FEAT),
            await mocks.retrieve_guidelines("aktivitas fisik"),
            await mocks.get_active_plan(1),
            await mocks.save_plan(
                1, PlanIn(content=mocks.SAMPLE_PLAN_CONTENT, starts_on=date(2026, 11, 17))
            ),
            await mocks.estimate_meal_from_image("", None),
            await mocks.red_flag_rules(latest, "halo"),
            await mocks.build_chart_payload(trends),
            latest,
        ]

    for out in asyncio.run(run()):
        roundtrip(out)
    assert asyncio.run(mocks.render_chart_png(asyncio.run(mocks.compute_trends(1)))).startswith(
        b"\x89PNG"
    )


def test_interrupt_payloads_discriminated() -> None:
    async def build() -> list[BaseModel]:
        p = await mocks.get_active_plan(1)
        assert p is not None
        profile, latest = mocks.SAMPLE_PROFILE, mocks.SAMPLE_LATEST
        assessment = Assessment(
            flags=await mocks.guideline_flags(profile, latest),
            framingham=await mocks.framingham_nonlab(profile, latest),
            diabetes=await mocks.predict_diabetes(FEAT),
            trends=await mocks.compute_trends(1),
        )
        return [
            ClarifyPayload(question="Tidur berapa jam?", missing=["sleep_hours"]),
            ConfirmLogPayload(log=LOG, measurements=[MEAS]),
            ConfirmMealPayload(estimate=await mocks.estimate_meal_from_image("", None)),
            ClinicianReviewPayload(review_id=1, plan=p, assessment=assessment),
        ]

    ta: TypeAdapter[object] = TypeAdapter(InterruptPayload)
    for payload in asyncio.run(build()):
        assert ta.validate_json(payload.model_dump_json()) == payload


def test_resume_validation() -> None:
    ConfirmLogResume(action="confirm")
    ConfirmMealResume(
        action="edit", items=[FoodItem(name="x", portion="1", kcal_low=1, kcal_high=2)]
    )
    for bad in (
        lambda: ConfirmLogResume(action="edit"),
        lambda: ConfirmMealResume(action="edit"),
        lambda: ClinicianDecision(decision="edit"),
        lambda: FoodItem(name="x", portion="1", kcal_low=5, kcal_high=1),
        lambda: DiabetesFeatures(**{**FEAT.model_dump(), "Age": 14}),
    ):
        with pytest.raises(ValidationError):
            bad()
