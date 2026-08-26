"""다운로드한 업종·투자자 수급 CSV를 FATE DB에 적재한다.

실행:
    python -m etl.reference_data_loader --profiles data/external/stock_profiles.csv
    python -m etl.reference_data_loader --flows data/external/investor_flows.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

from config.database import engine


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "data" / "external" / "stock_profiles.csv"
DEFAULT_FLOW_PATH = PROJECT_ROOT / "data" / "external" / "investor_flows.csv"


def normalize_ticker(value: object) -> str:
    return str(value).split(".")[0].zfill(6)


def require_columns(data: pd.DataFrame, columns: set[str], path: Path) -> None:
    missing = columns.difference(data.columns)
    if missing:
        raise ValueError(f"{path.name}에 필수 컬럼이 없습니다: {sorted(missing)}")


def stock_ids(tickers: list[str]) -> dict[str, int]:
    if not tickers:
        return {}
    query = text("SELECT ticker, stock_id FROM stocks WHERE ticker IN :tickers").bindparams(
        bindparam("tickers", expanding=True)
    )
    with engine.connect() as connection:
        return dict(connection.execute(query, {"tickers": tickers}).all())


def save_log(pipeline: str, records: int, status: str, error: str | None = None) -> None:
    query = text("""
        INSERT INTO etl_logs (pipeline_name, status, records_processed, error_message)
        VALUES (:pipeline, :status, :records, :error)
    """)
    with engine.begin() as connection:
        connection.execute(query, {"pipeline": pipeline, "status": status, "records": records, "error": error})


def load_profiles(path: Path) -> int:
    data = pd.read_csv(path, dtype={"ticker": str}, encoding="utf-8-sig")
    require_columns(data, {"ticker", "sector", "industry"}, path)
    data["ticker"] = data["ticker"].map(normalize_ticker)
    ids = stock_ids(data["ticker"].unique().tolist())
    data["stock_id"] = data["ticker"].map(ids)
    data = data.dropna(subset=["stock_id"]).copy()
    if data.empty:
        return 0
    data["source"] = data["source"].fillna("KRX CSV") if "source" in data else "KRX CSV"
    query = text("""
        INSERT INTO stock_profiles (stock_id, sector, industry, source)
        VALUES (:stock_id, :sector, :industry, :source)
        ON DUPLICATE KEY UPDATE sector=VALUES(sector), industry=VALUES(industry),
            source=VALUES(source)
    """)
    with engine.begin() as connection:
        connection.execute(query, data[["stock_id", "sector", "industry", "source"]].to_dict("records"))
    return len(data)


def load_flows(path: Path) -> int:
    data = pd.read_csv(path, dtype={"ticker": str}, encoding="utf-8-sig")
    required = {"trade_date", "ticker", "foreign_net_value", "institution_net_value", "individual_net_value"}
    require_columns(data, required, path)
    data["ticker"] = data["ticker"].map(normalize_ticker)
    data["trade_date"] = pd.to_datetime(data["trade_date"], errors="raise").dt.date
    for column in required - {"trade_date", "ticker"}:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).astype("int64")
    ids = stock_ids(data["ticker"].unique().tolist())
    data["stock_id"] = data["ticker"].map(ids)
    data = data.dropna(subset=["stock_id"]).copy()
    if data.empty:
        return 0
    data["stock_id"] = data["stock_id"].astype(int)
    data["source"] = data["source"].fillna("KRX CSV") if "source" in data else "KRX CSV"
    query = text("""
        INSERT INTO investor_flows (
            stock_id, trade_date, foreign_net_value, institution_net_value,
            individual_net_value, source
        ) VALUES (
            :stock_id, :trade_date, :foreign_net_value, :institution_net_value,
            :individual_net_value, :source
        ) ON DUPLICATE KEY UPDATE
            foreign_net_value=VALUES(foreign_net_value),
            institution_net_value=VALUES(institution_net_value),
            individual_net_value=VALUES(individual_net_value), source=VALUES(source)
    """)
    columns = ["stock_id", "trade_date", "foreign_net_value", "institution_net_value", "individual_net_value", "source"]
    with engine.begin() as connection:
        connection.execute(query, data[columns].to_dict("records"))
    return len(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="업종·수급 CSV DB 적재")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--flows", type=Path, default=DEFAULT_FLOW_PATH)
    args = parser.parse_args()
    loaded = 0
    try:
        if args.profiles.exists():
            count = load_profiles(args.profiles)
            save_log("reference_profile_loader", count, "SUCCESS")
            print(f"업종 프로필: {count:,}건 적재")
            loaded += count
        if args.flows.exists():
            count = load_flows(args.flows)
            save_log("investor_flow_loader", count, "SUCCESS")
            print(f"투자자 수급: {count:,}건 적재")
            loaded += count
        if not args.profiles.exists() and not args.flows.exists():
            raise FileNotFoundError("입력 CSV가 없습니다. data/external의 template 파일을 복사해 작성하세요.")
    except Exception as error:
        save_log("reference_data_loader", loaded, "FAILED", str(error)[:1000])
        raise


if __name__ == "__main__":
    main()
