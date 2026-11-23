import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from app.schemas import DailyLogIn, PlanIn
from app.tools import data, mocks, plan

PROFILE = {
    "birth_date": "1995-03-02",
    "sex": "female",
    "height_cm": 160.5,
    "gen_health": 3,
    "dx_hypertension": False,
}


def register(client: TestClient) -> int:
    """Register user baru; cookie tersimpan di client. Return user id."""
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/auth/register", json={"email": email, "password": "rahasia123", "name": "Uji"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "user"
    return r.json()["id"]


def test_auth_flow(client: TestClient) -> None:
    email = f"u{uuid.uuid4().hex[:8]}@Example.com"
    body = {"email": email, "password": "rahasia123", "name": "Uji"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/profile").status_code == 401
    bad = client.post("/api/auth/login", json={"email": email, "password": "salah12345"})
    assert bad.status_code == 401
    ok = client.post("/api/auth/login", json={"email": email.lower(), "password": "rahasia123"})
    assert ok.status_code == 200 and "access_token" in ok.cookies
    client.cookies.clear()
    client.cookies.set("access_token", "rusak")
    assert client.get("/api/profile").status_code == 401


def test_register_validation(client: TestClient) -> None:
    r = client.post(
        "/api/auth/register", json={"email": "bukan-email", "password": "pendek", "name": ""}
    )
    assert r.status_code == 422


def test_profile_upsert(client: TestClient) -> None:
    uid = register(client)
    assert client.get("/api/profile").status_code == 404
    assert client.put("/api/profile", json=PROFILE).status_code == 200
    r = client.put("/api/profile", json={**PROFILE, "height_cm": 161})
    assert r.json()["height_cm"] == 161 and r.json()["user_id"] == uid
    got = client.get("/api/profile").json()
    assert got["height_cm"] == 161 and got["sex"] == "female"
    assert client.put("/api/profile", json={**PROFILE, "gen_health": 9}).status_code == 422


def test_measurement_and_logs(client: TestClient, run) -> None:  # type: ignore[no-untyped-def]
    uid = register(client)
    r = client.post(
        "/api/measurements",
        json={"kind": "systolic", "value": 128, "measured_at": datetime.now(UTC).isoformat()},
    )
    assert r.status_code == 201 and r.json()["user_id"] == uid
    assert (
        client.post(
            "/api/measurements",
            json={"kind": "gula", "value": 1, "measured_at": "2026-01-01T00:00:00Z"},
        ).status_code
        == 422
    )

    today = data.today()
    run(data.save_daily_log, uid, DailyLogIn(log_date=today, steps=6000, source="web"))
    run(data.save_daily_log, uid, DailyLogIn(log_date=today, sleep_hours=5.5, source="telegram"))
    logs = client.get("/api/logs").json()
    assert len(logs) == 1
    assert logs[0]["steps"] == 6000 and logs[0]["sleep_hours"] == 5.5  # merge, tidak ditimpa
    assert logs[0]["source"] == "telegram"
    old = client.get("/api/logs", params={"from": "2020-01-01", "to": "2020-01-31"}).json()
    assert old == []


def test_query_history(client: TestClient, run) -> None:  # type: ignore[no-untyped-def]
    uid = register(client)
    today = data.today()
    run(
        data.save_daily_log,
        uid,
        DailyLogIn(log_date=today - timedelta(days=1), steps=4000, smoked=True, source="web"),
    )
    for v in (120, 130):
        client.post(
            "/api/measurements",
            json={"kind": "systolic", "value": v, "measured_at": datetime.now(UTC).isoformat()},
        )
    table = run(data.query_history, uid, ["steps", "smoked", "systolic"], 3)
    assert table.days == 3 and [r.date for r in table.rows] == [
        today - timedelta(days=2),
        today - timedelta(days=1),
        today,
    ]
    by_day = {r.date: r.values for r in table.rows}
    assert by_day[today - timedelta(days=1)] == {"steps": 4000.0, "smoked": True, "systolic": None}
    assert by_day[today]["systolic"] == 125.0
    assert run(data.query_history, uid, ["steps"], 500).days == 90
    assert run(data.query_history, uid, ["steps"], 0).days == 1


def test_plans(client: TestClient, run) -> None:  # type: ignore[no-untyped-def]
    uid = register(client)
    assert client.get("/api/plans/active").json() is None
    body = PlanIn(status="active", content=mocks.SAMPLE_PLAN_CONTENT, starts_on=date(2026, 11, 1))
    first = run(plan.save_plan, uid, body)
    second = run(plan.save_plan, uid, body)
    active = run(plan.get_active_plan, uid)
    assert active is not None and active.id == second.id != first.id
    assert active.content == mocks.SAMPLE_PLAN_CONTENT
    assert client.get("/api/plans/active").json()["id"] == second.id
