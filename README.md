# FATE (Financial Analysis Trend Engine)

> 생성형 AI 기반 금융시장 분석 및 투자 의사결정 지원 시스템

FATE는 국내 주식의 정제된 시세 데이터를 바탕으로 시장 흐름을 분석하고, 예측 모델·대시보드·LLM 기반 인사이트로 확장하는 금융 데이터 분석 프로젝트입니다.

## 프로젝트 개요

- **핵심 목적:** 신뢰할 수 있는 시장 데이터를 반복 수집·관리하고, EDA·피처 엔지니어링·예측·리포팅까지 연결
- **현재 분석 범위:** KOSPI 종목의 일별 OHLCV(시가·고가·저가·종가·거래량)
- **공식 데이터 원천:** KRX Open API의 유가증권 종목기본정보와 유가증권 일별매매정보

## 시스템 흐름

```text
KRX Open API / 시장 지표 / 뉴스
            ↓
       ETL Pipeline
            ↓
       MySQL Data Warehouse
            ↓
  EDA · Feature Engineering · CDA
            ↓
   ML Prediction · LLM Insight · Dashboard
```

## 사용 기술

- **분석:** Python, pandas, NumPy, SciPy, scikit-learn
- **데이터베이스:** MySQL, SQLAlchemy, PyMySQL
- **데이터 수집:** KRX Open API, yfinance
- **시각화·대시보드:** matplotlib, Plotly, Streamlit
- **환경·LLM:** python-dotenv, OpenAI API

## 현재 구현 현황

### 데이터베이스

- MySQL `fate` 데이터베이스와 Python 연결
- 종목·일별 시세 테이블: `stocks`, `stock_prices`
- 시장 지표 테이블: `market_indicators`, `market_indicator_values`
- 투자자 수급 확장 테이블: `investor_flows`, `stock_profiles`
- ETL 실행 이력 테이블: `etl_logs`

### 데이터 적재

- `etl/stock_master_loader.py`: KRX 유가증권 종목기본정보로 KOSPI 종목코드·종목명을 동기화
- `etl/stock_loader.py`: KRX 유가증권 일별매매정보를 날짜별 전 종목 단위로 `stock_prices`에 upsert
- `etl/daily_update.py`: 마지막 적재일 이후 누락 거래일을 증분 적재
- `etl/market_loader.py`: KOSPI 지수 등 시장 지표 적재

### 분석·모델

- OHLCV 패널 생성과 데이터 품질 검증
- RSI, MACD, 이동평균 괴리율, 변동성, 거래량 피처 생성
- 피처와 다음 거래일 수익률의 EDA·확인적 데이터 분석(CDA)
- Logistic Regression, Random Forest, XGBoost 기반 다음 거래일 상승 여부 예측 및 워크포워드 검증 코드
- Streamlit 기반 종목 검색·예측 확률 조회 대시보드

## 주요 테이블

| 테이블 | 역할 |
|---|---|
| `stocks` | 종목코드, 종목명, 시장 구분 |
| `stock_prices` | 종목별 일별 시가·고가·저가·종가·거래량 |
| `market_indicators`, `market_indicator_values` | 시장 지표 확장 분석용 |
| `investor_flows` | 투자자 수급 확장 분석용 |

## 환경 설정

`.env`에 데이터베이스 정보와 KRX 인증키를 설정합니다. 키는 저장소에 커밋하지 않습니다.

```env
MYSQL_USER=사용자명
MYSQL_PASSWORD=비밀번호
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=fate
KRX_API_KEY=KRX에서_발급받은_인증키
```

필요한 패키지를 설치합니다.

```powershell
python -m pip install -r requirements.txt
```

KRX 인증키 발급 후 **유가증권 종목기본정보**와 **유가증권 일별매매정보**를 각각 활용 신청·승인받아야 합니다.

## 데이터 적재

처음 한 번은 종목 목록을 먼저 적재한 뒤 시세를 적재합니다. KRX 당일 데이터가 아직 없으면 마지막 거래일을 `--base-date`, `--end-date`로 지정합니다.

```powershell
python -m etl.stock_master_loader --base-date 20260828
python -m etl.stock_loader --start-date 20250801 --end-date 20260828
```

그다음부터는 KRX가 전 거래일 데이터를 제공한 뒤 증분 갱신합니다.

```powershell
python -m etl.daily_update
```

## 데이터 수집 전환 배경과 해결

### 기존 방식에서 막힌 지점

초기에는 FinanceDataReader를 통해 NAVER 기반 시세와 공개 캐시를 사용했습니다. 이 방식은 빠르게 프로토타입을 만들기에는 편리했지만, 외부 웹·캐시의 변경에 영향을 받고 데이터 원천과 재현성을 명확히 관리하기 어려웠습니다. 또한 투자자 수급처럼 웹 접근 제한과 이용 조건을 별도로 확인해야 하는 데이터는 안정적인 자동 적재 대상으로 쓰기 어려웠습니다.

### 변경한 수집 로직

시세 수집을 한국거래소의 공식 KRX Open API로 전환했습니다.

| 이전 방식 | 변경 후 |
|---|---|
| FinanceDataReader가 제공하는 종목 목록·종목별 시세 요청 | KRX Open API의 종목기본정보·일별매매정보 요청 |
| 종목별 반복 호출 | 거래일별 KOSPI 전 종목을 한 번에 요청 |
| 외부 웹·공개 캐시 상태에 의존 | 서비스별 승인된 인증키와 공식 응답 스키마 사용 |
| 원천별 형식 차이를 코드에서 처리 | KRX의 `OutBlock_1` 필드를 DB 스키마에 명시적으로 매핑 |

