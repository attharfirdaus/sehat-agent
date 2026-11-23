// Cermin dari backend/app/schemas (kontrak bagian 6.3 dan 7).

export type DailyLogIn = {
  log_date: string;
  steps: number | null;
  sleep_hours: number | null;
  water_l: number | null;
  calories_kcal: number | null;
  smoked: boolean | null;
  alcohol: boolean | null;
  source: "web" | "telegram" | "form";
  raw_text: string | null;
};

export type MeasurementIn = { kind: string; value: number; measured_at: string };

export type FoodItem = { name: string; portion: string; kcal_low: number; kcal_high: number };

export type MealEstimate = {
  items: FoodItem[];
  confidence: "low" | "medium" | "high";
  caveats: string[];
};

export type InterruptPayload =
  | { type: "clarify"; question: string; missing: string[] }
  | { type: "confirm_log"; log: DailyLogIn; measurements: MeasurementIn[] }
  | { type: "confirm_meal"; estimate: MealEstimate };

export type ChatEvent =
  | { event: "node_start"; data: { node: string } }
  | { event: "token"; data: { text: string } }
  | { event: "interrupt"; data: InterruptPayload }
  | { event: "chart"; data: unknown }
  | { event: "final"; data: { text: string } }
  | { event: "error"; data: { message: string } };

export type User = { id: number; email: string; name: string; role: "user" | "clinician" | "admin" };

export type Profile = {
  birth_date: string;
  sex: "male" | "female";
  height_cm: number;
  gen_health: number | null;
} & Record<string, boolean | number | string | null>;

export type Flag = {
  code: string;
  severity: "info" | "warn" | "urgent";
  metric: string;
  value: number | string | null;
  threshold: string;
  source_id: string | null;
  stale: boolean;
};

export type MetricTrend = {
  mean: number | null;
  min: number | null;
  max: number | null;
  delta: number | null;
  slope_per_day: number | null;
  n_obs: number;
  adherence_pct: number | null;
};

export type TrendReport = { days: number; start: string; end: string; metrics: Record<string, MetricTrend> };

export type PlanContent = {
  weeks: {
    range: string;
    targets: { metric: string; target: number }[];
    actions: { text: string; citations: string[] }[];
  }[];
};

export type Plan = { id: number; status: string; content: PlanContent; starts_on: string };

export type Assessment = {
  flags: Flag[];
  framingham: { applicable: boolean; reason: string | null; risk_10y_pct: number | null; category: string | null };
  diabetes: {
    prob: number;
    band: "low" | "moderate" | "high";
    top_factors: { feature: string; value: number; shap: number; direction: "increase" | "decrease" }[];
    model_version: string;
  };
  trends: TrendReport;
};

export type Dashboard = {
  trends: TrendReport;
  chart: { series: string[]; data: Record<string, number | string | null>[] };
  assessment: Assessment | null;
  assessment_at: string | null;
  plan: Plan | null;
  red_flags: { code: string; detail: Record<string, unknown>; created_at: string }[];
};

export type ReviewItem = {
  review_id: number;
  plan_id: number;
  user_name: string;
  created_at: string;
  payload: { review_id: number; plan: Plan; assessment: Assessment };
};
