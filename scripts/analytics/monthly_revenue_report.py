#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    report_dir = REPO_ROOT / "reports" / "monetization"
    report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    path = report_dir / f"{today}-monthly-revenue-review.md"
    path.write_text(
        "\n".join(
            [
                "# 월간 수익 검토",
                "",
                "AdSense 인증정보가 없어 실제 수익 데이터 수집을 건너뛰었습니다.",
                "월 200 USD는 목표 KPI이며 보장 수익이 아닙니다.",
                "실제 Page RPM이 없으므로 필요 페이지뷰는 가정값 시나리오로만 다룹니다.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[monthly] 안전 리포트 생성: {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

