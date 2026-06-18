#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from bedrock_common import (
    SEEN_ITEMS_PATH,
    STATE_PATH,
    classified_items_path,
    daily_report_path,
    generation_report_path,
    now_iso,
    read_json_default,
    selected_topic_path,
    today_string,
    validation_report_path,
    write_json,
)


VERSION_KEYS = {
    "bedrock_stable_release": "latest_stable_version",
    "bedrock_hotfix": "latest_hotfix_version",
    "bedrock_beta": "latest_beta_version",
    "bedrock_preview": "latest_preview_version",
}


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Tracker] {message}")


def update_state(items: list[dict[str, Any]], post_created: bool, dry_run: bool) -> None:
    state = read_json_default(
        STATE_PATH,
        {
            "last_started_at": None,
            "last_successful_run_at": None,
            "last_post_created_at": None,
            "latest_stable_version": None,
            "latest_hotfix_version": None,
            "latest_beta_version": None,
            "latest_preview_version": None,
        },
    )
    if dry_run:
        return
    state["last_successful_run_at"] = now_iso()
    if post_created:
        state["last_post_created_at"] = now_iso()
    for item in items:
        key = VERSION_KEYS.get(item.get("release_channel"))
        version = item.get("version")
        if key and version:
            state[key] = version
    write_json(STATE_PATH, state)


def update_seen(items: list[dict[str, Any]], dry_run: bool) -> None:
    if dry_run:
        return
    seen = read_json_default(SEEN_ITEMS_PATH, {"items": []})
    existing = {item.get("canonical_url") for item in seen.get("items", [])}
    for item in items:
        source = item.get("source", {})
        canonical = source.get("canonical_url")
        if not canonical or canonical in existing:
            continue
        seen.setdefault("items", []).append(
            {
                "id": item.get("id"),
                "canonical_url": canonical,
                "title": source.get("title"),
                "release_channel": item.get("release_channel"),
                "version": item.get("version"),
                "seen_at": now_iso(),
            }
        )
        existing.add(canonical)
    write_json(SEEN_ITEMS_PATH, seen)


def write_daily_report(date_value: str, dry_run: bool) -> None:
    classified = read_json_default(classified_items_path(date_value), {"items": [], "excluded": [], "failures": [], "checked_sources": []})
    selected = read_json_default(selected_topic_path(date_value), {"selected": {}})
    generated = read_json_default(generation_report_path(date_value), {"generated": False, "reason": ""})
    validation = read_json_default(validation_report_path(date_value), {"ok": None, "issues": []})
    selected_item = selected.get("selected", {})
    lines = [
        f"# {date_value} Minecraft Bedrock 일일 리포트",
        "",
        f"- 실행 이벤트: {'dry_run' if dry_run else 'scheduled_or_manual'}",
        f"- 실행 시각: {now_iso()}",
        f"- 확인한 Bedrock 공식 페이지: {len(classified.get('checked_sources', []))}개",
        f"- 발견한 Bedrock 후보: {len(classified.get('items', []))}개",
        f"- 제외한 항목: {len(classified.get('excluded', []))}개",
        f"- 실패한 출처: {len(classified.get('failures', []))}개",
        "",
        "## 확인한 Bedrock 공식 페이지",
        "",
    ]
    for source in classified.get("checked_sources", []):
        lines.append(f"- {source.get('name')}: {source.get('url')}")
    if not classified.get("checked_sources"):
        lines.append("- 없음")
    lines.extend(["", "## 발견한 Bedrock 버전", ""])
    for item in classified.get("items", []):
        lines.append(f"- {item.get('release_channel')} · {item.get('version') or 'version-null'} · {item.get('source', {}).get('title')}")
    if not classified.get("items"):
        lines.append("- 없음")
    lines.extend(["", "## 제외한 Java 또는 범위 외 항목", ""])
    for item in classified.get("excluded", []):
        lines.append(f"- {item.get('reason')}: {item.get('title') or item.get('url')}")
    if not classified.get("excluded"):
        lines.append("- 없음")
    lines.extend(
        [
            "",
            "## 플랫폼별 확인 정보",
            "",
            "- 플랫폼 정보는 원문에서 확인된 경우에만 구조화 JSON의 `supported_platforms`에 기록합니다.",
            "",
            "## 최종 주제",
            "",
            f"- Action: {selected_item.get('action', 'REPORT_ONLY')}",
            f"- Candidate score: {selected_item.get('score', {}).get('total', 0)}",
            f"- Reason: {selected_item.get('reason', '')}",
            f"- Generated: {generated.get('generated', False)}",
            f"- Post: {generated.get('post', '')}",
            "",
            "## 검증 결과",
            "",
            f"- Bedrock validation: {validation.get('ok')}",
            f"- Issue count: {len(validation.get('issues', []))}",
        ]
    )
    daily_report_path(date_value).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bedrock 전용 state, seen item, 일일 리포트를 갱신합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="state/seen_items를 갱신하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    classified = read_json_default(classified_items_path(date_value), {"items": []})
    generation = read_json_default(generation_report_path(date_value), {"generated": False})
    items = classified.get("items", [])
    update_state(items, bool(generation.get("generated")), args.dry_run)
    update_seen(items, args.dry_run)
    write_daily_report(date_value, args.dry_run)
    log("Bedrock tracker 갱신 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
