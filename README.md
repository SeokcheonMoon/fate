

## 프로젝트 소개

## 프로젝트 목적

## 사용 기술

## 시스템 아키텍처

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
│   ├── customer_loader.py
│   ├── stock_loader.py
│   ├── news_loader.py
│   └── market_loader.py
│
├── analysis/
│   ├── eda.ipynb
│   ├── feature_engineering.ipynb
│   └── visualization.ipynb
│
├── ml/
│   ├── segmentation.py
│   ├── churn_prediction.py
│   ├── anomaly_detection.py
│   └── models/
│
├── llm/
│   ├── prompt.py
│   ├── report_generator.py
│   └── chatbot.py
│
├── dashboard/
│
├── streamlit/
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