-- 뉴스 테이블 생성

CREATE TABLE news (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    ticker VARCHAR(20),

    title VARCHAR(500),

    content TEXT,

    source VARCHAR(100),

    published_date DATETIME,

    sentiment_score DECIMAL(5,4),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

);