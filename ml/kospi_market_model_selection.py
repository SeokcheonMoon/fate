"""KOSPI 시장 결합 피처의 최종 분류 모델을 간단히 선택한다.

실행:
    python -m ml.kospi_market_model_selection

후보는 전체 시장 결합 피처와, 상관성이 높거나 기여도가 낮은 피처를 뺀 간결 피처의
Logistic Regression 두 개다. 같은 확장 윈도우 워크포워드 구간에서 비교하고,
평균 ROC-AUC를 우선 기준으로 최종 모델을 저장한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score

from ml.kospi_market_walk_forward import (
    INITIAL_TRAIN_MONTHS,
    MARKET_MODEL_FEATURES,
    TARGET_COLUMN,
    build_model,
    prepare_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
OUTPUT_DIR = PROJECT_ROOT / "analysis" / "output"


COMPACT_FEATURES = [
    "intraday_range",
    "ma_20_ratio",
    "return_1d",
    "rsi_14",
    "macd_ratio",
    "kospi_return_1d",
    "kospi_return_5d",
    "kospi_volatility_20d",
    "kospi_ma_20_ratio",
    "relative_strength_5d",
]

MODEL_DEFINITIONS = {
    "시장 결합 전체 피처 Logistic Regression": (build_model, MARKET_MODEL_FEATURES),
    "시장 결합 간결 피처 Logistic Regression": (build_model, COMPACT_FEATURES),
}


def evaluate_model(
    dataset: pd.DataFrame, model_name: str, model_builder: object, features: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """한 후보 모델을 월별 확장 윈도우로 평가한다."""
    months = sorted(dataset["validation_month"].unique())
    metrics_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    for month in months[INITIAL_TRAIN_MONTHS:]:
        train = dataset.loc[dataset["validation_month"] < month]
        test = dataset.loc[dataset["validation_month"] == month]
        model = model_builder()
        model.fit(train[features], train[TARGET_COLUMN])
        probability = model.predict_proba(test[features])[:, 1]
        prediction = (probability >= 0.5).astype(int)
        actual = test[TARGET_COLUMN]
        top_mask = probability >= pd.Series(probability).quantile(0.8)
        metrics_rows.append(
            {
                "model": model_name,
                "validation_month": str(month),
                "train_rows": len(train),
                "validation_rows": len(test),
                "accuracy": accuracy_score(actual, prediction),
                "majority_baseline_accuracy": max(actual.mean(), 1 - actual.mean()),
                "roc_auc": roc_auc_score(actual, probability),
                "top_quintile_up_rate": actual.loc[top_mask].mean(),
                "top_quintile_lift": actual.loc[top_mask].mean() - actual.mean(),
            }
        )
        predictions = test[["ticker", "name", "trade_date", "next_return_1d", TARGET_COLUMN]].copy()
        predictions["model"] = model_name
        predictions["validation_month"] = str(month)
        predictions["up_probability"] = probability
        predictions["prediction_up_1d"] = prediction
        prediction_frames.append(predictions)
    return pd.DataFrame(metrics_rows), pd.concat(prediction_frames, ignore_index=True)


def select_final_model(summary: pd.DataFrame) -> str:
    """AUC 우선, 동률이면 상위 20% 선별력 우선으로 후보를 하나 선택한다."""
    ranked = summary.sort_values(
        ["mean_roc_auc", "mean_top_quintile_lift"], ascending=False
    )
    return str(ranked.iloc[0]["model"])


def save_chart(metrics: pd.DataFrame) -> None:
    """후보별 월간 AUC와 상위 20% 선별력을 시각화한다."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(16, 5), constrained_layout=True)
    for model_name, group in metrics.groupby("model"):
        axes[0].plot(group["validation_month"], group["roc_auc"], marker="o", label=model_name)
        axes[1].plot(group["validation_month"], group["top_quintile_lift"] * 100, marker="o", label=model_name)
    axes[0].axhline(0.5, color="black", linewidth=1, linestyle="--", label="무작위 기준")
    axes[0].set(title="후보 모델 ROC-AUC", xlabel="검증 월", ylabel="ROC-AUC")
    axes[1].axhline(0, color="black", linewidth=1, linestyle="--")
    axes[1].set(title="상위 20% 예측 종목 상승률 개선", xlabel="검증 월", ylabel="개선폭(%p)")
    for axis in axes:
        axis.tick_params(axis="x", rotation=35)
        axis.legend(fontsize=8)
    figure.savefig(OUTPUT_DIR / "kospi_market_model_selection.png", dpi=180)
    plt.close(figure)


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = prepare_dataset()
    all_metrics: list[pd.DataFrame] = []
    all_predictions: list[pd.DataFrame] = []
    for model_name, (model_builder, features) in MODEL_DEFINITIONS.items():
        print(f"검증 중: {model_name}")
        metrics, predictions = evaluate_model(dataset, model_name, model_builder, features)
        all_metrics.append(metrics)
        all_predictions.append(predictions)
    metrics = pd.concat(all_metrics, ignore_index=True)
    predictions = pd.concat(all_predictions, ignore_index=True)
    summary = metrics.groupby("model", as_index=False).agg(
        folds=("validation_month", "count"),
        mean_accuracy=("accuracy", "mean"),
        mean_majority_baseline_accuracy=("majority_baseline_accuracy", "mean"),
        mean_roc_auc=("roc_auc", "mean"),
        mean_top_quintile_lift=("top_quintile_lift", "mean"),
    )
    selected_name = select_final_model(summary)
    final_builder, selected_features = MODEL_DEFINITIONS[selected_name]
    final_model = final_builder()
    final_model.fit(dataset[selected_features], dataset[TARGET_COLUMN])
    joblib.dump(
        {
            "model": final_model,
            "model_name": selected_name,
            "features": selected_features,
            "selection_metric": "mean expanding-window walk-forward ROC-AUC",
            "trained_until": str(dataset["trade_date"].max().date()),
        },
        MODEL_DIR / "final_kospi_direction_model.joblib",
    )
    metrics.to_csv(MODEL_DIR / "kospi_market_model_selection_metrics.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(
        MODEL_DIR / "kospi_market_model_selection_predictions.csv", index=False, encoding="utf-8-sig"
    )
    (MODEL_DIR / "final_kospi_direction_model_summary.json").write_text(
        json.dumps(
            {
                "selected_model": selected_name,
                "selection_metric": "mean expanding-window walk-forward ROC-AUC",
                "features": selected_features,
                "candidate_results": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    save_chart(metrics)
    print("\n후보 모델 평균 성능")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"\n최종 모델: {selected_name}")
    print(f"저장 위치: {MODEL_DIR / 'final_kospi_direction_model.joblib'}")


if __name__ == "__main__":
    main()
