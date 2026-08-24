"""FATE 다음 거래일 상승 여부 분류 모델 학습.

실행:
    python -m ml.train

분석 노트북이 만든 data/processed/fate_train.csv와
data/processed/fate_validation.csv를 입력으로 사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "ml" / "models"

TRAIN_PATH = DATA_DIR / "fate_train.csv"
VALIDATION_PATH = DATA_DIR / "fate_validation.csv"
MODEL_PATH = MODEL_DIR / "up_direction_logistic_regression.joblib"
METRICS_PATH = MODEL_DIR / "up_direction_metrics.json"

FEATURE_COLUMNS = [
    "return_1d",
    "return_5d",
    "return_20d",
    "ma_5_ratio",
    "ma_20_ratio",
    "ma_60_ratio",
    "volatility_20d",
    "volume_change_1d",
    "volume_ratio_20",
    "rsi_14",
    "macd",
    "macd_signal",
    "kospi_return_1d",
    "kospi_return_5d",
    "kospi_volatility_20d",
]
TARGET_COLUMN = "target_up_1d"


def load_dataset(path: Path) -> pd.DataFrame:
    """학습 데이터 파일의 필수 컬럼과 레이블을 검증해 불러온다."""
    if not path.exists():
        raise FileNotFoundError(
            f"학습 데이터가 없습니다: {path}\n"
            "analysis/feature_engineering.ipynb를 먼저 모두 실행하세요."
        )

    dataset = pd.read_csv(path, parse_dates=["trade_date"])
    required_columns = set(FEATURE_COLUMNS + [TARGET_COLUMN, "trade_date", "ticker"])
    missing_columns = required_columns.difference(dataset.columns)
    if missing_columns:
        raise ValueError(f"필수 컬럼이 없습니다: {sorted(missing_columns)}")
    if dataset.empty:
        raise ValueError(f"데이터가 비어 있습니다: {path}")

    dataset[TARGET_COLUMN] = dataset[TARGET_COLUMN].astype(int)
    return dataset


def calculate_metrics(y_true: pd.Series, y_pred: pd.Series, probabilities: pd.Series) -> dict:
    """검증 예측 결과를 저장하기 쉬운 숫자 지표로 변환한다."""
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
    metrics["roc_auc"] = (
        roc_auc_score(y_true, probabilities) if y_true.nunique() == 2 else None
    )
    return metrics


def main() -> None:
    train_data = load_dataset(TRAIN_PATH)
    validation_data = load_dataset(VALIDATION_PATH)

    x_train = train_data[FEATURE_COLUMNS]
    y_train = train_data[TARGET_COLUMN]
    x_validation = validation_data[FEATURE_COLUMNS]
    y_validation = validation_data[TARGET_COLUMN]

    # Logistic Regression은 해석하기 쉬운 기준선 모델이다.
    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2_000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_validation)
    probabilities = model.predict_proba(x_validation)[:, 1]
    metrics = calculate_metrics(y_validation, predictions, probabilities)
    metrics.update(
        {
            "model": "LogisticRegression",
            "train_rows": len(train_data),
            "validation_rows": len(validation_data),
            "features": FEATURE_COLUMNS,
            "validation_start": validation_data["trade_date"].min().date().isoformat(),
            "validation_end": validation_data["trade_date"].max().date().isoformat(),
        }
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("모델 학습 완료")
    print(f"- 모델: {MODEL_PATH}")
    print(f"- 검증 지표: {METRICS_PATH}")
    print(f"- 정확도: {metrics['accuracy']:.3f}")
    print(f"- 정밀도: {metrics['precision']:.3f}")
    print(f"- 재현율: {metrics['recall']:.3f}")
    print(f"- F1: {metrics['f1']:.3f}")
    print(
        f"- ROC-AUC: {metrics['roc_auc']:.3f}"
        if metrics["roc_auc"] is not None
        else "- ROC-AUC: 계산 불가"
    )
    print("\n상세 분류 리포트")
    print(classification_report(y_validation, predictions, digits=3, zero_division=0))


if __name__ == "__main__":
    main()
