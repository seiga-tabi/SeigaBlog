#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from normalize_java_release import (
    CHANNELS,
    classified_items_path,
    ensure_tree,
    log,
    normalized_items_path,
    read_json,
    repo_path,
    score_item,
    today_string,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Java 정규화 항목의 상태와 후보 점수를 계산합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 저장하지 않고 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_tree()
    date_value = today_string(args.date)
    payload = read_json(normalized_items_path(date_value), {"items": []})
    items = []
    issues = []
    for item in payload.get("items", []):
        channel = item.get("release_channel")
        if channel not in CHANNELS:
            issues.append({"url": item.get("source", {}).get("url", ""), "message": f"알 수 없는 release_channel: {channel}"})
            continue
        scored = dict(item)
        scored["candidate_score"] = score_item(item)
        items.append(scored)
    result = {
        "ok": not issues,
        "date": date_value,
        "item_count": len(items),
        "items": items,
        "issues": issues,
    }
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        write_json(classified_items_path(date_value), result)
        log(f"분류 결과 저장: {repo_path(classified_items_path(date_value))}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
