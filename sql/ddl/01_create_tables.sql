-- # 데이터베이스 생성
-- stocks (종목 정보)
-- stock_prices (일별 주가)

CREATE TABLE stocks (
    stock_id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE COMMENT '종목 코드',
    name VARCHAR(100) NOT NULL COMMENT '종목명',
    market VARCHAR(20) NOT NULL COMMENT '시장 구분 (KOSPI, KOSDAQ 등)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE stock_prices (
    price_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_id INT NOT NULL,
    trade_date DATE NOT NULL,
    open_price DECIMAL(15, 2),
    high_price DECIMAL(15, 2),
    low_price DECIMAL(15, 2),
    close_price DECIMAL(15, 2) NOT NULL,
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_stock_prices_stock
        FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),

    CONSTRAINT uq_stock_prices_stock_date
        UNIQUE (stock_id, trade_date),

    INDEX idx_stock_prices_trade_date (trade_date)
);