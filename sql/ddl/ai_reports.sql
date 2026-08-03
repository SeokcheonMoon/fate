-- AI 보고서 테이블

CREATE TABLE ai_reports (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    ticker VARCHAR(20),

    report_date DATE,

    market_summary TEXT,

    investment_opinion TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);