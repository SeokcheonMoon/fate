"""KOSPI·KOSDAQ 종목 마스터를 stocks 테이블에 동기화한다.

실행:
    python -m etl.stock_master_loader
"""

from __future__ import annotations

import FinanceDataReader as fdr
from sqlalchemy import text

from config.database import engine


MARKETS = ("KOSPI", "KOSDAQ")


def normalize_ticker(value: object) -> str:
    """CSV/캐시에서 숫자로 읽힌 종목코드도 6자리 문자열로 정규화한다."""
    return str(value).split(".")[0].zfill(6)


def get_market_listing(market: str):
    """공개 캐시 기반 FinanceDataReader에서 시장별 상장 종목을 가져온다."""
    listing = fdr.StockListing(market)
    required_columns = {"Code", "Name"}
    missing_columns = required_columns.difference(listing.columns)
    if missing_columns or listing.empty:
        raise RuntimeError(
            f"{market} 종목 목록을 조회하지 못했습니다. "
            f"누락 컬럼: {sorted(missing_columns)}"
        )
    return listing


def load_stock_master(markets: tuple[str, ...] = MARKETS) -> dict[str, int]:
    """각 시장의 종목 코드·이름을 upsert한다."""
    upsert_sql = text("""
        INSERT INTO stocks (ticker, name, market)
        VALUES (:ticker, :name, :market)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            market = VALUES(market)
    """)

    results: dict[str, int] = {}
    for market in markets:
        listing = get_market_listing(market)
        rows = [
            {
                "ticker": normalize_ticker(row.Code),
                "name": str(row.Name),
                "market": market,
            }
            for row in listing[["Code", "Name"]].itertuples(index=False)
        ]
        with engine.begin() as connection:
            connection.execute(upsert_sql, rows)
        results[market] = len(rows)
        print(f"{market}: {len(rows):,}개 종목 동기화 완료")
    return results


if __name__ == "__main__":
    load_stock_master()
