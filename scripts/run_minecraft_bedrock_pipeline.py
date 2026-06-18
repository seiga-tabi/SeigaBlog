#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "minecraft" / "bedrock"))

from bedrock_common import STATE_PATH, now_iso, read_json_default, today_string, write_json


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Pipeline] {message}", flush=True)


def run_step(name: str, command: list[str]) -> int:
    log(f"{name} 실행: {' '.join(command)}")
    result = subprocess.run(command, text=True, check=False)
    if result.returncode != 0:
        log(f"{name} 실패: exit {result.returncode}")
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Bedrock Edition 일일 수집·생성 파이프라인을 실행합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="검색과 검증만 수행하고 글과 상태를 갱신하지 않습니다.")
    parser.add_argument("--channel", default="all", choices=["all", "stable", "test"], help="수집 채널입니다.")
    parser.add_argument("--force-generate", action="store_true", help="70점 이상 후보 생성을 강제로 허용합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
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
    state["last_started_at"] = now_iso()
    if not args.dry_run:
        write_json(STATE_PATH, state)

    common = ["--date", date_value]
    dry = ["--dry-run"] if args.dry_run else []
    steps = [
        ("Bedrock 공식 정보 수집", ["python3", "scripts/minecraft/bedrock/collect_bedrock_updates.py", *common, "--channel", args.channel, *dry]),
        ("Bedrock 원문 정규화", ["python3", "scripts/minecraft/bedrock/normalize_bedrock_release.py", *common, *dry]),
        ("Bedrock 상태 분류", ["python3", "scripts/minecraft/bedrock/classify_bedrock_release.py", *common, *dry]),
        ("Bedrock 주제 선정", ["python3", "scripts/minecraft/bedrock/select_bedrock_topic.py", *common, *(["--force-generate"] if args.force_generate else []), *dry]),
        ("Bedrock 글 생성", ["python3", "scripts/minecraft/bedrock/generate_bedrock_post.py", *common, *dry]),
        ("Bedrock 전용 검증", ["python3", "scripts/minecraft/bedrock/validate_bedrock_content.py", *common]),
        ("Bedrock tracker 갱신", ["python3", "scripts/minecraft/bedrock/update_bedrock_tracker.py", *common, *dry]),
    ]
    for name, command in steps:
        code = run_step(name, command)
        if code != 0:
            return code
    log("Bedrock 파이프라인 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
