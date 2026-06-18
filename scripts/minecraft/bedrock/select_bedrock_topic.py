#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from bedrock_common import classified_items_path, selected_topic_path, today_string, write_json, read_json_default


MAJOR_PREVIEW_TERMS = [
    "new mob",
    "new biome",
    "new block",
    "new item",
    "touch control",
    "rendering",
    "graphics",
    "world generation",
    "realms",
    "add-on",
    "script api",
    "creator",
]
CHANNEL_PRIORITY = {
    "bedrock_stable_release": 7,
    "bedrock_hotfix": 6,
    "bedrock_platform_specific": 5,
    "bedrock_beta": 4,
    "bedrock_preview": 4,
    "bedrock_official_announcement": 3,
    "bedrock_official_planned": 2,
    "bedrock_superseded": 1,
    "bedrock_withdrawn": 1,
}
ACTION_PRIORITY = {"NEW_POST": 2, "UPDATE_EXISTING": 1, "REPORT_ONLY": 0}


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Select] {message}")


def score_item(item: dict[str, Any]) -> dict[str, int]:
    channel = item.get("release_channel", "")
    duplicate = bool(item.get("duplicate", {}).get("is_duplicate"))
    official_source = 30 if item.get("source", {}).get("publisher") == "Mojang Studios" else 15
    stable_importance = 20 if channel == "bedrock_stable_release" else 16 if channel == "bedrock_hotfix" else 8 if channel in {"bedrock_beta", "bedrock_preview"} else 6
    change_count = sum(len(item.get(key, [])) for key in ["added", "changed", "fixed", "technical_changes", "add_on_changes", "realms_changes"])
    user_impact = min(20, 6 + change_count * 2)
    platform_scope = min(10, max(3, len(item.get("supported_platforms", [])) * 2)) if item.get("supported_platforms") else 3
    novelty = 0 if duplicate else 10
    change_scale = min(5, max(1, change_count))
    i18n = 5
    return {
        "official_source": official_source,
        "stable_release_importance": stable_importance,
        "bedrock_user_impact": user_impact,
        "platform_scope": platform_scope,
        "novelty": novelty,
        "change_scale": change_scale,
        "i18n_feasibility": i18n,
        "total": official_source + stable_importance + user_impact + platform_scope + novelty + change_scale + i18n,
    }


def is_major_preview(item: dict[str, Any]) -> bool:
    text = "\n".join(
        [
            item.get("source", {}).get("title", ""),
            *item.get("added", []),
            *item.get("changed", []),
            *item.get("experimental_features", []),
            *item.get("technical_changes", []),
            *item.get("add_on_changes", []),
            *item.get("realms_changes", []),
        ]
    ).lower()
    return any(term in text for term in MAJOR_PREVIEW_TERMS)


def version_key(version: str | None) -> tuple[int, ...]:
    if not version:
        return (0,)
    parts = []
    for part in str(version).replace("/", ".").split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            digits = "".join(character for character in part if character.isdigit())
            parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def action_for(item: dict[str, Any], score: int, force_generate: bool) -> tuple[str, bool, str]:
    channel = item.get("release_channel")
    if item.get("duplicate", {}).get("is_duplicate"):
        return "REPORT_ONLY", False, "이미 처리한 Bedrock 원문입니다."
    if force_generate and score >= 70:
        return "NEW_POST", True, "수동 실행에서 force-generate가 지정됐고 기준 점수를 넘었습니다."
    if channel in {"bedrock_beta", "bedrock_preview"} and not is_major_preview(item):
        if score >= 70:
            return "UPDATE_EXISTING", True, "작은 Beta/Preview 변경이므로 추적 글에 누적합니다."
        return "REPORT_ONLY", False, "작은 Beta/Preview 변경이고 점수가 낮아 리포트만 생성합니다."
    if score >= 85:
        return "NEW_POST", True, "새 Bedrock 글 생성 기준을 충족했습니다."
    if score >= 70:
        return "UPDATE_EXISTING", True, "새 단독 글 대신 Bedrock 추적 글 갱신 기준입니다."
    return "REPORT_ONLY", False, "선정 점수가 70점 미만입니다."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="하루 최대 1개의 Bedrock 주제를 선택합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--force-generate", action="store_true", help="70점 이상 후보 생성을 강제로 허용합니다.")
    parser.add_argument("--dry-run", action="store_true", help="호환용 옵션입니다. 선택 산출물은 생성합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    classified = read_json_default(classified_items_path(date_value), {"items": [], "excluded": [], "failures": [], "checked_sources": []})
    candidates = []
    for item in classified.get("items", []):
        score = score_item(item)
        action, should_generate, reason = action_for(item, score["total"], args.force_generate)
        candidates.append(
            {
                "item_id": item.get("id"),
                "title": item.get("source", {}).get("title"),
                "channel": item.get("release_channel"),
                "version": item.get("version"),
                "score": score,
                "major_preview": is_major_preview(item),
                "action": action,
                "should_generate": should_generate,
                "reason": reason,
                "sort_key": [
                    1 if should_generate else 0,
                    ACTION_PRIORITY.get(action, 0),
                    CHANNEL_PRIORITY.get(item.get("release_channel"), 0),
                    *version_key(item.get("version")),
                    score["total"],
                ],
            }
        )
    item_by_id = {item.get("id"): item for item in classified.get("items", [])}
    candidates.sort(key=lambda candidate: candidate["sort_key"], reverse=True)

    selected = None
    if candidates:
        top = candidates[0]
        item = item_by_id.get(top["item_id"])
        selected = {
            "item_id": top["item_id"],
            "action": top["action"] if item else "REPORT_ONLY",
            "should_generate": bool(top["should_generate"] if item else False),
            "reason": top["reason"] if item else "후보 item을 찾지 못했습니다.",
            "score": top["score"],
            "major_preview": top["major_preview"],
        }
    else:
        selected = {"item_id": None, "action": "REPORT_ONLY", "should_generate": False, "reason": "Bedrock 후보가 없습니다.", "score": {"total": 0}}

    payload = {
        "date": date_value,
        "checked_sources": classified.get("checked_sources", []),
        "candidates": candidates,
        "selected": selected,
        "excluded": classified.get("excluded", []),
        "failures": classified.get("failures", []),
    }
    write_json(selected_topic_path(date_value), payload)
    log(f"선정 결과: {selected['action']} · {selected['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
