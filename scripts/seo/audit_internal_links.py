#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "_site"
BASE_PATH = ""
HREF_RE = re.compile(r'href="([^"]+)"')
ID_RE = re.compile(r'\sid="([^"]+)"')


def target_exists(url_path: str) -> bool:
    if url_path == "" or url_path == "/":
        return (SITE_ROOT / "index.html").exists()
    if BASE_PATH and url_path.startswith(BASE_PATH):
        url_path = url_path[len(BASE_PATH):] or "/"
    url_path = url_path.lstrip("/")
    target = SITE_ROOT / url_path
    if target.is_dir():
        return (target / "index.html").exists()
    if target.exists():
        return True
    return (target / "index.html").exists()


def main() -> int:
    if not SITE_ROOT.exists():
        print("[links] _site가 없습니다. 먼저 npm run build를 실행하세요.")
        return 1

    issues: list[str] = []
    for html_path in SITE_ROOT.rglob("*.html"):
        html = html_path.read_text(encoding="utf-8")
        ids = set(ID_RE.findall(html))
        for href in HREF_RE.findall(html):
            if href.startswith(("http://", "https://", "mailto:", "tel:", "javascript:")):
                continue
            if href.startswith("#"):
                anchor = href[1:]
                if anchor and anchor not in ids:
                    issues.append(f"{html_path.relative_to(REPO_ROOT)}: 없는 앵커 {href}")
                continue
            parsed = urlparse(href)
            if parsed.fragment and not parsed.path:
                if parsed.fragment not in ids:
                    issues.append(f"{html_path.relative_to(REPO_ROOT)}: 없는 앵커 #{parsed.fragment}")
                continue
            if parsed.path and not target_exists(parsed.path):
                issues.append(f"{html_path.relative_to(REPO_ROOT)}: 내부 링크 대상 없음 {href}")

    if issues:
        print("[links] 오류")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("[links] 내부 링크와 페이지 내 앵커 검사를 통과했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
