import pandas as pd

from llm.report_generator import build_report_context, create_report_pdf, generate_report


def test_data_only_report_keeps_prediction_and_actuals_separate():
    predictions = pd.DataFrame(
        {
            "ticker": ["000001", "000002"],
            "name": ["가나다", "라마바"],
            "up_probability": [0.75, 0.40],
            "prediction": ["상승", "하락 또는 보합"],
            "prediction_rank": [1, 2],
            "close_price": [1000, 2000],
        }
    )
    daily = pd.DataFrame(
        {
            "model": ["모델A"],
            "trade_date": ["2026-09-10"],
            "evaluated_predictions": [2],
            "successful_predictions": [1],
            "accuracy": [0.5],
        }
    )
    context = build_report_context(
        selected_date="2026-09-10",
        model_name="모델A",
        predictions=predictions,
        displayed_predictions=predictions,
        daily_performance=daily,
    )

    report = generate_report(context)

    assert report.source == "데이터 기반 기본 리포트"
    assert "평균 상승확률은 57.5%" in report.content
    assert "성공률은 50.0%" in report.content
    assert "실제 상승률이나 미래 결과를 의미하지 않습니다" in report.content


def test_context_marks_missing_selected_date_actuals():
    predictions = pd.DataFrame(
        {"up_probability": [0.5], "prediction": ["상승"], "ticker": ["000001"]}
    )
    daily = pd.DataFrame({"model": ["모델A"], "trade_date": ["2026-09-09"]})

    context = build_report_context(
        selected_date="2026-09-10",
        model_name="모델A",
        predictions=predictions,
        displayed_predictions=predictions,
        daily_performance=daily,
    )

    assert context["selected_date_actual_performance"] is None
    assert any("실제 결과" in note for note in context["data_quality_notes"])


def test_selected_llm_provider_requires_a_key():
    context = {"report_date": "2026-09-10"}

    try:
        generate_report(context, provider="Gemini")
    except RuntimeError as exc:
        assert "API 키" in str(exc)
    else:
        raise AssertionError("API 키가 없으면 리포트 생성이 중단되어야 합니다.")


def test_gemini_generation_uses_rest_api_without_google_sdk():
    import llm.report_generator as generator

    class FakeResponse:
        ok = True

        @staticmethod
        def json():
            return {"candidates": [{"content": {"parts": [{"text": "Gemini 리포트"}]}}]}

    calls = []
    original_post = generator.requests.post
    generator.requests.post = lambda *args, **kwargs: calls.append((args, kwargs)) or FakeResponse()
    try:
        report = generator.generate_report(
            {"report_date": "2026-09-10"}, provider="Gemini", api_key="test-key", model="gemini-test"
        )
    finally:
        generator.requests.post = original_post

    assert report.content == "Gemini 리포트"
    assert "gemini-test:generateContent" in calls[0][0][0]
    assert calls[0][1]["headers"]["x-goog-api-key"] == "test-key"


def test_data_only_report_can_be_exported_as_pdf():
    pdf = create_report_pdf("# 시장 데이터 AI 리포트\n\n## 요약\n\n테스트 리포트입니다.", "2026-09-10")

    assert pdf.startswith(b"%PDF")
