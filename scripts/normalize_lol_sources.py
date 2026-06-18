#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from lol_daily_intel import (
    REPO_ROOT,
    SEEN_ITEMS_PATH,
    canonical_url,
    ensure_intel_tree,
    existing_claim_fingerprints,
    existing_post_source_urls,
    normalized_items_path,
    normalize_title,
    raw_items_path,
    read_json_default,
    stable_hash,
    today_string,
    write_json,
)


def log(message: str) -> None:
    print(f"[LoL Intel Normalize] {message}")


def platform_id_from_url(url: str) -> str:
    parts = [part for part in canonical_url(url).split("/") if part]
    return parts[-1] if parts else stable_hash(url)


def normalize_item(item: dict[str, Any], seen: dict[str, list[str]], existing_urls: set[str], existing_claims: set[str]) -> dict[str, Any]:
    canonical = canonical_url(item.get("canonical_url") or item.get("url") or "")
    title_normalized = normalize_title(item.get("title", ""))
    content_basis = "\n".join(
        [
            title_normalized,
            item.get("description", ""),
            item.get("published_at", ""),
            canonical,
        ]
    )
    title_hash = stable_hash(title_normalized, 24)
    content_hash = stable_hash(content_basis, 32)
    platform_id = platform_id_from_url(canonical)
    rough_fingerprint = stable_hash(f"{title_normalized}|{platform_id}", 24)

    duplicate_reasons = []
    if canonical in existing_urls or canonical in set(seen.get("urls", [])):
        duplicate_reasons.append("canonical_url")
    if platform_id in set(seen.get("platform_ids", [])):
        duplicate_reasons.append("platform_id")
    if title_hash in set(seen.get("title_hashes", [])):
        duplicate_reasons.append("title_normalized")
    if content_hash in set(seen.get("content_hashes", [])):
        duplicate_reasons.append("content_hash")
    if rough_fingerprint in existing_claims or rough_fingerprint in set(seen.get("claim_fingerprints", [])):
        duplicate_reasons.append("claim_fingerprint")

    return {
        **item,
        "canonical_url": canonical,
        "platform_id": platform_id,
        "title_normalized": title_normalized,
        "title_hash": title_hash,
        "content_hash": content_hash,
        "rough_claim_fingerprint": rough_fingerprint,
        "duplicate": {
            "is_duplicate": bool(duplicate_reasons),
            "reasons": duplicate_reasons,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="수집한 LoL 원문 메타데이터를 정규화하고 중복 후보를 표시합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일 저장 없이 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_intel_tree()
    date_value = today_string(args.date)
    raw_path = raw_items_path(date_value)
    raw = read_json_default(raw_path, {"items": [], "checked_sources": [], "failures": []})
    seen = read_json_default(
        SEEN_ITEMS_PATH,
        {"urls": [], "platform_ids": [], "title_hashes": [], "content_hashes": [], "claim_fingerprints": []},
    )
    existing_urls = existing_post_source_urls()
    existing_claims = existing_claim_fingerprints()

    normalized = [
        normalize_item(item, seen, existing_urls, existing_claims)
        for item in raw.get("items", [])
        if item.get("product") == "lol_pc"
    ]
    duplicates = [item for item in normalized if item["duplicate"]["is_duplicate"]]
    payload = {
        "ok": True,
        "date": date_value,
        "source_count": raw.get("source_count", len(raw.get("checked_sources", []))),
        "checked_sources": raw.get("checked_sources", []),
        "failures": raw.get("failures", []),
        "item_count": len(normalized),
        "duplicate_count": len(duplicates),
        "items": normalized,
    }
    output_path = normalized_items_path(date_value)
    if args.dry_run:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        write_json(output_path, payload)
        log(f"정규화 결과 저장: {output_path.relative_to(REPO_ROOT)}")
        log(f"중복 후보: {len(duplicates)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
