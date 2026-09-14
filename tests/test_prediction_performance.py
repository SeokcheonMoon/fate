import pandas as pd

import ml.track_prediction_performance as performance
from ml.track_prediction_performance import DAILY_SUMMARY_COLUMNS, build_daily_summary


def test_daily_performance_columns_cover_success_rate_recording():
    """일별 성과 파일은 날짜별 성공 수와 성공률을 함께 남긴다."""
    expected = {
        "model",
        "trade_date",
        "evaluated_predictions",
        "successful_predictions",
        "accuracy",
    }

    assert expected.issubset(DAILY_SUMMARY_COLUMNS)


def test_daily_success_rate_is_mean_of_prediction_correctness():
    detail = pd.DataFrame(
        {
            "model": ["model-a", "model-a", "model-a"],
            "trade_date": pd.to_datetime(["2026-09-10"] * 3),
            "correct": [True, False, True],
        }
    )

    detail["target_return_1d"] = [0.01, -0.01, 0.02]
    daily = build_daily_summary(detail)

    assert daily.iloc[0]["successful_predictions"] == 2
    assert daily.iloc[0]["accuracy"] == 2 / 3


def test_confirmed_actuals_excludes_predictions_without_next_close(monkeypatch):
    feature_rows = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-09-10", "2026-09-11"]),
            "ticker": ["005930", "005930"],
            "next_return_1d": [0.01, float("nan")],
        }
    )
    monkeypatch.setattr(performance, "load_panel", lambda: pd.DataFrame())
    monkeypatch.setattr(performance, "add_features", lambda _: feature_rows)

    actuals = performance.load_confirmed_actuals()

    assert len(actuals) == 1
    assert actuals.iloc[0]["target_up_1d"] == 1
    assert actuals.iloc[0]["target_return_1d"] == 0.01
