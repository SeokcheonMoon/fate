"""FATE 예측용 원천 데이터를 오늘 기준으로 증분 갱신한다.

실행:
    python -m etl.daily_update
"""

from __future__ import annotations

from datetime import date, timedelta

from etl.investor_flow_pykrx_loader import run_loader
from etl.market_loader import load_latest_kospi_index
from etl.stock_loader import load_all_latest_stock_prices


def main() -> None:
    end_date = date.today().strftime("%Y%m%d")
    print(f"FATE 일일 증분 갱신 시작: {end_date}")
    load_all_latest_stock_prices(end_date=end_date)
    load_latest_kospi_index(end_date=end_date)
    run_loader(
        tickers=None,
        requested_start=date.today() - timedelta(days=31),
        end=date.today(),
        sleep_seconds=0.4,
    )


if __name__ == "__main__":
    main()
