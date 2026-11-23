from app.schemas import ChartPayload, TrendReport


async def build_chart_payload(trends: TrendReport) -> ChartPayload:
    """JSON untuk Recharts: satu baris per tanggal, satu key per metrik."""
    rows: dict[str, dict[str, float | str | None]] = {}
    for metric, t in trends.metrics.items():
        for p in t.series:
            rows.setdefault(p.date.isoformat(), {"date": p.date.isoformat()})[metric] = p.value
    return ChartPayload(series=list(trends.metrics), data=[rows[d] for d in sorted(rows)])


async def render_chart_png(trends: TrendReport) -> bytes:
    """PNG matplotlib untuk Telegram."""
    raise NotImplementedError  # TODO(PRD): M6 Telegram dilewati (keputusan A 2026-11-21)
