#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from lol_daily_intel import (
    REPO_ROOT,
    STATE_PATH,
    SOURCES_PATH,
    canonical_url,
    ensure_intel_tree,
    normalize_space,
    now_iso,
    now_jst,
    parse_iso,
    raw_items_path,
    read_json_default,
    strip_html,
    today_string,
    write_json,
)


USER_AGENT = "SeigaBlog LoL daily intelligence (https://github.com/seiga-tabi/SeigaBlog)"
BASE_URL = "https://www.leagueoflegends.com"


def log(message: str) -> None:
    print(f"[LoL Intel Collect] {message}", file=sys.stderr)


def parse_sources() -> list[dict[str, Any]]:
    if not SOURCES_PATH.exists():
        return []

    sources: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in SOURCES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        item_match = re.match(r"\s*-\s+id:\s*(.+)$", line)
        if item_match:
            if current:
                sources.append(current)
            current = {"id": clean_yaml_value(item_match.group(1))}
            continue
        if current is None:
            continue
        field_match = re.match(r"\s+(url|tier|type|category|product|priority|enabled|publisher):\s*(.+)$", line)
        if field_match:
            key = field_match.group(1)
            value: Any = clean_yaml_value(field_match.group(2))
            if key in {"tier", "priority"}:
                try:
                    value = int(value)
                except ValueError:
                    pass
            if key == "enabled":
                value = str(value).lower() not in {"false", "0", "no"}
            current[key] = value
    if current:
        sources.append(current)
    return [source for source in sources if source.get("enabled", True)]


def clean_yaml_value(value: str) -> str:
    value = value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')):
        return value[1:-1]
    return value


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_next_data(page_html: str) -> dict[str, Any] | None:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        page_html,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return json.loads(html.unescape(match.group(1)))


def article_url(value: dict[str, Any]) -> str:
    action_url = (
        value.get("action", {})
        .get("payload", {})
        .get("url")
    )
    url = action_url or value.get("url") or value.get("link") or ""
    if isinstance(url, dict):
        url = url.get("url", "")
    return urllib.parse.urljoin(BASE_URL, str(url)) if url else ""


def article_description(value: dict[str, Any]) -> str:
    description = value.get("description") or value.get("body") or value.get("excerpt") or ""
    if isinstance(description, dict):
        description = description.get("body") or description.get("text") or ""
    return strip_html(str(description))


def walk_articles(value: Any) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    if isinstance(value, dict):
        title = normalize_space(value.get("title", ""))
        published_at = value.get("publishedAt") or value.get("published_at") or value.get("date")
        url = article_url(value)
        if title and published_at and url:
            articles.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": str(published_at),
                    "description": article_description(value),
                    "image_url": image_url(value),
                }
            )
        for item in value.values():
            articles.extend(walk_articles(item))
    elif isinstance(value, list):
        for item in value:
            articles.extend(walk_articles(item))
    return articles


def image_url(value: dict[str, Any]) -> str:
    media = value.get("media") or value.get("imageMedia") or value.get("image") or {}
    if isinstance(media, dict):
        return str(media.get("url") or media.get("src") or "")
    return ""


def collect_source(
    source: dict[str, Any],
    fetched_at: str,
    last_successful_run_at: dt.datetime | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    url = source["url"]
    try:
        page_html = fetch_text(url)
        next_data = extract_next_data(page_html)
        if not next_data:
            return [], {"id": source.get("id"), "url": url, "error": "__NEXT_DATA__를 찾지 못했습니다."}
        articles = walk_articles(next_data)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return [], {"id": source.get("id"), "url": url, "error": str(error)}

    result = []
    seen_urls: set[str] = set()
    for article in articles:
        if not within_search_window(article.get("published_at", ""), source, last_successful_run_at):
            continue
        normalized_url = canonical_url(article["url"])
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        result.append(
            {
                "raw_item_id": f"raw-{canonical_url_hash(normalized_url)}",
                "product": source.get("product", "lol_pc"),
                "source_id": source.get("id"),
                "source_tier": source.get("tier", 1),
                "source_type": source.get("type", "riot_official"),
                "content_category": source.get("category", "other"),
                "publisher": source.get("publisher", "Riot Games"),
                "title": article["title"],
                "url": article["url"],
                "canonical_url": normalized_url,
                "published_at": article["published_at"],
                "description": article["description"],
                "image_url": article["image_url"],
                "fetched_at": fetched_at,
            }
        )
    return result, None


def within_search_window(
    published_at: str,
    source: dict[str, Any],
    last_successful_run_at: dt.datetime | None,
) -> bool:
    published = parse_iso(published_at)
    if not published:
        return True
    if last_successful_run_at and published >= last_successful_run_at:
        return True
    category = str(source.get("category", "other"))
    lookback_hours = 168 if category in {"patch", "dev"} else 36
    age_hours = max(0.0, (now_jst() - published).total_seconds() / 3600)
    return age_hours <= lookback_hours


def canonical_url_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="최근 LoL 공식 정보를 수집해 raw item JSON으로 저장합니다.")
    parser.add_argument("--date", help="저장 파일에 사용할 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 저장하지 않고 결과만 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_intel_tree()
    date_value = today_string(args.date)
    fetched_at = now_iso()
    sources = parse_sources()
    state = read_json_default(STATE_PATH, {})
    last_successful_run_at = parse_iso(state.get("last_successful_run_at"))
    if not sources:
        log(f"수집 출처가 없습니다: {SOURCES_PATH}")
    items: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for source in sources:
        source_items, failure = collect_source(source, fetched_at, last_successful_run_at)
        if failure:
            failures.append(failure)
            log(f"수집 실패: {failure['url']} ({failure['error']})")
            continue
        items.extend(source_items)
        log(f"{source.get('id')} 수집 항목: {len(source_items)}개")

    payload = {
        "ok": True,
        "date": date_value,
        "fetched_at": fetched_at,
        "source_count": len(sources),
        "checked_sources": sources,
        "item_count": len(items),
        "items": items,
        "failures": failures,
        "optional_collectors": {
            "youtube": "YOUTUBE_API_KEY가 있을 때 별도 확장 대상입니다.",
            "x": "X_BEARER_TOKEN이 있을 때 별도 확장 대상입니다.",
            "web_search": "WEB_SEARCH_API_KEY가 있을 때 보도/교차 검증 확장 대상입니다.",
        },
    }
    output_path = raw_items_path(date_value)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        write_json(output_path, payload)
        log(f"raw item 저장: {output_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
