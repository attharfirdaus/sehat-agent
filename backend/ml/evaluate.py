"""Metrik model diabetes (PRD 8.3): ROC-AUC, PR-AUC, recall/precision pada threshold band
"high", Brier score, calibration plot. `python -m ml.evaluate` menghitung ulang di test split."""

from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.calibration import calibration_curve  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.risk import guidelines as g  # noqa: E402


def metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float = g.DIABETES_HIGH_PROB) -> dict:
    pred = prob >= threshold
    return {
        "roc_auc": round(float(roc_auc_score(y_true, prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, prob)), 4),
        "threshold": threshold,
        "recall": round(float(recall_score(y_true, pred)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(y_true, prob)), 4),
        "prevalence": round(float(np.mean(y_true)), 4),
    }


def calibration_plot(y_true: np.ndarray, prob: np.ndarray, out: Path) -> None:
    frac, mean_pred = calibration_curve(y_true, prob, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="kalibrasi sempurna")
    ax.plot(mean_pred, frac, "o-", label="model")
    ax.set_xlabel("Probabilitas prediksi")
    ax.set_ylabel("Proporsi positif aktual")
    ax.set_title("Kalibrasi model diabetes (test split)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    from ml.train_diabetes import MODEL_PATH, load_split

    _, X_test, _, y_test = load_split()
    bundle = joblib.load(MODEL_PATH)
    p = bundle["calibrated"].predict_proba(X_test[bundle["features"]])[:, 1]
    print(metrics(y_test.to_numpy(), p))
    calibration_plot(y_test.to_numpy(), p, MODEL_PATH.with_name("diabetes_xgb_v1_calibration.png"))
