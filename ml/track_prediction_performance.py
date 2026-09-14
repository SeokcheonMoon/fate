"""저장된 예측 이력과 실제 다음 거래일 결과를 비교한다.

실행:
    python -m ml.track_prediction_performance
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score

from analysis.ohlcv_eda import add_features, load_panel


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = PROJECT_ROOT / "data" / "predictions" / "prediction_history.csv"
METRICS_DIR = PROJECT_ROOT / "data" / "metrics"
DETAIL_PATH = METRICS_DIR / "prediction_performance_detail.csv"
SUMMARY_PATH = METRICS_DIR / "prediction_performance_summary.csv"
CALIBRATION_PATH = METRICS_DIR / "prediction_calibration.csv"
DAILY_SUMMARY_PATH = METRICS_DIR / "prediction_performance_daily.csv"


DAILY_SUMMARY_COLUMNS = [
    "model",
    "trade_date",
    "evaluated_predictions",
    "successful_predictions",
    "accuracy",
    "mean_actual_return",
]


def build_daily_summary(detail: pd.DataFrame) -> pd.DataFrame:
    """모델·예측 기준일 단위로 확정 예측의 성공률을 집계한다."""
    return (
        detail.groupby(["model", "trade_date"], as_index=False)
        .agg(
            evaluated_predictions=("correct", "size"),
            successful_predictions=("correct", "sum"),
            accuracy=("correct", "mean"),
            mean_actual_return=("target_return_1d", "mean"),
        )
        .sort_values(["model", "trade_date"], ascending=[True, False])
    )


def load_confirmed_actuals() -> pd.DataFrame:
    """DB의 최신 종가로, 다음 거래일 결과가 확정된 예측 기준일만 만든다."""
    panel = add_features(load_panel())
    actuals = panel.dropna(subset=["next_return_1d"])[
        ["trade_date", "ticker", "next_return_1d"]
    ].copy()
    actuals["target_return_1d"] = actuals["next_return_1d"]
    actuals["target_up_1d"] = actuals["next_return_1d"].gt(0).astype(int)
    return actuals.drop(columns="next_return_1d")


def main() -> None:
    if not HISTORY_PATH.exists():
        raise FileNotFoundError("예측 이력이 없습니다. 먼저 `python -m ml.prediction`을 실행하세요.")

    history = pd.read_csv(HISTORY_PATH, encoding="utf-8-sig", dtype={"ticker": str})
    actuals = load_confirmed_actuals()
    # 예측 이력에 날짜만 있는 행과 자정 시간이 붙은 행이 함께 있을 수 있다.
    history["trade_date"] = pd.to_datetime(history["trade_date"], format="mixed").dt.normalize()
    history["up_probability"] = pd.to_numeric(history["up_probability"], errors="coerce")

    detail = history.merge(actuals, on=["trade_date", "ticker"], how="inner")
    detail = detail.dropna(subset=["up_probability"]).copy()
    detail["target_up_1d"] = detail["target_up_1d"].astype(int)
    detail["predicted_up"] = detail["up_probability"].ge(0.5).astype(int)
    detail["correct"] = detail["predicted_up"].eq(detail["target_up_1d"])
    detail["probability_bucket"] = pd.cut(
        detail["up_probability"],
        bins=[0, 0.4, 0.5, 0.6, 0.7, 1.0],
        labels=["0~40%", "40~50%", "50~60%", "60~70%", "70~100%"],
        include_lowest=True,
    )

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    if detail.empty:
        pd.DataFrame(columns=["model", "evaluated_predictions", "accuracy", "roc_auc", "brier_score"]).to_csv(
            SUMMARY_PATH, index=False, encoding="utf-8-sig"
        )
        pd.DataFrame(columns=DAILY_SUMMARY_COLUMNS).to_csv(
            DAILY_SUMMARY_PATH, index=False, encoding="utf-8-sig"
        )
        print("아직 실제 결과가 확정된 예측이 없습니다.")
        return

    summaries = []
    for model, group in detail.groupby("model"):
        summaries.append(
            {
                "model": model,
                "evaluated_predictions": len(group),
                "accuracy": accuracy_score(group["target_up_1d"], group["predicted_up"]),
                "roc_auc": roc_auc_score(group["target_up_1d"], group["up_probability"])
                if group["target_up_1d"].nunique() == 2 else np.nan,
                "brier_score": brier_score_loss(group["target_up_1d"], group["up_probability"]),
                "mean_actual_return": group["target_return_1d"].mean(),
                "latest_actual_date": group["trade_date"].max().date().isoformat(),
            }
        )
    summary = pd.DataFrame(summaries).sort_values("roc_auc", ascending=False)
    calibration = (
        detail.groupby(["model", "probability_bucket"], observed=False)
        .agg(predictions=("target_up_1d", "size"), mean_predicted_probability=("up_probability", "mean"), actual_up_rate=("target_up_1d", "mean"))
        .reset_index()
    )
    # 예측 기준일별 성공률을 별도 보존해 대시보드에서 일간 추이를 표시한다.
    daily_summary = build_daily_summary(detail)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    calibration.to_csv(CALIBRATION_PATH, index=False, encoding="utf-8-sig")
    daily_summary.to_csv(DAILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    print(f"성과 요약: {SUMMARY_PATH}")
    print(f"확률 보정: {CALIBRATION_PATH}")
    print(f"일별 성과: {DAILY_SUMMARY_PATH}")
    print(summary.to_string(index=False, float_format="{:.3f}".format))


if __name__ == "__main__":
    main()
