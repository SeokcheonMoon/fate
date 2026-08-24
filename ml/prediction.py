"""검증 ROC-AUC가 가장 높은 FATE 모델로 다음 거래일 상승 확률을 예측한다.

실행:
    python -m ml.prediction
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from ml.train import FEATURE_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
PREDICTION_DIR = PROJECT_ROOT / "data" / "predictions"
INPUT_PATH = DATA_DIR / "fate_prediction_features.csv"
OUTPUT_PATH = PREDICTION_DIR / "latest_direction_predictions.csv"

MODEL_CANDIDATES = [
    (
        "Logistic Regression",
        PROJECT_ROOT / "ml" / "models" / "up_direction_metrics.json",
        PROJECT_ROOT / "ml" / "models" / "up_direction_logistic_regression.joblib",
    ),
    (
        "XGBoost",
        PROJECT_ROOT / "ml" / "models" / "up_direction_xgboost_metrics.json",
        PROJECT_ROOT / "ml" / "models" / "up_direction_xgboost.joblib",
    ),
    (
        "Random Forest",
        PROJECT_ROOT / "ml" / "models" / "up_direction_random_forest_metrics.json",
        PROJECT_ROOT / "ml" / "models" / "up_direction_random_forest.joblib",
    ),
]


def select_best_model() -> dict:
    """저장된 검증 결과 중 ROC-AUC가 가장 높은 모델을 선택한다."""
    candidates = []
    for name, metrics_path, model_path in MODEL_CANDIDATES:
        if not metrics_path.exists() or not model_path.exists():
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        score = metrics.get("roc_auc")
        if score is not None:
            candidates.append(
                {"name": name, "model_path": model_path, "score": score}
            )

    if not candidates:
        raise FileNotFoundError(
            "학습된 모델 또는 ROC-AUC 지표가 없습니다. 먼저 모델 학습을 실행하세요."
        )
    return max(candidates, key=lambda candidate: candidate["score"])


def predict_probabilities(model_artifact: object, x_data: pd.DataFrame) -> pd.Series:
    """Pipeline과 {imputer, model} 형태의 트리 모델을 모두 지원한다."""
    if isinstance(model_artifact, dict):
        transformed_data = model_artifact["imputer"].transform(x_data)
        probabilities = model_artifact["model"].predict_proba(transformed_data)[:, 1]
    else:
        probabilities = model_artifact.predict_proba(x_data)[:, 1]
    return pd.Series(probabilities, index=x_data.index)


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"예측 피처 파일이 없습니다: {INPUT_PATH}\n"
            "analysis/feature_engineering.ipynb를 다시 실행하세요."
        )

    features = pd.read_csv(INPUT_PATH, parse_dates=["trade_date"])
    required_columns = set(FEATURE_COLUMNS + ["ticker", "name", "trade_date", "close_price"])
    missing_columns = required_columns.difference(features.columns)
    if missing_columns:
        raise ValueError(f"예측 피처에 필수 컬럼이 없습니다: {sorted(missing_columns)}")

    latest = (
        features.sort_values(["ticker", "trade_date"])
        .groupby("ticker", as_index=False)
        .tail(1)
        .copy()
    )
    selected = select_best_model()
    model_artifact = joblib.load(selected["model_path"])
    latest["up_probability"] = predict_probabilities(
        model_artifact, latest[FEATURE_COLUMNS]
    )
    latest["prediction"] = latest["up_probability"].ge(0.5).map(
        {True: "상승", False: "하락 또는 보합"}
    )
    latest["model"] = selected["name"]
    latest["validation_roc_auc"] = selected["score"]

    result = latest[
        [
            "trade_date", "ticker", "name", "close_price", "up_probability",
            "prediction", "model", "validation_roc_auc",
        ]
    ].sort_values("up_probability", ascending=False)

    PREDICTION_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"선택 모델: {selected['name']} (검증 ROC-AUC {selected['score']:.3f})")
    print(f"예측 결과: {OUTPUT_PATH}")
    print(result.to_string(index=False, formatters={"up_probability": "{:.1%}".format}))


if __name__ == "__main__":
    main()
