"""일별 KRX 갱신 후 최종 모델 예측 CSV를 만드는 단일 실행 진입점.

실행:
    python -m etl.daily_prediction_update
"""

from etl.daily_update import main as update_market_data
from ml.kospi_daily_prediction import main as create_predictions
from ml.track_prediction_performance import main as update_prediction_performance


def main() -> None:
    update_market_data()
    create_predictions()
    # 다음 거래일의 실제 결과가 새로 들어온 기존 예측을 함께 채점한다.
    update_prediction_performance()


if __name__ == "__main__":
    main()
