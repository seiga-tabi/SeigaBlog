#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from normalize_java_release import (
    POSTS_DIR,
    REPO_ROOT,
    classified_items_path,
    normalized_items_path,
    read_json,
    repo_path,
    today_string,
    validation_report_path,
    write_json,
)


BEDROCK_WORDS = ["Bedrock", "베드락", "統合版", "Beta", "Preview"]
TEST_CHANNELS = {"java_snapshot", "java_pre_release", "java_release_candidate"}
REQUIRED_POST_FIELDS = [
    "slug",
    "category",
    "content_type",
    "edition",
    "release_channel",
    "minecraft_version",
    "accent",
    "read_time",
    "date",
    "last_modified_at",
    "source_url",
    "source_title",
    "source_published_at",
    "last_checked",
    "information_status",
    "sources",
    "author",
    "badge",
    "title",
    "excerpt",
    "post_tags",
    "lead",
    "body",
    "summary_image",
    "content_images",
    "sections",
    "update_history",
]


def top_section(frontmatter: str, key: str) -> str:
    lines = frontmatter.splitlines()
    selected: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped == f"{key}:":
            in_section = True
            selected.append(line)
            continue
        if in_section and indent == 0 and stripped and not stripped.startswith("-"):
            break
        if in_section:
            selected.append(line)
    return "\n".join(selected)


def extract_scalar(frontmatter: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip('"').strip("'")


def split_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


def local_asset_exists(src: str) -> bool:
    if not src.startswith("/assets/"):
        return False
    return (REPO_ROOT / src.lstrip("/")).exists()


def image_srcs(frontmatter: str) -> list[str]:
    return re.findall(r"['\"](/assets/images/[^'\"]+)['\"]", frontmatter)


def validate_data_item(item: dict, label: str) -> list[dict]:
    issues = []
    if item.get("product") != "minecraft":
        issues.append({"file": label, "type": "data", "message": "product가 minecraft가 아닙니다."})
    if item.get("edition") != "java":
        issues.append({"file": label, "type": "data", "message": "edition이 java가 아닙니다."})
    title = item.get("source", {}).get("title", "")
    source_url = item.get("source", {}).get("url", "")
    if not source_url:
        issues.append({"file": label, "type": "source", "message": "source.url이 없습니다."})
    if re.search(r"bedrock|beta & preview|marketplace|education|dungeons|legends", title + " " + source_url, re.IGNORECASE):
        issues.append({"file": label, "type": "bedrock", "message": "Java 데이터에 제외 대상 키워드가 있습니다."})
    if item.get("release_channel") in TEST_CHANNELS and "정식 업데이트" in json.dumps(item, ensure_ascii=False):
        issues.append({"file": label, "type": "status", "message": "테스트 버전을 정식 업데이트로 표현했습니다."})
    for key in ["server_compatibility", "mod_compatibility"]:
        if item.get(key) not in {None, ""}:
            issues.append({"file": label, "type": "unsupported_claim", "message": f"{key}를 원문 없이 확정하면 안 됩니다."})
    return issues


def validate_post(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    fm = split_frontmatter(text)
    if extract_scalar(fm, "content_type") != "minecraft_java_update":
        return []
    label = repo_path(path)
    issues = []
    for field in REQUIRED_POST_FIELDS:
        if not top_section(fm, field) and not extract_scalar(fm, field):
            issues.append({"file": label, "type": "frontmatter", "message": f"{field} 값이 없습니다."})
    if extract_scalar(fm, "category") != "minecraft":
        issues.append({"file": label, "type": "frontmatter", "message": "category는 minecraft여야 합니다."})
    if extract_scalar(fm, "edition") != "java":
        issues.append({"file": label, "type": "frontmatter", "message": "edition은 java여야 합니다."})
    if "edition: bedrock" in fm.lower():
        issues.append({"file": label, "type": "bedrock", "message": "edition: bedrock이 포함되어 있습니다."})
    source_url = extract_scalar(fm, "source_url")
    if not source_url.startswith("https://"):
        issues.append({"file": label, "type": "source", "message": "source_url은 https 공식 URL이어야 합니다."})
    if re.search(r"bedrock|beta-preview|beta & preview", source_url, re.IGNORECASE):
        issues.append({"file": label, "type": "bedrock", "message": "대표 출처가 Bedrock/Beta 계열입니다."})
    channel = extract_scalar(fm, "release_channel")
    title_scope = top_section(fm, "title")
    if channel in TEST_CHANNELS and ("정식 업데이트" in title_scope or "正式アップデート" in title_scope):
        issues.append({"file": label, "type": "status", "message": "테스트 버전 제목이 정식 업데이트처럼 보입니다."})
    for word in BEDROCK_WORDS:
        if word in fm and "Bedrock 변경은 제외" not in fm and "Bedrock変更は除外" not in fm:
            issues.append({"file": label, "type": "bedrock", "message": f"문맥 없는 제외 키워드가 있습니다: {word}"})
    for lang in ["ko", "ja"]:
        for field in ["title", "excerpt", "lead", "body"]:
            if f"{lang}:" not in top_section(fm, field):
                issues.append({"file": label, "type": "i18n", "message": f"{field}.{lang} 값이 없습니다."})
    for src in image_srcs(fm):
        if not local_asset_exists(src):
            issues.append({"file": label, "type": "image", "message": f"로컬 이미지가 없습니다: {src}"})
    if re.search(r"src:\s*['\"]?https?://", fm):
        issues.append({"file": label, "type": "image", "message": "외부 이미지 hotlink가 있습니다."})
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Java 데이터와 생성 글을 검증합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    issues = []
    for path in [normalized_items_path(date_value), classified_items_path(date_value)]:
        payload = read_json(path, {"items": []})
        for index, item in enumerate(payload.get("items", []), start=1):
            issues.extend(validate_data_item(item, f"{repo_path(path)}[{index}]"))
    seen_sources: set[str] = set()
    for path in POSTS_DIR.glob("*.md"):
        issues.extend(validate_post(path))
        fm = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if extract_scalar(fm, "content_type") == "minecraft_java_update":
            source_url = extract_scalar(fm, "source_url")
            if source_url in seen_sources:
                issues.append({"file": repo_path(path), "type": "duplicate", "message": f"중복 Java source_url입니다: {source_url}"})
            seen_sources.add(source_url)
    report = {"ok": not issues, "date": date_value, "issue_count": len(issues), "issues": issues}
    write_json(validation_report_path(date_value), report)
    if issues:
        for issue in issues:
            print(f"[Minecraft Java Validate] {issue['type']}: {issue['file']} - {issue['message']}")
        return 1
    print(f"[Minecraft Java Validate] 검증 통과: {repo_path(validation_report_path(date_value))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
