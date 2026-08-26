# 업종·수급 참조 데이터 적재

`sql/ddl/05_create_stock_reference_tables.sql`을 MySQL `fate` 데이터베이스에서 한 번 실행합니다.

## 자동 수집(pykrx)

현재 설치되는 `pykrx` 1.2.8은 KRX 로그인 세션을 사용한다. `.env`에 본인의 KRX 계정을 설정한 뒤 종목별 일자별 투자자 순매수 거래대금을 가져온다. 자격 증명은 Git에 커밋하거나 공유하지 않는다.

```env
KRX_ID=본인_KRX_아이디
KRX_PW=본인_KRX_비밀번호
```

로그인이 실패하거나 KRX가 빈 응답을 반환하면 적재기는 실패로 기록하며 데이터를 0건 성공으로 처리하지 않는다. 처음에는 반드시 한 종목·짧은 기간으로 확인한다.

```powershell
python -m pip install pykrx
python -m etl.investor_flow_pykrx_loader --ticker 005930 --start-date 20260801 --end-date 20260827
```

확인 후 모든 이미 적재된 종목의 누락 기간을 수집하려면 다음을 실행한다. 요청이 많으므로 장시간 걸릴 수 있다.

```powershell
python -m etl.investor_flow_pykrx_loader --all --backfill --start-date 20250801 --end-date 20260827
```

## 다음 단계

수급 데이터가 충분히 쌓이면 feature engineering에서 최근 1·5·20일 순매수, 거래대금 대비 순매수 비율, 업종 대비 수익률을 생성한 뒤 모델을 다시 학습합니다.
