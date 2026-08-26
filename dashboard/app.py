"""FATE 주가 방향 예측 대시보드.

실행:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREDICTION_PATH = PROJECT_ROOT / "data" / "predictions" / "latest_direction_predictions.csv"
PERFORMANCE_PATH = PROJECT_ROOT / "data" / "metrics" / "prediction_performance_summary.csv"
WALK_FORWARD_PATH = PROJECT_ROOT / "data" / "metrics" / "walk_forward_metrics.csv"


st.set_page_config(page_title="FATE | 주가 방향 예측", page_icon="📈", layout="wide")


@st.cache_data(show_spinner=False)
def load_predictions(path: str, modified_at: float) -> pd.DataFrame:
    """예측 결과를 읽고 화면 표시용 타입을 정리한다."""
    del modified_at
    data = pd.read_csv(path, encoding="utf-8-sig", dtype={"ticker": str})
    data["trade_date"] = pd.to_datetime(data["trade_date"])
    data["up_probability"] = pd.to_numeric(data["up_probability"], errors="coerce")
    data["close_price"] = pd.to_numeric(data["close_price"], errors="coerce")
    return data.dropna(subset=["up_probability"]).copy()


@st.cache_data(show_spinner=False)
def load_optional_csv(path: str, modified_at: float) -> pd.DataFrame:
    """있을 때만 생성되는 성과 파일을 안전하게 읽는다."""
    del modified_at
    return pd.read_csv(path, encoding="utf-8-sig")


def main() -> None:
    st.title("FATE 주가 방향 예측")
    st.caption("다음 거래일 상승 확률을 기반으로 한 참고용 분석 화면입니다. 투자 판단의 근거로 단독 사용하지 마세요.")

    if not PREDICTION_PATH.exists():
        st.error("예측 결과 파일을 찾을 수 없습니다. `python -m ml.prediction`을 먼저 실행해 주세요.")
        st.code("python -m ml.prediction", language="powershell")
        return

    predictions = load_predictions(str(PREDICTION_PATH), PREDICTION_PATH.stat().st_mtime)
    if predictions.empty:
        st.warning("표시할 예측 결과가 없습니다.")
        return

    latest_date = predictions["trade_date"].max()
    model_name = predictions["model"].iloc[0]
    validation_auc = predictions["validation_roc_auc"].iloc[0]
    up_count = int((predictions["prediction"] == "상승").sum())

    first, second, third, fourth = st.columns(4)
    first.metric("예측 종목 수", f"{len(predictions):,}개")
    second.metric("상승 예측", f"{up_count:,}개", f"{up_count / len(predictions):.1%}")
    third.metric("선택 모델", model_name)
    fourth.metric("검증 ROC-AUC", f"{validation_auc:.3f}")
    st.caption(f"데이터 기준일: 종목별 최신 거래일 기준 · 가장 최근 거래일: {latest_date:%Y-%m-%d}")

    st.subheader("실전 예측 성과")
    if PERFORMANCE_PATH.exists():
        performance = load_optional_csv(str(PERFORMANCE_PATH), PERFORMANCE_PATH.stat().st_mtime)
        selected_performance = performance[performance["model"] == model_name]
        if not selected_performance.empty:
            item = selected_performance.iloc[0]
            score_one, score_two, score_three = st.columns(3)
            score_one.metric("확정 예측 수", f"{int(item['evaluated_predictions']):,}건")
            score_two.metric("실제 예측 정확도", f"{item['accuracy']:.1%}")
            score_three.metric("실제 ROC-AUC", f"{item['roc_auc']:.3f}")
        else:
            st.info("현재 선택 모델의 확정 성과가 없습니다.")
    else:
        st.info("예측 이력을 쌓은 뒤 `python -m ml.track_prediction_performance`를 실행하면 실제 성과가 표시됩니다.")

    if WALK_FORWARD_PATH.exists():
        walk_forward = load_optional_csv(str(WALK_FORWARD_PATH), WALK_FORWARD_PATH.stat().st_mtime)
        if not walk_forward.empty:
            st.caption(f"워크포워드 평균 ROC-AUC: {walk_forward['roc_auc'].mean():.3f} · {len(walk_forward)}개 구간 검증")

    with st.sidebar:
        st.header("필터")
        keyword = st.text_input("종목명 또는 종목코드 검색")
        directions = st.multiselect(
            "예측 방향", ["상승", "하락 또는 보합"], default=["상승", "하락 또는 보합"]
        )
        min_probability = st.slider("최소 상승 확률", 0.0, 1.0, 0.0, 0.01)
        display_count = st.selectbox("표시 종목 수", [10, 20, 50, 100], index=1)

    filtered = predictions[predictions["prediction"].isin(directions)].copy()
    filtered = filtered[filtered["up_probability"] >= min_probability]
    if keyword:
        query = keyword.strip()
        filtered = filtered[
            filtered["name"].astype(str).str.contains(query, case=False, na=False)
            | filtered["ticker"].astype(str).str.contains(query, case=False, na=False)
        ]
    filtered = filtered.sort_values("up_probability", ascending=False)

    left, right = st.columns([3, 2])
    with left:
        st.subheader("상승 확률 상위 종목")
        chart_data = filtered.head(display_count).sort_values("up_probability")
        if chart_data.empty:
            st.info("조건에 맞는 종목이 없습니다.")
        else:
            chart = px.bar(
                chart_data,
                x="up_probability",
                y="name",
                color="prediction",
                orientation="h",
                text="up_probability",
                labels={"up_probability": "상승 확률", "name": "종목명", "prediction": "예측"},
                color_discrete_map={"상승": "#e45756", "하락 또는 보합": "#4c78a8"},
            )
            chart.update_traces(texttemplate="%{text:.1%}", textposition="outside")
            chart.update_xaxes(tickformat=".0%", range=[0, min(1, chart_data["up_probability"].max() + 0.08)])
            chart.update_layout(showlegend=False, height=max(380, len(chart_data) * 34), margin=dict(l=0, r=30, t=10, b=0))
            st.plotly_chart(chart, use_container_width=True)

    with right:
        st.subheader("예측 분포")
        distribution = predictions["prediction"].value_counts().rename_axis("prediction").reset_index(name="count")
        pie = px.pie(
            distribution, names="prediction", values="count", hole=0.55,
            color="prediction", color_discrete_map={"상승": "#e45756", "하락 또는 보합": "#4c78a8"},
        )
        pie.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(pie, use_container_width=True)

    st.subheader(f"종목별 예측 결과 ({len(filtered):,}개)")
    table = filtered[["trade_date", "ticker", "name", "close_price", "up_probability", "prediction"]].copy()
    table.columns = ["기준일", "종목코드", "종목명", "종가", "상승 확률", "예측"]
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "기준일": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "종가": st.column_config.NumberColumn(format="%,d원"),
            "상승 확률": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.1f%%"),
        },
    )
    st.download_button(
        "필터링 결과 CSV 내려받기",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="fate_direction_predictions.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
