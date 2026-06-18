#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from bedrock_common import (
    JAVA_EXCLUSION_TERMS,
    POSTS_DIR,
    REPO_ROOT,
    canonical_url,
    extract_scalar,
    split_frontmatter,
    validation_report_path,
    today_string,
    write_json,
)


REQUIRED_KEYS = [
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
FORBIDDEN_PLATFORM_CLAIMS = [
    "모든 플랫폼에 즉시 적용",
    "모든 콘솔에서 같은 시간",
    "모바일에서는 문제가 없습니다",
    "Realms에도 자동 적용",
    "すべてのプラットフォーム",
    "全コンソールで同時",
]
ALLOWED_JAVA_CONTEXT = ["제외", "범위", "대상外", "除外", "対象外"]
OFFICIAL_SOURCE_DOMAINS = ("feedback.minecraft.net", "www.minecraft.net", "minecraft.net")


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Validate] {message}")


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
        if in_section and indent == 0 and stripped:
            break
        if in_section:
            selected.append(line)
    return "\n".join(selected)


def has_localized(frontmatter: str, section: str, lang: str) -> bool:
    block = top_section(frontmatter, section)
    if not block:
        return False
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^\s+{re.escape(lang)}:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip().strip("\"'")
        if value and value not in {"null", "[]", "{}"}:
            return True
        current_indent = len(line) - len(line.lstrip(" "))
        for next_line in lines[index + 1 :]:
            if not next_line.strip():
                continue
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_indent <= current_indent:
                break
            if re.match(r"^\s+[a-z]{2}:\s*", next_line):
                break
            if re.search(r"\S", next_line) and not next_line.strip().endswith(":"):
                return True
    return False


def image_paths(frontmatter: str) -> list[str]:
    paths = []
    for match in re.finditer(r"^\s*(?:image|og_image):\s*(.+)$", frontmatter, flags=re.MULTILINE):
        paths.append(match.group(1).strip().strip("\"'"))
    for match in re.finditer(r"^\s*src:\s*(.+)$", frontmatter, flags=re.MULTILINE):
        raw = match.group(1).strip().strip("\"'")
        if raw.startswith("{"):
            continue
        paths.append(raw)
    for match in re.finditer(r"['\"](/assets/images/[^'\"]+)['\"]", frontmatter):
        paths.append(match.group(1))
    return sorted(set(paths))


