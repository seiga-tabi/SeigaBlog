#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess

from lol_content_utils import (
    CHAMPION_NAME_MAP_PATH,
    SAMPLE_PATTERNS,
    TODO_PATTERNS,
    champion_entries,
    extract_localized_list,
    extract_localized_scalar,
    extract_scalar,
    image_srcs_from_frontmatter,
    load_champion_map,
    local_asset_exists,
    localized_name,
    post_paths,
    repo_path,
    split_frontmatter,
    write_report,
)


def log(message: str) -> None:
    print(f"[Blog Validate] {message}")


def line_has_pattern(text: str, patterns: list[str]) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lowered]


def validate_post(path, name_map: dict) -> list[dict]:
    issues: list[dict] = []
    text = path.read_text(encoding="utf-8")
    frontmatter, _, _ = split_frontmatter(text)
    file_label = repo_path(path)

    if not frontmatter:
        issues.append({"file": file_label, "type": "frontmatter", "message": "frontmatter가 없습니다."})
        return issues

    sample_hits = line_has_pattern(path.name + "\n" + frontmatter, SAMPLE_PATTERNS)
    if sample_hits:
        issues.append({"file": file_label, "type": "sample", "message": f"샘플 패턴 감지: {sample_hits}"})

    todo_hits = line_has_pattern(frontmatter, TODO_PATTERNS)
    if todo_hits:
        issues.append({"file": file_label, "type": "todo", "message": f"미완성 문구 감지: {todo_hits}"})

    for key in ["slug", "image", "description", "date"]:
        if not extract_scalar(frontmatter, key):
            issues.append({"file": file_label, "type": "frontmatter", "message": f"{key} 값이 없습니다."})

    for section in ["title", "excerpt", "lead", "body", "quote"]:
        for lang in ["ko", "ja"]:
            value = (
                "\n".join(extract_localized_list(frontmatter, section, lang))
                if section == "body"
                else extract_localized_scalar(frontmatter, section, lang)
            )
            if not value:
                issues.append(
                    {
                        "file": file_label,
                        "type": "i18n",
                        "message": f"{section}.{lang} 값이 없습니다.",
                    }
                )

    for src in image_srcs_from_frontmatter(frontmatter):
        if not local_asset_exists(src):
            issues.append({"file": file_label, "type": "image", "message": f"이미지 경로가 없습니다: {src}"})

    if "summary_image:" in frontmatter and not re.search(r"summary_image:[\s\S]*?alt:[\s\S]*?ko:[\s\S]*?ja:", frontmatter):
        issues.append({"file": file_label, "type": "alt", "message": "summary_image alt.ko/alt.ja가 없습니다."})

    ko_text = "\n".join(
        [
            extract_localized_scalar(frontmatter, "title", "ko"),
            extract_localized_scalar(frontmatter, "excerpt", "ko"),
            extract_localized_scalar(frontmatter, "lead", "ko"),
            "\n".join(extract_localized_list(frontmatter, "body", "ko")),
        ]
    )
    ja_text = "\n".join(
        [
            extract_localized_scalar(frontmatter, "title", "ja"),
            extract_localized_scalar(frontmatter, "excerpt", "ja"),
            extract_localized_scalar(frontmatter, "lead", "ja"),
            "\n".join(extract_localized_list(frontmatter, "body", "ja")),
        ]
    )

    for entry in champion_entries(name_map):
        ko = localized_name(entry, "ko")
        ja = localized_name(entry, "ja")
        key = entry["key"]
        if ko and ko in ja_text:
            issues.append({"file": file_label, "type": "champion_locale", "message": f"일본어 영역에 한국어 챔피언명 노출: {ko}"})
        if ja and ja in ko_text:
            issues.append({"file": file_label, "type": "champion_locale", "message": f"한국어 영역에 일본어 챔피언명 노출: {ja}"})
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", ko_text + ja_text):
            issues.append({"file": file_label, "type": "champion_key", "message": f"사용자 노출 문구에 champion key가 있습니다: {key}"})

    return issues


def run_build() -> tuple[bool, str]:
    result = subprocess.run(["jekyll", "build"], text=True, capture_output=True, check=False)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="블로그 콘텐츠, 이미지 경로, 챔피언명 locale을 검증합니다.")
    parser.add_argument("--skip-build", action="store_true", help="Jekyll build 검증을 건너뜁니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    name_map = load_champion_map()
    issues: list[dict] = []

    if not CHAMPION_NAME_MAP_PATH.exists():
        issues.append({"file": repo_path(CHAMPION_NAME_MAP_PATH), "type": "data", "message": "챔피언명 맵이 없습니다."})

    for path in post_paths():
        issues.extend(validate_post(path, name_map))

    build_ok = True
    build_output = ""
    if not args.skip_build:
        build_ok, build_output = run_build()
        if not build_ok:
            issues.append({"file": "_site", "type": "build", "message": build_output})

    report = {
        "ok": not issues,
        "post_count": len(post_paths()),
        "issue_count": len(issues),
        "issues": issues,
        "build": {"ok": build_ok, "output": build_output[-2000:]},
    }
    report_path = write_report("blog-validation-report.json", report)
    log(f"검증 리포트 저장: {repo_path(report_path)}")
    if issues:
        for issue in issues:
            log(f"{issue['type']}: {issue['file']} - {issue['message']}")
        return 1
    log("검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
