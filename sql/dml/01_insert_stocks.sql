USE fate;

INSERT INTO stocks (ticker, name, market)
VALUES
    ('005930', '삼성전자', 'KOSPI'),
    ('000660', 'SK하이닉스', 'KOSPI'),
    ('035420', 'NAVER', 'KOSPI');

SELECT * FROM stocks;