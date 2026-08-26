## STEP 1: 프로젝트 기획서 작성 (8/1 완료)

#### - GitHub Repository 생성
#### -  프로젝트 폴더 구조 생성
#### -  requirements.txt 작성
#### -  .gitignore 작성
#### -  Python 가상환경 생성 및 활성화
#### -  pip install -r requirements.txt 실행
#### -  MySQL 설치 및 접속 확인

## Step 2. 데이터베이스 환경 구축 (8/3 완료)

#### - MySQL 사용 결정
#### - fate 데이터베이스 생성
#### - MySQL DB 생성
#### - Python DB 연결

## Step 3. ETL 적재 검증 + 파이썬 연결 (8/23 완료)

#### - MySQL 스키마 및 핵심 테이블
#### - 종목 주가·KOSPI 수집/증분 적재 ETL
#### - ETL 실행 이력 관리
#### - 초기 적재·조회 검증 결과
#### - 환경변수 및 실행 방법
#### - MySQL 기준 개발 일정 완료 현황

## STEP 4: KOSPI·KOSDAQ 전체 종목 초기 적재 (8/24 완료)

#### - KOSPI·KOSDAQ 전체 종목 마스터를 `stocks` 테이블에 동기화
#### - 전체 미적재 종목의 최근 1년 일별 OHLCV를 `stock_prices`에 초기 적재
#### - 이후 증분 적재와 종목명·종목코드 기반 대시보드 구현을 위한 데이터 기반 확보

## STEP 5: 예측 모델·대시보드·수급 데이터 기반 구축 (8/27 진행 중)

#### - 기술지표 15개를 사용한 다음 거래일 상승 여부 분류 모델 학습
#### - Logistic Regression·XGBoost·Random Forest 성능 비교 및 XGBoost 선택
#### - 최신 종목별 상승 확률 예측 파일 생성
#### - Streamlit 예측 대시보드 구현: 종목 검색, 방향·확률 필터, 확률 순위 차트, CSV 다운로드
#### - 워크포워드 검증 및 예측-실제 성과 추적 스크립트 추가
#### - 업종 프로필·외국인/기관/개인 순매수 데이터용 MySQL 테이블 설계
#### - KRX 로그인 기반 pykrx 수급 자동 적재기 구현 및 삼성전자 단건 적재 검증 완료
#### - 주가·KOSPI·수급을 오늘 기준으로 증분 갱신하는 `etl.daily_update` 추가
# 처음 한 번: 과거 1년 수급 이력 채우기
python -m etl.investor_flow_pykrx_loader --all --backfill --start-date 20250801 --end-date (마지막날짜)

# 이후 매일: 최신 데이터만 갱신
python -m etl.daily_update


### 다음 작업

#### - 전체 종목의 최근 1년 수급 이력 초기 적재 (`--backfill` 옵션 사용)
#### - 수급 피처(1·5·20일 순매수, 거래대금 대비 비율)를 feature engineering에 연결
#### - 모델 재학습 및 워크포워드 성능 비교
#### - 업종·산업 분류 데이터 연동
