#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    report = REPO_ROOT / "reports" / "monetization" / "site-audit.md"
    if not report.exists():
        print("[site audit] reports/monetization/site-audit.md 파일이 없습니다.")
        return 1

    text = report.read_text(encoding="utf-8")
    required = [
        "홈과 개별 글의 URL 구조",
        "sitemap.xml",
        "robots.txt",
        "AdSense",
        "Riot",
        "NOT_READY_FOR_ADSENSE_REVIEW",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        print(f"[site audit] 감사 리포트 필수 항목이 부족합니다: {', '.join(missing)}")
        return 1

    print("[site audit] 감사 리포트가 존재하고 필수 항목을 포함합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

