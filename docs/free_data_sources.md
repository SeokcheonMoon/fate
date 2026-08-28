# 무료·공식 데이터 소스 전환

## 사용할 소스

| 목적 | 소스 | 수집 방식 | 비고 |
| --- | --- | --- | --- |
| 일별 OHLCV | [공공데이터포털 금융위원회 주식시세정보 API](https://www.data.go.kr/data/15094808/openapi.do) | 공식 REST API | 무료 서비스 키 필요, 영업일 다음 날 13시 이후 갱신 |
| 재무제표 | [Open DART API](https://opendart.fss.or.kr/intro/main.do) | 공식 REST API | 무료 인증키 필요 |
| RSI·MACD·이동평균·변동성 | 자체 계산 | OHLCV 기반 로컬 계산 | 별도 외부 수집 불필요 |

## 수집하지 않을 소스

- KRX 웹 페이지를 `pykrx` 등으로 자동 수집하지 않는다.
- [TradingView 이용정책](https://www.tradingview.com/policies/)과 [Investing.com 이용약관](https://cdn.investing.com/about-us/terms_and_conditions.pdf)에서 스크래핑·데이터 마이닝·자동 수집을 금지하므로 크롤링하지 않는다.

## 투자자 수급 데이터

개인·외국인·기관 수급은 공식 API의 사용 허가와 데이터 이용 범위가 명확해진 뒤에만 연결한다. 그 전에는 수급 피처 없이 가격·거래량·기술 지표·DART 재무 지표만으로 모델을 운영한다.

## 필요한 준비

1. 공공데이터포털에서 `금융위원회_주식시세정보` 활용 신청 후 서비스 키 발급
2. Open DART에서 인증키 발급
3. 키는 `.env`에만 저장하고 Git에 올리지 않기
4. 공식 API 적재기가 구현되기 전에는 `python -m etl.daily_update`를 실행하지 않기
