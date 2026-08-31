# FATE — Financial Analysis Trend Engine

국내 KOSPI 종목의 공식 일별 시세를 수집하고, 기술지표 기반 EDA·유의검정·예측을 수행하는 금융 데이터 분석 프로젝트입니다.

## 현재 범위

- 데이터 원천: KRX Open API의 **유가증권 종목기본정보**, **유가증권 일별매매정보**
- 분석 대상: KOSPI 944종목, 2025-08-01 ~ 2026-08-28 일별 OHLCV 246,389건
- 분석 흐름: KRX 적재 → OHLCV 패널 생성 → EDA·CDA → 예측 모델 검증

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
analysis/     OHLCV 패널 생성, EDA, 가설검정, 노트북
config/       환경 변수와 DB 연결
data/         원천·가공 데이터
etl/          KRX 적재와 일일 갱신
ml/           피처 기반 예측·검증 모델
sql/          테이블 정의와 초기 데이터 SQL
```
