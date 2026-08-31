"""KOSPI OHLCV 패널 데이터의 전처리, EDA, 확인적 데이터 분석(CDA).

실행:
    python -m analysis.ohlcv_eda

생성물:
    data/processed/kospi_ohlcv_panel.csv
    analysis/output/ohlcv_eda_*.png
    analysis/output/ohlcv_cda_results.csv
    analysis/output/ohlcv_data_quality.csv
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

from config.database import engine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "analysis" / "output"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PANEL_PATH = PROCESSED_DIR / "kospi_ohlcv_panel.csv"

FEATURES = {
    "return_1d": "전일 종가 변화율",
    "volume_change_1d": "거래량 변화율",
    "volume_ratio_20": "20일 평균 대비 거래량",
    "intraday_range": "장중 변동성",
    "ma_5_ratio": "5일 이동평균 괴리율",
    "ma_20_ratio": "20일 이동평균 괴리율",
    "rsi_14": "RSI(14)",
    "macd_ratio": "종가 대비 MACD",
}

CHART_LABELS = {
    **FEATURES,
    "next_return_1d_winsor": "다음 거래일 수익률",
}


def load_panel() -> pd.DataFrame:
    """KOSPI 종목·일별시세를 하나의 패널 데이터로 읽는다."""
    query = text("""
        SELECT s.ticker, s.name, s.market, p.trade_date,
               p.open_price, p.high_price, p.low_price, p.close_price, p.volume
        FROM stock_prices AS p
        JOIN stocks AS s ON s.stock_id = p.stock_id
        WHERE s.market = 'KOSPI'
        ORDER BY s.ticker, p.trade_date
    """)
    with engine.connect() as connection:
        panel = pd.read_sql(query, connection, parse_dates=["trade_date"])
    if panel.empty:
        raise ValueError("KOSPI 시세가 없습니다. stock_loader를 먼저 실행하세요.")
    return panel


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    """미래 정보를 쓰지 않는 기술·거래량 피처와 다음 거래일 수익률을 만든다."""
    result = panel.copy().sort_values(["ticker", "trade_date"])
    price_columns = ["open_price", "high_price", "low_price", "close_price", "volume"]
    result[price_columns] = result[price_columns].apply(pd.to_numeric, errors="coerce")

    grouped = result.groupby("ticker", group_keys=False)
    result["return_1d"] = grouped["close_price"].pct_change(fill_method=None)
    result["next_return_1d"] = result.groupby("ticker")["return_1d"].shift(-1)
    result["volume_change_1d"] = grouped["volume"].pct_change(fill_method=None)
    result["volume_ratio_20"] = result["volume"].div(
        grouped["volume"].transform(lambda values: values.rolling(20, min_periods=20).mean())
    )
    result["intraday_range"] = (result["high_price"] - result["low_price"]).div(
        result["close_price"].replace(0, np.nan)
    )
    for window in (5, 20, 60):
        moving_average = grouped["close_price"].transform(
            lambda values: values.rolling(window, min_periods=window).mean()
        )
        result[f"ma_{window}_ratio"] = result["close_price"].div(moving_average) - 1

    delta = grouped["close_price"].diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.groupby(result["ticker"]).transform(
        lambda values: values.rolling(14, min_periods=14).mean()
    )
    average_loss = losses.groupby(result["ticker"]).transform(
        lambda values: values.rolling(14, min_periods=14).mean()
    )
    relative_strength = average_gain.div(average_loss.replace(0, np.nan))
    result["rsi_14"] = 100 - (100 / (1 + relative_strength))

    ema_12 = grouped["close_price"].transform(lambda values: values.ewm(span=12, adjust=False).mean())
    ema_26 = grouped["close_price"].transform(lambda values: values.ewm(span=26, adjust=False).mean())
    result["macd"] = ema_12 - ema_26
    result["macd_signal"] = result.groupby("ticker")["macd"].transform(
        lambda values: values.ewm(span=9, adjust=False).mean()
    )
    result["macd_ratio"] = result["macd"].div(result["close_price"].replace(0, np.nan))
    result["target_up_1d"] = (result["next_return_1d"] > 0).astype("Int64")

    # 극단적 기업행사/거래정지의 영향을 줄이고, 수익률·거래량 변화율은 1%/99% 절단한다.
    for column in ("return_1d", "next_return_1d", "volume_change_1d"):
        lower, upper = result[column].quantile([0.01, 0.99])
        result[f"{column}_winsor"] = result[column].clip(lower, upper)
    return result


def data_quality(panel: pd.DataFrame) -> pd.DataFrame:
    """EDA 이전에 확인해야 할 행·종목·결측·중복 상태를 요약한다."""
    return pd.DataFrame(
        {
            "metric": [
                "rows", "stocks", "start_date", "end_date", "duplicate_stock_dates",
                "missing_ohlcv_cells", "zero_or_negative_close", "zero_or_negative_volume",
            ],
            "value": [
                len(panel), panel["ticker"].nunique(), panel["trade_date"].min().date(),
                panel["trade_date"].max().date(),
                panel.duplicated(["ticker", "trade_date"]).sum(),
                panel[["open_price", "high_price", "low_price", "close_price", "volume"]].isna().sum().sum(),
                (panel["close_price"] <= 0).sum(), (panel["volume"] <= 0).sum(),
            ],
        }
    )


def daily_spearman_ic(data: pd.DataFrame, feature: str) -> pd.Series:
    """날짜별 횡단면 Spearman 상관계수(Information Coefficient)를 계산한다."""
    values: dict[pd.Timestamp, float] = {}
    for trade_date, group in data[["trade_date", feature, "next_return_1d_winsor"]].dropna().groupby("trade_date"):
        if len(group) >= 30 and group[feature].nunique() > 1:
            values[trade_date] = stats.spearmanr(group[feature], group["next_return_1d_winsor"]).statistic
    return pd.Series(values, name=feature)


def newey_west_mean_test(values: pd.Series, lags: int = 5) -> tuple[float, float, float, float]:
    """일별 시계열 평균의 HAC(Newey-West) 표준오차·p값·95% CI를 계산한다."""
    series = values.dropna().astype(float).to_numpy()
    n = len(series)
    if n < 10:
        return (np.nan, np.nan, np.nan, np.nan)
    centered = series - series.mean()
    long_run_variance = np.mean(centered * centered)
    for lag in range(1, min(lags, n - 1) + 1):
        covariance = np.mean(centered[lag:] * centered[:-lag])
        long_run_variance += 2 * (1 - lag / (lags + 1)) * covariance
    standard_error = np.sqrt(max(long_run_variance, 0) / n)
    mean = series.mean()
    if standard_error == 0:
        return (mean, standard_error, np.nan, np.nan)
    t_statistic = mean / standard_error
    p_value = 2 * stats.t.sf(abs(t_statistic), df=n - 1)
    interval = stats.t.ppf(0.975, df=n - 1) * standard_error
    return (mean, standard_error, p_value, interval)


def cda_results(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """사전 정의한 피처가 다음날 수익률과 관계가 있는지 날짜별 횡단면으로 검정한다."""
    usable = panel.replace([np.inf, -np.inf], np.nan).copy()
    records: list[dict[str, object]] = []
    ic_series: dict[str, pd.Series] = {}
    for feature, label in FEATURES.items():
        ic = daily_spearman_ic(usable, feature)
        ic_series[feature] = ic
        mean_ic, ic_se, p_value, interval = newey_west_mean_test(ic)

        spreads: dict[pd.Timestamp, float] = {}
        for trade_date, group in usable[["trade_date", feature, "next_return_1d_winsor"]].dropna().groupby("trade_date"):
            if len(group) < 50 or group[feature].nunique() < 5:
                continue
            ranked = group[feature].rank(method="first", pct=True)
            high = group.loc[ranked >= 0.8, "next_return_1d_winsor"].mean()
            low = group.loc[ranked <= 0.2, "next_return_1d_winsor"].mean()
            spreads[trade_date] = high - low
        mean_spread, spread_se, spread_p, spread_interval = newey_west_mean_test(pd.Series(spreads))
        records.append(
            {
                "feature": feature,
                "label": label,
                "observed_days": len(ic),
                "mean_spearman_ic": mean_ic,
                "ic_hac_se": ic_se,
                "ic_p_value": p_value,
                "ic_95_ci_half_width": interval,
                "q5_minus_q1_next_return": mean_spread,
                "spread_hac_se": spread_se,
                "spread_p_value": spread_p,
                "spread_95_ci_half_width": spread_interval,
            }
        )
    results = pd.DataFrame(records)
    # 여러 가설을 동시에 보므로 Benjamini-Hochberg 방식으로 FDR 보정한다.
    ordered = results["ic_p_value"].rank(method="first")
    results["ic_p_value_fdr"] = (results["ic_p_value"] * len(results) / ordered).clip(upper=1)
    results["significant_at_5pct_fdr"] = results["ic_p_value_fdr"] < 0.05
    return results.sort_values("ic_p_value"), ic_series


def save_eda_charts(panel: pd.DataFrame, cda: pd.DataFrame, ic_series: dict[str, pd.Series]) -> None:
    """분포·상관·기술지표·가설검정 결과를 시각화한다."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    analysis_data = panel.replace([np.inf, -np.inf], np.nan).dropna(subset=["next_return_1d_winsor"])

    figure, axes = plt.subplots(2, 2, figsize=(16, 11), constrained_layout=True)
    axes[0, 0].hist(analysis_data["next_return_1d_winsor"] * 100, bins=80, color="#2a6fbb")
    axes[0, 0].axvline(0, color="black", linewidth=1)
    axes[0, 0].set(title="다음 거래일 수익률 분포", xlabel="수익률(%)", ylabel="관측치 수")

    correlation_columns = list(FEATURES) + ["next_return_1d_winsor"]
    correlations = analysis_data[correlation_columns].corr(method="spearman")
    image = axes[0, 1].imshow(correlations, vmin=-1, vmax=1, cmap="coolwarm")
    axes[0, 1].set(title="스피어만 상관계수 행렬")
    chart_labels = [CHART_LABELS[column] for column in correlation_columns]
    axes[0, 1].set_xticks(range(len(correlation_columns)), chart_labels, rotation=55, ha="right")
    axes[0, 1].set_yticks(range(len(correlation_columns)), chart_labels)
    figure.colorbar(image, ax=axes[0, 1], shrink=0.8)

    sample = analysis_data[["volume_change_1d_winsor", "next_return_1d_winsor"]].dropna()
    sample = sample.sample(min(12_000, len(sample)), random_state=42)
    axes[1, 0].scatter(sample["volume_change_1d_winsor"] * 100, sample["next_return_1d_winsor"] * 100,
                       alpha=0.08, s=8, color="#6b4c9a")
    bins = pd.qcut(analysis_data["volume_change_1d_winsor"], q=20, duplicates="drop")
    binned = analysis_data.groupby(bins, observed=True).agg(
        x=("volume_change_1d_winsor", "mean"), y=("next_return_1d_winsor", "mean")
    )
    axes[1, 0].plot(binned["x"] * 100, binned["y"] * 100, color="#e45756", linewidth=2)
    axes[1, 0].set(title="거래량 변화율과 다음 거래일 수익률", xlabel="거래량 변화율(%)", ylabel="다음 거래일 수익률(%)")

    ic_frame = pd.DataFrame(ic_series)
    for feature in ("return_1d", "volume_ratio_20", "rsi_14", "macd_ratio"):
        if feature in ic_frame:
            axes[1, 1].plot(
                ic_frame.index, ic_frame[feature].rolling(20, min_periods=10).mean(),
                label=CHART_LABELS[feature],
            )
    axes[1, 1].axhline(0, color="black", linewidth=1)
    axes[1, 1].set(title="20일 이동 횡단면 스피어만 IC", xlabel="거래일", ylabel="IC")
    axes[1, 1].legend(fontsize=8)
    figure.savefig(OUTPUT_DIR / "ohlcv_eda_overview.png", dpi=180)
    plt.close(figure)

    samsung = panel.loc[panel["ticker"] == "005930"].dropna(subset=["rsi_14"]).copy()
    if not samsung.empty:
        figure, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True, constrained_layout=True,
                                    gridspec_kw={"height_ratios": [2, 1, 1]})
        axes[0].plot(samsung["trade_date"], samsung["close_price"], label="종가", color="#2a6fbb")
        axes[0].plot(samsung["trade_date"], samsung["close_price"] / (1 + samsung["ma_20_ratio"]),
                     label="20일 이동평균", color="#e45756")
        axes[0].set(title="삼성전자: 주가와 기술지표", ylabel="원")
        axes[0].legend()
        axes[1].plot(samsung["trade_date"], samsung["rsi_14"], color="#6b4c9a")
        axes[1].axhline(70, color="#e45756", linestyle="--"); axes[1].axhline(30, color="#2a6fbb", linestyle="--")
        axes[1].set(ylabel="RSI(14)")
        axes[2].bar(samsung["trade_date"], samsung["macd"], color=np.where(samsung["macd"] >= 0, "#2a9d8f", "#e45756"))
        axes[2].plot(samsung["trade_date"], samsung["macd_signal"], color="black", linewidth=1, label="시그널")
        axes[2].set(ylabel="MACD", xlabel="거래일"); axes[2].legend()
        figure.savefig(OUTPUT_DIR / "ohlcv_eda_technical_indicators.png", dpi=180)
        plt.close(figure)

    plotted = cda.sort_values("mean_spearman_ic")
    figure, axis = plt.subplots(figsize=(13, 6), constrained_layout=True)
    axis.barh(plotted["label"], plotted["mean_spearman_ic"], xerr=plotted["ic_95_ci_half_width"],
              color=np.where(plotted["significant_at_5pct_fdr"], "#2a9d8f", "#9aa0a6"), capsize=3)
    axis.axvline(0, color="black", linewidth=1)
    axis.set(title="CDA: 피처와 다음 거래일 수익률의 관계", xlabel="일별 스피어만 IC 평균(95% HAC 신뢰구간)")
    figure.savefig(OUTPUT_DIR / "ohlcv_cda_hypothesis_tests.png", dpi=180)
    plt.close(figure)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw_panel = load_panel()
    quality = data_quality(raw_panel)
    panel = add_features(raw_panel)
    cda, ic_series = cda_results(panel)
    panel.to_csv(PANEL_PATH, index=False, encoding="utf-8-sig")
    quality.to_csv(OUTPUT_DIR / "ohlcv_data_quality.csv", index=False, encoding="utf-8-sig")
    cda.to_csv(OUTPUT_DIR / "ohlcv_cda_results.csv", index=False, encoding="utf-8-sig")
    save_eda_charts(panel, cda, ic_series)
    print(quality.to_string(index=False))
    print("\nCDA results")
    print(cda.to_string(index=False, float_format=lambda value: f"{value:.6f}"))
    print(f"\nPanel: {PANEL_PATH}")
    print(f"Charts and results: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
