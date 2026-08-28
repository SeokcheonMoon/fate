"""일일 갱신 진입점.

공식 API 기반 적재기로 전환 중이므로 현재는 외부 웹 데이터 수집을 실행하지
않는다. 공공데이터포털·Open DART 적재기 연결 후 다시 활성화한다.
"""

from __future__ import annotations

def main() -> None:
    raise RuntimeError(
        "외부 웹 기반 일일 수집은 중지되었습니다. "
        "공식 API 서비스 키를 설정하고 새 적재기를 연결한 뒤 실행하세요."
    )


if __name__ == "__main__":
    main()
