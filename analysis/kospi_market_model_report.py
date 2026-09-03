"""시장 결합 다음날 상승 분류 모델의 간단한 결과 리포트를 만든다.

실행:
    python -m analysis.kospi_market_model_report

워크포워드 검증 기간의 예측확률 상위 20% 종목과 전체 KOSPI 종목의 다음 거래일
평균 수익률을 비교한다. 이는 모델 선별력이 있는지 확인하는 요약 분석이며,
거래비용·체결·보유기간을 반영한 투자전략 백테스트는 아니다.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models"
OUTPUT_DIR = PROJECT_ROOT / "analysis" / "output"
PREDICTIONS_PATH = MODEL_DIR / "kospi_market_walk_forward_predictions.csv"
METRICS_PATH = MODEL_DIR / "kospi_market_walk_forward_metrics.csv"
MODEL_NAME = "OHLCV + KOSPI 시장"


def build_daily_comparison(predictions: pd.DataFrame) -> pd.DataFrame:
    """매 거래일 확률 상위 20%와 전체 종목의 실현 다음날 수익률을 비교한다."""
    records: list[dict[str, object]] = []
    for trade_date, group in predictions.groupby("trade_date"):
        group = group.dropna(subset=["up_probability", "next_return_1d"])
        if group.empty:
            continue
        top_count = max(1, int(len(group) * 0.2))
        selected = group.nlargest(top_count, "up_probability")
        universe_return = group["next_return_1d"].mean()
        selected_return = selected["next_return_1d"].mean()
        records.append(
            {
                "signal_date": trade_date,
                "stocks_evaluated": len(group),
                "selected_stocks": len(selected),
                "universe_next_return": universe_return,
                "top_quintile_next_return": selected_return,
                "excess_return": selected_return - universe_return,
                "top_quintile_win": selected_return > universe_return,
            }
        )
    daily = pd.DataFrame(records).sort_values("signal_date")
    daily["universe_cumulative_return"] = (1 + daily["universe_next_return"]).cumprod() - 1
    daily["top_quintile_cumulative_return"] = (1 + daily["top_quintile_next_return"]).cumprod() - 1
    return daily


def build_summary(daily: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    """사용자가 바로 해석할 수 있는 소수의 핵심 지표만 요약한다."""
    market_metrics = metrics.loc[metrics["model"] == MODEL_NAME]
    return pd.DataFrame(
        {
            "metric": [
                "검증 시작일",
                "검증 종료일",
                "검증 거래일 수",
                "평균 ROC-AUC",
                "평균 정확도",
                "다수 클래스 기준 정확도",
                "상위 20% 평균 다음날 수익률",
                "전체 종목 평균 다음날 수익률",
                "상위 20% 일평균 초과수익률",
                "상위 20%가 전체 평균을 이긴 거래일 비율",
                "상위 20% 누적수익률(비용 미반영)",
                "전체 종목 누적수익률(비용 미반영)",
            ],
            "value": [
                str(daily["signal_date"].min().date()),
                str(daily["signal_date"].max().date()),
                len(daily),
                market_metrics["roc_auc"].mean(),
                market_metrics["accuracy"].mean(),
                market_metrics["majority_baseline_accuracy"].mean(),
                daily["top_quintile_next_return"].mean(),
                daily["universe_next_return"].mean(),
                daily["excess_return"].mean(),
                daily["top_quintile_win"].mean(),
                daily["top_quintile_cumulative_return"].iloc[-1],
                daily["universe_cumulative_return"].iloc[-1],
            ],
        }
    )


def save_chart(daily: pd.DataFrame) -> None:
    """상위 확률 종목과 전체 종목의 비용 미반영 누적 성과를 저장한다."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    axes[0].plot(
        daily["signal_date"], daily["top_quintile_cumulative_return"] * 100,
        label="예측확률 상위 20%", color="#2a6fbb",
    )
    axes[0].plot(
        daily["signal_date"], daily["universe_cumulative_return"] * 100,
        label="전체 KOSPI 종목 평균", color="#7f8c8d",
    )
    axes[0].set(title="워크포워드 구간 누적수익률(거래비용 미반영)", xlabel="신호일", ylabel="누적수익률(%)")
    axes[0].legend()
    axes[1].hist(daily["excess_return"] * 100, bins=45, color="#2a9d8f")
    axes[1].axvline(0, color="black", linewidth=1)
    axes[1].set(title="상위 20%의 일별 초과수익률 분포", xlabel="전체 평균 대비 초과수익률(%p)", ylabel="거래일 수")
    figure.savefig(OUTPUT_DIR / "kospi_market_model_report.png", dpi=180)
    plt.close(figure)


def main() -> None:
    if not PREDICTIONS_PATH.exists() or not METRICS_PATH.exists():
        raise FileNotFoundError("시장 결합 모델을 먼저 실행하세요: python -m ml.kospi_market_walk_forward")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(PREDICTIONS_PATH, parse_dates=["trade_date"])
    predictions = predictions.loc[predictions["model"] == MODEL_NAME].copy()
    metrics = pd.read_csv(METRICS_PATH)
    daily = build_daily_comparison(predictions)
    summary = build_summary(daily, metrics)
    daily.to_csv(OUTPUT_DIR / "kospi_market_simple_evaluation_daily.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / "kospi_market_model_summary.csv", index=False, encoding="utf-8-sig")
    save_chart(daily)
    print("시장 결합 모델 간단 평가 완료")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print("\n주의: 위 누적수익률은 예측 순위의 선별력 확인용이며 거래비용·체결 제약은 반영하지 않았습니다.")


if __name__ == "__main__":
    main()