구체적으로 `.env`의 `KRX_API_KEY`를 요청 헤더 `AUTH_KEY`로 전달하고, 기준일자 `basDd`를 사용해 아래 두 API를 호출합니다.

- `sto/stk_isu_base_info`: 단축코드·종목명·시장구분 등 종목기본정보를 `stocks`에 upsert
- `sto/stk_bydd_trd`: 시가·고가·저가·종가·거래량을 `stock_prices`에 upsert

각 거래일은 KOSPI 전 종목을 한 번에 반환하므로, 초기 적재도 종목 단위가 아니라 날짜 단위로 처리합니다. 같은 종목·날짜는 upsert로 갱신되어 초기 적재 명령을 다시 실행해도 중복 행이 생기지 않습니다.

### 운영 시 처리한 예외

- KRX 당일 데이터는 즉시 제공되지 않을 수 있습니다. 이 경우 API의 빈 응답을 오류로 간주하지 않고 건너뛰며, 다음 `daily_update` 실행 때 마지막 적재일 다음 날짜부터 다시 요청합니다.
- 최초 적재는 DB에 마지막 적재일이 없으므로 반드시 `--start-date`와 `--end-date`를 지정합니다.
- 현재 승인받은 두 API에는 투자자별 수급이 포함되지 않습니다. 수급 분석은 공식적으로 허용된 별도 데이터 원천을 확보한 뒤 확장합니다.

이 전환으로 KOSPI 944종목의 2025-08-01부터 2026-08-28까지 OHLCV 246,389건을 공식 KRX 응답 기준으로 적재했습니다.

## OHLCV EDA와 확인적 데이터 분석

아래 명령은 DB의 `stocks`와 `stock_prices`를 결합해 패널 데이터를 만들고, 피처 생성·EDA 시각화·가설검정을 한 번에 수행합니다.

```powershell
python -m analysis.ohlcv_eda
```

생성 결과:

- `data/processed/kospi_ohlcv_panel.csv`: RSI, MACD, 이동평균 괴리율, 거래량 지표, 다음 거래일 수익률이 포함된 분석 패널
- `analysis/output/ohlcv_data_quality.csv`: 중복·결측·범위 검증 결과
- `analysis/output/ohlcv_cda_results.csv`: 가설검정 결과
- `analysis/output/ohlcv_eda_overview.png`: 수익률 분포, 상관행렬, 거래량 산점도, IC 추이
- `analysis/output/ohlcv_eda_technical_indicators.png`: 삼성전자 기술지표 예시
- `analysis/output/ohlcv_cda_hypothesis_tests.png`: 피처별 검정 결과

### 검정 방법

각 거래일에 KOSPI 종목 간 스피어만 상관계수(IC)를 계산하고, 날짜별 IC 평균이 0인지 HAC(Newey-West) 표준오차로 검정했습니다. 8개 가설의 다중검정 문제는 Benjamini-Hochberg FDR 5% 보정으로 처리했습니다.

### 상관관계 및 유의성 결과

| 피처 | 다음 거래일 수익률과 평균 IC | FDR 5% 유의성 | 해석 |
|---|---:|---|---|
| 장중 변동성 | -0.0590 | 유의 | 변동성이 높았던 종목은 다음날 상대적으로 약세 |
| 5일 이동평균 괴리율 | -0.0451 | 유의 | 단기 과열 후 평균회귀 성향 |
| 20일 이동평균 괴리율 | -0.0377 | 유의 | 중기 과열 후 평균회귀 성향 |
| 전일 종가 변화율 | -0.0348 | 유의 | 단기 평균회귀 성향 |
| RSI(14) | -0.0307 | 유의 | RSI가 높은 종목의 다음날 상대수익률이 낮은 경향 |
| 종가 대비 MACD | -0.0249 | 유의 | 강한 MACD도 단기적으로 평균회귀 성향 |
| 거래량 변화율 | +0.0057 | 유의하지 않음 | 단독 예측력 확인 불가 |
| 20일 평균 대비 거래량 | +0.0011 | 유의하지 않음 | 단독 예측력 확인 불가 |

이 결과는 OHLCV 관측자료의 통계적 연관성입니다. 인과관계 또는 실현 가능한 매매전략을 증명하지는 않으므로, 다음 단계에서 시간순 검증을 포함한 예측 모델 성능 평가가 필요합니다.

## 프로젝트 구조

```text
FATE/
├── analysis/       OHLCV 패널 생성, EDA·CDA 스크립트와 분석 노트북
├── config/         환경 변수와 MySQL 연결
├── dashboard/      Streamlit 대시보드
├── data/           원천·가공·외부 데이터
├── docs/           ERD, 아키텍처, 작업 기록
├── etl/            KRX 적재와 일일 갱신
├── llm/            리포트·챗봇 관련 코드
├── ml/             피처 기반 예측·검증 모델
├── sql/            테이블 정의와 초기 데이터 SQL
├── tests/          테스트 코드
├── README.md
└── requirements.txt
```

## 다음 단계

- OHLCV 유의 피처를 기준으로 시간순 학습·검증 데이터셋 정리
- 워크포워드 검증으로 통계적 유의성이 실제 예측 성능으로 이어지는지 확인
- 투자자별 수급 데이터는 공식적으로 허용된 원천을 확보한 뒤 확장 피처로 추가
