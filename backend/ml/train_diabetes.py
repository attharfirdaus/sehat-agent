"""Training model risiko diabetes (PRD 8.3).

Data: CDC Diabetes Health Indicators (UCI 891, BRFSS 2015). Model: XGBoost dengan
scale_pos_weight, split stratified 80/20 + 5-fold CV, kalibrasi isotonic, SHAP TreeExplainer.
Jalankan: `make train` (atau `uv run python -m ml.train_diabetes` dari backend/).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from xgboost import XGBClassifier

from app.schemas import DiabetesFeatures
from ml.evaluate import calibration_plot, metrics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ml" / "data" / "cdc_diabetes.csv"
MODEL_PATH = ROOT / "models" / "diabetes_xgb_v1.joblib"
FEATURES = list(DiabetesFeatures.model_fields)  # 12 fitur yang bisa dikumpulkan dari user
TARGET = "Diabetes_binary"
VERSION = "diabetes_xgb_v1"
SEED = 42


def load_data() -> pd.DataFrame:
    if not DATA.exists():
        from ucimlrepo import fetch_ucirepo

        d = fetch_ucirepo(id=891)
        df = d.data.features.copy()
        df[TARGET] = d.data.targets[TARGET]
        DATA.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(DATA, index=False)
    return pd.read_csv(DATA)


def load_split() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    df = load_data()
    return train_test_split(
        df[FEATURES], df[TARGET], test_size=0.2, stratify=df[TARGET], random_state=SEED
    )


def make_model(y: pd.Series) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=float((y == 0).sum() / (y == 1).sum()),
        eval_metric="logloss",
        tree_method="hist",
        random_state=SEED,
        n_jobs=-1,
    )


def train(X: pd.DataFrame, y: pd.Series, cv_folds: int = 5) -> dict:
    """Kembalikan bundle {calibrated, base, features}. `base` dipakai SHAP."""
    base = make_model(y).fit(X, y)
    calibrated = CalibratedClassifierCV(make_model(y), method="isotonic", cv=cv_folds).fit(X, y)
    return {"calibrated": calibrated, "base": base, "features": FEATURES}


def main() -> None:
    X_train, X_test, y_train, y_test = load_split()
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    cv_auc = cross_val_score(make_model(y_train), X_train, y_train, cv=cv, scoring="roc_auc")
    bundle = train(X_train, y_train)
    prob = bundle["calibrated"].predict_proba(X_test)[:, 1]
    test = metrics(y_test.to_numpy(), prob)
    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    calibration_plot(y_test.to_numpy(), prob, MODEL_PATH.with_name(f"{VERSION}_calibration.png"))
    meta = {
        "model_version": VERSION,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data": "UCI 891 CDC Diabetes Health Indicators (BRFSS 2015)",
        "n_train": len(X_train),
        "n_test": len(X_test),
        "features": FEATURES,
        "cv_roc_auc_mean": round(float(cv_auc.mean()), 4),
        "cv_roc_auc_std": round(float(cv_auc.std()), 4),
        "test": test,
        "limits": "Survei self-report AS, fitur biner; indikasi skrining dini, bukan diagnosis.",
    }
    MODEL_PATH.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
