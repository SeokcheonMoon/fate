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
- 유의 OHLCV 피처 기반 Logistic Regression 시간순 워크포워드 검증
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
python -m etl.stock_loader --start-date 20230901 --end-date 20260828
```

`stock_loader`는 ETL 이력에서 이미 성공·건너뜀 처리된 날짜를 자동으로 제외합니다. 중간에 끊겨도 같은 명령을 다시 실행하면 남은 날짜부터 재개하며, 완료 이력을 무시하고 전체 기간을 다시 적재하려면 `--force`를 추가합니다.

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

### 운영 안정성과 예외 처리

- KRX 당일 데이터는 즉시 제공되지 않을 수 있습니다. 이 경우 API의 빈 응답을 오류로 간주하지 않고 건너뛰며, 다음 `daily_update` 실행 때 마지막 적재일 다음 날짜부터 다시 요청합니다.
- 최초 적재는 DB에 마지막 적재일이 없으므로 반드시 `--start-date`와 `--end-date`를 지정합니다.
- 현재 승인받은 두 API에는 투자자별 수급이 포함되지 않습니다. 수급 분석은 공식적으로 허용된 별도 데이터 원천을 확보한 뒤 확장합니다.
- 장기간 백필 중 KRX가 JSON이 아닌 응답을 일시적으로 반환한 사례가 있었습니다. 같은 인증키로 즉시 재확인했을 때 정상 HTTP 200·944개 종목 응답이 확인되어, 인증키 만료나 영구 차단이 아니라 일시적 응답·호출 부담 문제로 판단했습니다. 요청 간격 0.35초, 최대 5회 지수 백오프 재시도, 실패 일자 ETL 로그 기록을 적용했습니다.
- `stock_loader`는 성공 또는 빈 응답으로 처리한 날짜를 ETL 이력에서 읽어 자동으로 건너뜁니다. 따라서 중단된 명령을 동일하게 다시 실행하면 미적재 날짜부터 이어서 적재하며, 명시적으로 전체 재처리가 필요할 때만 `--force`를 사용합니다.

이 전환으로 KOSPI 944종목의 2023-09-01부터 2026-08-28까지 OHLCV 675,189건을 공식 KRX 응답 기준으로 적재했습니다.

### 포트폴리오용 문제 해결 사례

**문제.** 초기에는 외부 웹·공개 캐시에 의존한 시세 수집을 사용해 원천의 재현성과 운영 안정성이 낮았습니다. 공식 KRX Open API로 전환한 뒤에도 3년치 일별 데이터를 백필하던 중 2024-06-06 부근에서 JSON이 아닌 응답으로 작업이 중단됐습니다.

**판단.** 호출 대상은 거래일별 전 종목을 한 번에 반환하므로 3년치 약 780 거래일은 일일 한도 10,000회보다 충분히 작습니다. 오류 직후 동일 인증키·동일 엔드포인트를 재확인해 정상 HTTP 200과 944개 종목 데이터를 확인했습니다. 따라서 데이터를 처음부터 지우거나 인증키를 교체하지 않고, 일시적인 응답 제한에 견디면서 중단 지점만 복구하는 방식이 적절하다고 판단했습니다.

**해결.** 공식 API의 승인된 두 엔드포인트를 기준으로 종목 마스터와 일별 시세를 분리했고, 날짜 단위 upsert로 중복 적재를 방지했습니다. 여기에 요청 간격, 최대 5회 지수 백오프 재시도, 실패 일자 ETL 로그, 성공 일자를 건너뛰는 재개 로직을 추가했습니다. 이후 같은 적재 명령을 다시 실행해 남은 날짜만 처리하도록 만들었습니다.

**결과.** 944종목·675,189건의 3년 OHLCV 패널을 완성했고, 종목·날짜 중복과 OHLCV 결측은 모두 0건으로 검증했습니다. 이후 EDA·CDA·시간순 모델 검증까지 같은 재현 가능한 파이프라인으로 연결했습니다. 모델 성능이 기준선보다 낮다는 결과도 그대로 기록해, 통계적 상관관계와 실제 예측력의 차이를 검증한 분석으로 마무리했습니다.

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
| 장중 변동성 | -0.0621 | 유의 | 변동성이 높았던 종목은 다음날 상대적으로 약세 |
| 5일 이동평균 괴리율 | -0.0419 | 유의 | 단기 과열 후 평균회귀 성향 |
| 전일 종가 변화율 | -0.0398 | 유의 | 단기 평균회귀 성향 |
| 20일 이동평균 괴리율 | -0.0355 | 유의 | 중기 과열 후 평균회귀 성향 |
| RSI(14) | -0.0261 | 유의 | RSI가 높은 종목의 다음날 상대수익률이 낮은 경향 |
| 종가 대비 MACD | -0.0188 | 유의 | 강한 MACD도 단기적으로 평균회귀 성향 |
| 거래량 변화율 | +0.0052 | 유의 | 약하지만 양의 횡단면 관계 확인 |
| 20일 평균 대비 거래량 | +0.0025 | 유의하지 않음 | 단독 예측력 확인 불가 |

이 결과는 OHLCV 관측자료의 통계적 연관성입니다. 인과관계 또는 실현 가능한 매매전략을 증명하지는 않으므로, 다음 단계에서 시간순 검증을 포함한 예측 모델 성능 평가가 필요합니다.

## 다음 거래일 상승 예측: 시간순 검증

EDA·CDA에서 유의했던 장중 변동성, 5·20일 이동평균 괴리율, 전일 종가 변화율, 거래량 변화율, RSI(14), 종가 대비 MACD를 사용해 Logistic Regression 기준 모델을 만들었습니다. 이 모델의 목표는 **종목별 다음 거래일 상승 여부 분류**이며, 목표 주가를 예측하지 않습니다.

```powershell
python -m ml.ohlcv_walk_forward
```

검증은 초기 6개월을 학습하고 이후 한 달씩 앞으로 이동하는 확장 윈도우 방식입니다. 각 검증 월에서는 그 월 이전에 존재한 데이터만 학습에 사용하므로 미래 정보가 섞이지 않습니다.

| 지표 | 결과 | 해석 |
|---|---:|---|
| 검증 구간 | 2024-04 ~ 2026-08, 29회 | 월별 완전 분리 검증 |
| 평균 정확도 | 50.7% | 다수 클래스 기준선 55.2%보다 낮음 |
| 평균 ROC-AUC | 0.524 | 무작위 기준 0.500보다 조금 높지만 약함 |
| 상위 20% 예측 종목 상승 비율 개선 | +3.9%p | 확률 순위에는 약한 정보가 있을 가능성 |

따라서 현재 기준 모델은 **상승·하락을 안정적으로 맞히는 수준이 아니며**, 매매 또는 서비스 배포에 사용하지 않습니다. 다음 개선 단계는 시장 지표·업종·공식 수급 데이터와 같은 외부 설명변수를 추가하고, 확률 임계값·거래비용을 포함한 워크포워드 검증을 수행하는 것입니다.

생성 결과:

- `ml/models/ohlcv_logistic_regression.joblib`: 전체 이용 가능 기간으로 학습한 최종 기준 모델
- `ml/models/ohlcv_walk_forward_metrics.csv`: 월별 시간순 검증 지표
- `ml/models/ohlcv_walk_forward_predictions.csv`: 검증 구간의 종목별 확률·예측값
- `analysis/output/ohlcv_walk_forward_metrics.png`: 월별 성능과 상위 확률 종목의 적중률

## 최종 모델: KOSPI 시장 피처 결합

종목 자체의 OHLCV만으로는 약했던 예측 순위를 보완하기 위해 KOSPI 지수를 2023-09-01부터 2026-08-28까지 725건 보강했습니다. 당일 장 마감까지 알 수 있는 KOSPI 1·5일 수익률, 20일 변동성, 20일 이동평균 괴리율과 종목의 5·20일 상대강도를 종목 피처에 결합했습니다.

```powershell
# KOSPI 지수 초기 적재 또는 기간 보강
python -m etl.market_loader --start-date 20230901 --end-date 20260828

