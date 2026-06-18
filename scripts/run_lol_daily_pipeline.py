#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys

from lol_daily_intel import (
    STATE_PATH,
    claims_path,
    ensure_intel_tree,
    generation_report_path,
    normalized_items_path,
    now_iso,
    read_json_default,
    today_string,
    update_seen_items,
    write_json,
)


def log(message: str) -> None:
    print(f"[LoL Daily Pipeline] {message}")


def run_step(name: str, command: list[str]) -> int:
    log(f"{name} 실행: {' '.join(command)}")
    result = subprocess.run(command, text=True, check=False)
    if result.returncode != 0:
        log(f"{name} 실패: exit {result.returncode}")
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LoL 일일 정보 수집·분류·선정·생성 파이프라인을 실행합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="글과 PR용 산출물을 만들지 않고 검색 및 검증만 수행합니다.")
    parser.add_argument("--force-generate", action="store_true", help="품질 기준을 충족한 주제가 있을 때 강제로 글 생성을 허용합니다.")
    parser.add_argument("--use-ai", action="store_true", help="AI 문장 생성을 요청합니다.")
    parser.add_argument("--no-ai", action="store_true", help="AI를 사용하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_intel_tree()
    date_value = today_string(args.date)
    state = read_json_default(
        STATE_PATH,
        {
            "last_started_at": None,
            "last_successful_run_at": None,
            "last_article_created_at": None,
            "last_pull_request_number": None,
        },
    )
    state["last_started_at"] = now_iso()
    if not args.dry_run:
        write_json(STATE_PATH, state)

    common_args = ["--date", date_value]
    dry_args = ["--dry-run"] if args.dry_run else []
    steps = [
        ("최근 LoL 정보 수집", ["python3", "scripts/collect_lol_intel.py", *common_args, *dry_args]),
        ("원문 정규화", ["python3", "scripts/normalize_lol_sources.py", *common_args, *dry_args]),
        ("claim 분류", ["python3", "scripts/classify_lol_claims.py", *common_args, *dry_args]),
        ("claim 재검증", ["python3", "scripts/revalidate_lol_claims.py", *common_args]),
        (
            "오늘 주제 선택",
            [
                "python3",
                "scripts/select_daily_lol_topic.py",
                *common_args,
                *(["--force-generate"] if args.force_generate else []),
                *dry_args,
            ],
        ),
        (
            "일일 글 생성",
            [
                "python3",
                "scripts/generate_daily_lol_post.py",
                *common_args,
                *(["--dry-run"] if args.dry_run else []),
                *(["--use-ai"] if args.use_ai and not args.no_ai else ["--no-ai"]),
            ],
        ),
    ]

    for name, command in steps:
        code = run_step(name, command)
        if code != 0:
            return code

    normalized = read_json_default(normalized_items_path(date_value), {"items": []}).get("items", [])
    claims = read_json_default(claims_path(date_value), {"claims": []}).get("claims", [])
    generated = read_json_default(generation_report_path(date_value), {"generated": False})
    if not args.dry_run:
        update_seen_items(normalized, claims)
        state["last_successful_run_at"] = now_iso()
        if generated.get("generated"):
            state["last_article_created_at"] = now_iso()
        write_json(STATE_PATH, state)
    log("일일 파이프라인 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
