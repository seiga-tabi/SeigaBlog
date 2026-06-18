#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    report_dir = REPO_ROOT / "reports" / "seo"
    report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    path = report_dir / f"{today}-weekly-growth-audit.md"
    path.write_text(
        "\n".join(
            [
                "# 주간 성장 감사",
                "",
                "GA4/Search Console 인증정보가 없어 실제 검색·트래픽 원본 데이터 수집을 건너뛰었습니다.",
                "공개 저장소에는 실제 수익, 원본 쿼리 데이터, 사용자 식별 정보를 저장하지 않습니다.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[weekly] 안전 리포트 생성: {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

