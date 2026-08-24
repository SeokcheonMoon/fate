"""미적재 KOSPI·KOSDAQ 종목의 초기 주가 데이터를 배치로 적재한다.

예시:
    python -m etl.initial_stock_loader --batch-size 50
    python -m etl.initial_stock_loader --all
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta

from sqlalchemy import bindparam, text

from config.database import engine
from etl.stock_loader import load_stock_prices, save_etl_log


def get_unloaded_tickers(markets: list[str], limit: int | None) -> list[str]:
    """주가가 한 건도 없는 종목만 코드순으로 조회한다."""
    query = text("""
        SELECT s.ticker
        FROM stocks AS s
        WHERE s.market IN :markets
          AND NOT EXISTS (
              SELECT 1
              FROM stock_prices AS p
              WHERE p.stock_id = s.stock_id
          )
        ORDER BY s.ticker
    """).bindparams(bindparam("markets", expanding=True))
    if limit is not None:
        query = text(f"{query.text}\nLIMIT :limit").bindparams(
            bindparam("markets", expanding=True)
        )

    parameters: dict[str, object] = {"markets": markets}
    if limit is not None:
        parameters["limit"] = limit
    with engine.connect() as connection:
        return connection.execute(query, parameters).scalars().all()


def parse_arguments() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(description="미적재 종목의 일별 OHLCV 초기 적재")
    parser.add_argument(
        "--start-date",
        default=(today - timedelta(days=365)).strftime("%Y%m%d"),
        help="적재 시작일(YYYYMMDD). 기본값: 최근 1년",
    )
    parser.add_argument(
        "--end-date",
        default=today.strftime("%Y%m%d"),
        help="적재 종료일(YYYYMMDD). 기본값: 오늘",
    )
    parser.add_argument(
        "--batch-size", type=int, default=50, help="한 번에 처리할 종목 수. 기본값: 50",
    )
    parser.add_argument(
        "--all", action="store_true", help="남은 모든 종목을 처리한다. 장시간 실행될 수 있다.")
    parser.add_argument(
        "--sleep-seconds", type=float, default=0.2, help="API 요청 간 대기 시간(초)")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if args.batch_size < 1:
        raise ValueError("--batch-size는 1 이상이어야 합니다.")

    tickers = get_unloaded_tickers(
        markets=["KOSPI", "KOSDAQ"],
        limit=None if args.all else args.batch_size,
    )
    if not tickers:
        print("초기 적재가 필요한 KOSPI·KOSDAQ 종목이 없습니다.")
        return

    print(f"초기 적재 대상: {len(tickers):,}개 종목 ({args.start_date} ~ {args.end_date})")
    success_count = 0
    failed_count = 0
    for index, ticker in enumerate(tickers, start=1):
        try:
            load_stock_prices(ticker, args.start_date, args.end_date)
            success_count += 1
        except Exception as error:
            failed_count += 1
            save_etl_log(
                ticker=ticker,
                start_date=args.start_date,
                end_date=args.end_date,
                status="FAILED",
                error_message=str(error)[:1000],
            )
            print(f"{ticker} 적재 실패: {error}")

        if index < len(tickers):
            time.sleep(args.sleep_seconds)

    print(f"배치 완료: 성공 {success_count:,}개 / 실패 {failed_count:,}개")
    if not args.all:
        print("남은 종목은 같은 명령을 다시 실행해 다음 배치로 적재하세요.")


if __name__ == "__main__":
    main()
