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

## 프로젝트 목적

## 사용 기술

## 시스템 아키텍처
```
Data Source
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

- STEP 1: 프로젝트 기획서 작성 (README 수준)
- STEP 2: ERD 및 데이터베이스 설계
- STEP 3: PostgreSQL + SQL 구현
- STEP 4: Python 분석(EDA, Feature Engineering)
- STEP 5: 머신러닝(세분화, 이탈 예측, 이상 탐지)
- STEP 6: Tableau 대시보드
- STEP 7: LLM + RAG + Streamlit
- STEP 8: GitHub 및 발표 자료 완성