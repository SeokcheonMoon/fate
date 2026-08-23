-- etl_logs: 주가 수집 프로그램이 언제 실행됐는지 기록
-- pipeline_name: 어떤 ETL 프로그램을 실행했는지
-- ticker: 어느 종목 데이터를 처리했는지
-- status: 성공(SUCCESS), 실패(FAILED), 최신 상태라 건너뜀(SKIPPED)
-- records_processed: 몇 건의 주가 데이터를 처리했는지
-- error_message: 실패했다면 오류 내용
-- executed_at: 실행한 시간

USE fate;

CREATE TABLE etl_logs (
    log_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL COMMENT '실행한 파이프라인 이름',
    ticker VARCHAR(20) NULL COMMENT '대상 종목 코드',
    start_date DATE NULL COMMENT '수집 시작일',
    end_date DATE NULL COMMENT '수집 종료일',
    status VARCHAR(20) NOT NULL COMMENT 'SUCCESS, FAILED, SKIPPED',
    records_processed INT NOT NULL DEFAULT 0 COMMENT '처리한 데이터 건수',
    error_message TEXT NULL COMMENT '실패 상세 메시지',
    executed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '실행 시각',

    INDEX idx_etl_logs_pipeline_time (pipeline_name, executed_at),
    INDEX idx_etl_logs_ticker (ticker)
);