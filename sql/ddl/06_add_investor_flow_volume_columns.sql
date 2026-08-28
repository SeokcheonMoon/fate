-- 기존 investor_flows 테이블에 종목별 투자자 순매수 수량(주) 열을 추가한다.
-- 새 DB는 05_create_stock_reference_tables.sql만 실행하면 된다.

USE fate;

ALTER TABLE investor_flows
    ADD COLUMN foreign_net_volume BIGINT NULL COMMENT '외국인 순매수 수량(주)' AFTER individual_net_value,
    ADD COLUMN institution_net_volume BIGINT NULL COMMENT '기관 합계 순매수 수량(주)' AFTER foreign_net_volume,
    ADD COLUMN individual_net_volume BIGINT NULL COMMENT '개인 순매수 수량(주)' AFTER institution_net_volume;
