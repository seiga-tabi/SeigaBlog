#!/usr/bin/env python3
from __future__ import annotations

import argparse
import urllib.parse
from typing import Any

from bedrock_common import (
    canonical_url,
    ensure_tree,
    fetch_url,
    is_bedrock_candidate,
    now_iso,
    parse_html,
    parse_sources,
    raw_items_path,
    stable_hash,
    today_string,
    write_json,
)


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Collect] {message}")


def article_title(parser: Any) -> str:
    return (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or (parser.headings[0] if parser.headings else "")
        or parser.title
    ).replace(" – Minecraft Feedback", "").replace(" | Minecraft", "").strip()


def article_published_at(parser: Any) -> str:
    return (
        parser.meta.get("article:published_time")
        or parser.meta.get("date")
        or parser.meta.get("dc.date")
        or ""
    )


def is_allowed_candidate_url(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host == "feedback.minecraft.net":
        return "/hc/en-us/articles/" in path or "/hc/en-us/sections/" in path
    if host in {"www.minecraft.net", "minecraft.net"}:
        return path.startswith("/en-us/article/")
    return False


def discover_candidates(source: dict[str, Any], body: str, final_url: str) -> list[dict[str, str]]:
    parser = parse_html(body)
    candidates: list[dict[str, str]] = []
    title = article_title(parser)
    page_text = "\n".join(parser.paragraphs[:12])
    if is_bedrock_candidate(title, page_text):
        candidates.append({"url": final_url, "title": title, "reason": "source_page"})

    for link in parser.links:
        text = link.get("text", "")
        href = link.get("url", "")
        if not href:
            continue
        url = urllib.parse.urljoin(final_url, href)
        if "minecraft.net" not in url and "feedback.minecraft.net" not in url:
            continue
        if not is_allowed_candidate_url(url):
            continue
        if not is_bedrock_candidate(text):
            continue
        candidates.append({"url": url, "title": text, "reason": "linked_article"})

    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = canonical_url(candidate["url"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def fetch_candidate(candidate: dict[str, str], source: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        final_url, body = fetch_url(candidate["url"])
    except Exception as error:  # noqa: BLE001 - 리포트에 원인 기록
        return None, {"url": candidate["url"], "error": str(error), "stage": "article_fetch"}

    parser = parse_html(body)
    title = article_title(parser) or candidate["title"]
    text = "\n".join(parser.paragraphs)
    if not is_bedrock_candidate(title, text):
        return None, {"url": final_url, "title": title, "reason": "not_bedrock_after_fetch", "stage": "article_filter"}
    canonical = canonical_url(parser.meta.get("og:url") or final_url)
    item = {
        "id": stable_hash(canonical, 24),
        "source_id": source.get("id"),
        "source_name": source.get("name"),
        "publisher": source.get("publisher", "Mojang Studios"),
        "url": final_url,
        "canonical_url": canonical,
        "title": title,
        "published_at": article_published_at(parser),
        "fetched_at": now_iso(),
        "discovery_reason": candidate.get("reason", ""),
        "headings": parser.headings[:30],
        "paragraphs": parser.paragraphs[:120],
    }
    return item, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="공식 출처에서 Minecraft Bedrock Edition 후보 원문을 수집합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--channel", default="all", choices=["all", "stable", "test"], help="수집 채널 필터입니다.")
    parser.add_argument("--dry-run", action="store_true", help="상태 갱신 없이 수집 산출물만 만듭니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_tree()
    date_value = today_string(args.date)
    checked_sources: list[dict[str, str]] = []
    items: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for source in parse_sources():
        url = str(source.get("url"))
        try:
            final_url, body = fetch_url(url)
        except Exception as error:  # noqa: BLE001 - 리포트에 원인 기록
            failures.append({"source": source.get("id"), "url": url, "error": str(error), "stage": "source_fetch"})
            continue
        checked_sources.append({"id": str(source.get("id")), "url": final_url, "name": str(source.get("name"))})
        for candidate in discover_candidates(source, body, final_url):
            canonical = canonical_url(candidate["url"])
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)
            item, failure = fetch_candidate(candidate, source)
            if item:
                title = item["title"].lower()
                if args.channel == "stable" and any(term in title for term in ["beta", "preview"]):
                    excluded.append({"url": item["canonical_url"], "title": item["title"], "reason": "channel_stable_filter"})
                    continue
                if args.channel == "test" and not any(term in title for term in ["beta", "preview"]):
                    excluded.append({"url": item["canonical_url"], "title": item["title"], "reason": "channel_test_filter"})
                    continue
                items.append(item)
            elif failure:
                if failure.get("stage") == "article_filter":
                    excluded.append(failure)
                else:
                    failures.append(failure)

    payload = {
        "date": date_value,
        "run_started_at": now_iso(),
        "dry_run": args.dry_run,
        "channel": args.channel,
        "checked_sources": checked_sources,
        "items": items,
        "excluded": excluded,
        "failures": failures,
    }
    write_json(raw_items_path(date_value), payload)
    log(f"수집 완료: 후보 {len(items)}개, 제외 {len(excluded)}개, 실패 {len(failures)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
