from pykrx import stock
from sqlalchemy import text

from config.database import engine

def save_etl_log(
    ticker: str,
    start_date: str,
    end_date: str,
    status: str,
    records_processed: int = 0,
    error_message: str | None = None,
):
    """ETL 실행 결과를 etl_logs 테이블에 저장한다."""

    log_sql = text("""
        INSERT INTO etl_logs (
            pipeline_name,
            ticker,
            start_date,
            end_date,
            status,
            records_processed,
            error_message
        )
        VALUES (
            'stock_loader',
            :ticker,
            :start_date,
            :end_date,
            :status,
            :records_processed,
            :error_message
        )
    """)

    with engine.begin() as connection:
        connection.execute(
            log_sql,
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "status": status,
                "records_processed": records_processed,
                "error_message": error_message,
            },
        )


def load_stock_prices(ticker: str, start_date: str, end_date: str):
    """pykrx 일별 주가 데이터를 MySQL stock_prices 테이블에 저장한다."""

    # KRX에서 주가 데이터 조회
    df = stock.get_market_ohlcv(start_date, end_date, ticker)

    # 조회된 데이터가 없으면 로그만 남기고 종료
    if df.empty:
        print(f"수집된 데이터가 없습니다: {ticker}")

        save_etl_log(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            status="SKIPPED",
        )
        return

    # 인덱스 날짜를 컬럼으로 변환하고 DB 컬럼명에 맞게 변경
    df = df.reset_index()
    df = df.rename(
        columns={
            "날짜": "trade_date",
            "시가": "open_price",
            "고가": "high_price",
            "저가": "low_price",
            "종가": "close_price",
            "거래량": "volume",
        }
    )

    # 종목 ID 조회
    stock_id_sql = text("""
        SELECT stock_id
        FROM stocks
        WHERE ticker = :ticker
    """)

    # 동일한 종목·날짜 데이터는 업데이트하는 적재 SQL
    upsert_sql = text("""
        INSERT INTO stock_prices (
            stock_id,
            trade_date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume
        )
        VALUES (
            :stock_id,
            :trade_date,
            :open_price,
            :high_price,
            :low_price,
            :close_price,
            :volume
        )
        ON DUPLICATE KEY UPDATE
            open_price = VALUES(open_price),
            high_price = VALUES(high_price),
            low_price = VALUES(low_price),
            close_price = VALUES(close_price),
            volume = VALUES(volume)
    """)

    with engine.begin() as connection:
        stock_id = connection.execute(
            stock_id_sql,
            {"ticker": ticker},
        ).scalar()

        if stock_id is None:
            raise ValueError(
                f"stocks 테이블에 종목코드 {ticker}가 없습니다. "
                "먼저 종목 정보를 추가하세요."
            )

        # 일별 데이터 적재
        for _, row in df.iterrows():
            connection.execute(
                upsert_sql,
                {
                    "stock_id": stock_id,
                    "trade_date": row["trade_date"].date(),
                    "open_price": int(row["open_price"]),
                    "high_price": int(row["high_price"]),
                    "low_price": int(row["low_price"]),
                    "close_price": int(row["close_price"]),
                    "volume": int(row["volume"]),
                },
            )

    # 성공 로그 저장
    save_etl_log(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        status="SUCCESS",
        records_processed=len(df),
    )

    print(f"{ticker}: {len(df)}건 적재 완료")

def load_all_stock_prices(start_date: str, end_date: str):
    """stocks 테이블의 모든 종목에 대해 주가 데이터를 적재한다."""

    ticker_sql = text("""
        SELECT ticker
        FROM stocks
        ORDER BY ticker
    """)

    with engine.connect() as connection:
        tickers = connection.execute(ticker_sql).scalars().all()

    for ticker in tickers:
        try:
            load_stock_prices(ticker, start_date, end_date)
        except Exception as error:
            print(f"{ticker} 적재 실패: {error}")

from datetime import timedelta


def load_latest_stock_prices(ticker: str, end_date: str):
    """마지막 적재일 이후의 주가만 추가 적재한다."""

    last_date_sql = text("""
        SELECT MAX(p.trade_date)
        FROM stock_prices AS p
        JOIN stocks AS s
            ON s.stock_id = p.stock_id
        WHERE s.ticker = :ticker
    """)

    with engine.connect() as connection:
        last_date = connection.execute(
            last_date_sql,
            {"ticker": ticker},
        ).scalar()

    if last_date is None:
        raise ValueError(
            f"{ticker}의 기존 데이터가 없습니다. "
            "먼저 전체 기간 데이터를 적재하세요."
        )

    start_date = (last_date + timedelta(days=1)).strftime("%Y%m%d")

    if start_date > end_date:
        print(f"{ticker}: 이미 최신 데이터입니다.")

        save_etl_log(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            status="SKIPPED",
        )
        return

    load_stock_prices(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

def load_all_latest_stock_prices(end_date: str):
    ticker_sql = text("SELECT ticker FROM stocks ORDER BY ticker")

    with engine.connect() as connection:
        tickers = connection.execute(ticker_sql).scalars().all()

    for ticker in tickers:
        try:
            load_latest_stock_prices(ticker, end_date)
        except Exception as error:
            print(f"{ticker} 갱신 실패: {error}")

# #  날짜 선택하고 실행시키는 부분(내가 원하는 날짜로 바꿔서 실행시키면 됨)
# if __name__ == "__main__":
#     load_all_stock_prices(
#         start_date="20250801",
#         end_date="20260821",
#     )


if __name__ == "__main__":
    load_all_latest_stock_prices(end_date="20260821")