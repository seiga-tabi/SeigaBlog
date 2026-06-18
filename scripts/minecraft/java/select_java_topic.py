#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re

from normalize_java_release import (
    POSTS_DIR,
    classified_items_path,
    daily_report_path,
    ensure_tree,
    log,
    raw_items_path,
    read_json,
    repo_path,
    selected_topic_path,
    today_string,
    write_daily_report,
    write_json,
)


PRIORITY = {
    "java_stable_release": 7,
    "java_hotfix": 6,
    "java_snapshot": 5,
    "java_release_candidate": 4,
    "java_pre_release": 3,
    "java_official_announcement": 2,
    "java_official_planned": 1,
}


def existing_source_urls() -> set[str]:
    urls: set[str] = set()
    for path in POSTS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.startswith("source_url:"):
                urls.add(line.split(":", 1)[1].strip().strip('"'))
    return urls


def version_rank(version: str) -> tuple[int, int, int, int]:
    numbers = [int(item) for item in re.findall(r"\d+", version or "")[:4]]
    numbers.extend([0] * (4 - len(numbers)))
    return tuple(numbers[:4])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오늘 생성할 Minecraft Java 주제를 선택합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 저장하지 않고 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_tree()
    date_value = today_string(args.date)
    payload = read_json(classified_items_path(date_value), {"items": []})
    source_urls = existing_source_urls()
    candidates = []
    duplicates = []
    for item in payload.get("items", []):
        url = item.get("source", {}).get("canonical_url") or item.get("source", {}).get("url", "")
        if url in source_urls:
            duplicates.append(item)
            continue
        score = item.get("candidate_score", {})
        candidates.append(
            {
                "item": item,
                "total": int(score.get("total", 0)),
                "priority": PRIORITY.get(item.get("release_channel", ""), 0),
                "version_rank": version_rank(item.get("version", "")),
                "published_at": item.get("source", {}).get("published_at", ""),
            }
        )
    candidates.sort(key=lambda current: (current["total"], current["priority"], current["version_rank"], current["published_at"]), reverse=True)
    selected = candidates[0]["item"] if candidates else None
    score = selected.get("candidate_score", {}) if selected else {}
    action = score.get("action", "REPORT_ONLY") if selected else "REPORT_ONLY"
    reason = ""
    if not selected:
        reason = "Java Edition 신규 후보가 없습니다."
    elif action == "REPORT_ONLY":
        reason = "후보 점수가 70점 미만이거나 새 글 기준을 충족하지 못했습니다."
    result = {
        "ok": True,
        "date": date_value,
        "action": action,
        "selected": selected,
        "score": score,
        "duplicates": duplicates,
        "reason": reason,
    }
    raw_payload = read_json(raw_items_path(date_value), {})
    report_payload = {
        "run_started_at": "",
        "checked_sources": raw_payload.get("checked_sources", []),
        "found_versions": [item.get("version") for item in payload.get("items", []) if item.get("version")],
        "excluded_bedrock": raw_payload.get("excluded_bedrock", []),
        "duplicates": duplicates,
        "selected_title": selected.get("source", {}).get("title") if selected else "",
        "score": score.get("total", ""),
        "action": action,
        "reason": reason,
    }
    if args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        write_json(selected_topic_path(date_value), result)
        report = write_daily_report(date_value, report_payload)
        log(f"선택 결과 저장: {repo_path(selected_topic_path(date_value))}")
        log(f"일일 리포트 저장: {repo_path(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