# 시장 피처 결합 모델의 기준 성능 확인
python -m ml.kospi_market_walk_forward

# 전체 피처와 간결 피처 Logistic Regression을 비교해 최종 모델 저장
python -m ml.kospi_market_model_selection
```

동일한 29회 확장 윈도우 검증에서 다음과 같이 비교했습니다. 간결 모델은 상관성이 높거나 기여도가 낮았던 5일 이동평균 괴리율, 거래량 변화율, 20일 상대강도를 제외했습니다.

| 모델 | 평균 정확도 | 평균 ROC-AUC | 상위 20% 상승률 개선 | 판단 |
|---|---:|---:|---:|---|
| OHLCV 기준 | 50.7% | 0.5247 | +3.98%p | 시장 정보 없이 약한 순위 예측력 |
| OHLCV + KOSPI 전체 피처 | 52.8% | 0.5627 | +8.46%p | 시장 국면 결합으로 개선 |
| **OHLCV + KOSPI 간결 피처** | **52.8%** | **0.5628** | **+8.54%p** | **최종 선택** |

최종 입력 피처는 장중 변동성, 20일 이동평균 괴리율, 전일 종가 변화율, RSI(14), 종가 대비 MACD, KOSPI 1·5일 수익률, KOSPI 20일 변동성·이동평균 괴리율, 5일 상대강도입니다. 모든 피처는 예측 기준일 장 마감 시점까지의 정보로 계산했습니다.

최종 모델도 정확도는 다수 클래스 기준선(55.2%)보다 낮습니다. 따라서 “모든 종목의 방향을 맞히는 모델”로 해석하지 않고, **상승 가능성에 따라 종목을 정렬하는 기준 모델**로만 사용합니다. 이 프로젝트 범위에서는 추가적인 복잡 모델 탐색 대신 이 결과를 최종 모델로 기록합니다.

### 트리 모델 최종 비교

로지스틱 회귀만 선택했다는 한계를 확인하기 위해, 간결 시장 결합 피처를 동일하게 사용한 Random Forest·XGBoost·LightGBM도 추가로 비교했습니다. 2026-03-03부터 2026-08-28까지 111,927건을 한 번도 학습에 사용하지 않는 최종 홀드아웃으로 고정했고, 그 이전 532,751건으로 각 모델을 학습했습니다.

| 모델 | 정확도 | ROC-AUC | 상위 20% 상승률 개선 | 판단 |
|---|---:|---:|---:|---|
| **Logistic Regression** | 47.9% | **0.5800** | **+10.90%p** | **최종 선택: 확률 순위 선별력 최고** |
| XGBoost | 55.1% | 0.5660 | +6.32%p | 정확도는 높지만 순위 선별력은 낮음 |
| LightGBM | 54.6% | 0.5443 | +3.76%p | 개선 폭이 제한적 |
| Random Forest | 55.4% | 0.5241 | +6.53%p | 방향 정확도는 기준선 근처, 순위 선별력 약함 |

모델 선택 기준은 상승확률의 순위 품질인 ROC-AUC와 상위 20% 선별력입니다. 클래스 균형을 적용한 Logistic Regression은 0.5 임계값 정확도가 낮게 나올 수 있으므로, 정확도만으로 최종 모델을 고르지 않았습니다. 홀드아웃 비교 뒤 선택된 Logistic Regression은 일일 예측에 사용할 수 있도록 전체 이용 가능 기간으로 다시 학습해 저장했습니다.

```powershell
python -m ml.kospi_market_holdout_benchmark
```

생성 결과:

- `ml/models/final_kospi_direction_model.joblib`: 최종 시장 결합 간결 Logistic Regression 모델
- `ml/models/final_kospi_direction_model_summary.json`: 후보별 시간순 검증 결과와 선택 근거
- `ml/models/kospi_market_model_selection_metrics.csv`: 월별 후보 모델 성능
- `analysis/output/kospi_market_model_selection.png`: 후보별 ROC-AUC·상위 20% 선별력 비교 차트
- `ml/models/kospi_market_holdout_benchmark.csv`: 네 모델의 최종 홀드아웃 비교 결과
- `analysis/output/kospi_market_holdout_benchmark.png`: 네 모델의 ROC-AUC·상위 20% 선별력 비교 차트

## 일일 예측 CSV와 대시보드

모델링 단계 이후에는 아래 한 명령으로 KRX 종목 마스터·일별 시세·KOSPI 지수를 증분 갱신하고, 최종 모델의 종목별 다음 거래일 상승확률을 생성합니다.

```powershell
python -m etl.daily_prediction_update
```

당일 KRX 시세가 아직 제공되지 않은 경우에는 마지막 적재 거래일 데이터로 예측을 다시 생성합니다. 최신 피처가 충분한 종목만 예측 대상에 포함되며, 최근 실행에서는 944종목 중 913종목의 예측이 생성됐습니다.

생성 결과:

- `data/predictions/latest_direction_predictions.csv`: 예측 가능한 전 종목의 기준일·종가·상승확률·예측 순위
- `data/predictions/kospi_top20_predictions.csv`: 상승확률 상위 20개 종목
- `data/predictions/prediction_history.csv`: 기준일별 예측 이력

대시보드는 같은 CSV를 바로 표시합니다.

```powershell
streamlit run dashboard/app.py
```

대시보드에서는 최종 모델의 홀드아웃 ROC-AUC, 상위 확률 종목, 개별 종목 검색·필터·CSV 내려받기를 제공합니다. 예측확률은 분석 참고용 순위이며 투자 권유가 아닙니다.

## 최종 성과와 프로젝트 결론

FATE의 1차 프로젝트 범위는 **공식 데이터 기반의 KOSPI 다음 거래일 방향 분석·검증·일일 예측 화면을 재현 가능하게 완성하는 것**이었습니다. 이 범위는 완료했습니다.

| 구분 | 최종 결과 |
|---|---|
| 데이터 기반 | KRX Open API 기반 KOSPI 944종목, OHLCV 675,189건(2023-09-01 ~ 2026-08-28) |
| 데이터 품질 | 종목·날짜 중복 0건, OHLCV 결측 0건 |
| 검증 설계 | 확장 윈도우 29회 검증 및 2026-03-03 ~ 2026-08-28 최종 홀드아웃 111,927건 |
| 최종 모델 | KOSPI 시장 피처를 결합한 간결 Logistic Regression |
| 후보 비교 | Logistic Regression, Random Forest, XGBoost, LightGBM |
| 최종 홀드아웃 ROC-AUC | 0.5800 |
| 상위 20% 상승률 개선 | 전체 종목 대비 +10.90%p |
| 운영 결과물 | 일일 갱신 명령, 종목별 예측 CSV, 상위 20개 CSV, Streamlit 대시보드 |

### 성능을 어떻게 해석했는가

최종 모델의 0.5 임계값 정확도는 47.9%로 다수 클래스 기준 54.7%보다 낮았습니다. 따라서 FATE를 모든 종목의 상승·하락을 안정적으로 맞히는 모델이나 매매 신호 서비스로 해석하지 않습니다.

반면 최종 홀드아웃 ROC-AUC는 0.5800이고 예측확률 상위 20% 종목의 실제 상승 비율은 전체 종목보다 평균 10.90%p 높았습니다. 즉, OHLCV와 KOSPI 시장 정보에는 **종목의 상승 가능성을 정렬하는 데 쓸 수 있는 약한 정보**가 있었지만, 단기 방향을 확정적으로 예측할 정도로 강하지는 않았습니다.

이는 단순히 데이터 행 수가 부족해서라고 단정하기 어렵습니다. 일별 주가 방향은 뉴스, 공시, 투자자 수급, 업종·재무 상태, 거시 이벤트처럼 현재 모델이 관측하지 않은 요인의 영향을 크게 받고, 하루 단위 레이블 자체도 잡음이 큽니다. 실제로 트리 기반 모델까지 같은 홀드아웃에서 비교했지만 로지스틱 회귀를 넘지 못했습니다. 이 결과는 무리한 모델 복잡화보다 데이터 원천과 검증 방식이 더 중요하다는 판단 근거가 됐습니다.

### 완료 범위와 향후 확장

현재 버전은 포트폴리오·학습 목적의 분석 시스템으로 완료합니다. 실제 투자 의사결정이나 자동매매에는 사용하지 않습니다. 후속 프로젝트로 확장한다면, 검증 기간과 시점을 엄격히 맞춘 공식 투자자 수급·재무·업종·공시/뉴스 데이터를 추가하고 별도 홀드아웃에서 다시 검증해야 합니다.

포트폴리오 발표 자료는 [FATE_포트폴리오.pptx](C:/Develops/fate/docs/FATE_포트폴리오.pptx)에서 확인할 수 있습니다.

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

## 이후 확장 방향

- 3년 구간과 일치하도록 KOSPI 시장지표도 과거 데이터를 보강한 뒤 시장 국면 피처를 추가
- 업종·재무·공식 수급처럼 시점이 맞는 외부 설명변수를 더해 동일한 워크포워드 방식으로 재검증
- 확률 임계값·거래비용을 포함한 전략 수준의 검증은 기준 모델이 개선된 뒤 별도로 수행
