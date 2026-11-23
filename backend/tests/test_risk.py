"""Risk tools (bagian 7-8): kasus normal, batas ambang, input kosong."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.risk import features as feat
from app.risk.framingham import risk_10y_pct
from app.schemas import (
    DailyLogIn,
    LatestValues,
    MeasurementIn,
    MeasurementValue,
    PlanContent,
    PlanIn,
    PlanTarget,
    PlanWeek,
    Profile,
)
from app.tools import analytics, data, plan, risk
from app.tools.mocks import SAMPLE_FEATURES
from ml import train_diabetes
from tests.test_graph import make_user

NOW = datetime.now(UTC)


def mv(value: float, days_ago: int = 1) -> MeasurementValue:
    return MeasurementValue(value=value, measured_at=NOW - timedelta(days=days_ago))


def profile(age: int = 40, **kw: Any) -> Profile:
    born = data.today().replace(year=data.today().year - age) - timedelta(days=1)
    return Profile(user_id=1, birth_date=born, sex=kw.pop("sex", "male"), height_cm=170, **kw)


def codes(latest: LatestValues, **kw: Any) -> dict[str, Any]:
    import asyncio

    return {f.code: f for f in asyncio.run(risk.guideline_flags(profile(**kw), latest))}


def test_framingham_matches_cvrisk_example() -> None:
    # Contoh dokumentasi CVrisk::ascvd_10y_frs_simple: hasil 16.7 (%).
    assert risk_10y_pct("male", 55, 30, 140, False, False, False) == pytest.approx(16.7, abs=0.06)
    assert risk_10y_pct("male", 55, 30, 140, True, True, True) > 16.75  # faktor menaikkan risiko


@pytest.mark.parametrize("age", [25, 29, 75, 80])
def test_framingham_age_gate(age: int, run: Any) -> None:
    latest = LatestValues(weight_kg=mv(80), systolic=mv(130))
    r = run(risk.framingham_nonlab, profile(age), latest)
    assert (r.applicable, r.reason, r.risk_10y_pct) == (False, "age_out_of_range", None)


def test_framingham_applicable_and_missing(run: Any) -> None:
    r = run(risk.framingham_nonlab, profile(55), LatestValues(weight_kg=mv(86.7), systolic=mv(140)))
    assert r.applicable and r.category == "intermediate" and 10 <= r.risk_10y_pct < 20
    assert run(risk.framingham_nonlab, profile(55), LatestValues()).reason == "missing_weight"


@pytest.mark.parametrize(
    ("sys_", "dia", "code", "severity"),
    [
        (119, 79, None, None),
        (129, 79, "BP_ELEVATED", "info"),
        (130, 70, "BP_STAGE1", "warn"),
        (118, 80, "BP_STAGE1", "warn"),
        (139, 89, "BP_STAGE1", "warn"),
        (140, 70, "BP_STAGE2", "warn"),
        (120, 90, "BP_STAGE2", "warn"),
        (180, 100, "BP_CRISIS", "urgent"),
        (150, 120, "BP_CRISIS", "urgent"),
    ],
)
def test_bp_thresholds(sys_: int, dia: int, code: str | None, severity: str | None) -> None:
    flags = codes(LatestValues(systolic=mv(sys_), diastolic=mv(dia)))
    bp = [f for f in flags.values() if f.metric == "blood_pressure"]
    assert [(f.code, f.severity) for f in bp] == ([(code, severity)] if code else [])


def test_stale_measurement_never_urgent() -> None:
    f = codes(LatestValues(systolic=mv(190, 120), diastolic=mv(100, 120)))["BP_CRISIS"]
    assert f.stale and f.severity == "warn"


@pytest.mark.parametrize(
    ("weight", "code"),
    [
        (53.4, "BMI_UNDERWEIGHT"),
        (53.5, None),
        (66.2, None),
        (66.5, "BMI_OVERWEIGHT"),
        (72.3, "BMI_OBESE"),
    ],
)
def test_bmi_asia_pacific(weight: float, code: str | None) -> None:
    got = [c for c in codes(LatestValues(weight_kg=mv(weight))) if c.startswith("BMI")]
    assert got == ([code] if code else [])


def test_other_flags_and_boundaries() -> None:
    assert codes(LatestValues()) == {}
    f = codes(
        LatestValues(
            avg_sleep_7d=6.9, cholesterol_total=mv(200), resting_hr=mv(101), smoked_days_7d=2
        ),
        phys_activity_30d=False,
    )
    assert set(f) == {"SLEEP_SHORT", "CHOL_BORDERLINE", "RHR_HIGH", "SMOKING", "PA_NONE"}
    assert f["SMOKING"].source_id == "WHO-FS-TOB"
    edge = codes(
        LatestValues(
            avg_sleep_7d=7, cholesterol_total=mv(199), resting_hr=mv(100), smoked_days_7d=0
        )
    )
    assert edge == {}
    assert "CHOL_HIGH" in codes(LatestValues(cholesterol_total=mv(240)))


def test_features_mapping() -> None:
    assert [feat.age_category(a) for a in (18, 24, 25, 30, 74, 75, 80, 95)] == [
        1,
        1,
        2,
        3,
        11,
        12,
        13,
        13,
    ]
    p = profile(40, dx_hypertension=False, smoker_lifetime_100=True, gen_health=None)
    assert feat.build_features(p, LatestValues(), 40, [], []) is None
    f = feat.build_features(p, LatestValues(weight_kg=mv(80)), 40, [131, 129], [70])
    assert (f.HighBP, f.Smoker, f.GenHlth, f.BMI, f.Age, f.Sex) == (1, 1, 3, 27.7, 5, 1)
    f = feat.build_features(
        p, LatestValues(weight_kg=mv(80), cholesterol_total=mv(240)), 40, [120], [75]
    )
    assert (f.HighBP, f.HighChol) == (0, 1)


@pytest.fixture
def tiny_model(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Model kecil dari data sintetis supaya test tidak bergantung pada `make train`."""
    rng = np.random.default_rng(0)
    n = 600
    X = pd.DataFrame({f: rng.integers(0, 2, n) for f in train_diabetes.FEATURES})
    X["BMI"], X["GenHlth"], X["Age"] = (
        rng.normal(28, 5, n),
        rng.integers(1, 6, n),
        rng.integers(1, 14, n),
    )
    y = pd.Series(((X["BMI"] > 30) | (X["HighBP"] == 1)).astype(int))
    import joblib

    path = tmp_path / "m.joblib"
    joblib.dump(train_diabetes.train(X, y, cv_folds=2), path)
    path.with_suffix(".json").write_text('{"model_version": "test"}')
    monkeypatch.setattr(risk, "MODEL_PATH", path)


