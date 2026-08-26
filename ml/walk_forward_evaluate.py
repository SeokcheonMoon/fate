"""시간 순서를 보존한 워크포워드 방식으로 XGBoost를 검증한다.

실행 예시:
    python -m ml.walk_forward_evaluate --folds 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from xgboost import XGBClassifier

from ml.train import FEATURE_COLUMNS, TARGET_COLUMN, load_dataset


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "fate_features.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "metrics" / "walk_forward_metrics.csv"


def build_model(scale_pos_weight: float) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=300, max_depth=3, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, objective="binary:logistic",
        eval_metric="logloss", scale_pos_weight=scale_pos_weight,
        random_state=42, n_jobs=-1,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=4, help="최근 검증 구간 수")
    parser.add_argument("--validation-days", type=int, default=30, help="각 검증 구간의 거래일 수")
    args = parser.parse_args()

    data = load_dataset(DATA_PATH).sort_values("trade_date")
    dates = pd.Index(data["trade_date"].drop_duplicates().sort_values())
    required_days = args.folds * args.validation_days
    if len(dates) <= required_days:
        raise ValueError("워크포워드 검증을 위한 과거 거래일이 부족합니다.")

    rows = []
    for fold in range(args.folds):
        start = len(dates) - required_days + fold * args.validation_days
        validation_dates = dates[start : start + args.validation_days]
        train = data[data["trade_date"] < validation_dates[0]]
        validation = data[data["trade_date"].isin(validation_dates)]
        imputer = SimpleImputer(strategy="median")
        x_train = imputer.fit_transform(train[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan))
        x_validation = imputer.transform(validation[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan))
        y_train, y_validation = train[TARGET_COLUMN], validation[TARGET_COLUMN]
        positives = int((y_train == 1).sum())
        negatives = int((y_train == 0).sum())
        model = build_model(negatives / positives if positives else 1.0)
        model.fit(x_train, y_train)
        probability = model.predict_proba(x_validation)[:, 1]
        predicted = (probability >= 0.5).astype(int)
        rows.append(
            {
                "fold": fold + 1,
                "train_end": train["trade_date"].max().date().isoformat(),
                "validation_start": validation["trade_date"].min().date().isoformat(),
                "validation_end": validation["trade_date"].max().date().isoformat(),
                "train_rows": len(train), "validation_rows": len(validation),
                "accuracy": accuracy_score(y_validation, predicted),
                "roc_auc": roc_auc_score(y_validation, probability),
                "brier_score": brier_score_loss(y_validation, probability),
            }
        )

    result = pd.DataFrame(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"워크포워드 결과: {OUTPUT_PATH}")
    print(result.to_string(index=False, float_format="{:.3f}".format))
    print(f"평균 ROC-AUC: {result['roc_auc'].mean():.3f}")


if __name__ == "__main__":
    main()
