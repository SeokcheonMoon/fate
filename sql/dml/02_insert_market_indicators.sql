-- # KOSPI를 수집 대상 지표로 등록하는 SQL입니다

USE fate;

INSERT INTO market_indicators (
    indicator_code,
    indicator_name,
    category,
    unit,
    source
)
VALUES (
    'KOSPI',
    '코스피 지수',
    'STOCK_INDEX',
    'point',
    'KRX'
);