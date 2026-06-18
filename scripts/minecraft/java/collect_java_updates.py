#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
import urllib.parse
from typing import Any

from normalize_java_release import (
    QUEUE_PATH,
    SEEN_ITEMS_PATH,
    SOURCES_PATH,
    canonical_url,
    ensure_tree,
    fetch_text,
    has_bedrock_context,
    is_java_candidate,
    log,
    normalize_space,
    now_iso,
    raw_items_path,
    read_json,
    repo_path,
    stable_hash,
    strip_html,
    today_string,
    write_json,
)


def clean_yaml_value(value: str) -> Any:
    text = value.strip()
    if text.startswith(("'", '"')) and text.endswith(("'", '"')):
        text = text[1:-1]
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        return int(text)
    except ValueError:
        return text


def read_sources() -> list[dict[str, Any]]:
    if not SOURCES_PATH.exists():
        return []
    sources: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in SOURCES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line.strip() == "sources:":
            continue
        item_match = re.match(r"\s*-\s+id:\s*(.+)$", line)
        if item_match:
            if current:
                sources.append(current)
            current = {"id": clean_yaml_value(item_match.group(1))}
            continue
        if current is None:
            continue
        field_match = re.match(r"\s+([a-zA-Z0-9_]+):\s*(.+)$", line)
        if field_match:
            current[field_match.group(1)] = clean_yaml_value(field_match.group(2))
    if current:
        sources.append(current)
    return [source for source in sources if source.get("enabled", True)]


def extract_links(page_html: str, base_url: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page_html, flags=re.IGNORECASE | re.DOTALL):
        href = html.unescape(match.group(1))
        title = normalize_space(strip_html(match.group(2)))
        if not title:
            continue
        url = urllib.parse.urljoin(base_url, href)
        canonical = canonical_url(url)
        if canonical in seen:
            continue
        seen.add(canonical)
        if "feedback.minecraft.net/hc/en-us/articles" not in canonical and "minecraft.net/en-us/article" not in canonical:
            continue
        links.append({"title": title, "url": url, "canonical_url": canonical})
    return links


def collect_source(source: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    url = str(source["url"])
    try:
        page_html = fetch_text(url)
    except Exception as error:
        return [], [], {"id": source.get("id"), "url": url, "error": str(error)}

    candidates: list[dict[str, Any]] = []
    excluded_bedrock: list[dict[str, Any]] = []
    for link in extract_links(page_html, url):
        title = link["title"]
        if has_bedrock_context(title):
            excluded_bedrock.append(link)
            continue
        if not is_java_candidate(title, link["url"]):
            continue
        canonical = link["canonical_url"]
        candidates.append(
            {
                "raw_item_id": f"minecraft-java-raw-{stable_hash(canonical)}",
                "product": "minecraft",
                "edition_hint": "java",
                "source_id": source.get("id"),
                "source_tier": source.get("source_tier", 1),
                "publisher": source.get("publisher", "Mojang Studios"),
                "title": title,
                "url": link["url"],
                "canonical_url": canonical,
                "published_at": "",
                "fetched_at": now_iso(),
            }
        )
    return candidates, excluded_bedrock, None


def seen_keys() -> set[str]:
    data = read_json(SEEN_ITEMS_PATH, {"items": []})
    keys = set()
    for item in data.get("items", []):
        if isinstance(item, str):
            keys.add(item)
        elif isinstance(item, dict):
            keys.add(item.get("canonical_url") or item.get("raw_item_id") or "")
    return {key for key in keys if key}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Java 공식 업데이트 후보를 수집합니다.")
    parser.add_argument("--date", help="저장 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--channel", choices=["all", "stable", "test"], default="all", help="수집 채널입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 저장하지 않고 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_tree()
    date_value = today_string(args.date)
    sources = [
        source for source in read_sources()
        if args.channel == "all" or source.get("channel", "all") in {"all", args.channel}
    ]
    items: list[dict[str, Any]] = []
    excluded_bedrock: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    seen = seen_keys()

    for source in sources:
        source_items, source_excluded, failure = collect_source(source)
        if failure:
            failures.append(failure)
            log(f"수집 실패: {failure['url']} ({failure['error']})")
            continue
        items.extend(source_items)
        excluded_bedrock.extend(source_excluded)
        log(f"{source.get('id')} Java 후보 {len(source_items)}개, Bedrock 제외 {len(source_excluded)}개")

    unique_items: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen_in_run: set[str] = set()
    for item in items:
        key = item["canonical_url"]
        if key in seen or key in seen_in_run:
            duplicates.append(item)
            continue
        seen_in_run.add(key)
        unique_items.append(item)

    payload = {
        "ok": True,
        "date": date_value,
        "fetched_at": now_iso(),
        "checked_sources": sources,
        "item_count": len(unique_items),
        "items": unique_items,
        "excluded_bedrock": excluded_bedrock,
        "duplicates": duplicates,
        "failures": failures,
    }
    if args.dry_run:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        write_json(raw_items_path(date_value), payload)
        write_json(QUEUE_PATH, {"items": unique_items, "updated_at": now_iso()})
        log(f"raw item 저장: {repo_path(raw_items_path(date_value))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