def test_predict_diabetes(tiny_model: None, run: Any) -> None:
    low = run(risk.predict_diabetes, SAMPLE_FEATURES.model_copy(update={"BMI": 21.0, "HighBP": 0}))
    high = run(risk.predict_diabetes, SAMPLE_FEATURES.model_copy(update={"BMI": 38.0}))
    assert 0 <= low.prob < high.prob <= 1 and high.model_version == "test"
    assert len(high.top_factors) == 3 and high.top_factors[0].feature in {"BMI", "HighBP"}
    assert high.top_factors[0].direction == "increase"


def test_predict_without_model(tmp_path: Any, monkeypatch: pytest.MonkeyPatch, run: Any) -> None:
    monkeypatch.setattr(risk, "MODEL_PATH", tmp_path / "missing.joblib")
    with pytest.raises(FileNotFoundError, match="make train"):
        run(risk.predict_diabetes, SAMPLE_FEATURES)


def test_ols_slope_and_adherence() -> None:
    assert analytics.ols_slope([(0, 1), (1, 3), (2, 5)]) == 2
    assert analytics.ols_slope([(0, 1)]) is None
    assert analytics.adherence([6000, 8000], "steps", 7000) == 50
    assert analytics.adherence([1, 0, 0, 0], "smoked", 0) == 75


def test_compute_trends(client: Any, run: Any) -> None:
    uid = run(make_user)
    t = data.today()
    for i, steps in enumerate([4000, 4000, 6000, 7000, 8000]):  # 2 hari periode lalu, 3 hari ini
        day = t - timedelta(days=4 - i)
        run(data.save_daily_log, uid, DailyLogIn(log_date=day, steps=steps, source="web"))
    run(data.save_measurement, uid, MeasurementIn(kind="systolic", value=128, measured_at=NOW))
    content = PlanContent(
        weeks=[
            PlanWeek(
                range="minggu 1", targets=[PlanTarget(metric="steps", target=7000)], actions=[]
            )
        ]
    )
    run(plan.save_plan, uid, PlanIn(status="active", content=content, starts_on=t))
    r = run(analytics.compute_trends, uid, 3)
    steps = r.metrics["steps"]
    assert (steps.mean, steps.min, steps.max, steps.n_obs) == (7000, 6000, 8000, 3)
    assert steps.delta == 3000 and steps.slope_per_day == 1000
    assert steps.adherence_pct == pytest.approx(66.7) and len(steps.series) == 3
    assert r.metrics["systolic"].mean == 128 and "sleep_hours" not in r.metrics
    empty = run(analytics.compute_trends, run(make_user, False), 7)
    assert empty.metrics == {} and empty.end == t and empty.start == t - timedelta(days=6)
    assert date.fromisoformat(str(r.start)) == t - timedelta(days=2)
