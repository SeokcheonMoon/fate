"""pykrx로 KRX 종목별 외국인·기관·개인 일별 순매수 거래대금을 적재한다.

처음에는 한 종목·짧은 기간으로 연결을 확인한다.

    python -m etl.investor_flow_pykrx_loader --ticker 005930 --start-date 20260801 --end-date 20260821

전체 종목 증분 적재는 명시적으로 --all을 붙여 실행한다.

    python -m etl.investor_flow_pykrx_loader --all --end-date 20260821
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import bindparam, text
from tqdm import tqdm

from config.database import engine


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def format_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def get_targets(tickers: list[str] | None) -> list[tuple[int, str]]:
    query_text = """
        SELECT s.stock_id, s.ticker
        FROM stocks AS s
        WHERE EXISTS (SELECT 1 FROM stock_prices AS p WHERE p.stock_id = s.stock_id)
    """
    if tickers:
        query = text(f"{query_text} AND s.ticker IN :tickers ORDER BY s.ticker").bindparams(
            bindparam("tickers", expanding=True)
        )
    else:
        query = text(f"{query_text} ORDER BY s.ticker")
    with engine.connect() as connection:
        return connection.execute(query, {"tickers": tickers} if tickers else {}).all()


def last_loaded_date(stock_id: int) -> date | None:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT MAX(trade_date) FROM investor_flows WHERE stock_id = :stock_id"),
            {"stock_id": stock_id},
        ).scalar()


def last_volume_loaded_date(stock_id: int) -> date | None:
    """수량이 실제로 채워진 마지막 날짜를 반환한다."""
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT MAX(trade_date) FROM investor_flows "
                "WHERE stock_id = :stock_id AND foreign_net_volume IS NOT NULL"
            ),
            {"stock_id": stock_id},
        ).scalar()


def require_volume_columns() -> None:
    """수량 적재에 필요한 DB 열이 준비됐는지 먼저 확인한다."""
    required = {
        "foreign_net_volume",
        "institution_net_volume",
        "individual_net_volume",
    }
    with engine.connect() as connection:
        rows = connection.execute(text("SHOW COLUMNS FROM investor_flows")).all()
    existing = {row[0] for row in rows}
    missing = required - existing
    if missing:
        raise RuntimeError(
            "투자자 순매수 수량 열이 없습니다. "
            "sql/ddl/06_add_investor_flow_volume_columns.sql을 먼저 실행하세요: "
            f"{sorted(missing)}"
        )


def get_column(data: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in data.columns:
            return pd.to_numeric(data[name], errors="coerce").fillna(0).astype("int64")
    return pd.Series(0, index=data.index, dtype="int64")


def normalize_flow_data(data: pd.DataFrame) -> pd.DataFrame:
    """pykrx 응답의 날짜 인덱스를 조인 가능한 열로 표준화한다."""
    data = data.reset_index().rename(columns={data.index.name or "index": "trade_date"})
    if "trade_date" not in data:
        data = data.rename(columns={data.columns[0]: "trade_date"})
    data["trade_date"] = pd.to_datetime(data["trade_date"]).dt.date
    return data


def fetch_flow(ticker: str, start: date, end: date) -> pd.DataFrame:
    try:
        from pykrx import stock
    except ImportError as error:
        raise ImportError("pykrx가 없습니다. `python -m pip install pykrx`를 실행하세요.") from error

    value_data = stock.get_market_trading_value_by_date(
        format_date(start), format_date(end), ticker, on="순매수"
    )
    volume_data = stock.get_market_trading_volume_by_date(
        format_date(start), format_date(end), ticker, on="순매수"
    )
    if value_data.empty or volume_data.empty:
        raise RuntimeError(
            "pykrx가 수급 데이터를 반환하지 않았습니다. KRX_ID/KRX_PW 설정, "
            "조회 기간, KRX 접속 상태를 확인하세요. 빈 응답은 성공으로 처리하지 않습니다."
        )
    value_data = normalize_flow_data(value_data)
    volume_data = normalize_flow_data(volume_data)
    values = pd.DataFrame(
        {
            "trade_date": value_data["trade_date"],
            "foreign_net_value": get_column(value_data, "외국인합계", "외국인"),
            "institution_net_value": get_column(value_data, "기관합계", "기관"),
            "individual_net_value": get_column(value_data, "개인"),
        }
    )
    volumes = pd.DataFrame(
        {
            "trade_date": volume_data["trade_date"],
            "foreign_net_volume": get_column(volume_data, "외국인합계", "외국인"),
            "institution_net_volume": get_column(volume_data, "기관합계", "기관"),
            "individual_net_volume": get_column(volume_data, "개인"),
        }
    )
    return values.merge(volumes, on="trade_date", how="inner").drop_duplicates(
        subset=["trade_date"]
    )


def fetch_flow_with_retry(
    ticker: str, start: date, end: date, max_retries: int, retry_delay_seconds: float
) -> pd.DataFrame:
    """일시적인 KRX 세션·접근 제한에는 점진적으로 대기한 뒤 다시 시도한다."""
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fetch_flow(ticker, start, end)
        except Exception as error:
            last_error = error
            if attempt == max_retries:
                break
            delay = retry_delay_seconds * (2**attempt)
            print(
                f"{ticker}: 수급 조회 재시도 {attempt + 1}/{max_retries} "
                f"({delay:.0f}초 대기) - {error}"
            )
            time.sleep(delay)
    raise RuntimeError(f"KRX 수급 조회 재시도 소진: {last_error}") from last_error


def upsert_flows(stock_id: int, data: pd.DataFrame) -> int:
    if data.empty:
        return 0
    rows = data.assign(stock_id=stock_id, source="pykrx / KRX").to_dict("records")
    query = text("""
        INSERT INTO investor_flows (
            stock_id, trade_date, foreign_net_value, institution_net_value,
            individual_net_value, foreign_net_volume, institution_net_volume,
            individual_net_volume, source
        ) VALUES (
            :stock_id, :trade_date, :foreign_net_value, :institution_net_value,
            :individual_net_value, :foreign_net_volume, :institution_net_volume,
            :individual_net_volume, :source
        ) ON DUPLICATE KEY UPDATE
            foreign_net_value=VALUES(foreign_net_value),
            institution_net_value=VALUES(institution_net_value),
            individual_net_value=VALUES(individual_net_value),
            foreign_net_volume=VALUES(foreign_net_volume),
            institution_net_volume=VALUES(institution_net_volume),
            individual_net_volume=VALUES(individual_net_volume), source=VALUES(source)
    """)
    with engine.begin() as connection:
        connection.execute(query, rows)
    return len(rows)


def save_log(ticker: str, start: date, end: date, status: str, records: int = 0, error: str | None = None) -> None:
    query = text("""
        INSERT INTO etl_logs (pipeline_name, ticker, start_date, end_date, status, records_processed, error_message)
        VALUES ('investor_flow_pykrx_loader', :ticker, :start, :end, :status, :records, :error)
    """)
    with engine.begin() as connection:
        connection.execute(query, {"ticker": ticker, "start": start, "end": end, "status": status, "records": records, "error": error})


def run_loader(
    tickers: list[str] | None,
    requested_start: date,
    end: date,
    sleep_seconds: float,
    backfill: bool = False,
    max_retries: int = 3,
    retry_delay_seconds: float = 5.0,
    max_consecutive_failures: int = 5,
) -> None:
    """지정 종목 또는 전체 종목의 미적재 수급 구간을 채운다."""
    require_volume_columns()
    targets = get_targets(tickers)
    if not targets:
        raise ValueError("대상 종목을 찾지 못했습니다. stocks·stock_prices 적재 상태를 확인하세요.")

    success, failed, total_rows, consecutive_failures = 0, 0, 0, 0
    progress = tqdm(targets, desc="투자자 수급 적재", unit="종목")
    for index, (stock_id, ticker) in enumerate(progress, start=1):
        start = requested_start
        if backfill:
            volume_end = last_volume_loaded_date(stock_id)
            if volume_end is not None and volume_end >= end:
                tqdm.write(f"{ticker}: 요청 기간의 수급 수량이 이미 적재되었습니다.")
                save_log(ticker, start, end, "SKIPPED")
                continue
        else:
            existing_end = last_loaded_date(stock_id)
            if existing_end is not None:
                start = max(start, existing_end + timedelta(days=1))
        if start > end:
            tqdm.write(f"{ticker}: 이미 최신 수급 데이터입니다.")
            save_log(ticker, start, end, "SKIPPED")
            continue
        try:
            flows = fetch_flow_with_retry(
                ticker, start, end, max_retries, retry_delay_seconds
            )
            loaded = upsert_flows(stock_id, flows)
            save_log(ticker, start, end, "SUCCESS", loaded)
            total_rows += loaded
            success += 1
            consecutive_failures = 0
            tqdm.write(f"{ticker}: {loaded:,}건 적재")
        except Exception as error:
            failed += 1
            consecutive_failures += 1
            save_log(ticker, start, end, "FAILED", error=str(error)[:1000])
            tqdm.write(f"{ticker}: 적재 실패 - {error}")
            if consecutive_failures >= max_consecutive_failures:
                raise RuntimeError(
                    "KRX 수급 조회가 연속 실패해 적재를 중단했습니다. "
                    "잠시 후 다시 실행하면 이미 성공한 종목은 건너뜁니다."
                ) from error
        if index < len(targets):
            time.sleep(sleep_seconds)
    print(f"완료: 성공 {success:,}개 / 실패 {failed:,}개 / 수급 행 {total_rows:,}건")


def main() -> None:
    today = date.today()
    parser = argparse.ArgumentParser(description="pykrx 투자자 수급 증분 적재")
    parser.add_argument("--ticker", action="append", help="대상 종목코드(여러 번 지정 가능)")
    parser.add_argument("--all", action="store_true", help="적재된 모든 종목을 대상으로 실행")
    parser.add_argument("--start-date", default=(today - timedelta(days=31)).strftime("%Y%m%d"))
    parser.add_argument("--end-date", default=today.strftime("%Y%m%d"))
    parser.add_argument(
        "--sleep-seconds", type=float, default=1.0,
        help="종목 사이 대기 시간(초). KRX 접근 제한 방지를 위해 기본 1초",
    )
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", type=float, default=5.0)
    parser.add_argument("--max-consecutive-failures", type=int, default=5)
    parser.add_argument(
        "--backfill", action="store_true",
        help="기존 최신 적재일과 관계없이 지정 기간 전체를 다시 조회해 과거 누락 구간을 채운다",
    )
    args = parser.parse_args()
    if not args.all and not args.ticker:
        parser.error("먼저 --ticker 005930으로 확인하거나, 전체 수집에는 --all을 지정하세요.")

    end = parse_date(args.end_date)
    requested_start = parse_date(args.start_date)
    run_loader(
        args.ticker,
        requested_start,
        end,
        args.sleep_seconds,
        args.backfill,
        args.max_retries,
        args.retry_delay_seconds,
        args.max_consecutive_failures,
    )


if __name__ == "__main__":
    main()
