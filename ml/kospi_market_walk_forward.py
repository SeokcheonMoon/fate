"""KOSPI 시장 국면 피처를 결합해 다음 거래일 상승 여부를 시간순 비교 검증한다.

실행:
    python -m ml.kospi_market_walk_forward

동일한 날짜·검증 구간에서 OHLCV 기준 모델과 시장 결합 모델을 함께 평가한다.
시장 피처는 모두 해당 거래일 장 마감 시점까지의 KOSPI 종가만 사용한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sqlalchemy import text

from analysis.ohlcv_eda import add_features, load_panel
from config.database import engine
from ml.ohlcv_walk_forward import FEATURE_COLUMNS as OHLCV_FEATURES
from ml.ohlcv_walk_forward import INITIAL_TRAIN_MONTHS, TARGET_COLUMN, build_model


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
OUTPUT_DIR = PROJECT_ROOT / "analysis" / "output"

MARKET_FEATURES = [
    "kospi_return_1d",
    "kospi_return_5d",
    "kospi_volatility_20d",
    "kospi_ma_20_ratio",
    "relative_strength_5d",
    "relative_strength_20d",
]
MARKET_MODEL_FEATURES = OHLCV_FEATURES + MARKET_FEATURES


def load_kospi_index() -> pd.DataFrame:
    """DB에서 KOSPI 종가를 읽고 미래 정보를 쓰지 않는 시장 피처를 만든다."""
    query = text("""
        SELECT miv.observation_date AS trade_date,
               miv.indicator_value AS kospi_close
        FROM market_indicator_values AS miv
        JOIN market_indicators AS mi ON mi.indicator_id = miv.indicator_id
        WHERE mi.indicator_code = 'KOSPI'
        ORDER BY miv.observation_date
    """)
    with engine.connect() as connection:
        index_data = pd.read_sql(query, connection, parse_dates=["trade_date"])
    if index_data.empty:
        raise ValueError("KOSPI 지수가 없습니다. etl.market_loader를 먼저 실행하세요.")

    index_data["kospi_close"] = pd.to_numeric(index_data["kospi_close"], errors="coerce")
    index_data["kospi_return_1d"] = index_data["kospi_close"].pct_change(fill_method=None)
    index_data["kospi_return_5d"] = index_data["kospi_close"].pct_change(5, fill_method=None)
    index_data["kospi_return_20d"] = index_data["kospi_close"].pct_change(20, fill_method=None)
    index_data["kospi_volatility_20d"] = index_data["kospi_return_1d"].rolling(20, min_periods=20).std()
    index_data["kospi_ma_20_ratio"] = index_data["kospi_close"].div(
        index_data["kospi_close"].rolling(20, min_periods=20).mean()
    ) - 1
    return index_data


def prepare_dataset() -> pd.DataFrame:
    """종목 기술지표와 시장 피처를 거래일 기준으로 결합한다."""
    stock_panel = add_features(load_panel())
    stock_panel["stock_return_5d"] = stock_panel.groupby("ticker")["close_price"].pct_change(
        5, fill_method=None
    )
    stock_panel["stock_return_20d"] = stock_panel.groupby("ticker")["close_price"].pct_change(
        20, fill_method=None
    )
    dataset = stock_panel.merge(load_kospi_index(), on="trade_date", how="inner", validate="many_to_one")
    dataset["relative_strength_5d"] = dataset["stock_return_5d"] - dataset["kospi_return_5d"]
    dataset["relative_strength_20d"] = dataset["stock_return_20d"] - dataset["kospi_return_20d"]
    dataset = dataset.replace([np.inf, -np.inf], np.nan).dropna(
        subset=MARKET_MODEL_FEATURES + [TARGET_COLUMN, "trade_date"]
    ).copy()
    dataset[TARGET_COLUMN] = dataset[TARGET_COLUMN].astype(int)
    dataset["validation_month"] = dataset["trade_date"].dt.to_period("M")
    return dataset


def evaluate_fold(
    train: pd.DataFrame, test: pd.DataFrame, validation_month: pd.Period, features: list[str], model_name: str
) -> tuple[dict[str, object], pd.DataFrame]:
    """한 검증 월의 모델 성능과 종목별 예측을 계산한다."""
    model = build_model()
    model.fit(train[features], train[TARGET_COLUMN])
    probability = model.predict_proba(test[features])[:, 1]
    prediction = (probability >= 0.5).astype(int)
    actual = test[TARGET_COLUMN]
    top_mask = probability >= np.quantile(probability, 0.8)
    metrics: dict[str, object] = {
        "model": model_name,
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
    predictions["model"] = model_name
    predictions["validation_month"] = str(validation_month)
    predictions["up_probability"] = probability
    predictions["prediction_up_1d"] = prediction
    return metrics, predictions


def walk_forward(dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """동일한 월별 시간순 구간에서 기준 모델과 시장 결합 모델을 비교한다."""
    months = sorted(dataset["validation_month"].unique())
    if len(months) <= INITIAL_TRAIN_MONTHS:
        raise ValueError("워크포워드 검증을 위한 데이터 기간이 충분하지 않습니다.")

    metric_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    model_definitions = {
        "OHLCV 기준": OHLCV_FEATURES,
        "OHLCV + KOSPI 시장": MARKET_MODEL_FEATURES,
    }
    for month in months[INITIAL_TRAIN_MONTHS:]:
        train = dataset.loc[dataset["validation_month"] < month]
        test = dataset.loc[dataset["validation_month"] == month]
        for model_name, features in model_definitions.items():
            metrics, predictions = evaluate_fold(train, test, month, features, model_name)
            metrics["train_start"] = train["trade_date"].min().date().isoformat()
            metrics["train_end"] = train["trade_date"].max().date().isoformat()
            metric_rows.append(metrics)
            prediction_frames.append(predictions)
    return pd.DataFrame(metric_rows), pd.concat(prediction_frames, ignore_index=True)


def train_final_market_model(dataset: pd.DataFrame) -> pd.DataFrame:
    """시장 결합 모델 전체 학습본과 표준화 계수를 저장한다."""
    model = build_model()
    model.fit(dataset[MARKET_MODEL_FEATURES], dataset[TARGET_COLUMN])
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "features": MARKET_MODEL_FEATURES,
            "trained_until": str(dataset["trade_date"].max().date()),
        },
        MODEL_DIR / "kospi_market_logistic_regression.joblib",
    )
    coefficients = pd.DataFrame(
        {"feature": MARKET_MODEL_FEATURES, "coefficient": model.named_steps["classifier"].coef_[0]}
    ).sort_values("coefficient", key=lambda values: values.abs(), ascending=False)
    coefficients.to_csv(
        MODEL_DIR / "kospi_market_logistic_coefficients.csv", index=False, encoding="utf-8-sig"
    )
    return coefficients


def save_chart(metrics: pd.DataFrame) -> None:
    """두 모델의 월별 정확도·AUC·상위 분위 성능을 비교해 저장한다."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    for model_name, group in metrics.groupby("model"):
        axes[0].plot(group["validation_month"], group["roc_auc"], marker="o", label=model_name)
        axes[1].plot(group["validation_month"], group["top_quintile_lift"] * 100, marker="o", label=model_name)
    axes[0].axhline(0.5, color="black", linewidth=1, linestyle="--", label="무작위 기준")
    axes[0].set(title="월별 시간순 ROC-AUC 비교", xlabel="검증 월", ylabel="ROC-AUC", ylim=(0.4, 0.65))
    axes[1].axhline(0, color="black", linewidth=1, linestyle="--")
    axes[1].set(title="상위 20% 예측 종목 상승률 개선", xlabel="검증 월", ylabel="개선폭(%p)")
    for axis in axes:
        axis.tick_params(axis="x", rotation=35)
        axis.legend()
    figure.savefig(OUTPUT_DIR / "kospi_market_walk_forward_comparison.png", dpi=180)
    plt.close(figure)


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = prepare_dataset()
    metrics, predictions = walk_forward(dataset)
    coefficients = train_final_market_model(dataset)
    metrics.to_csv(MODEL_DIR / "kospi_market_walk_forward_metrics.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(
        MODEL_DIR / "kospi_market_walk_forward_predictions.csv", index=False, encoding="utf-8-sig"
    )
    summary = metrics.groupby("model").agg(
        folds=("validation_month", "count"),
        mean_accuracy=("accuracy", "mean"),
        mean_majority_baseline_accuracy=("majority_baseline_accuracy", "mean"),
        mean_roc_auc=("roc_auc", "mean"),
        mean_top_quintile_lift=("top_quintile_lift", "mean"),
    ).reset_index().to_dict(orient="records")
    (MODEL_DIR / "kospi_market_walk_forward_summary.json").write_text(
        json.dumps({"features": MARKET_MODEL_FEATURES, "models": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("KOSPI 시장 피처 결합 시간순 검증 완료")
    print(metrics.groupby("model")[
        ["accuracy", "majority_baseline_accuracy", "roc_auc", "top_quintile_lift"]
    ].mean().to_string(float_format=lambda value: f"{value:.4f}"))
    print("\n최종 시장 결합 모델 계수")
    print(coefficients.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
