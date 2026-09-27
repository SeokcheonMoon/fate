"""대시보드 데이터에서 투자자용 리포트를 안전하게 생성한다."""

from __future__ import annotations

import json
import os
import html
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests

from llm.prompt import INVESTOR_REPORT_SYSTEM_PROMPT


@dataclass(frozen=True)
class ReportResult:
    """발행 화면에 표시할 리포트와 생성 방식을 담는다."""

    content: str
    source: str


def _number(value: object, digits: int = 4) -> float | None:
    """JSON에 안전하게 실을 수 있는 숫자로 변환한다."""
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else round(float(numeric), digits)


def _date(value: object) -> str | None:
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    """존재하는 열만 골라 결측값을 null로 바꾼 JSON 레코드를 만든다."""
    available = [column for column in columns if column in frame.columns]
    if not available:
        return []
    return json.loads(frame[available].where(pd.notna(frame[available]), None).to_json(
        orient="records", force_ascii=False, date_format="iso"
    ))


def build_report_context(
    *,
    selected_date: object,
    model_name: str,
    predictions: pd.DataFrame,
    displayed_predictions: pd.DataFrame,
    performance: pd.DataFrame | None = None,
    daily_performance: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """LLM과 기본 템플릿이 공유할, 검증 가능한 사실표를 만든다.

    모든 요약 통계는 여기서 pandas로 계산하고, 모델이 계산하도록 넘기지 않는다.
    """
    selected = predictions.copy()
    probability = pd.to_numeric(selected.get("up_probability"), errors="coerce")
    up_mask = selected.get("prediction", pd.Series(index=selected.index, dtype="object")).eq("상승")
    report_date = _date(selected_date) or "확인 불가"

    top = displayed_predictions.sort_values("up_probability", ascending=False).head(10).copy()
    top_records: list[dict[str, Any]] = []
    for row in _records(
        top,
        ["prediction_rank", "ticker", "name", "close_price", "up_probability", "prediction"],
    ):
        for key in ("prediction_rank", "close_price", "up_probability"):
            if key in row:
                row[key] = _number(row[key])
        top_records.append(row)

    context: dict[str, Any] = {
        "report_date": report_date,
        "model": model_name,
        "prediction_summary": {
            "prediction_count": int(len(selected)),
            "up_prediction_count": int(up_mask.sum()),
            "down_or_flat_prediction_count": int((~up_mask).sum()),
            "mean_up_probability": _number(probability.mean()),
        },
        "displayed_prediction_count": int(len(displayed_predictions)),
        "top_displayed_predictions": top_records,
        "performance": None,
        "selected_date_actual_performance": None,
        "data_quality_notes": [],
    }
    if probability.isna().any():
        context["data_quality_notes"].append("일부 예측확률이 누락되어 화면 집계에서 제외되었습니다.")
    if displayed_predictions.empty:
        context["data_quality_notes"].append("현재 화면 필터에 맞는 종목이 없습니다.")

    if performance is not None and not performance.empty:
        item = performance[performance["model"] == model_name] if "model" in performance else pd.DataFrame()
        if not item.empty:
            row = item.iloc[0]
            context["performance"] = {
                "evaluated_predictions": _number(row.get("evaluated_predictions"), 0),
                "accuracy": _number(row.get("accuracy")),
                "roc_auc": _number(row.get("roc_auc")),
                "brier_score": _number(row.get("brier_score")),
                "mean_actual_return": _number(row.get("mean_actual_return")),
                "latest_actual_date": _date(row.get("latest_actual_date")),
            }

    if daily_performance is not None and not daily_performance.empty and "model" in daily_performance:
        daily = daily_performance[daily_performance["model"] == model_name].copy()
        if "trade_date" in daily:
            daily["trade_date"] = pd.to_datetime(daily["trade_date"], errors="coerce").dt.normalize()
            item = daily[daily["trade_date"] == pd.Timestamp(selected_date).normalize()]
            if not item.empty:
                row = item.iloc[0]
                context["selected_date_actual_performance"] = {
                    "evaluated_predictions": _number(row.get("evaluated_predictions"), 0),
                    "successful_predictions": _number(row.get("successful_predictions"), 0),
                    "accuracy": _number(row.get("accuracy")),
                    "mean_actual_return": _number(row.get("mean_actual_return")),
                }
            else:
                context["data_quality_notes"].append(
                    "선택 기준일의 다음 거래일 실제 결과가 확정되지 않았거나 제공되지 않았습니다."
                )
    else:
        context["data_quality_notes"].append("일별 실제 성과 데이터가 제공되지 않았습니다.")
    return context


def _percent(value: object) -> str:
    return "확인 불가" if value is None else f"{float(value):.1%}"


def render_data_only_report(context: dict[str, Any]) -> str:
    """API 키가 없어도 사실표만으로 발행 가능한 안전한 기본 리포트."""
    summary = context["prediction_summary"]
    lines = [
        "# 시장 데이터 AI 리포트",
        f"**기준일:** {context['report_date']}",
        "",
        "## 요약",
        f"{context['report_date']} 기준 {context['model']} 모델의 예측 대상은 {summary['prediction_count']:,}개입니다.",
        f"이 중 상승 예측은 {summary['up_prediction_count']:,}개이며, 평균 상승확률은 {_percent(summary['mean_up_probability'])}입니다.",
        "해당 확률은 모델의 예측값이며 실제 상승률이나 미래 결과를 의미하지 않습니다.",
        "",
        "## 시장 예측 현황",
        f"상승 예측 {summary['up_prediction_count']:,}개, 하락 또는 보합 예측 {summary['down_or_flat_prediction_count']:,}개가 집계되었습니다.",
        f"현재 화면 조건에 해당하는 종목은 {context['displayed_prediction_count']:,}개입니다.",
        "",
        "## 주요 변화",
        "비교 대상 이전 기준일 데이터가 이 리포트의 사실표에 포함되지 않아 확률·순위의 변화를 판단할 수 없습니다.",
        "",
        "## 주요 예측 종목",
    ]
    top = context["top_displayed_predictions"]
    if top:
        for item in top:
            name = item.get("name") or item.get("ticker") or "종목명 확인 불가"
            rank = item.get("prediction_rank")
            rank_text = f"순위 {int(rank):,}" if rank is not None else "순위 확인 불가"
            lines.append(f"- {name}: {rank_text}, 상승확률 {_percent(item.get('up_probability'))}, 예측 {item.get('prediction', '확인 불가')}")
    else:
        lines.append("현재 화면 조건에 해당하는 주요 예측 종목 데이터가 없습니다.")

    lines.extend(["", "## 모델 성과"])
    performance = context.get("performance")
    if performance:
        lines.append(
            f"확정 예측 {int(performance['evaluated_predictions']):,}건 기준 정확도 {_percent(performance['accuracy'])}, "
            f"실제 ROC-AUC {performance['roc_auc'] if performance['roc_auc'] is not None else '확인 불가'}로 집계되었습니다."
        )
        if performance.get("latest_actual_date"):
            lines.append(f"해당 전체 성과의 최신 실제 결과 기준일은 {performance['latest_actual_date']}입니다.")
    else:
        lines.append("제공된 데이터에서 선택 모델의 확정 성과를 확인할 수 없습니다.")
    daily = context.get("selected_date_actual_performance")
    if daily:
        lines.append(
            f"선택 기준일의 확정 예측은 {int(daily['evaluated_predictions']):,}건, 성공 수는 "
            f"{int(daily['successful_predictions']):,}건, 성공률은 {_percent(daily['accuracy'])}입니다."
        )

    lines.extend([
        "",
        "## 데이터 기반 관찰",
        "상위 목록은 제공된 상승확률을 기준으로 정렬한 상대적 위치입니다. 원인 데이터가 제공되지 않아 확률이나 순위의 원인은 판단할 수 없습니다.",
        "",
        "## 유의사항",
    ])
    notes = context.get("data_quality_notes", [])
    lines.extend(f"- {note}" for note in notes)
    lines.append("- 본 리포트는 제공된 모델 예측과 과거 확정 성과를 정리한 참고 정보이며, 투자 판단이나 미래 결과를 보장하지 않습니다.")
    return "\n".join(lines)


def _generate_openai_report(*, api_key: str, model: str, prompt: str) -> str:
    """사용자가 이번 요청에 입력한 OpenAI 키로만 리포트를 생성한다."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai 패키지를 설치한 뒤 다시 시도해 주세요.") from exc
    response = OpenAI(api_key=api_key).responses.create(
        model=model,
        instructions=INVESTOR_REPORT_SYSTEM_PROMPT,
        input=prompt,
        store=False,
    )
    return (response.output_text or "").strip()


def _generate_gemini_report(*, api_key: str, model: str, prompt: str) -> str:
    """Gemini GenerateContent REST API를 호출해 별도 SDK 의존성을 없앤다."""
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": INVESTOR_REPORT_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
        },
        timeout=90,
    )
    if not response.ok:
        raise RuntimeError("Gemini API 요청이 거부되었습니다. API 키와 모델명을 확인해 주세요.")
    payload = response.json()
    candidates = payload.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    content = "".join(part.get("text", "") for part in parts).strip()
    if not content:
        raise RuntimeError("Gemini 리포트 생성 결과가 비어 있습니다.")
    return content


def generate_report(
    context: dict[str, Any],
    provider: str = "기본",
    api_key: str | None = None,
    model: str | None = None,
) -> ReportResult:
    """선택한 제공자로 리포트를 생성한다. API 키는 저장하지 않는다."""
    if provider == "기본":
        return ReportResult(render_data_only_report(context), "데이터 기반 기본 리포트")
    if provider not in {"OpenAI", "Gemini"}:
        raise RuntimeError("지원하지 않는 리포트 제공자입니다.")
    if not api_key or not api_key.strip():
        raise RuntimeError(f"{provider} API 키를 입력해 주세요.")
    resolved_model = model or ("gpt-5-mini" if provider == "OpenAI" else "gemini-3.8-flash")
    prompt = (
        "아래 JSON 사실표만 근거로 투자자용 리포트를 작성하세요. "
        "JSON에 없는 사실·수치·원인·계산은 추가하지 마세요.\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )
    try:
        if provider == "OpenAI":
            content = _generate_openai_report(
                api_key=api_key.strip(), model=resolved_model, prompt=prompt
            )
        else:
            content = _generate_gemini_report(
                api_key=api_key.strip(), model=resolved_model, prompt=prompt
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"{provider} 리포트 생성 요청이 실패했습니다. API 키와 모델명을 확인한 뒤 다시 시도해 주세요."
        ) from exc
    if not content:
        raise RuntimeError("리포트 생성 결과가 비어 있습니다. 다시 시도해 주세요.")
    return ReportResult(content, f"{provider} 생성 리포트 ({resolved_model})")


def _korean_font_path() -> Path | None:
    """PDF에서 한글이 깨지지 않도록 설치된 한글 글꼴을 찾는다."""
    candidates = (
        Path(r"C:\Windows\Fonts\malgun.ttf"),
        Path(r"C:\Windows\Fonts\NanumGothic.ttf"),
        Path(r"C:\Windows\Fonts\gulim.ttc"),
    )
    return next((path for path in candidates if path.exists()), None)


def create_report_pdf(report_content: str, report_date: str) -> bytes:
    """Markdown 리포트의 핵심 구조를 보존한 한글 PDF 바이트를 만든다."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("reportlab 패키지를 설치한 뒤 PDF 발행을 다시 시도해 주세요.") from exc

    font_path = _korean_font_path()
    if font_path is None:
        raise RuntimeError("PDF 한글 글꼴을 찾을 수 없습니다. Malgun Gothic 또는 NanumGothic을 설치해 주세요.")
    font_name = "FateKorean"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=0))

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "FateBody", parent=styles["BodyText"], fontName=font_name, fontSize=9.5,
        leading=16, alignment=TA_LEFT, spaceAfter=6,
    )
    heading = ParagraphStyle(
        "FateHeading", parent=styles["Heading2"], fontName=font_name, fontSize=14,
        leading=20, textColor=colors.HexColor("#17365D"), spaceBefore=12, spaceAfter=7,
    )
    title = ParagraphStyle(
        "FateTitle", parent=styles["Title"], fontName=font_name, fontSize=20,
        leading=28, textColor=colors.HexColor("#17365D"), spaceAfter=10,
    )
    metadata = ParagraphStyle(
        "FateMetadata", parent=body, fontSize=10, textColor=colors.HexColor("#555555"), spaceAfter=15,
    )
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm, title=f"FATE 시장 데이터 AI 리포트 - {report_date}",
        author="FATE",
    )
    story: list[Any] = []
    for raw_line in report_content.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 4))
        elif line.startswith("# "):
            story.append(Paragraph(html.escape(line[2:]), title))
        elif line.startswith("## "):
            story.append(Paragraph(html.escape(line[3:]), heading))
        elif line.startswith("**기준일:**"):
            story.append(Paragraph(html.escape(line.replace("**", "")), metadata))
        elif line.startswith("- "):
            story.append(Paragraph("• " + html.escape(line[2:]), body))
        else:
            story.append(Paragraph(html.escape(line).replace("\n", "<br/>"), body))

    def add_page_number(canvas: Any, _: Any) -> None:
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(18 * mm, 10 * mm, "FATE | 시장 데이터 AI 리포트")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{canvas.getPageNumber()} 페이지")
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return stream.getvalue()
