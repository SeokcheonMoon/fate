"""투자자별 수급 원천 데이터를 모델 입력 피처로 변환한다."""

from __future__ import annotations

import pandas as pd


INVESTORS = ("foreign", "institution", "individual")
WINDOWS = (1, 5, 20)


def feature_columns() -> list[str]:
    """수급 적재 후 모델에 추가할 피처명 목록을 반환한다."""
    columns: list[str] = []
    for investor in INVESTORS:
        columns.extend(
            f"{investor}_net_value_{window}d" for window in WINDOWS
        )
        columns.append(f"{investor}_net_value_ratio_1d")
        columns.extend(
            f"{investor}_net_volume_{window}d" for window in WINDOWS
        )
    return columns


FLOW_FEATURE_COLUMNS = feature_columns()


def add_investor_flow_features(
    prices: pd.DataFrame, flows: pd.DataFrame
) -> pd.DataFrame:
    """주가 행에 1·5·20일 순매수와 거래대금 대비 순매수 비율을 붙인다.

    ``prices``에는 ticker, trade_date, close_price, volume이 필요하고,
    ``flows``에는 ticker, trade_date와 투자자별 순매수 금액·수량이 필요하다.
    수급 원천이 없는 종목·일자는 결측으로 보존해 임의의 0 순매수로 해석하지 않는다.
    """
    required_price = {"ticker", "trade_date", "close_price", "volume"}
    required_flow = {"ticker", "trade_date"}
    required_flow.update(
        f"{investor}_net_{unit}"
        for investor in INVESTORS
        for unit in ("value", "volume")
    )
    missing_price = required_price - set(prices.columns)
    missing_flow = required_flow - set(flows.columns)
    if missing_price:
        raise ValueError(f"주가 데이터 필수 열 누락: {sorted(missing_price)}")
    if missing_flow:
        raise ValueError(f"수급 데이터 필수 열 누락: {sorted(missing_flow)}")

    result = prices.copy()
    result["ticker"] = result["ticker"].astype(str).str.zfill(6)
    result["trade_date"] = pd.to_datetime(result["trade_date"])

    normalized_flows = flows.copy()
    normalized_flows["ticker"] = normalized_flows["ticker"].astype(str).str.zfill(6)
    normalized_flows["trade_date"] = pd.to_datetime(normalized_flows["trade_date"])
    numeric_columns = sorted(required_flow - {"ticker", "trade_date"})
    normalized_flows[numeric_columns] = normalized_flows[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )

    result = result.merge(
        normalized_flows, on=["ticker", "trade_date"], how="left", validate="one_to_one"
    )
    result = result.sort_values(["ticker", "trade_date"]).reset_index(drop=True)
    trading_value = pd.to_numeric(result["close_price"], errors="coerce") * pd.to_numeric(
        result["volume"], errors="coerce"
    )

    for investor in INVESTORS:
        for unit in ("value", "volume"):
            raw_column = f"{investor}_net_{unit}"
            for window in WINDOWS:
                feature = f"{raw_column}_{window}d"
                result[feature] = result.groupby("ticker", group_keys=False)[raw_column].transform(
                    lambda values: values.rolling(window, min_periods=window).sum()
                )
        ratio_column = f"{investor}_net_value_ratio_1d"
        result[ratio_column] = result[f"{investor}_net_value_1d"].div(
            trading_value.where(trading_value.ne(0))
        )

    return result.drop(
        columns=sorted(required_flow - {"ticker", "trade_date"}), errors="ignore"
    )
