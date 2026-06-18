#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "_site"
SCRIPT_RE = re.compile(
    r'<script\s+type="application/ld\+json">\s*(?P<body>.*?)\s*</script>',
    re.DOTALL,
)


def main() -> int:
    if not SITE_ROOT.exists():
        print("[schema] _site가 없습니다. 먼저 npm run build를 실행하세요.")
        return 1

    issues: list[str] = []
    article_count = 0
    breadcrumb_count = 0

    for html_path in SITE_ROOT.rglob("*.html"):
        html = html_path.read_text(encoding="utf-8")
        blocks = [match.group("body") for match in SCRIPT_RE.finditer(html)]
        if "/posts/" in str(html_path.relative_to(SITE_ROOT)) and not blocks:
            issues.append(f"{html_path.relative_to(REPO_ROOT)}: JSON-LD 없음")
            continue

        for block in blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError as error:
                issues.append(f"{html_path.relative_to(REPO_ROOT)}: JSON-LD 파싱 실패: {error}")
                continue

            schema_type = data.get("@type")
            if schema_type == "Article":
                article_count += 1
                for field in ["headline", "description", "datePublished", "dateModified", "author", "mainEntityOfPage"]:
                    if not data.get(field):
                        issues.append(f"{html_path.relative_to(REPO_ROOT)}: Article.{field} 누락")
            if schema_type == "BreadcrumbList":
                breadcrumb_count += 1
                if len(data.get("itemListElement", [])) < 2:
                    issues.append(f"{html_path.relative_to(REPO_ROOT)}: BreadcrumbList 항목 부족")

    if article_count == 0:
        issues.append("Article JSON-LD가 하나도 없습니다.")
    if breadcrumb_count == 0:
        issues.append("BreadcrumbList JSON-LD가 하나도 없습니다.")

    if issues:
        print("[schema] 오류")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("[schema] 구조화 데이터 JSON 파싱과 필수 필드 검사를 통과했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

