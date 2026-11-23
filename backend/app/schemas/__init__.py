"""Kontrak I/O Pydantic untuk tools (PRD bagian 7) dan payload interrupt (bagian 6.3).

Dibekukan setelah Gate 1. Perubahan harus disetujui A + pemilik track terdampak (bagian 16).
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

Metric = Literal[
    "steps",
    "sleep_hours",
    "water_l",
    "calories",
    "smoked",
    "alcohol",
    "systolic",
    "diastolic",
    "resting_hr",
    "weight_kg",
    "cholesterol",
]
# TODO(PRD): Metric "calories"/"cholesterol" vs kolom DB calories_kcal / kind cholesterol_total.
# Pemetaan dilakukan di implementasi tool, nama Metric mengikuti bagian 7.

MeasurementKind = Literal["weight_kg", "systolic", "diastolic", "resting_hr", "cholesterol_total"]
LogSource = Literal["web", "telegram", "form"]
PlanStatus = Literal["pending_review", "active", "superseded", "rejected"]
Binary = Literal[0, 1]


# --- auth (API, bagian 10) ---------------------------------------------------


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: Literal["user", "clinician", "admin"]


# --- data -------------------------------------------------------------------


class DailyLogIn(BaseModel):
    log_date: date
    steps: int | None = Field(None, ge=0)
    sleep_hours: float | None = Field(None, ge=0, le=24)
    water_l: float | None = Field(None, ge=0, le=99.9)  # NUMERIC(3,1)
    calories_kcal: int | None = Field(None, ge=0)
    smoked: bool | None = None
    alcohol: bool | None = None
    source: LogSource
    raw_text: str | None = None


class DailyLogOut(DailyLogIn):
    id: int
    user_id: int
    created_at: datetime


# Batas masuk akal untuk validasi input (form dan hasil ekstraksi LLM). Bukan ambang klinis.
MEASUREMENT_RANGE: dict[str, tuple[float, float]] = {
    "weight_kg": (20, 300),
    "systolic": (60, 260),
    "diastolic": (30, 160),
    "resting_hr": (25, 250),
    "cholesterol_total": (50, 600),
}


class MeasurementIn(BaseModel):
    kind: MeasurementKind
    value: float = Field(ge=0, lt=100_000)  # NUMERIC(6,1)
    measured_at: datetime


class MeasurementOut(MeasurementIn):
    id: int
    user_id: int


class ProfileIn(BaseModel):
    """Body PUT /api/profile. `Profile` = ProfileIn + user_id."""

    birth_date: date
    sex: Literal["male", "female"]
    height_cm: float = Field(gt=0, lt=10_000)  # NUMERIC(5,1)
    family_history_cvd: bool | None = None
    family_history_diabetes: bool | None = None
    dx_hypertension: bool | None = None
    dx_high_chol: bool | None = None
    dx_diabetes: bool | None = None
    bp_treated: bool | None = None
    smoker_lifetime_100: bool | None = None
    phys_activity_30d: bool | None = None
    fruits_daily: bool | None = None
    veggies_daily: bool | None = None
    heavy_alcohol: bool | None = None
    gen_health: int | None = Field(None, ge=1, le=5)
    diff_walk: bool | None = None


class Profile(ProfileIn):
    user_id: int


class MeasurementValue(BaseModel):
    value: float
    measured_at: datetime  # dipakai untuk aturan "data lama" (>90 hari) dan RF ≤24 jam


class LatestValues(BaseModel):
    """Nilai terakhir per measurement + ringkasan log 7 hari untuk risk/safety tools."""

    weight_kg: MeasurementValue | None = None
    systolic: MeasurementValue | None = None
    diastolic: MeasurementValue | None = None
    resting_hr: MeasurementValue | None = None
    cholesterol_total: MeasurementValue | None = None
    # TODO(PRD): ringkasan 7 hari tidak dirinci PRD; dibutuhkan flag aktivitas/tidur/merokok.
    avg_steps_7d: float | None = None
    avg_sleep_7d: float | None = None
    smoked_days_7d: int | None = None


class HistoryRow(BaseModel):
    date: date
    values: dict[Metric, float | bool | None]


class HistoryTable(BaseModel):
    metrics: list[Metric]
    days: int = Field(ge=1, le=90)
    rows: list[HistoryRow]


# --- analytics ----------------------------------------------------------------


class SeriesPoint(BaseModel):
    date: date
    value: float


class MetricTrend(BaseModel):
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    delta: float | None = None  # mean periode ini - mean periode sebelumnya
    slope_per_day: float | None = None  # OLS
    n_obs: int = Field(ge=0)
    adherence_pct: float | None = Field(None, ge=0, le=100)  # vs target plan aktif
    series: list[SeriesPoint] = []  # dipakai build_chart_payload / render_chart_png


class TrendReport(BaseModel):
    days: int = Field(ge=1)
    start: date
    end: date
    metrics: dict[Metric, MetricTrend]


# --- risk ---------------------------------------------------------------------


class Flag(BaseModel):
    code: str
    severity: Literal["info", "warn", "urgent"]
    metric: str
    value: float | str | None  # str untuk nilai gabungan, mis. tekanan darah "130/85"
    threshold: str
    source_id: str | None  # NEEDS_VERIFICATION: diisi setelah ambang diverifikasi ke korpus
    stale: bool = False  # measurement > 90 hari: label "data lama", tidak boleh urgent


class FraminghamResult(BaseModel):
    applicable: bool
    reason: str | None = None  # mis. "age_out_of_range"
    risk_10y_pct: float | None = Field(None, ge=0, le=100)
    # TODO(PRD): kategori tidak dirinci; batasnya ditetapkan di app/risk/guidelines.py.
    category: Literal["low", "intermediate", "high"] | None = None


class DiabetesFeatures(BaseModel):
    """Fitur CDC BRFSS 2015 (UCI 891), nama dan kode persis seperti codebook."""

    HighBP: Binary
    HighChol: Binary
    BMI: float = Field(gt=0)
    Smoker: Binary
    PhysActivity: Binary
    Fruits: Binary
    Veggies: Binary
    HvyAlcoholConsump: Binary
    GenHlth: int = Field(ge=1, le=5)
    DiffWalk: Binary
    Sex: Binary  # BRFSS: 0 = female, 1 = male
    Age: int = Field(ge=1, le=13)  # _AGEG5YR


class ShapFactor(BaseModel):
    feature: str
    value: float  # nilai fitur user
    shap: float
    direction: Literal["increase", "decrease"]


class DiabetesPrediction(BaseModel):
    prob: float = Field(ge=0, le=1)
    band: Literal["low", "moderate", "high"]
    top_factors: list[ShapFactor] = Field(max_length=3)
    model_version: str


class Assessment(BaseModel):
    flags: list[Flag]
    framingham: FraminghamResult
    diabetes: DiabetesPrediction
    trends: TrendReport


# --- knowledge ----------------------------------------------------------------


class Passage(BaseModel):
    source_id: str
    chunk_id: int
    title: str
    url: str
    publisher: str
    year: int | None
    text: str
    score: float


# --- plan ---------------------------------------------------------------------


class PlanTarget(BaseModel):
    metric: Metric
    target: float


class PlanAction(BaseModel):
    text: str
    citations: list[str]  # source_id; validitas dicek Safety Critic, bukan schema


class PlanWeek(BaseModel):
    range: str
    targets: list[PlanTarget]
    actions: list[PlanAction]


class PlanContent(BaseModel):
    weeks: list[PlanWeek]


class PlanIn(BaseModel):
    assessment_id: int | None = None
    status: PlanStatus = "pending_review"
    content: PlanContent
    starts_on: date


class Plan(PlanIn):
    id: int
    user_id: int
    created_at: datetime


# --- nutrition ----------------------------------------------------------------


class FoodItem(BaseModel):
    name: str
    portion: str
    kcal_low: int = Field(ge=0)
    kcal_high: int = Field(ge=0)

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.kcal_low > self.kcal_high:
            raise ValueError("kcal_low > kcal_high")
        return self


class MealEstimate(BaseModel):
    items: list[FoodItem]
    confidence: Literal["low", "medium", "high"]
    caveats: list[str] = []


# --- safety -------------------------------------------------------------------


class RedFlag(BaseModel):
    code: Literal["RF-BP-CRISIS", "RF-SYMPTOM", "RF-HR", "RF-SELFHARM"]
    detail: dict[str, Any]  # disimpan apa adanya ke red_flag_events.detail


# --- charts -------------------------------------------------------------------


class ChartPayload(BaseModel):
    """Data Recharts: baris per tanggal (ISO), satu key per metrik di `series`."""

    series: list[Metric]
    data: list[dict[str, float | str | None]]


# --- interrupt (bagian 6.3) ---------------------------------------------------


class ClarifyPayload(BaseModel):
    type: Literal["clarify"] = "clarify"
    question: str
    missing: list[str]


class ConfirmLogPayload(BaseModel):
    type: Literal["confirm_log"] = "confirm_log"
    log: DailyLogIn
    measurements: list[MeasurementIn]


class ConfirmMealPayload(BaseModel):
    type: Literal["confirm_meal"] = "confirm_meal"
    estimate: MealEstimate


class ClinicianReviewPayload(BaseModel):
    type: Literal["clinician_review"] = "clinician_review"
    review_id: int
    plan: Plan
    assessment: Assessment


InterruptPayload = Annotated[
    ClarifyPayload | ConfirmLogPayload | ConfirmMealPayload | ClinicianReviewPayload,
    Field(discriminator="type"),
]

ClarifyResume = str  # teks jawaban user


class ConfirmLogResume(BaseModel):
    action: Literal["confirm", "edit"]
    log: DailyLogIn | None = None

    @model_validator(mode="after")
    def _edit_needs_log(self) -> Self:
        if self.action == "edit" and self.log is None:
            raise ValueError("action=edit butuh log")
        return self


class ConfirmMealResume(BaseModel):
    action: Literal["confirm", "edit", "cancel"]
    items: list[FoodItem] | None = None

    @model_validator(mode="after")
    def _edit_needs_items(self) -> Self:
        if self.action == "edit" and not self.items:
            raise ValueError("action=edit butuh items")
        return self


class ClinicianDecision(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edited_content: PlanContent | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _edit_needs_content(self) -> Self:
        if self.decision == "edit" and self.edited_content is None:
            raise ValueError("decision=edit butuh edited_content")
        return self


# --- API web (bagian 10), bukan kontrak tool ---------------------------------


class RedFlagEventOut(BaseModel):
    code: str
    detail: dict[str, Any]
    created_at: datetime


class Dashboard(BaseModel):
    trends: TrendReport
    chart: ChartPayload
    assessment: Assessment | None
    assessment_at: datetime | None
    plan: Plan | None
    red_flags: list[RedFlagEventOut]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatHistory(BaseModel):
    messages: list[ChatMessage]
    pending: dict[str, Any] | None  # payload interrupt yang menunggu jawaban


class ReviewItem(BaseModel):
    review_id: int
    plan_id: int
    user_name: str
    created_at: datetime
    payload: ClinicianReviewPayload


class CheckinMeasurement(BaseModel):
    kind: MeasurementKind
    value: float

    @model_validator(mode="after")
    def _range(self) -> Self:
        low, high = MEASUREMENT_RANGE[self.kind]
        if not low <= self.value <= high:
            raise ValueError(f"{self.kind} harus di antara {low:g} dan {high:g}")
        return self


class CheckinIn(BaseModel):
    """Body POST /api/checkin: 5 field wajib (log_complete, bagian 6.2) + data opsional."""

    # TODO(PRD): endpoint form check-in tidak ada di tabel API bagian 10; disetujui A 2026-11-21.
    steps: int = Field(ge=0, le=200_000)
    sleep_hours: float = Field(ge=0, le=24)
    water_l: float = Field(ge=0, le=20)
    smoked: bool
    alcohol: bool
    calories_kcal: int | None = Field(None, ge=0, le=20_000)
    measurements: list[CheckinMeasurement] = Field([], max_length=5)

    @model_validator(mode="after")
    def _unique_kinds(self) -> Self:
        kinds = [m.kind for m in self.measurements]
        if len(kinds) != len(set(kinds)):
            raise ValueError("jenis pengukuran tidak boleh dobel")
        return self
