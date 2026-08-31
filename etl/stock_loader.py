"""KRX 유가증권 일별매매정보를 ``stock_prices``에 적재한다."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta

from sqlalchemy import text

from config.database import engine
from etl.krx_client import fetch_rows


KOSPI_DAILY_TRADE_PATH = "sto/stk_bydd_trd"


def save_etl_log(
    ticker: str | None, start_date: str, end_date: str, status: str,
    records_processed: int = 0, error_message: str | None = None,
) -> None:
    """ETL 실행 결과를 기록한다. KRX는 시장 단위 요청이라 ticker는 NULL이다."""
    log_sql = text("""
        INSERT INTO etl_logs (pipeline_name, ticker, start_date, end_date, status,
                              records_processed, error_message)
        VALUES ('krx_stock_loader', :ticker, :start_date, :end_date, :status,
                :records_processed, :error_message)
    """)
    with engine.begin() as connection:
        connection.execute(log_sql, {
            "ticker": ticker, "start_date": start_date, "end_date": end_date,
            "status": status, "records_processed": records_processed,
            "error_message": error_message,
        })


def _as_int(value: object) -> int | None:
    if value in (None, "", "-"):
        return None
    return int(str(value).replace(",", ""))


def load_stock_prices_for_date(base_date: str) -> int:
    """한 거래일의 KOSPI 전 종목 OHLCV를 한 번의 API 요청으로 적재한다."""
    market_rows = fetch_rows(KOSPI_DAILY_TRADE_PATH, base_date)
    if not market_rows:
        save_etl_log(None, base_date, base_date, "SKIPPED")
        print(f"{base_date}: 거래 데이터가 없습니다.")
        return 0

    upsert_sql = text("""
        INSERT INTO stock_prices (
            stock_id, trade_date, open_price, high_price, low_price, close_price, volume
        )
        SELECT stock_id, :trade_date, :open_price, :high_price, :low_price,
               :close_price, :volume
        FROM stocks
        WHERE ticker = :ticker AND market = 'KOSPI'
        ON DUPLICATE KEY UPDATE
            open_price = VALUES(open_price), high_price = VALUES(high_price),
            low_price = VALUES(low_price), close_price = VALUES(close_price),
            volume = VALUES(volume)
    """)
    price_rows = [
        {
            "ticker": str(row["ISU_CD"])[-6:],
            "trade_date": datetime.strptime(str(row.get("BAS_DD", base_date)), "%Y%m%d").date(),
            "open_price": _as_int(row.get("TDD_OPNPRC")),
            "high_price": _as_int(row.get("TDD_HGPRC")),
            "low_price": _as_int(row.get("TDD_LWPRC")),
            "close_price": _as_int(row.get("TDD_CLSPRC")),
            "volume": _as_int(row.get("ACC_TRDVOL")),
        }
        for row in market_rows
        if row.get("ISU_CD") and row.get("TDD_CLSPRC") not in (None, "", "-")
    ]
    with engine.begin() as connection:
        result = connection.execute(upsert_sql, price_rows)
    processed = result.rowcount
    save_etl_log(None, base_date, base_date, "SUCCESS", processed)
    print(f"{base_date}: KOSPI 일별 시세 {processed:,}건 적재 완료")
    return processed


def _iter_dates(start_date: str, end_date: str):
    current = datetime.strptime(start_date, "%Y%m%d").date()
    final = datetime.strptime(end_date, "%Y%m%d").date()
    while current <= final:
        if current.weekday() < 5:
            yield current.strftime("%Y%m%d")
        current += timedelta(days=1)


def load_all_stock_prices(start_date: str, end_date: str) -> int:
    """기간 내 KOSPI 전 종목 일별 시세를 날짜별로 적재한다."""
    return sum(load_stock_prices_for_date(day) for day in _iter_dates(start_date, end_date))


def load_all_latest_stock_prices(end_date: str | None = None) -> int:
    """마지막 KOSPI 적재일 다음 거래일부터 증분 적재한다."""
    end_date = end_date or date.today().strftime("%Y%m%d")
    with engine.connect() as connection:
        last_date = connection.execute(text("""
            SELECT MAX(p.trade_date)
            FROM stock_prices AS p JOIN stocks AS s ON s.stock_id = p.stock_id
            WHERE s.market = 'KOSPI'
        """)).scalar()
    if last_date is None:
        raise ValueError("KOSPI 초기 적재가 없습니다. --start-date를 지정해 먼저 적재하세요.")
    return load_all_stock_prices((last_date + timedelta(days=1)).strftime("%Y%m%d"), end_date)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KRX 유가증권 일별매매정보 적재")
    parser.add_argument("--start-date", help="초기 적재 시작일(YYYYMMDD)")
    parser.add_argument("--end-date", default=date.today().strftime("%Y%m%d"))
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    if arguments.start_date:
        load_all_stock_prices(arguments.start_date, arguments.end_date)
    else:
        load_all_latest_stock_prices(arguments.end_date)
