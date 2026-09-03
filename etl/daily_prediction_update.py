"""일별 KRX 갱신 후 최종 모델 예측 CSV를 만드는 단일 실행 진입점.

실행:
    python -m etl.daily_prediction_update
"""

from etl.daily_update import main as update_market_data
from ml.kospi_daily_prediction import main as create_predictions


def main() -> None:
    update_market_data()
    create_predictions()


if __name__ == "__main__":
    main()
