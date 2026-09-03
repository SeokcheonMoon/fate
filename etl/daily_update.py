"""KRX 기반 KOSPI 종목·일별 시세의 일일 증분 갱신 진입점."""

from __future__ import annotations

from datetime import date

from etl.stock_loader import load_all_latest_stock_prices
from etl.stock_master_loader import load_stock_master
from etl.market_loader import load_latest_kospi_index


def main() -> None:
    base_date = date.today().strftime("%Y%m%d")
    load_stock_master(base_date)
    load_all_latest_stock_prices(base_date)
    load_latest_kospi_index(base_date)


if __name__ == "__main__":
    main()
