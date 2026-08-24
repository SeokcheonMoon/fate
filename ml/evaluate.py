"""저장된 FATE 분류 모델의 검증 지표를 출력한다."""

from __future__ import annotations

import json
from pathlib import Path


METRICS_PATH = Path(__file__).resolve().parent / "models" / "up_direction_metrics.json"


def main() -> None:
    if not METRICS_PATH.exists():
        raise FileNotFoundError(
            "검증 지표가 없습니다. 먼저 `python -m ml.train`을 실행하세요."
        )

    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    print(f"모델: {metrics['model']}")
    print(f"검증 기간: {metrics['validation_start']} ~ {metrics['validation_end']}")
    print(f"학습/검증 행 수: {metrics['train_rows']:,} / {metrics['validation_rows']:,}")
    print(f"정확도: {metrics['accuracy']:.3f}")
    print(f"정밀도: {metrics['precision']:.3f}")
    print(f"재현율: {metrics['recall']:.3f}")
    print(f"F1: {metrics['f1']:.3f}")
    if metrics['roc_auc'] is not None:
        print(f"ROC-AUC: {metrics['roc_auc']:.3f}")
    print(f"혼동 행렬 [[TN, FP], [FN, TP]]: {metrics['confusion_matrix']}")


if __name__ == "__main__":
    main()
