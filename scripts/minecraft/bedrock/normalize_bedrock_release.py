#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from typing import Any

from bedrock_common import (
    canonical_url,
    existing_bedrock_source_urls,
    has_java_exclusion,
    normalized_items_path,
    now_iso,
    raw_items_path,
    read_json_default,
    SEEN_ITEMS_PATH,
    today_string,
    write_json,
)


EXCLUDE_TITLE_TERMS = ["Minecraft Education", "Minecraft Dungeons", "Minecraft Legends", "Marketplace"]
PLATFORM_TERMS = ["Xbox", "PlayStation", "Nintendo Switch", "Windows", "Android", "iOS", "Fire"]
BUG_ID_RE = re.compile(r"\b(?:MCPE|REALMS|BDS)-\d+\b", re.IGNORECASE)
VERSION_RE = re.compile(r"\b(?:v(?:ersion)?\s*)?(\d+\.\d+(?:\.\d+){0,2})(?:\.\d+)?\b", re.IGNORECASE)


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Normalize] {message}")


def release_channel(title: str, text: str) -> str:
    lowered_title = title.lower()
    lowered = f"{title}\n{text}".lower()
    if "withdrawn" in lowered or "removed from preview" in lowered:
        return "bedrock_withdrawn"
    if "hotfix" in lowered_title:
        return "bedrock_hotfix"
    if "preview" in lowered_title:
        return "bedrock_preview"
    if "beta" in lowered_title:
        return "bedrock_beta"
    if "bedrock edition" in lowered_title or "(bedrock)" in lowered_title or "changelog" in lowered_title:
        return "bedrock_stable_release"
    if any(platform.lower() in lowered_title for platform in PLATFORM_TERMS) and "bedrock" in lowered:
        return "bedrock_platform_specific"
    if any(term in lowered for term in ["planned", "coming soon", "future", "experimental"]):
        return "bedrock_official_planned"
    return "bedrock_official_announcement"


def version_from(title: str, paragraphs: list[str]) -> str:
    text = "\n".join([title, *paragraphs[:12]])
    match = VERSION_RE.search(text)
    return match.group(1) if match else ""


def has_excluded_product_title(title: str) -> bool:
    return any(term.lower() in title.lower() for term in EXCLUDE_TITLE_TERMS)


def select_lines(paragraphs: list[str], keywords: list[str], limit: int = 12) -> list[str]:
    selected: list[str] = []
    for paragraph in paragraphs:
        lowered = paragraph.lower()
        if any(keyword.lower() in lowered for keyword in keywords):
            selected.append(paragraph)
        if len(selected) >= limit:
            break
    return selected


def supported_platforms(paragraphs: list[str]) -> list[str]:
    text = "\n".join(paragraphs)
    return [platform for platform in PLATFORM_TERMS if re.search(rf"\b{re.escape(platform)}\b", text, flags=re.IGNORECASE)]


def summary(title: str, channel: str, version: str) -> dict[str, str]:
    version_part = f" {version}" if version else ""
    if channel == "bedrock_stable_release":
        return {
            "ko": f"Mojang Studios 공식 원문에서 확인한 Minecraft Bedrock Edition{version_part} 정식 업데이트 후보입니다.",
            "ja": f"Mojang Studios公式原文で確認したMinecraft Bedrock Edition{version_part}正式アップデート候補です。",
        }
    if channel == "bedrock_hotfix":
        return {
            "ko": f"Minecraft Bedrock Edition{version_part} 핫픽스 원문을 구조화했습니다.",
            "ja": f"Minecraft Bedrock Edition{version_part}ホットフィックスの原文を構造化しました。",
        }
    if channel in {"bedrock_beta", "bedrock_preview"}:
        return {
            "ko": f"정식판이 아닌 Bedrock 테스트 채널 변경점입니다. 원문에서 확인된 내용만 기록했습니다.",
            "ja": f"正式版ではないBedrockテストチャンネルの変更点です。原文で確認できた内容のみ記録しました。",
        }
    return {
        "ko": f"Bedrock 관련 공식 발표를 원문 기준으로 구조화했습니다.",
        "ja": f"Bedrock関連の公式発表を原文基準で構造化しました。",
    }


