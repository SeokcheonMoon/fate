-- 주가 데이터 테이블 생성

CREATE TABLE stock_prices (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    ticker VARCHAR(20) NOT NULL,

    market VARCHAR(20),

    trade_date DATE NOT NULL,

    open_price DECIMAL(12,2),

    high_price DECIMAL(12,2),

    low_price DECIMAL(12,2),

    close_price DECIMAL(12,2),

    volume BIGINT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);

-- | 컬럼          | 설명                     |
-- | ----------- | ---------------------- |
-- | id          | 내부 PK                  |
-- | ticker      | 종목 코드 (005930, AAPL 등) |
-- | market      | KOSPI/NASDAQ           |
-- | trade_date  | 거래일                    |
-- | open_price  | 시가                     |
-- | high_price  | 고가                     |
-- | low_price   | 저가                     |
-- | close_price | 종가                     |
-- | volume      | 거래량                    |
