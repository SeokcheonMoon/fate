"""FATE 다음 거래일 상승 여부 Random Forest 모델 학습 및 성능 비교.

실행:
    python -m ml.train_random_forest
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

from ml.train import FEATURE_COLUMNS, METRICS_PATH, MODEL_DIR, TARGET_COLUMN, load_dataset


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
TRAIN_PATH = DATA_DIR / "fate_train.csv"
VALIDATION_PATH = DATA_DIR / "fate_validation.csv"
MODEL_PATH = MODEL_DIR / "up_direction_random_forest.joblib"
METRICS_PATH_RANDOM_FOREST = MODEL_DIR / "up_direction_random_forest_metrics.json"
IMPORTANCE_PATH = MODEL_DIR / "up_direction_random_forest_feature_importance.csv"
XGBOOST_METRICS_PATH = MODEL_DIR / "up_direction_xgboost_metrics.json"


def evaluate(y_true: pd.Series, predictions: pd.Series, probabilities: pd.Series) -> dict:
    """모든 분류 모델이 공유하는 검증 지표를 계산한다."""
    return {
        "accuracy": accuracy_score(y_true, predictions),
        "precision": precision_score(y_true, predictions, zero_division=0),
        "recall": recall_score(y_true, predictions, zero_division=0),
        "f1": f1_score(y_true, predictions, zero_division=0),
        "roc_auc": roc_auc_score(y_true, probabilities) if y_true.nunique() == 2 else None,
    }


def metric_text(metrics: dict | None, metric: str) -> str:
    if metrics is None:
        return "미학습"
    value = metrics[metric]
    return "계산 불가" if value is None else f"{value:.3f}"


def load_metrics(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main() -> None:
    train_data = load_dataset(TRAIN_PATH)
    validation_data = load_dataset(VALIDATION_PATH)

    imputer = SimpleImputer(strategy="median")
    x_train = imputer.fit_transform(train_data[FEATURE_COLUMNS])
    x_validation = imputer.transform(validation_data[FEATURE_COLUMNS])
    y_train = train_data[TARGET_COLUMN]
    y_validation = validation_data[TARGET_COLUMN]

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=6,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_validation)
    probabilities = model.predict_proba(x_validation)[:, 1]
    metrics = evaluate(y_validation, predictions, probabilities)
    metrics.update(
        {
            "model": "RandomForestClassifier",
            "train_rows": len(train_data),
            "validation_rows": len(validation_data),
            "features": FEATURE_COLUMNS,
            "validation_start": validation_data["trade_date"].min().date().isoformat(),
            "validation_end": validation_data["trade_date"].max().date().isoformat(),
        }
    )

    importance = pd.DataFrame(
        {"feature": FEATURE_COLUMNS, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"imputer": imputer, "model": model}, MODEL_PATH)
    METRICS_PATH_RANDOM_FOREST.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    importance.to_csv(IMPORTANCE_PATH, index=False, encoding="utf-8-sig")

    baseline = load_metrics(METRICS_PATH)
    xgboost = load_metrics(XGBOOST_METRICS_PATH)
    print("Random Forest 모델 학습 완료")
    print(f"- 모델: {MODEL_PATH}")
    print(f"- 피처 중요도: {IMPORTANCE_PATH}")
    print("\n검증 성능 비교")
    print(f"{'지표':<12} {'Logistic Regression':>22} {'XGBoost':>12} {'Random Forest':>16}")
    for metric in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        print(
            f"{metric:<12} {metric_text(baseline, metric):>22} "
            f"{metric_text(xgboost, metric):>12} {metric_text(metrics, metric):>16}"
        )

    print("\n상위 10개 중요 피처")
    print(importance.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
