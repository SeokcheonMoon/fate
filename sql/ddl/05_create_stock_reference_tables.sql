-- 업종 분류와 일별 투자자 수급 데이터를 위한 테이블
-- 기존 fate 데이터베이스에서 한 번 실행한다.

USE fate;

CREATE TABLE IF NOT EXISTS stock_profiles (
    stock_id INT NOT NULL PRIMARY KEY,
    sector VARCHAR(100) NULL COMMENT '업종 대분류',
    industry VARCHAR(150) NULL COMMENT '업종 소분류',
    source VARCHAR(100) NOT NULL DEFAULT 'KRX CSV',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_profiles_stock
        FOREIGN KEY (stock_id) REFERENCES stocks(stock_id)
);

CREATE TABLE IF NOT EXISTS investor_flows (
    stock_id INT NOT NULL,
    trade_date DATE NOT NULL,
    foreign_net_value BIGINT NULL COMMENT '외국인 순매수 거래대금(원)',
    institution_net_value BIGINT NULL COMMENT '기관 합계 순매수 거래대금(원)',
    individual_net_value BIGINT NULL COMMENT '개인 순매수 거래대금(원)',
    foreign_net_volume BIGINT NULL COMMENT '외국인 순매수 수량(주)',
    institution_net_volume BIGINT NULL COMMENT '기관 합계 순매수 수량(주)',
    individual_net_volume BIGINT NULL COMMENT '개인 순매수 수량(주)',
    source VARCHAR(100) NOT NULL DEFAULT 'KRX CSV',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (stock_id, trade_date),
    CONSTRAINT fk_investor_flows_stock
        FOREIGN KEY (stock_id) REFERENCES stocks(stock_id),
    INDEX idx_investor_flows_date (trade_date)
);
