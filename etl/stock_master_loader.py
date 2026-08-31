"""KRX 유가증권 종목기본정보를 ``stocks`` 테이블에 동기화한다.

실행: ``python -m etl.stock_master_loader --base-date 20260828``
"""

from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import text

from config.database import engine
from etl.krx_client import fetch_rows


KOSPI_STOCK_INFO_PATH = "sto/stk_isu_base_info"


def normalize_ticker(value: object) -> str:
    """KRX 단축코드를 6자리 문자열로 정규화한다."""
    return str(value).split(".")[0].zfill(6)


def get_stock_master(base_date: str) -> list[dict[str, object]]:
    """기준일의 유가증권 종목기본정보를 조회한다."""
    return fetch_rows(KOSPI_STOCK_INFO_PATH, base_date)


def load_stock_master(base_date: str | None = None) -> int:
    """유가증권 종목 코드·이름을 upsert하고 적재 건수를 반환한다."""
    base_date = base_date or date.today().strftime("%Y%m%d")
    rows = get_stock_master(base_date)
    stock_rows = [
        {
            "ticker": normalize_ticker(row["ISU_SRT_CD"]),
            "name": str(row["ISU_NM"]),
            "market": "KOSPI",
        }
        for row in rows
        if row.get("ISU_SRT_CD") and row.get("ISU_NM")
    ]
    if not stock_rows:
        print(f"{base_date}: KOSPI 종목기본정보가 없습니다.")
        return 0

    upsert_sql = text("""
        INSERT INTO stocks (ticker, name, market)
        VALUES (:ticker, :name, :market)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name), market = VALUES(market)
    """)
    with engine.begin() as connection:
        connection.execute(upsert_sql, stock_rows)
    print(f"{base_date}: KOSPI 종목 {len(stock_rows):,}개 동기화 완료")
    return len(stock_rows)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KRX 유가증권 종목기본정보 동기화")
    parser.add_argument("--base-date", default=date.today().strftime("%Y%m%d"))
    return parser.parse_args()


if __name__ == "__main__":
    load_stock_master(parse_arguments().base_date)
