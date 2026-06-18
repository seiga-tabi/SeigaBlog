#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from minecraft.java.normalize_java_release import (
    STATE_PATH,
    classified_items_path,
    generation_report_path,
    now_iso,
    raw_items_path,
    read_json,
    selected_topic_path,
    today_string,
    write_daily_report,
    write_json,
)


def log(message: str) -> None:
    print(f"[Minecraft Java Pipeline] {message}")


def run_step(name: str, command: list[str]) -> int:
    log(f"{name}: {' '.join(command)}")
    result = subprocess.run(command, text=True, check=False)
    if result.returncode != 0:
        log(f"{name} 실패: exit {result.returncode}")
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Java 일일 수집·분류·생성 파이프라인을 실행합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--channel", choices=["all", "stable", "test"], default="all", help="수집 채널입니다.")
    parser.add_argument("--dry-run", action="store_true", help="검색과 검증만 수행하고 글/state를 저장하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
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
    state["last_started_at"] = now_iso()
    if not args.dry_run:
        write_json(STATE_PATH, state)

    common = ["--date", date_value]
    steps = [
        ("Java 공식 정보 수집", ["python3", "scripts/minecraft/java/collect_java_updates.py", *common, "--channel", args.channel]),
        ("Java 원문 정규화", ["python3", "scripts/minecraft/java/normalize_java_release.py", *common]),
        ("Java 상태 분류", ["python3", "scripts/minecraft/java/classify_java_release.py", *common]),
        ("Java 주제 선정", ["python3", "scripts/minecraft/java/select_java_topic.py", *common]),
        ("Java 글 생성", ["python3", "scripts/minecraft/java/generate_java_post.py", *common, *(["--dry-run"] if args.dry_run else [])]),
        ("Java 전용 검증", ["python3", "scripts/minecraft/java/validate_java_content.py", *common]),
    ]
    for name, command in steps:
        code = run_step(name, command)
        if code != 0:
            write_daily_report(date_value, {"event": "pipeline", "action": "FAILED", "reason": f"{name} 실패", "validation": "failed"})
            return code

    generation = read_json(generation_report_path(date_value), {})
    if not args.dry_run:
        code = run_step("Java tracker 갱신", ["python3", "scripts/minecraft/java/update_java_tracker.py", *common])
        if code != 0:
            return code
    raw_payload = read_json(raw_items_path(date_value), {})
    classified_payload = read_json(classified_items_path(date_value), {})
    selected_payload = read_json(selected_topic_path(date_value), {})
    selected = selected_payload.get("selected") or {}
    score = selected_payload.get("score") or selected.get("candidate_score", {})
    write_daily_report(
        date_value,
        {
            "event": "pipeline",
            "checked_sources": raw_payload.get("checked_sources", []),
            "found_versions": [item.get("version") for item in classified_payload.get("items", []) if item.get("version")],
            "excluded_bedrock": raw_payload.get("excluded_bedrock", []),
            "duplicates": selected_payload.get("duplicates", raw_payload.get("duplicates", [])),
            "action": generation.get("action") or selected_payload.get("action") or "REPORT_ONLY",
            "reason": generation.get("reason", "dry-run: 글과 이미지는 저장하지 않았습니다." if args.dry_run else ""),
            "selected_title": selected.get("source", {}).get("title") or generation.get("slug", ""),
            "score": score.get("total", ""),
            "validation": "passed",
        },
    )
    log("파이프라인 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
