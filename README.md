# FATE (Financial Analysis Trend Engine)

> **생성형 AI 기반 금융시장 분석 및 투자 의사결정 지원 시스템**

FATE는 정제된 금융시장 데이터를 기반으로 주가 흐름 예측 및 LLM 기반 투자 분석 서비스를 제공하는 AI 금융 플랫폼입니다.

---

## 프로젝트 개요

* **프로젝트명:** FATE (Financial Analysis Trend Engine)
* **핵심 컨셉:** 금융 데이터 분석 및 생성형 AI 기반의 이상 탐지 / 레포팅 플랫폼
* **주요 역할:** 데이터 엔지니어링부터 시각화, AI 인텔리전스 제공까지 전 과정을 아우르는 엔드투엔드(End-to-End) 솔루션

---

## 🛠️ 핵심 기능 및 흐름

```text
[ Data Engineering ] ➔ [ Data Analysis ] ➔ [ Visualization ] ➔ [ AI Decision Support ]
    (ETL Pipeline)        (EDA & ML)         (Dashboards)          (LLM Insights)
```

## 프로젝트 소개

FATE는 국내 주식의 일별 시세와 시장 지표를 수집·저장하고, 이를 기반으로 분석·예측·투자 인사이트를 제공하는 금융 데이터 플랫폼입니다.

현재는 MySQL 기반 데이터 저장소와 주가·KOSPI 수집 ETL 파이프라인을 구축했습니다.

## 프로젝트 목적

- 신뢰할 수 있는 금융시장 데이터를 반복 수집하고 관리한다.
- 수집 데이터를 바탕으로 EDA, 피처 엔지니어링, 예측 모델을 구현한다.
- LLM 기반 리포트와 대시보드로 투자 의사결정을 지원한다.

## 사용 기술

- **Language / Analysis:** Python, pandas, NumPy
- **Database:** MySQL, SQLAlchemy, PyMySQL
- **Data Collection:** FinanceDataReader, yfinance
- **Environment:** python-dotenv, virtual environment
- **Planned:** scikit-learn, XGBoost, Streamlit, OpenAI API

## 시스템 아키텍처
```
Data Source (주가 데이터 API ＋ 경제 지표 API ＋ 뉴스 크롤링)
    |
    ↓
ETL Pipeline
    |
    ↓
MySQL Data Warehouse
    |
    ↓
Feature Engineering
    |
    ↓
ML Prediction
    |
    ↓
LLM Decision Support
    |
    ↓
Dashboard
```

## 현재 구현 현황

### 데이터베이스

- MySQL `fate` 데이터베이스 및 Python 연결 완료
- 종목 및 일별 주가 테이블: `stocks`, `stock_prices`
- 시장 지표 테이블: `market_indicators`, `market_indicator_values`
- 뉴스 저장 테이블: `news_articles`, `news_stock_map`
- ETL 실행 이력 테이블: `etl_logs`

### 데이터 적재 파이프라인

- `etl/stock_loader.py`
  - FinanceDataReader(NAVER 소스)로 종목별 일별 OHLCV 데이터를 수집
  - `stocks` 테이블의 모든 종목을 순회하여 `stock_prices`에 적재
  - 동일 종목·일자의 데이터는 갱신하고, 마지막 적재일 이후 데이터만 증분 적재
  - 성공·건너뜀 상태와 처리 건수를 `etl_logs`에 기록
- `etl/market_loader.py`
  - yfinance에서 KOSPI(`^KS11`) 일별 지수를 수집
  - `market_indicator_values`에 적재하고 마지막 적재일 이후 데이터만 증분 적재
- `etl/stock_master_loader.py`
  - FinanceDataReader의 공개 캐시에서 KOSPI·KOSDAQ 전체 종목 코드와 이름을 조회해 `stocks`에 동기화
- `etl/initial_stock_loader.py`
  - 아직 주가가 없는 종목만 골라 최근 1년 OHLCV를 배치 단위로 초기 적재
  - API 요청 부담을 줄이기 위해 기본 50종목씩 처리하며, 재실행하면 다음 종목을 이어서 처리

### 초기 적재 데이터

- 대상 종목: 삼성전자(`005930`), SK하이닉스(`000660`), NAVER(`035420`)
- 종목별 최근 약 1년의 일별 주가 데이터 적재 및 조회 검증 완료
- KOSPI 일별 지수 데이터 적재 및 조회 검증 완료

## 실행 방법

`.env` 파일에 MySQL 연결 정보를 설정합니다. `.env` 파일은 Git에 커밋하지 않습니다.

```env
MYSQL_USER=사용자명
MYSQL_PASSWORD=비밀번호
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=fate
```

프로젝트 루트에서 증분 적재를 실행합니다.

```powershell
py -m etl.stock_loader
py -m etl.market_loader
```

매 거래일 원천 데이터를 최신화할 때는 주가·KOSPI·투자자 수급을 아래 순서로 갱신합니다.

```powershell
python -m etl.stock_loader
python -m etl.market_loader
python -m etl.investor_flow_pykrx_loader --all
```

위 세 단계를 한 번에 실행하려면 다음을 사용합니다. 모든 적재기는 실행일 기준으로 마지막 적재일 이후 데이터만 가져옵니다.

```powershell
python -m etl.daily_update
```

KOSPI·KOSDAQ 전체 종목을 처음 적재할 때는 아래 순서로 실행합니다.

```powershell
# 1) 전체 종목 마스터 동기화
python -m etl.stock_master_loader

# 2) 미적재 종목 50개씩 최근 1년 일별 시세 적재 (반복 실행)
python -m etl.initial_stock_loader --batch-size 50

# 모든 미적재 종목을 한 번에 처리하려면 장시간 실행될 수 있으므로 명시적으로 실행
python -m etl.initial_stock_loader --all
```

> 실행 전 필요한 라이브러리를 현재 Python 환경에 설치해야 합니다: `python -m pip install -r requirements.txt`
## 프로젝트 구조

```
FATE/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── config/
│   ├── config.py
│   └── database.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
│
├── sql/
│   ├── ddl/
│   ├── dml/
│   ├── query/
│   └── feature/
│
├── etl/
│   ├── stock_loader.py
│   ├── news_loader.py
│   ├── market_loader.py
│   └── preprocessing.py
│
├── analysis/
│   ├── eda.ipynb
│   ├── feature_engineering.ipynb
│   └── visualization.ipynb
│
├── ml/
│   ├── train.py
│   ├── prediction.py
│   ├── evaluate.py
│   └── models/
│       ├── xgboost.pkl
│       └── lstm.pth
│
├── llm/
│   ├── prompt.py
│   ├── report_generator.py
│   └── chatbot.py
│
├── dashboard/
│   └── app.py
│
├── docs/
│   ├── ERD.md
│   ├── Architecture.md
│   └── Portfolio.md
│
└── tests/
```

## 개발 일정

- [x] STEP 1: 프로젝트 기획서 작성
- [x] STEP 2: MySQL 데이터베이스 환경 구축 및 핵심 테이블 설계
- [x] STEP 3: MySQL SQL 구현 및 주가·KOSPI ETL 파이프라인 구축
- [x] STEP 4: Python 분석(EDA, Feature Engineering)
- [x] STEP 5: 머신러닝(예측, 이상 탐지)
- [x] STEP 6: 대시보드
- [ ] STEP 7: LLM + RAG + Streamlit
- [ ] STEP 8: GitHub 및 발표 자료 완성
