import pandas as pd

from ml.flow_features import FLOW_FEATURE_COLUMNS, add_investor_flow_features


def test_add_investor_flow_features_keeps_missing_data_as_nan():
    prices = pd.DataFrame(
        {
            "ticker": ["005930"] * 5 + ["000660"],
            "trade_date": pd.date_range("2026-08-01", periods=5).tolist()
            + [pd.Timestamp("2026-08-01")],
            "close_price": [100] * 6,
            "volume": [10] * 6,
        }
    )
    flows = pd.DataFrame(
        {
            "ticker": ["005930"] * 5,
            "trade_date": pd.date_range("2026-08-01", periods=5),
            "foreign_net_value": [1, 2, 3, 4, 5],
            "institution_net_value": [1, 1, 1, 1, 1],
            "individual_net_value": [-2, -3, -4, -5, -6],
            "foreign_net_volume": [10, 20, 30, 40, 50],
            "institution_net_volume": [1, 1, 1, 1, 1],
            "individual_net_volume": [-11, -21, -31, -41, -51],
        }
    )

    result = add_investor_flow_features(prices, flows)

    samsung = result[result["ticker"] == "005930"].sort_values("trade_date")
    assert samsung.iloc[-1]["foreign_net_value_5d"] == 15
    assert samsung.iloc[-1]["foreign_net_volume_5d"] == 150
    assert samsung.iloc[-1]["foreign_net_value_ratio_1d"] == 0.005
    assert pd.isna(result.loc[result["ticker"] == "000660", "foreign_net_value_1d"].iloc[0])
    assert "foreign_net_value_20d" in FLOW_FEATURE_COLUMNS
