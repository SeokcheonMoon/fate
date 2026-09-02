"""유의 OHLCV 피처로 다음 거래일 상승 여부를 시간순 검증한다.

피처는 당일 장 마감 후 알 수 있는 값만 사용하고, 각 검증 월보다 이전 데이터로만
학습한다. 따라서 무작위 분할에서 생길 수 있는 미래 정보 누출을 피한다.

실행:
    python -m ml.ohlcv_walk_forward
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from analysis.ohlcv_eda import add_features, load_panel


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
OUTPUT_DIR = PROJECT_ROOT / "analysis" / "output"

FEATURE_COLUMNS = [
    "intraday_range",
    "ma_5_ratio",
    "ma_20_ratio",
    "return_1d",
    "volume_change_1d",
    "rsi_14",
    "macd_ratio",
]
TARGET_COLUMN = "target_up_1d"
INITIAL_TRAIN_MONTHS = 6


def build_model() -> Pipeline:
    """계수 해석이 가능한 기준 분류 모델을 만든다."""
    return Pipeline(
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


def prepare_dataset() -> pd.DataFrame:
    """OHLCV에서 피처를 다시 계산하고 학습 가능한 행만 남긴다."""
    panel = add_features(load_panel())
    dataset = panel.replace([np.inf, -np.inf], np.nan).dropna(
        subset=FEATURE_COLUMNS + [TARGET_COLUMN, "trade_date"]
    ).copy()
    dataset[TARGET_COLUMN] = dataset[TARGET_COLUMN].astype(int)
    dataset["validation_month"] = dataset["trade_date"].dt.to_period("M")
    return dataset


def evaluate_fold(
    train: pd.DataFrame, test: pd.DataFrame, validation_month: pd.Period
) -> tuple[dict[str, object], pd.DataFrame]:
    """한 검증 월을 학습·평가하고 예측 행을 반환한다."""
    model = build_model()
    model.fit(train[FEATURE_COLUMNS], train[TARGET_COLUMN])
    probability = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]
    prediction = (probability >= 0.5).astype(int)
    actual = test[TARGET_COLUMN]
    top_cutoff = np.quantile(probability, 0.8)
    top_mask = probability >= top_cutoff
    metrics: dict[str, object] = {
        "validation_month": str(validation_month),
        "train_rows": len(train),
        "validation_rows": len(test),
        "positive_rate": actual.mean(),
        "majority_baseline_accuracy": max(actual.mean(), 1 - actual.mean()),
        "accuracy": accuracy_score(actual, prediction),
        "precision": precision_score(actual, prediction, zero_division=0),
        "recall": recall_score(actual, prediction, zero_division=0),
        "roc_auc": roc_auc_score(actual, probability),
        "top_quintile_up_rate": actual.loc[top_mask].mean(),
        "top_quintile_lift": actual.loc[top_mask].mean() - actual.mean(),
    }
    predictions = test[["ticker", "name", "trade_date", "next_return_1d", TARGET_COLUMN]].copy()
    predictions["validation_month"] = str(validation_month)
    predictions["up_probability"] = probability
    predictions["prediction_up_1d"] = prediction
    return metrics, predictions


def walk_forward(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """초기 6개월 학습 후 매월 한 번씩 미래 구간을 검증한다."""
    months = sorted(dataset["validation_month"].unique())
    if len(months) <= INITIAL_TRAIN_MONTHS:
        raise ValueError("워크포워드 검증을 위한 데이터 기간이 충분하지 않습니다.")

    metric_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    for index, month in enumerate(months[INITIAL_TRAIN_MONTHS:], start=INITIAL_TRAIN_MONTHS):
        train = dataset.loc[dataset["validation_month"] < month]
        test = dataset.loc[dataset["validation_month"] == month]
        metrics, predictions = evaluate_fold(train, test, month)
        metrics["train_start"] = train["trade_date"].min().date().isoformat()
        metrics["train_end"] = train["trade_date"].max().date().isoformat()
        metric_rows.append(metrics)
        prediction_frames.append(predictions)
    return pd.DataFrame(metric_rows), pd.concat(prediction_frames, ignore_index=True)


def save_chart(metrics: pd.DataFrame) -> None:
    """월별 정확도·AUC와 상위 확률 종목의 적중률을 시각화한다."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    x = metrics["validation_month"]
    axes[0].plot(x, metrics["accuracy"], marker="o", label="모델 정확도")
    axes[0].plot(x, metrics["majority_baseline_accuracy"], marker="o", label="다수 클래스 기준")
    axes[0].plot(x, metrics["roc_auc"], marker="o", label="ROC-AUC")
    axes[0].axhline(0.5, color="black", linewidth=1, linestyle="--", label="무작위 기준")
    axes[0].set(title="월별 시간순 검증 성능", xlabel="검증 월", ylabel="점수", ylim=(0.35, 0.75))
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].legend()

    axes[1].plot(x, metrics["positive_rate"], marker="o", label="전체 상승 비율")
    axes[1].plot(x, metrics["top_quintile_up_rate"], marker="o", label="상위 20% 예측 상승 비율")
    axes[1].axhline(0.5, color="black", linewidth=1, linestyle="--")
    axes[1].set(title="상위 확률 종목의 상승 적중률", xlabel="검증 월", ylabel="상승 비율", ylim=(0.4, 0.65))
    axes[1].tick_params(axis="x", rotation=35)
    axes[1].legend()
    figure.savefig(OUTPUT_DIR / "ohlcv_walk_forward_metrics.png", dpi=180)
    plt.close(figure)


def train_final_model(dataset: pd.DataFrame) -> pd.DataFrame:
    """모든 이용 가능 기간으로 최종 모델을 학습하고 표준화 계수를 저장한다."""
    model = build_model()
    model.fit(dataset[FEATURE_COLUMNS], dataset[TARGET_COLUMN])
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "features": FEATURE_COLUMNS, "trained_until": str(dataset["trade_date"].max().date())},
        MODEL_DIR / "ohlcv_logistic_regression.joblib",
    )
    coefficients = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "coefficient": model.named_steps["classifier"].coef_[0],
        }
    ).sort_values("coefficient", key=lambda values: values.abs(), ascending=False)
    coefficients.to_csv(MODEL_DIR / "ohlcv_logistic_coefficients.csv", index=False, encoding="utf-8-sig")
    return coefficients


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = prepare_dataset()
    metrics, predictions = walk_forward(dataset)
    coefficients = train_final_model(dataset)
    metrics.to_csv(MODEL_DIR / "ohlcv_walk_forward_metrics.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(MODEL_DIR / "ohlcv_walk_forward_predictions.csv", index=False, encoding="utf-8-sig")
    summary = {
        "model": "LogisticRegression",
        "features": FEATURE_COLUMNS,
        "validation_method": "expanding-window monthly walk-forward",
        "initial_train_months": INITIAL_TRAIN_MONTHS,
        "folds": len(metrics),
        "mean_accuracy": metrics["accuracy"].mean(),
        "mean_majority_baseline_accuracy": metrics["majority_baseline_accuracy"].mean(),
        "mean_roc_auc": metrics["roc_auc"].mean(),
        "mean_top_quintile_lift": metrics["top_quintile_lift"].mean(),
        "validation_start": metrics["validation_month"].min(),
        "validation_end": metrics["validation_month"].max(),
    }
    (MODEL_DIR / "ohlcv_walk_forward_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    save_chart(metrics)
    print("시간순 검증 완료")
    print(metrics.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print("\n평균 성능")
    print(pd.Series(summary).to_string())
    print("\n최종 모델 계수")
    print(coefficients.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
