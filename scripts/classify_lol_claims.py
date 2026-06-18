#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from typing import Any

from lol_content_utils import detect_champions, load_champion_map
from lol_daily_intel import (
    REPO_ROOT,
    category_label,
    claim_fingerprint,
    claims_path,
    ensure_intel_tree,
    format_date,
    normalized_items_path,
    now_iso,
    read_json_default,
    stable_hash,
    status_label,
    today_string,
    write_claim_files,
    write_json,
)


def log(message: str) -> None:
    print(f"[LoL Intel Classify] {message}")


def contains_any(text: str, values: list[str]) -> bool:
    lowered = text.lower()
    return any(value.lower() in lowered for value in values)


def parse_patch(text: str) -> str | None:
    match = re.search(r"(\d{1,2})[.-](\d{1,2})", text)
    if not match:
        return None
    return f"{int(match.group(1))}.{int(match.group(2))}"


def parse_specific_date(text: str) -> str | None:
    match = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", text)
    if not match:
        return None
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def classify_status(item: dict[str, Any]) -> str:
    text = f"{item.get('title', '')} {item.get('description', '')} {item.get('url', '')}"
    category = item.get("content_category")
    source_type = str(item.get("source_type", ""))
    if category == "patch" and contains_any(text, ["패치 노트", "patch notes", "patch-notes"]):
        return "confirmed"
    if contains_any(text, ["pbe", "테스트 서버", "test server"]):
        return "pbe_testing"
    if contains_any(text, ["철회", "취소", "부인", "revert", "cancelled", "canceled"]):
        return "rejected"
    if contains_any(text, ["적용 예정", "출시 예정", "coming in", "will ship", "will launch"]):
        return "official_scheduled" if parse_patch(text) or parse_specific_date(text) else "official_planned"
    if "riot" in source_type.lower() and category in {"dev", "system", "ranked", "champion"}:
        return "official_planned"
    if "riot" in source_type.lower():
        return "official_considering"
    return "reported"


def refine_category(item: dict[str, Any]) -> str:
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    category = item.get("content_category") or "other"
    if category != "other":
        return category
    if "patch" in text or "패치" in text:
        return "patch"
    if any(term in text for term in ["champion", "챔피언", "신규 챔피언"]):
        return "champion"
    if any(term in text for term in ["ranked", "랭크"]):
        return "ranked"
    if any(term in text for term in ["pbe", "테스트 서버"]):
        return "pbe"
    if any(term in text for term in ["dev", "개발", "업데이트"]):
        return "dev"
    if any(term in text for term in ["lck", "esports", "e스포츠", "월드 챔피언십"]):
        return "esports"
    return "other"


def topic_for(item: dict[str, Any], status: str, category: str, patch: str | None) -> dict[str, str]:
    label = category_label(category)
    if category == "patch" and patch:
        return {"ko": f"LoL {patch} 패치노트", "ja": f"LoL {patch} パッチノート"}
    if category == "dev":
        return {"ko": "LoL 개발자 업데이트", "ja": "LoL開発者アップデート"}
    if category == "pbe":
        return {"ko": "LoL PBE 변경안", "ja": "LoL PBE変更案"}
    if status == "reported":
        return {"ko": f"LoL {label['ko']} 보도", "ja": f"LoL {label['ja']}報道"}
    return {"ko": f"LoL {label['ko']} 소식", "ja": f"LoL {label['ja']}ニュース"}


def claim_text_for(item: dict[str, Any], status: str, category: str, patch: str | None) -> dict[str, str]:
    label = category_label(category)
    status_name = status_label(status)
    patch_part_ko = f" {patch}" if patch else ""
    patch_part_ja = f" {patch}" if patch else ""
    return {
        "ko": f"Riot 공식 출처에서 LoL{patch_part_ko} {label['ko']} 관련 {status_name['ko']} 정보를 확인했습니다.",
        "ja": f"Riot公式ソースでLoL{patch_part_ja}の{label['ja']}に関する{status_name['ja']}情報を確認しました。",
    }


def subjects_for(item: dict[str, Any], name_map: dict) -> list[dict[str, str]]:
    text = f"{item.get('title', '')} {item.get('description', '')}"
    subjects = []
    for entry in detect_champions(text, name_map):
        subjects.append(
            {
                "type": "champion",
                "key": entry["key"],
                "ko": entry["ko"],
                "ja": entry["ja"],
            }
        )
    return subjects


def item_to_claim(item: dict[str, Any], name_map: dict) -> dict[str, Any]:
    category = refine_category(item)
    status = classify_status({**item, "content_category": category})
    text = f"{item.get('title', '')} {item.get('description', '')}"
    patch = parse_patch(text)
    date_value = parse_specific_date(text)
    direct_release_commitment = status in {"confirmed", "official_scheduled"}
    contains_specific_patch = patch is not None
    contains_specific_date = date_value is not None
    topic = topic_for(item, status, category, patch)
    claim_text = claim_text_for(item, status, category, patch)

    claim = {
        "claim_id": f"claim-{stable_hash(item.get('canonical_url', '') + '|' + topic['ko'], 20)}",
        "product": "lol_pc",
        "topic": topic,
        "claim": claim_text,
        "status": status,
        "content_category": category,
        "expected_patch": patch,
        "expected_date": date_value,
        "subjects": subjects_for(item, name_map),
        "primary_source": {
            "tier": item.get("source_tier", 1),
            "type": item.get("source_type", "riot_official"),
            "url": item.get("url", ""),
            "canonical_url": item.get("canonical_url", ""),
            "platform_id": item.get("platform_id"),
            "publisher": item.get("publisher", "Riot Games"),
            "author": item.get("author", ""),
            "published_at": format_date(item.get("published_at")),
            "fetched_at": item.get("fetched_at") or now_iso(),
        },
        "corroborating_sources": [],
        "evidence": {
            "summary": item.get("description") or item.get("title", ""),
            "direct_release_commitment": direct_release_commitment,
            "contains_specific_patch": contains_specific_patch,
            "contains_specific_date": contains_specific_date,
        },
        "first_seen_at": now_iso(),
        "last_verified_at": now_iso(),
        "content_hash": item.get("content_hash", ""),
        "superseded_by": None,
        "source_title": item.get("title", ""),
        "duplicate": item.get("duplicate", {"is_duplicate": False, "reasons": []}),
    }
    claim["claim_fingerprint"] = claim_fingerprint(claim)
    return claim


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정규화된 LoL 항목을 claim 단위로 분류합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일 저장 없이 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_intel_tree()
    date_value = today_string(args.date)
    normalized = read_json_default(normalized_items_path(date_value), {"items": [], "checked_sources": [], "failures": []})
    name_map = load_champion_map()
    claims = [item_to_claim(item, name_map) for item in normalized.get("items", []) if item.get("product") == "lol_pc"]
    status_counts = Counter(claim["status"] for claim in claims)
    payload = {
        "ok": True,
        "date": date_value,
        "claim_count": len(claims),
        "status_counts": dict(status_counts),
        "checked_sources": normalized.get("checked_sources", []),
        "failures": normalized.get("failures", []),
        "claims": claims,
    }
    output_path = claims_path(date_value)
    if args.dry_run:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        write_json(output_path, payload)
        written = write_claim_files(claims)
        log(f"claim 저장: {output_path.relative_to(REPO_ROOT)}")
        log(f"claim 파일 갱신: {len(written)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
