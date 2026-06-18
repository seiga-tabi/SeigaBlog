#!/usr/bin/env python3
from __future__ import annotations

import argparse

from normalize_java_release import (
    SEEN_ITEMS_PATH,
    STATE_PATH,
    generation_report_path,
    now_iso,
    read_json,
    selected_topic_path,
    today_string,
    write_json,
)


STATE_KEYS = {
    "java_stable_release": "latest_stable_version",
    "java_hotfix": "latest_hotfix_version",
    "java_snapshot": "latest_snapshot_version",
    "java_pre_release": "latest_pre_release_version",
    "java_release_candidate": "latest_release_candidate_version",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Java 전용 state와 seen item을 갱신합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 갱신하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    selected = read_json(selected_topic_path(date_value), {})
    generation = read_json(generation_report_path(date_value), {})
    item = selected.get("selected")
    if not item:
        return 0

    state = read_json(
        STATE_PATH,
        {
            "last_started_at": None,
            "last_successful_run_at": None,
            "last_post_created_at": None,
            "latest_stable_version": None,
            "latest_hotfix_version": None,
            "latest_snapshot_version": None,
            "latest_pre_release_version": None,
            "latest_release_candidate_version": None,
        },
    )
    seen = read_json(SEEN_ITEMS_PATH, {"items": []})
    src = item.get("source", {})
    seen_item = {
        "canonical_url": src.get("canonical_url") or src.get("url"),
        "title": src.get("title"),
        "version": item.get("version"),
        "release_channel": item.get("release_channel"),
        "seen_at": now_iso(),
    }
    if not any(current.get("canonical_url") == seen_item["canonical_url"] for current in seen.get("items", []) if isinstance(current, dict)):
        seen.setdefault("items", []).append(seen_item)

    state["last_successful_run_at"] = now_iso()
    if generation.get("generated") or generation.get("updated_existing"):
        state["last_post_created_at"] = now_iso()
    state_key = STATE_KEYS.get(item.get("release_channel"))
    if state_key and item.get("version"):
        state[state_key] = item["version"]

    if not args.dry_run:
        write_json(SEEN_ITEMS_PATH, seen)
        write_json(STATE_PATH, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
