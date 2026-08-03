-- 경제지표 테이블

CREATE TABLE economic_indicators (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    indicator_name VARCHAR(100),

    indicator_date DATE,

    value DECIMAL(15,4),

    unit VARCHAR(20),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);