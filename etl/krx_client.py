"""KRX Open API의 공통 요청 처리.

인증키는 환경 변수 ``KRX_API_KEY``로만 읽는다. 키 자체는 코드나 로그에 남기지 않는다.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import requests


BASE_URL = "https://data-dbg.krx.co.kr/svc/apis"
REQUEST_TIMEOUT_SECONDS = 30


class KRXAPIError(RuntimeError):
    """KRX API가 정상 데이터를 반환하지 않았을 때 발생한다."""


def get_api_key() -> str:
    api_key = os.getenv("KRX_API_KEY")
    if not api_key:
        raise KRXAPIError(
            "KRX_API_KEY가 설정되지 않았습니다. .env 파일에 KRX_API_KEY=발급키를 추가하세요."
        )
    return api_key


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    """KRX의 배열 응답과 래핑된 배열 응답을 모두 행 목록으로 정규화한다."""
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]

    if not isinstance(payload, Mapping):
        raise KRXAPIError("KRX API 응답 형식이 예상과 다릅니다.")

    # KRX는 HTTP 200에도 실패 내용을 respCode/respMsg로 반환한다.
    if payload.get("respCode"):
        raise KRXAPIError(str(payload.get("respMsg") or payload))

    out_blocks = [
        value for key, value in payload.items()
        if key.startswith("OutBlock_") and isinstance(value, list)
    ]
    if len(out_blocks) == 1:
        return [dict(row) for row in out_blocks[0] if isinstance(row, Mapping)]

    for key in ("output", "data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, Mapping)]

    if not payload:
        return []
    raise KRXAPIError(f"KRX API 행 목록을 찾을 수 없습니다: {sorted(payload.keys())}")


def fetch_rows(path: str, base_date: str) -> list[dict[str, Any]]:
    """한 기준일의 KRX API 데이터를 가져온다."""
    if len(base_date) != 8 or not base_date.isdigit():
        raise ValueError("base_date는 YYYYMMDD 형식이어야 합니다.")

    response = requests.get(
        f"{BASE_URL}/{path}.json",
        params={"basDd": base_date},
        headers={"AUTH_KEY": get_api_key()},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code in (401, 403):
        raise KRXAPIError("KRX 인증키 또는 API 활용 승인을 확인하세요.")
    if response.status_code == 429:
        raise KRXAPIError("KRX 일일 호출 한도를 초과했습니다.")
    response.raise_for_status()
    try:
        return _extract_rows(response.json())
    except ValueError as error:
        raise KRXAPIError("KRX API가 JSON 응답을 반환하지 않았습니다.") from error
