-- # 뉴스 기사와 기사별 관련 종목을 저장할 테이블을 만드는 SQL입니다.

USE fate;

CREATE TABLE news_articles (
    news_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content LONGTEXT NULL,
    publisher VARCHAR(100) NULL,
    published_at DATETIME NOT NULL,
    source_url VARCHAR(700) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (source_url),
    INDEX idx_news_articles_published_at (published_at)
);

CREATE TABLE news_stock_map (
    news_id BIGINT NOT NULL,
    stock_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (news_id, stock_id),

    CONSTRAINT fk_news_stock_map_news
        FOREIGN KEY (news_id)
        REFERENCES news_articles(news_id),

    CONSTRAINT fk_news_stock_map_stock
        FOREIGN KEY (stock_id)
        REFERENCES stocks(stock_id)
);