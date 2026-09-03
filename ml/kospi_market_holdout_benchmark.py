"""KOSPI 시장 결합 피처로 네 분류 모델을 최종 홀드아웃 구간에서 비교한다.

실행:
    python -m ml.kospi_market_holdout_benchmark

2026-03~08을 한 번도 학습에 쓰지 않는 공통 테스트 구간으로 고정한다.
이는 복잡한 하이퍼파라미터 탐색 대신, Logistic Regression·Random Forest·
XGBoost·LightGBM 중 프로젝트의 최종 후보를 고르기 위한 간결한 비교다.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier

from ml.kospi_market_model_selection import COMPACT_FEATURES
from ml.kospi_market_walk_forward import TARGET_COLUMN, build_model, prepare_dataset


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
OUTPUT_DIR = PROJECT_ROOT / "analysis" / "output"
HOLDOUT_START = pd.Timestamp("2026-03-01")


def build_random_forest() -> Pipeline:
    """깊이와 최소 리프 크기를 제한한 Random Forest 후보."""
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=150,
                    max_depth=8,
                    min_samples_leaf=150,
                    max_features=0.7,
                    class_weight="balanced_subsample",
                    n_jobs=-1,
                    random_state=42,
                ),
            ),
        ]
    )


def positive_weight(target: pd.Series) -> float:
    positives = target.sum()
    return float((len(target) - positives) / positives) if positives else 1.0


def build_xgboost(scale_pos_weight: float) -> XGBClassifier:
    """과도한 깊이를 제한한 XGBoost 후보."""
    return XGBClassifier(
        n_estimators=180,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=100,
        reg_lambda=3.0,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
    )


def build_lightgbm(scale_pos_weight: float) -> lgb.LGBMClassifier:
    """작은 리프 수로 복잡도를 제한한 LightGBM 후보."""
    return lgb.LGBMClassifier(
        n_estimators=180,
        learning_rate=0.05,
        num_leaves=15,
        max_depth=4,
        min_child_samples=150,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=3.0,
        scale_pos_weight=scale_pos_weight,
        n_jobs=-1,
        random_state=42,
        verbosity=-1,
    )


def evaluate_candidate(
    model_name: str, model: object, train: pd.DataFrame, test: pd.DataFrame
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame | None]:
    """한 모델을 학습하고 공통 홀드아웃 성능·예측·중요도를 반환한다."""
    model.fit(train[COMPACT_FEATURES], train[TARGET_COLUMN])
    probability = model.predict_proba(test[COMPACT_FEATURES])[:, 1]
    prediction = (probability >= 0.5).astype(int)
    actual = test[TARGET_COLUMN]
    probability_series = pd.Series(probability, index=test.index)
    top_indices = probability_series.nlargest(max(1, int(len(test) * 0.2))).index
    top_up_rate = actual.loc[top_indices].mean()
    metrics = {
        "model": model_name,
        "train_rows": len(train),
        "holdout_rows": len(test),
        "holdout_start": test["trade_date"].min().date().isoformat(),
        "holdout_end": test["trade_date"].max().date().isoformat(),
        "accuracy": accuracy_score(actual, prediction),
        "majority_baseline_accuracy": max(actual.mean(), 1 - actual.mean()),
        "roc_auc": roc_auc_score(actual, probability),
        "top_quintile_up_rate": top_up_rate,
        "top_quintile_lift": top_up_rate - actual.mean(),
    }
    predictions = test[["ticker", "name", "trade_date", "next_return_1d", TARGET_COLUMN]].copy()
    predictions["model"] = model_name
    predictions["up_probability"] = probability
    predictions["prediction_up_1d"] = prediction
    classifier = model.named_steps["classifier"] if isinstance(model, Pipeline) else model
    if hasattr(classifier, "feature_importances_"):
        importance = pd.DataFrame(
            {"model": model_name, "feature": COMPACT_FEATURES, "importance": classifier.feature_importances_}
        ).sort_values("importance", ascending=False)
    else:
        importance = None
    return metrics, predictions, importance


def save_chart(metrics: pd.DataFrame) -> None:
    """후보의 핵심 홀드아웃 성능을 한 장의 차트로 저장한다."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    axes[0].bar(metrics["model"], metrics["roc_auc"], color="#2a6fbb")
    axes[0].axhline(0.5, color="black", linewidth=1, linestyle="--")
    axes[0].set(title="최종 홀드아웃 ROC-AUC", ylabel="ROC-AUC", ylim=(0.4, 0.7))
    axes[1].bar(metrics["model"], metrics["top_quintile_lift"] * 100, color="#2a9d8f")
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set(title="상위 20% 상승률 개선", ylabel="개선폭(%p)")
    for axis in axes:
        axis.tick_params(axis="x", rotation=20)
    figure.savefig(OUTPUT_DIR / "kospi_market_holdout_benchmark.png", dpi=180)
    plt.close(figure)


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset = prepare_dataset()
    train = dataset.loc[dataset["trade_date"] < HOLDOUT_START].copy()
    test = dataset.loc[dataset["trade_date"] >= HOLDOUT_START].copy()
    if train.empty or test.empty:
        raise ValueError("학습·홀드아웃 구간을 만들 수 없습니다.")
    scale_weight = positive_weight(train[TARGET_COLUMN])
    candidate_builders = {
        "Logistic Regression": build_model,
        "Random Forest": build_random_forest,
        "XGBoost": lambda: build_xgboost(scale_weight),
        "LightGBM": lambda: build_lightgbm(scale_weight),
    }
    metric_rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    importances: list[pd.DataFrame] = []
    for model_name, model_builder in candidate_builders.items():
        print(f"검증 중: {model_name}")
        model = model_builder()
        metrics, predictions, importance = evaluate_candidate(model_name, model, train, test)
        metric_rows.append(metrics)
        prediction_frames.append(predictions)
        if importance is not None:
            importances.append(importance)

    metrics = pd.DataFrame(metric_rows).sort_values(["roc_auc", "top_quintile_lift"], ascending=False)
    selected_name = str(metrics.iloc[0]["model"])
    # 홀드아웃은 모델 선택에만 쓰고, 선택이 끝난 뒤에는 전체 기간으로 다시 학습한다.
    final_scale_weight = positive_weight(dataset[TARGET_COLUMN])
    final_builders = {
        "Logistic Regression": build_model,
        "Random Forest": build_random_forest,
        "XGBoost": lambda: build_xgboost(final_scale_weight),
        "LightGBM": lambda: build_lightgbm(final_scale_weight),
    }
    selected_model = final_builders[selected_name]()
    selected_model.fit(dataset[COMPACT_FEATURES], dataset[TARGET_COLUMN])
    joblib.dump(
        {
            "model": selected_model,
            "model_name": selected_name,
            "features": COMPACT_FEATURES,
            "selection_metric": "2026-03~2026-08 chronological holdout ROC-AUC",
            "trained_until": str(dataset["trade_date"].max().date()),
            "holdout_start": str(test["trade_date"].min().date()),
            "holdout_end": str(test["trade_date"].max().date()),
        },
        MODEL_DIR / "final_kospi_direction_model.joblib",
    )
    metrics.to_csv(MODEL_DIR / "kospi_market_holdout_benchmark.csv", index=False, encoding="utf-8-sig")
    pd.concat(prediction_frames, ignore_index=True).to_csv(
        MODEL_DIR / "kospi_market_holdout_predictions.csv", index=False, encoding="utf-8-sig"
    )
    if importances:
        pd.concat(importances, ignore_index=True).to_csv(
            MODEL_DIR / "kospi_market_tree_feature_importance.csv", index=False, encoding="utf-8-sig"
        )
    (MODEL_DIR / "final_kospi_direction_model_summary.json").write_text(
        json.dumps(
            {
                "selected_model": selected_name,
                "selection_metric": "2026-03~2026-08 chronological holdout ROC-AUC",
                "features": COMPACT_FEATURES,
                "holdout_results": metrics.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    save_chart(metrics)
    print("\n최종 홀드아웃 비교 결과")
    print(metrics.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"\n최종 모델: {selected_name}")


if __name__ == "__main__":
    main()
