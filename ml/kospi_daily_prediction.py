"""최종 KOSPI 방향 분류 모델로 최신 종목별 다음 거래일 상승확률을 생성한다.

실행:
    python -m ml.kospi_daily_prediction

생성 파일:
    data/predictions/latest_direction_predictions.csv
    data/predictions/kospi_top20_predictions.csv
    data/predictions/prediction_history.csv
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from analysis.ohlcv_eda import add_features, load_panel
from ml.kospi_market_walk_forward import load_kospi_index


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
PREDICTION_DIR = PROJECT_ROOT / "data" / "predictions"
MODEL_PATH = MODEL_DIR / "final_kospi_direction_model.joblib"
SUMMARY_PATH = MODEL_DIR / "final_kospi_direction_model_summary.json"
OUTPUT_PATH = PREDICTION_DIR / "latest_direction_predictions.csv"
TOP20_PATH = PREDICTION_DIR / "kospi_top20_predictions.csv"
HISTORY_PATH = PREDICTION_DIR / "prediction_history.csv"


def prepare_latest_features() -> pd.DataFrame:
    """최신 KOSPI 종목별로 당일 장 마감 정보만 사용한 피처를 계산한다."""
    panel = add_features(load_panel())
    panel["stock_return_5d"] = panel.groupby("ticker")["close_price"].pct_change(5, fill_method=None)
    panel["stock_return_20d"] = panel.groupby("ticker")["close_price"].pct_change(20, fill_method=None)
    data = panel.merge(load_kospi_index(), on="trade_date", how="inner", validate="many_to_one")
    data["relative_strength_5d"] = data["stock_return_5d"] - data["kospi_return_5d"]
    data["relative_strength_20d"] = data["stock_return_20d"] - data["kospi_return_20d"]
    return (
        data.replace([np.inf, -np.inf], np.nan)
        .sort_values(["ticker", "trade_date"])
        .groupby("ticker", as_index=False)
        .tail(1)
        .copy()
    )


def load_model() -> tuple[object, str, list[str], float]:
    """최종 모델과 피처 목록, 홀드아웃 ROC-AUC를 읽는다."""
    if not MODEL_PATH.exists() or not SUMMARY_PATH.exists():
        raise FileNotFoundError(
            "최종 모델이 없습니다. python -m ml.kospi_market_holdout_benchmark 를 먼저 실행하세요."
        )
    artifact = joblib.load(MODEL_PATH)
    if not isinstance(artifact, dict) or "model" not in artifact or "features" not in artifact:
        raise ValueError("최종 모델 파일 형식이 올바르지 않습니다.")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    model_name = str(artifact.get("model_name", summary.get("selected_model", "최종 모델")))
    selected_result = next(
        (row for row in summary.get("holdout_results", []) if row.get("model") == model_name),
        {},
    )
    return artifact["model"], model_name, list(artifact["features"]), float(selected_result.get("roc_auc", np.nan))


def save_history(result: pd.DataFrame) -> None:
    """같은 기준일·종목·모델 조합은 한 번만 남겨 예측 이력을 보존한다."""
    record = result.copy()
    record["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if HISTORY_PATH.exists():
        history = pd.read_csv(HISTORY_PATH, encoding="utf-8-sig", dtype={"ticker": str})
        history = pd.concat([history, record], ignore_index=True)
        history = history.drop_duplicates(subset=["trade_date", "ticker", "model"], keep="last")
    else:
        history = record
    history.to_csv(HISTORY_PATH, index=False, encoding="utf-8-sig")


def main() -> None:
    model, model_name, features, holdout_auc = load_model()
    latest = prepare_latest_features()
    missing = set(features).difference(latest.columns)
    if missing:
        raise ValueError(f"예측 피처가 없습니다: {sorted(missing)}")
    usable = latest.dropna(subset=features).copy()
    if usable.empty:
        raise ValueError("예측 가능한 최신 종목이 없습니다. OHLCV와 KOSPI 지수를 먼저 적재하세요.")
    usable["up_probability"] = model.predict_proba(usable[features])[:, 1]
    usable["prediction"] = np.where(usable["up_probability"] >= 0.5, "상승", "하락 또는 보합")
    usable["model"] = model_name
    usable["validation_roc_auc"] = holdout_auc
    usable["prediction_rank"] = usable["up_probability"].rank(method="first", ascending=False).astype(int)
    result = usable[
        [
            "trade_date", "ticker", "name", "close_price", "up_probability", "prediction",
            "prediction_rank", "model", "validation_roc_auc",
        ]
    ].sort_values("up_probability", ascending=False)
    PREDICTION_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    result.head(20).to_csv(TOP20_PATH, index=False, encoding="utf-8-sig")
    save_history(result)
    print(f"최종 모델: {model_name} (홀드아웃 ROC-AUC {holdout_auc:.3f})")
    print(f"예측 기준일: {result['trade_date'].max().date()} · 예측 종목: {len(result):,}개")
    print(f"전체 예측 CSV: {OUTPUT_PATH}")
    print(f"상위 20개 CSV: {TOP20_PATH}")
    print(result.head(20).to_string(index=False, formatters={"up_probability": "{:.1%}".format}))


if __name__ == "__main__":
    main()
