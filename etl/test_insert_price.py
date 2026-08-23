from sqlalchemy import text

from config.database import engine

insert_stock_sql = text("""
    INSERT IGNORE INTO stocks (ticker, name, market)
    VALUES ('005930', '삼성전자', 'KOSPI')
""")

insert_price_sql = text("""
    INSERT INTO stock_prices (
        stock_id,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume
    )
    SELECT
        stock_id,
        '2026-08-21',
        70000,
        71000,
        69500,
        70500,
        12000000
    FROM stocks
    WHERE ticker = '005930'
    ON DUPLICATE KEY UPDATE
        open_price = VALUES(open_price),
        high_price = VALUES(high_price),
        low_price = VALUES(low_price),
        close_price = VALUES(close_price),
        volume = VALUES(volume)
""")

select_sql = text("""
    SELECT
        s.ticker,
        s.name,
        p.trade_date,
        p.close_price,
        p.volume
    FROM stock_prices AS p
    JOIN stocks AS s ON s.stock_id = p.stock_id
    WHERE s.ticker = '005930'
    ORDER BY p.trade_date DESC
""")

with engine.begin() as connection:
    connection.execute(insert_stock_sql)
    connection.execute(insert_price_sql)

with engine.connect() as connection:
    rows = connection.execute(select_sql).fetchall()

for row in rows:
    print(row)