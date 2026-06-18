#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lol_content_utils import REPO_ROOT, repo_path, write_json, write_report
from validate_lol_content_data import CONTENT_QUEUE_PATH, SUPPORTED_TYPES, queue_items


SELECTED_TOPIC_PATH = REPO_ROOT / "data" / "lol" / "processed" / "selected-topic.json"


def log(message: str) -> None:
    print(f"[LoL Topic Select] {message}")


def load_queue(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return queue_items(json.loads(path.read_text(encoding="utf-8")))


def is_selectable(item: dict, content_type: str | None = None) -> bool:
    status = str(item.get("status", "ready")).lower()
    if status not in {"ready", "queued"}:
        return False
    if item.get("content_type") not in SUPPORTED_TYPES:
        return False
    if content_type and item.get("content_type") != content_type:
        return False
    return True


def select_item(items: list[dict], content_type: str | None = None, topic_id: str | None = None) -> dict | None:
    for item in items:
        if topic_id and item.get("id") != topic_id:
            continue
        if is_selectable(item, content_type):
            return item
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LoL 콘텐츠 queue에서 생성할 주제를 선택합니다.")
    parser.add_argument("--queue", default=str(CONTENT_QUEUE_PATH), help="content_queue.json 경로입니다.")
    parser.add_argument("--type", choices=sorted(SUPPORTED_TYPES), help="선택할 콘텐츠 유형입니다.")
    parser.add_argument("--id", help="선택할 topic id입니다.")
    parser.add_argument("--output", default=str(SELECTED_TOPIC_PATH), help="선택 결과를 저장할 경로입니다.")
    parser.add_argument("--print-only", action="store_true", help="파일 저장 없이 JSON만 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue_path = Path(args.queue)
    if not queue_path.is_absolute():
        queue_path = REPO_ROOT / queue_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    items = load_queue(queue_path)
    selected = select_item(items, args.type, args.id)
    report = {
        "ok": selected is not None,
        "queue": repo_path(queue_path) if queue_path.exists() else str(queue_path),
        "selected_id": selected.get("id") if selected else "",
        "content_type": selected.get("content_type") if selected else "",
        "candidate_count": len(items),
    }
    report_path = write_report("lol-content/topic-selection-report.json", report)

    if not selected:
        log(f"선택할 주제가 없습니다. 리포트: {repo_path(report_path)}")
        return 0

    if args.print_only:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        write_json(output_path, selected)
        log(f"선택 주제 저장: {repo_path(output_path)}")
    log(f"선택 리포트 저장: {repo_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