def normalize_item(item: dict[str, Any], existing_urls: set[str], seen_urls: set[str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    title = item.get("title", "")
    paragraphs = item.get("paragraphs", [])
    text = "\n".join([title, *paragraphs])
    if has_java_exclusion(title):
        return None, {"url": item.get("canonical_url"), "title": title, "reason": "java_title_exclusion"}
    if has_excluded_product_title(title):
        return None, {"url": item.get("canonical_url"), "title": title, "reason": "excluded_product"}
    if "bedrock" not in text.lower() and "preview" not in text.lower() and "beta" not in text.lower():
        return None, {"url": item.get("canonical_url"), "title": title, "reason": "not_clearly_bedrock"}

    canonical = canonical_url(item.get("canonical_url") or item.get("url", ""))
    channel = release_channel(title, text)
    version = version_from(title, paragraphs)
    platforms = supported_platforms(paragraphs)
    bug_ids = sorted(set(match.upper() for match in BUG_ID_RE.findall(text)))
    duplicate_reasons = []
    if canonical in existing_urls:
        duplicate_reasons.append("existing_post_source_url")
    if canonical in seen_urls:
        duplicate_reasons.append("seen_item")

    normalized = {
        "id": item.get("id"),
        "product": "minecraft",
        "edition": "bedrock",
        "release_channel": channel,
        "version": version,
        "release_name": None,
        "source": {
            "url": item.get("url", ""),
            "canonical_url": canonical,
            "title": title,
            "publisher": item.get("publisher", "Mojang Studios"),
            "published_at": item.get("published_at") or None,
            "last_verified_at": item.get("fetched_at") or now_iso(),
        },
        "summary": summary(title, channel, version),
        "added": select_lines(paragraphs, ["added", "new", "introducing", "experimental"]),
        "changed": select_lines(paragraphs, ["changed", "updated", "adjusted", "improved", "tweaked"]),
        "fixed": select_lines(paragraphs, ["fixed", "bug", "crash", "resolved", "issue"]),
        "removed": select_lines(paragraphs, ["removed", "withdrawn"]),
        "experimental_features": select_lines(paragraphs, ["experimental", "experiment"]),
        "platform_changes": select_lines(paragraphs, PLATFORM_TERMS),
        "touch_control_changes": select_lines(paragraphs, ["touch", "control", "joystick"]),
        "realms_changes": select_lines(paragraphs, ["realms", "realm"]),
        "creator_changes": select_lines(paragraphs, ["creator"]),
        "add_on_changes": select_lines(paragraphs, ["add-on", "addon", "add on", "script api"]),
        "technical_changes": select_lines(paragraphs, ["technical", "api", "server", "command", "molang"]),
        "known_issues": select_lines(paragraphs, ["known issue", "known issues"]),
        "bug_ids": bug_ids,
        "supported_platforms": platforms,
        "previous_version": None,
        "target_stable_version": None,
        "world_compatibility": None,
        "realms_compatibility": None,
        "add_on_compatibility": None,
        "duplicate": {"is_duplicate": bool(duplicate_reasons), "reasons": duplicate_reasons},
        "raw_excerpt": paragraphs[:12],
    }
    return normalized, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="수집한 Bedrock 원문을 구조화 JSON으로 정규화합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="상태 파일은 갱신하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    raw = read_json_default(raw_items_path(date_value), {"items": [], "excluded": [], "failures": [], "checked_sources": []})
    seen_payload = read_json_default(SEEN_ITEMS_PATH, {"items": []})
    seen_urls = {canonical_url(item.get("canonical_url") or item.get("url", "")) for item in seen_payload.get("items", [])}
    existing_urls = existing_bedrock_source_urls()

    normalized: list[dict[str, Any]] = []
    excluded = list(raw.get("excluded", []))
    for item in raw.get("items", []):
        value, exclusion = normalize_item(item, existing_urls, seen_urls)
        if value:
            normalized.append(value)
        elif exclusion:
            excluded.append(exclusion)

    payload = {
        "date": date_value,
        "run_started_at": raw.get("run_started_at"),
        "checked_sources": raw.get("checked_sources", []),
        "items": normalized,
        "excluded": excluded,
        "failures": raw.get("failures", []),
    }
    write_json(normalized_items_path(date_value), payload)
    log(f"정규화 완료: {len(normalized)}개, 제외 {len(excluded)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
