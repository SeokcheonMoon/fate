-- # 경제지표를 저장할 DB 테이블을 만드는 단계

USE fate;

-- 경제지표 기본 정보: 기준금리, 환율, CPI 등
CREATE TABLE market_indicators (
    indicator_id INT AUTO_INCREMENT PRIMARY KEY,
    indicator_code VARCHAR(50) NOT NULL UNIQUE,
    indicator_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit VARCHAR(30) NULL,
    source VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 날짜별 경제지표 값
CREATE TABLE market_indicator_values (
    value_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    indicator_id INT NOT NULL,
    observation_date DATE NOT NULL,
    indicator_value DECIMAL(20, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_market_indicator_values_indicator
        FOREIGN KEY (indicator_id)
        REFERENCES market_indicators(indicator_id),

    CONSTRAINT uq_indicator_date
        UNIQUE (indicator_id, observation_date),

    INDEX idx_indicator_values_date (observation_date)
);