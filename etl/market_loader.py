from datetime import datetime, timedelta

import yfinance as yf
from sqlalchemy import text

from config.database import engine


def load_kospi_index(start_date: str, end_date: str):
    """Yahoo Finance에서 KOSPI 지수를 가져와 MySQL에 적재한다."""

    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d") + timedelta(days=1)

    # ^KS11: Yahoo Finance의 KOSPI 지수 코드
    df = yf.Ticker("^KS11").history(
        start=start,
        end=end,
        auto_adjust=False,
    )

    if df.empty:
        print("수집된 KOSPI 데이터가 없습니다.")
        return

    df = df.reset_index()
    df["observation_date"] = df["Date"].dt.date
    df["indicator_value"] = df["Close"].astype(float)

    indicator_id_sql = text("""
        SELECT indicator_id
        FROM market_indicators
        WHERE indicator_code = 'KOSPI'
    """)

    upsert_sql = text("""
        INSERT INTO market_indicator_values (
            indicator_id,
            observation_date,
            indicator_value
        )
        VALUES (
            :indicator_id,
            :observation_date,
            :indicator_value
        )
        ON DUPLICATE KEY UPDATE
            indicator_value = VALUES(indicator_value)
    """)

    with engine.begin() as connection:
        indicator_id = connection.execute(indicator_id_sql).scalar()

        if indicator_id is None:
            raise ValueError("KOSPI 지표가 등록되지 않았습니다.")

        for _, row in df.iterrows():
            connection.execute(
                upsert_sql,
                {
                    "indicator_id": indicator_id,
                    "observation_date": row["observation_date"],
                    "indicator_value": row["indicator_value"],
                },
            )

    print(f"KOSPI: {len(df)}건 적재 완료")


def load_latest_kospi_index(end_date: str):
    """KOSPI의 마지막 적재일 이후 데이터만 추가 적재한다."""

    last_date_sql = text("""
        SELECT MAX(miv.observation_date)
        FROM market_indicator_values AS miv
        JOIN market_indicators AS mi
            ON mi.indicator_id = miv.indicator_id
        WHERE mi.indicator_code = 'KOSPI'
    """)

    with engine.connect() as connection:
        last_date = connection.execute(last_date_sql).scalar()

    if last_date is None:
        raise ValueError("기존 KOSPI 데이터가 없습니다.")

    start_date = (last_date + timedelta(days=1)).strftime("%Y%m%d")

    if start_date > end_date:
        print("KOSPI: 이미 최신 데이터입니다.")
        return

    load_kospi_index(
        start_date=start_date,
        end_date=end_date,
    )

if __name__ == "__main__":
    load_latest_kospi_index(end_date="20260821")