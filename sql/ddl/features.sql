-- -- Feature 저장 테이블
-- ML 입력 데이터가 저장됨.

CREATE TABLE features (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    ticker VARCHAR(20),

    trade_date DATE,

    return_rate DECIMAL(10,5),

    ma5 DECIMAL(12,2),

    ma20 DECIMAL(12,2),

    volatility DECIMAL(10,5),

    volume_change DECIMAL(10,5),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);