"""KRX Open API의 공통 요청 처리.

인증키는 환경 변수 ``KRX_API_KEY``로만 읽는다. 키 자체는 코드나 로그에 남기지 않는다.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

import requests
from dotenv import load_dotenv


BASE_URL = "https://data-dbg.krx.co.kr/svc/apis"
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_INTERVAL_SECONDS = 0.35
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 1.0
_last_request_at = 0.0

load_dotenv()


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
    """한 기준일의 KRX API 데이터를 가져온다.

    KRX가 일시적으로 빈 본문 또는 점검 HTML을 반환하는 경우가 있어, 요청 간격을
    두고 최대 5회 재시도한다. 인증·일일 한도 오류는 재시도하지 않는다.
    """
    if len(base_date) != 8 or not base_date.isdigit():
        raise ValueError("base_date는 YYYYMMDD 형식이어야 합니다.")

    global _last_request_at
    url = f"{BASE_URL}/{path}.json"
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        elapsed = time.monotonic() - _last_request_at
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)

        try:
            response = requests.get(
                url,
                params={"basDd": base_date},
                headers={"AUTH_KEY": get_api_key()},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _last_request_at = time.monotonic()
            if response.status_code in (401, 403):
                raise KRXAPIError("KRX 인증키 또는 API 활용 승인을 확인하세요.")
            if response.status_code == 429:
                raise KRXAPIError("KRX 일일 호출 한도를 초과했습니다.")
            response.raise_for_status()
            return _extract_rows(response.json())
        except KRXAPIError:
            raise
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt == MAX_RETRIES - 1:
                break
            wait_seconds = RETRY_BACKOFF_SECONDS * (2 ** attempt)
            print(
                f"{base_date}: KRX 응답 오류로 {wait_seconds:.0f}초 후 재시도 "
                f"({attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(wait_seconds)

    raise KRXAPIError(
        f"{base_date}: KRX API가 {MAX_RETRIES}회 연속 정상 JSON을 반환하지 않았습니다. "
        "잠시 후 같은 명령을 다시 실행하세요. 기존 적재 데이터는 중복되지 않습니다."
    ) from last_error