def validate_post(path: Path) -> list[dict[str, str]]:
    frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
    if extract_scalar(frontmatter, "content_type") != "minecraft_bedrock_update":
        return []
    label = str(path.relative_to(REPO_ROOT))
    issues: list[dict[str, str]] = []
    for key in REQUIRED_KEYS:
        if not extract_scalar(frontmatter, key) and not top_section(frontmatter, key):
            issues.append({"file": label, "type": "frontmatter", "message": f"{key} 값이 없습니다."})
    if extract_scalar(frontmatter, "edition") != "bedrock":
        issues.append({"file": label, "type": "edition", "message": "edition이 bedrock이 아닙니다."})
    if extract_scalar(frontmatter, "category") != "minecraft":
        issues.append({"file": label, "type": "category", "message": "category가 minecraft가 아닙니다."})
    source_url = extract_scalar(frontmatter, "source_url")
    if not source_url.startswith("https://"):
        issues.append({"file": label, "type": "source", "message": "source_url이 https 공식 URL이 아닙니다."})
    if source_url and not any(domain in source_url for domain in OFFICIAL_SOURCE_DOMAINS):
        issues.append({"file": label, "type": "source", "message": "source_url이 Minecraft/Mojang 공식 도메인이 아닙니다."})
    if any(term.lower() in source_url.lower() for term in ["java-edition", "snapshot", "pre-release", "release-candidate"]):
        issues.append({"file": label, "type": "source", "message": "Java 관련 source_url이 대표 출처입니다."})
    source_title = extract_scalar(frontmatter, "source_title")
    if any(term.lower() in source_title.lower() for term in ["java edition", "snapshot", "pre-release", "release candidate"]):
        issues.append({"file": label, "type": "source", "message": "Java 관련 source_title이 대표 출처입니다."})
    for section in ["title", "excerpt", "lead", "body", "post_tags"]:
        for lang in ["ko", "ja"]:
            if not has_localized(frontmatter, section, lang):
                issues.append({"file": label, "type": "i18n", "message": f"{section}.{lang} 값이 없습니다."})
    for src in image_paths(frontmatter):
        if src.startswith("http://") or src.startswith("https://"):
            issues.append({"file": label, "type": "image", "message": f"외부 이미지 hotlink가 있습니다: {src}"})
        elif src.startswith("/") and not (REPO_ROOT / src.lstrip("/")).exists():
            issues.append({"file": label, "type": "image", "message": f"이미지 파일이 없습니다: {src}"})
    text = frontmatter
    for term in JAVA_EXCLUSION_TERMS:
        if term not in text:
            continue
        for line in text.splitlines():
            if term in line and not any(allowed in line for allowed in ALLOWED_JAVA_CONTEXT):
                issues.append({"file": label, "type": "java_context", "message": f"Java 관련 표현 문맥 확인 필요: {line.strip()}"})
    for phrase in FORBIDDEN_PLATFORM_CLAIMS:
        if phrase in text:
            issues.append({"file": label, "type": "platform", "message": f"플랫폼 추측 표현이 있습니다: {phrase}"})
    channel = extract_scalar(frontmatter, "release_channel")
    title_block = top_section(frontmatter, "title")
    if channel == "bedrock_stable_release" and ("베타" in title_block or "Preview" in title_block or "プレビュー" in title_block):
        issues.append({"file": label, "type": "channel", "message": "Beta/Preview를 정식 업데이트처럼 표현했습니다."})
    return issues


def validate_duplicates(paths: list[Path]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    slugs: dict[str, list[str]] = {}
    urls: dict[str, list[str]] = {}
    for path in paths:
        frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if extract_scalar(frontmatter, "content_type") != "minecraft_bedrock_update":
            continue
        label = str(path.relative_to(REPO_ROOT))
        slug = extract_scalar(frontmatter, "slug")
        source_url = extract_scalar(frontmatter, "source_url")
        if slug:
            slugs.setdefault(slug, []).append(label)
        if source_url:
            urls.setdefault(canonical_url(source_url), []).append(label)
    for slug, labels in slugs.items():
        if len(labels) > 1:
            issues.append({"file": ", ".join(labels), "type": "duplicate", "message": f"중복 Bedrock slug입니다: {slug}"})
    for source_url, labels in urls.items():
        if len(labels) > 1:
            issues.append({"file": ", ".join(labels), "type": "duplicate", "message": f"중복 Bedrock source_url입니다: {source_url}"})
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Bedrock 전용 글 검증을 수행합니다.")
    parser.add_argument("--date", help="리포트 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--skip-build", action="store_true", help="Jekyll build 검증을 건너뜁니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    issues: list[dict[str, str]] = []
    post_paths = sorted(POSTS_DIR.glob("*.md"))
    issues.extend(validate_duplicates(post_paths))
    for path in post_paths:
        issues.extend(validate_post(path))
    build_ok = True
    build_output = ""
    if not args.skip_build:
        result = subprocess.run(["jekyll", "build"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        build_ok = result.returncode == 0
        build_output = (result.stdout + result.stderr).strip()[-4000:]
        if not build_ok:
            issues.append({"file": "_site", "type": "build", "message": "Jekyll build 실패"})
    report = {"ok": not issues and build_ok, "issues": issues, "build_ok": build_ok, "build_output": build_output}
    write_json(validation_report_path(date_value), report)
    if issues:
        for issue in issues:
            log(f"{issue['file']}: {issue['message']}")
        return 1
    log("Bedrock 검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
