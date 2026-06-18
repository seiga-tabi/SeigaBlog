#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from bedrock_common import (
    BEDROCK_CHANNELS,
    classified_items_path,
    has_java_exclusion,
    normalized_items_path,
    read_json_default,
    today_string,
    write_json,
)


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Classify] {message}")


def classify(item: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    title = item.get("source", {}).get("title", "")
    text = "\n".join(item.get("raw_excerpt", []))
    channel = item.get("release_channel")
    if channel not in BEDROCK_CHANNELS:
        return None, {"url": item.get("source", {}).get("canonical_url"), "title": title, "reason": "unknown_release_channel"}
    if item.get("edition") != "bedrock":
        return None, {"url": item.get("source", {}).get("canonical_url"), "title": title, "reason": "not_bedrock_edition"}
    if has_java_exclusion(title):
        return None, {"url": item.get("source", {}).get("canonical_url"), "title": title, "reason": "java_title_exclusion"}
    if channel == "bedrock_stable_release" and any(term in title.lower() for term in ["beta", "preview"]):
        return None, {"url": item.get("source", {}).get("canonical_url"), "title": title, "reason": "test_channel_as_stable"}
    item["classification"] = {
        "release_channel": channel,
        "confidence": "high" if "bedrock" in f"{title}\n{text}".lower() else "medium",
        "checked_rules": [
            "edition_is_bedrock",
            "java_title_exclusion",
            "beta_preview_not_stable",
            "known_channel",
        ],
    }
    return item, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정규화된 Bedrock 항목을 release_channel별로 분류합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="호환용 옵션입니다. 분류 산출물은 생성합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    normalized = read_json_default(normalized_items_path(date_value), {"items": [], "excluded": [], "failures": [], "checked_sources": []})
    classified: list[dict[str, Any]] = []
    excluded = list(normalized.get("excluded", []))
    for item in normalized.get("items", []):
        value, exclusion = classify(item)
        if value:
            classified.append(value)
        elif exclusion:
            excluded.append(exclusion)
    payload = {
        "date": date_value,
        "run_started_at": normalized.get("run_started_at"),
        "checked_sources": normalized.get("checked_sources", []),
        "items": classified,
        "excluded": excluded,
        "failures": normalized.get("failures", []),
    }
    write_json(classified_items_path(date_value), payload)
    log(f"분류 완료: {len(classified)}개, 제외 {len(excluded)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
