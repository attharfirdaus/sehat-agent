from datetime import date, timedelta
from statistics import fmean
from typing import get_args

from app.schemas import Metric, MetricTrend, Plan, SeriesPoint, TrendReport
from app.tools.data import query_history, today
from app.tools.plan import get_active_plan

# Target dianggap tercapai kalau nilai <= target untuk metrik ini, >= target untuk sisanya.
LOWER_IS_BETTER = {
    "smoked",
    "alcohol",
    "systolic",
    "diastolic",
    "resting_hr",
    "weight_kg",
    "cholesterol",
    "calories",
}


def ols_slope(points: list[tuple[float, float]]) -> float | None:
    """Kemiringan regresi linear (OLS) nilai per hari."""
    if len(points) < 2:
        return None
    mx, my = fmean(x for x, _ in points), fmean(y for _, y in points)
    sxx = sum((x - mx) ** 2 for x, _ in points)
    return sum((x - mx) * (y - my) for x, y in points) / sxx if sxx else None


def _targets(plan: Plan | None, on: date) -> dict[str, float]:
    if plan is None or not plan.content.weeks:
        return {}
    week = min(max((on - plan.starts_on).days // 7, 0), len(plan.content.weeks) - 1)
    return {t.metric: t.target for t in plan.content.weeks[week].targets}


def adherence(values: list[float], metric: str, target: float) -> float:
    ok = [v <= target if metric in LOWER_IS_BETTER else v >= target for v in values]
    return round(100 * sum(ok) / len(ok), 1)


async def compute_trends(user_id: int, days: int = 7) -> TrendReport:
    """Tren per metrik: mean, min, max, delta vs periode sebelumnya, slope OLS per hari,
    jumlah observasi, dan kepatuhan (%) terhadap target plan aktif. Tanpa LLM.

    Tool ★ untuk History Q&A agent.
    """
    days = max(1, min(days, 45))  # dua periode harus muat di batas 90 hari query_history
    end = today()
    start = end - timedelta(days=days - 1)
    history = await query_history(user_id, list(get_args(Metric)), days * 2)
    targets = _targets(await get_active_plan(user_id), end)

    metrics: dict[Metric, MetricTrend] = {}
    for metric in get_args(Metric):
        current: list[tuple[date, float]] = []
        previous: list[float] = []
        for row in history.rows:
            v = row.values.get(metric)
            if v is None:
                continue
            if row.date >= start:
                current.append((row.date, float(v)))
            else:
                previous.append(float(v))
        if not current:
            continue
        vals = [v for _, v in current]
        mean = fmean(vals)
        slope = ols_slope([((d - start).days, v) for d, v in current])
        metrics[metric] = MetricTrend(
            mean=round(mean, 2),
            min=min(vals),
            max=max(vals),
            delta=round(mean - fmean(previous), 2) if previous else None,
            slope_per_day=None if slope is None else round(slope, 3),
            n_obs=len(vals),
            adherence_pct=adherence(vals, metric, targets[metric]) if metric in targets else None,
            series=[SeriesPoint(date=d, value=v) for d, v in current],
        )
    return TrendReport(days=days, start=start, end=end, metrics=metrics)
