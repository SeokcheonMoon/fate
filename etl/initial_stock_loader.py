"""KRX 기반 KOSPI 초기 적재 호환 진입점.

이전의 종목별 배치 방식은 더 이상 필요하지 않다. KRX는 하루 전 종목을 한 번에
제공하므로 날짜별로 적재한다.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from etl.stock_loader import load_all_stock_prices
from etl.stock_master_loader import load_stock_master


def main() -> None:
    today = date.today()
    parser = argparse.ArgumentParser(description="KRX KOSPI 초기 일별 시세 적재")
    parser.add_argument("--start-date", default=(today - timedelta(days=365)).strftime("%Y%m%d"))
    parser.add_argument("--end-date", default=today.strftime("%Y%m%d"))
    args = parser.parse_args()
    load_stock_master(args.end_date)
    load_all_stock_prices(args.start_date, args.end_date)


if __name__ == "__main__":
    main()
