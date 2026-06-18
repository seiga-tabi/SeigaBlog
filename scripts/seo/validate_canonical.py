#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "_site"
BASE_URL = "https://blog.seigatabi.com"


def expected_url(path: Path) -> str:
    relative = path.relative_to(SITE_ROOT)
    if relative.name == "index.html":
        url_path = "/" + str(relative.parent).strip("/")
        if url_path == "/.":
            url_path = "/"
        if not url_path.endswith("/"):
            url_path += "/"
    else:
        url_path = "/" + str(relative)
    if url_path == "//":
        url_path = "/"
    return f"{BASE_URL}{url_path}"


def main() -> int:
    if not SITE_ROOT.exists():
        print("[canonical] _site가 없습니다. 먼저 npm run build를 실행하세요.")
        return 1

    issues: list[str] = []
    for html_path in SITE_ROOT.rglob("*.html"):
        html = html_path.read_text(encoding="utf-8")
        match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', html)
        if not match:
            issues.append(f"{html_path.relative_to(REPO_ROOT)}: canonical 없음")
            continue
        canonical = match.group(1)
        if "#" in canonical:
            issues.append(f"{html_path.relative_to(REPO_ROOT)}: hash canonical 사용")
        expected = expected_url(html_path)
        if canonical != expected:
            issues.append(f"{html_path.relative_to(REPO_ROOT)}: canonical 불일치 {canonical} != {expected}")

    if issues:
        print("[canonical] 오류")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("[canonical] 모든 HTML canonical이 현재 URL과 일치합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
