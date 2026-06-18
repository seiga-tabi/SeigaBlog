#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lol_content_utils import (
    REPO_ROOT,
    load_champion_map,
    repo_path,
    write_report,
)


CONTENT_QUEUE_PATH = REPO_ROOT / "data" / "lol" / "content_queue.json"
SUPPORTED_TYPES = {
    "patch-meta-followup",
    "position-meta",
    "champion-focus",
    "riot-dev-update",
    "system-guide",
}
POSITIONS = {"Top", "Jungle", "Mid", "Bot", "Support"}
REQUIRED_FIELDS = {
    "patch-meta-followup": [
        "patch_version",
        "current_patch",
        "previous_patch",
        "region",
        "tier_range",
        "queue",
        "sample_period",
        "sample_size",
        "champion_metrics",
        "source_notes",
        "related_patch_post",
    ],
    "position-meta": [
        "patch_version",
        "position",
        "region",
        "tier_range",
        "queue",
        "sample_period",
        "sample_size",
        "rising_picks",
        "stable_picks",
        "falling_picks",
        "ban_candidates",
        "source_notes",
    ],
    "champion-focus": [
        "patch_version",
        "champion_key",
        "champion_name_ko",
        "champion_name_ja",
        "official_changes",
        "riot_context",
        "position",
        "current_metrics",
        "previous_metrics",
        "build_data",
        "rune_data",
        "matchup_data",
        "source_notes",
    ],
    "riot-dev-update": [
        "source_url",
        "source_title",
        "source_published_at",
        "last_checked",
        "official_announcements",
        "confirmed_changes",
        "planned_changes",
        "undecided_topics",
        "release_schedule",
        "related_posts",
    ],
    "system-guide": [
        "system_name",
        "applicable_patch",
        "official_changes",
        "before_state",
        "after_state",
        "affected_positions",
        "affected_champions",
        "examples",
        "source_notes",
    ],
}
DATA_BASIS_FIELDS = ["region", "tier_range", "queue", "sample_period", "sample_size"]


def log(message: str) -> None:
    print(f"[LoL Content Data] {message}")


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def queue_items(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def item_label(item: dict, index: int) -> str:
    return str(item.get("id") or item.get("slug") or f"item-{index}")


def metric_values(item: dict) -> list[dict]:
    values: list[dict] = []
    for key in [
        "champion_metrics",
        "rising_picks",
        "stable_picks",
        "falling_picks",
        "ban_candidates",
        "affected_champions",
    ]:
        current = item.get(key)
        if isinstance(current, list):
            values.extend(value for value in current if isinstance(value, dict))
    if isinstance(item.get("current_metrics"), dict):
        values.append(item["current_metrics"])
    if isinstance(item.get("previous_metrics"), dict):
        values.append(item["previous_metrics"])
    return values


def validate_champion_name(
    issues: list[dict],
    file_label: str,
    label: str,
    key: str,
    ko: str | None,
    ja: str | None,
    name_map: dict,
) -> None:
    entry = name_map.get("champions", {}).get(key)
    if not entry:
        issues.append({"file": file_label, "item": label, "type": "champion", "message": f"Data Dragon에서 champion key를 찾지 못했습니다: {key}"})
        return
    if ko and ko != entry.get("ko"):
        issues.append({"file": file_label, "item": label, "type": "champion", "message": f"{key} 한국어명이 Data Dragon과 다릅니다: {ko} != {entry.get('ko')}"})
    if ja and ja != entry.get("ja"):
        issues.append({"file": file_label, "item": label, "type": "champion", "message": f"{key} 일본어명이 Data Dragon과 다릅니다: {ja} != {entry.get('ja')}"})


def validate_item(item: dict, index: int, file_label: str, name_map: dict) -> list[dict]:
    issues: list[dict] = []
    label = item_label(item, index)
    content_type = item.get("content_type")

    if content_type not in SUPPORTED_TYPES:
        issues.append({"file": file_label, "item": label, "type": "content_type", "message": f"지원하지 않는 content_type입니다: {content_type}"})
        return issues

    for field in REQUIRED_FIELDS[content_type]:
        if field not in item or is_empty(item.get(field)):
            issues.append({"file": file_label, "item": label, "type": "required", "message": f"{content_type} 필수 입력이 비어 있습니다: {field}"})

    if content_type in {"patch-meta-followup", "position-meta"}:
        for field in DATA_BASIS_FIELDS:
            if is_empty(item.get(field)):
                issues.append({"file": file_label, "item": label, "type": "data_basis", "message": f"데이터 기준 필드가 없습니다: {field}"})
        if content_type == "patch-meta-followup" and is_empty(item.get("previous_patch")):
            issues.append({"file": file_label, "item": label, "type": "data_basis", "message": "이전 패치 비교값이 없어 생성할 수 없습니다."})

    if item.get("position") and item.get("position") not in POSITIONS:
        issues.append({"file": file_label, "item": label, "type": "position", "message": f"지원하지 않는 포지션입니다: {item.get('position')}"})

    if content_type == "champion-focus":
        validate_champion_name(
            issues,
            file_label,
            label,
            str(item.get("champion_key", "")),
            item.get("champion_name_ko"),
            item.get("champion_name_ja"),
            name_map,
        )

    for metric in metric_values(item):
        key = metric.get("key") or metric.get("champion_key")
        if key:
            validate_champion_name(
                issues,
                file_label,
                label,
                str(key),
                metric.get("ko") or metric.get("champion_name_ko"),
                metric.get("ja") or metric.get("champion_name_ja"),
                name_map,
            )

    if content_type == "patch-meta-followup":
        for metric in item.get("champion_metrics", []):
            if not isinstance(metric, dict):
                continue
            if is_empty(metric.get("previous_metrics")) and is_empty(metric.get("previous")):
                issues.append({"file": file_label, "item": label, "type": "data_basis", "message": f"이전 패치 비교값이 없는 챔피언 지표가 있습니다: {metric.get('key') or metric.get('ko')}"})

    if content_type == "position-meta":
        for metric in metric_values(item):
            if "matchup" in metric and is_empty(metric.get("matchup")):
                issues.append({"file": file_label, "item": label, "type": "matchup", "message": "빈 matchup 필드는 제거하거나 실제 데이터를 넣어야 합니다."})

    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LoL 후속 콘텐츠 입력 JSON을 검증합니다.")
    parser.add_argument("path", nargs="?", default=str(CONTENT_QUEUE_PATH), help="검증할 JSON 파일 경로입니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    file_label = repo_path(path) if path.exists() else args.path

    issues: list[dict] = []
    items: list[dict] = []
    if not path.exists():
        issues.append({"file": file_label, "item": "-", "type": "file", "message": "입력 JSON 파일이 없습니다."})
    else:
        try:
            items = queue_items(load_json(path))
        except json.JSONDecodeError as error:
            issues.append({"file": file_label, "item": "-", "type": "json", "message": f"JSON 파싱 실패: {error}"})

    name_map = load_champion_map()
    for index, item in enumerate(items, start=1):
        status = str(item.get("status", "ready")).lower()
        if status in {"done", "published", "skip"}:
            continue
        issues.extend(validate_item(item, index, file_label, name_map))

    report = {
        "ok": not issues,
        "file": file_label,
        "item_count": len(items),
        "issue_count": len(issues),
        "issues": issues,
    }
    report_path = write_report("lol-content/data-validation-report.json", report)
    log(f"검증 리포트 저장: {repo_path(report_path)}")
    if issues:
        for issue in issues:
            log(f"{issue['type']}: {issue['item']} - {issue['message']}")
        return 1
    log("검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

