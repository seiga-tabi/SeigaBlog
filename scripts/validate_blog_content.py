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
    unquote,
    write_report,
)


def log(message: str) -> None:
    print(f"[Blog Validate] {message}")


def line_has_pattern(text: str, patterns: list[str]) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern.lower() in lowered]


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


def top_list_count(frontmatter: str, key: str) -> int:
    section = top_section(frontmatter, key)
    return len(re.findall(r"^\s{2}-", section, flags=re.MULTILINE))


def top_list_items(frontmatter: str, key: str) -> list[str]:
    section = top_section(frontmatter, key)
    items: list[str] = []
    current: list[str] = []
    for line in section.splitlines()[1:]:
        if re.match(r"^\s{2}-\s*", line):
            if current:
                items.append("\n".join(current))
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        items.append("\n".join(current))
    return items


def field_exists(block: str, field: str) -> bool:
    return bool(re.search(rf"^\s+{re.escape(field)}:", block, flags=re.MULTILINE))


def field_value(block: str, field: str) -> str:
    match = re.search(rf"^\s+{re.escape(field)}:\s*(.+)$", block, flags=re.MULTILINE)
    return unquote(match.group(1).strip()) if match else ""


def nested_localized_exists(block: str, field: str, lang: str) -> bool:
    lines = block.splitlines()
    in_field = False
    field_indent = 0
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if re.match(rf"\s*{re.escape(field)}:\s*$", line):
            in_field = True
            field_indent = indent
            continue
        if in_field and indent <= field_indent and stripped:
            break
        if in_field and re.match(rf"\s*{lang}:\s*", line):
            return True
    return False


def section_ids(frontmatter: str) -> set[str]:
    section = top_section(frontmatter, "sections")
    return set(re.findall(r"^\s*(?:-\s*)?id:\s*['\"]?([^'\"\n]+)['\"]?", section, flags=re.MULTILINE))


def status_count(frontmatter: str, status: str) -> int:
    section = top_section(frontmatter, "lol_champions")
    return len(re.findall(rf"^\s*status:\s*['\"]?{re.escape(status)}['\"]?\s*$", section, flags=re.MULTILINE))


def has_body_name_list(frontmatter: str) -> bool:
    body = "\n".join(
        extract_localized_list(frontmatter, "body", "ko")
        + extract_localized_list(frontmatter, "body", "ja")
    )
    patterns = [
        r"챔피언\s*(버프|너프)\s*[:：][^\n]*[,、，]",
        r"추천/주의할\s*챔피언\s*[:：][^\n]*[,、，]",
        r"チャンピオン(強化|弱体化)\s*[:：][^\n]*[、,，]",
        r"おすすめ/注意チャンピオン\s*[:：][^\n]*[、,，]",
    ]
    return any(re.search(pattern, body) for pattern in patterns)


def is_lol_patch_post(frontmatter: str) -> bool:
    return bool(extract_scalar(frontmatter, "patch_version") or "lol_champions:" in frontmatter)


def validate_image_block(file_label: str, block: str, label: str) -> list[dict]:
    issues: list[dict] = []
    for field in ["src", "width", "height", "alt", "caption"]:
        if not field_exists(block, field):
            issues.append({"file": file_label, "type": "image", "message": f"{label}에 {field} 값이 없습니다."})
    for field in ["alt", "caption"]:
        for lang in ["ko", "ja"]:
            if not nested_localized_exists(block, field, lang):
                issues.append({"file": file_label, "type": "image", "message": f"{label}에 {field}.{lang} 값이 없습니다."})
    if field_exists(block, "src"):
        srcs = re.findall(r"['\"](/assets/images/[^'\"]+)['\"]", block)
        for src in srcs:
            if not local_asset_exists(src):
                issues.append({"file": file_label, "type": "image", "message": f"{label} 이미지 경로가 없습니다: {src}"})
    return issues


def validate_champion_cards(file_label: str, frontmatter: str, key: str, name_map: dict) -> list[dict]:
    issues: list[dict] = []
    official = name_map.get("champions", {})
    required_fields = [
        "key",
        "ko",
        "ja",
        "image",
        "alt",
        "status_label",
        "role",
        "change_summary",
        "solo_queue_impact",
        "play_tip",
        "caution",
        "priority",
        "difficulty",
        "tags",
    ]
    vague_patterns = [
        "주목받을 수 있습니다",
        "가치가 커질 수 있습니다",
        "좋습니다",
        "확인하세요",
    ]

    for index, item in enumerate(top_list_items(frontmatter, key), start=1):
        card_label = f"{key}[{index}]"
        for field in required_fields:
            if not field_exists(item, field):
                issues.append({"file": file_label, "type": "champion_card", "message": f"{card_label}에 {field} 값이 없습니다."})

        image = field_value(item, "image")
        if image and not local_asset_exists(image):
            issues.append({"file": file_label, "type": "champion_card", "message": f"{card_label} 이미지 경로가 없습니다: {image}"})

        champion_key = field_value(item, "key")
        official_entry = official.get(champion_key)
        if official_entry:
            ko = field_value(item, "ko")
            ja = field_value(item, "ja")
            if ko != official_entry.get("ko"):
                issues.append({"file": file_label, "type": "champion_locale", "message": f"{card_label} 한국어명이 Data Dragon과 다릅니다: {ko} != {official_entry.get('ko')}"})
            if ja != official_entry.get("ja"):
                issues.append({"file": file_label, "type": "champion_locale", "message": f"{card_label} 일본어명이 Data Dragon과 다릅니다: {ja} != {official_entry.get('ja')}"})
        elif champion_key:
            issues.append({"file": file_label, "type": "champion_locale", "message": f"{card_label}의 key를 Data Dragon에서 찾지 못했습니다: {champion_key}"})

        if "⇒" not in top_section(item, "change_summary") and "⇒" not in item:
            issues.append({"file": file_label, "type": "champion_card", "message": f"{card_label} change_summary에 공식 변경 수치가 없습니다."})
        if any(pattern in item for pattern in vague_patterns) and "⇒" not in item:
            issues.append({"file": file_label, "type": "champion_card", "message": f"{card_label}가 모호한 표현만 포함합니다."})
    return issues


def sentence_count(value: str) -> int:
    return len([item for item in re.split(r"[.!?。]+", value) if item.strip()])


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

    lol_patch = is_lol_patch_post(frontmatter)
    if lol_patch:
        for key in ["source_url", "source_title", "source_published_at", "last_checked"]:
            if not extract_scalar(frontmatter, key):
                issues.append({"file": file_label, "type": "source", "message": f"LoL 패치 글에 {key} 값이 없습니다."})

    if "summary_image:" not in frontmatter:
        issues.append({"file": file_label, "type": "image", "message": "대표 패치 인포그래픽 summary_image가 없습니다."})
    else:
        issues.extend(validate_image_block(file_label, top_section(frontmatter, "summary_image"), "summary_image"))

    content_image_count = top_list_count(frontmatter, "content_images")
    if content_image_count < 5:
        issues.append(
            {
                "file": file_label,
                "type": "image",
                "message": f"중간 이미지가 5개 미만입니다: {content_image_count}개",
            }
        )
    for index, image_block in enumerate(top_list_items(frontmatter, "content_images"), start=1):
        issues.extend(validate_image_block(file_label, image_block, f"content_images[{index}]"))

    if "summary_image:" in frontmatter and not re.search(r"summary_image:[\s\S]*?alt:[\s\S]*?ko:[\s\S]*?ja:", frontmatter):
        issues.append({"file": file_label, "type": "alt", "message": "summary_image alt.ko/alt.ja가 없습니다."})

    for key in ["toc", "overview_table", "sections", "buff_champion_cards", "nerf_champion_cards", "recommended_pick_cards", "faq"]:
        if not top_section(frontmatter, key):
            issues.append({"file": file_label, "type": "structure", "message": f"{key} 섹션이 없습니다."})

    required_section_ids = {
        "quick-summary",
        "buff-champions",
        "nerf-champions",
        "solo-queue-tier-impact",
        "recommended-picks",
        "watch-picks",
        "item-rune-system",
        "patch-day-checklist",
        "faq",
        "source-note",
    }
    missing_section_ids = sorted(required_section_ids - section_ids(frontmatter))
    if missing_section_ids:
        issues.append(
            {
                "file": file_label,
                "type": "structure",
                "message": f"필수 섹션 id가 없습니다: {missing_section_ids}",
            }
        )

    buff_count = status_count(frontmatter, "버프")
    nerf_count = status_count(frontmatter, "너프")
    buff_card_count = top_list_count(frontmatter, "buff_champion_cards")
    nerf_card_count = top_list_count(frontmatter, "nerf_champion_cards")
    if buff_count and buff_card_count < buff_count:
        issues.append(
            {
                "file": file_label,
                "type": "champion_card",
                "message": f"버프 챔피언 카드가 부족합니다: {buff_card_count}/{buff_count}",
            }
        )
    if nerf_count and nerf_card_count < nerf_count:
        issues.append(
            {
                "file": file_label,
                "type": "champion_card",
                "message": f"너프 챔피언 카드가 부족합니다: {nerf_card_count}/{nerf_count}",
            }
        )
    if top_list_count(frontmatter, "recommended_pick_cards") < 1:
        issues.append({"file": file_label, "type": "champion_card", "message": "추천 픽 카드가 없습니다."})
    if lol_patch and top_list_count(frontmatter, "recommended_pick_cards") < 5:
        issues.append({"file": file_label, "type": "champion_card", "message": "추천 픽 카드는 5개 이상이어야 합니다."})
    if lol_patch:
        for card_key in ["buff_champion_cards", "nerf_champion_cards", "recommended_pick_cards", "watch_pick_cards"]:
            issues.extend(validate_champion_cards(file_label, frontmatter, card_key, name_map))
    faq_count = top_list_count(frontmatter, "faq")
    if faq_count < 5:
        issues.append({"file": file_label, "type": "faq", "message": f"FAQ는 최소 5개여야 합니다: {faq_count}개"})
    for index, faq_item in enumerate(top_list_items(frontmatter, "faq"), start=1):
        for field in ["question", "answer"]:
            for lang in ["ko", "ja"]:
                if not nested_localized_exists(faq_item, field, lang):
                    issues.append({"file": file_label, "type": "faq", "message": f"faq[{index}]에 {field}.{lang} 값이 없습니다."})
        answer_ko = re.search(r"answer:\s*\n(?:.*\n)*?\s+ko:\s*(.+)", faq_item)
        if answer_ko and sentence_count(unquote(answer_ko.group(1).strip())) > 3:
            issues.append({"file": file_label, "type": "faq", "message": f"faq[{index}] 한국어 답변이 3문장을 초과합니다."})
    faq_text = top_section(frontmatter, "faq")
    if lol_patch:
        for keyword in ["공식", "랭크", "추천", "너프"]:
            if keyword not in faq_text:
                issues.append({"file": file_label, "type": "faq", "message": f"FAQ에 '{keyword}' 관련 항목이 없습니다."})
    if has_body_name_list(frontmatter):
        issues.append({"file": file_label, "type": "champion_list", "message": "본문에 챔피언 이름 나열형 문장이 있습니다."})

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

    if lol_patch:
        title_ko = extract_localized_scalar(frontmatter, "title", "ko")
        description = extract_scalar(frontmatter, "description")
        if "26.12" in extract_scalar(frontmatter, "patch_version") and ("26.12" not in title_ko or "패치" not in title_ko):
            issues.append({"file": file_label, "type": "seo", "message": "title.ko에 26.12와 패치가 포함되어야 합니다."})
        for keyword in ["버프", "너프", "솔랭"]:
            if keyword not in description:
                issues.append({"file": file_label, "type": "seo", "message": f"description에 '{keyword}' 키워드가 없습니다."})
        if len(description) < 60 or len(description) > 180:
            issues.append({"file": file_label, "type": "seo", "message": f"description 길이를 확인하세요: {len(description)}자"})
        post_tags_ko = "\n".join(extract_localized_list(frontmatter, "post_tags", "ko"))
        post_tags_ja = "\n".join(extract_localized_list(frontmatter, "post_tags", "ja"))
        for keyword in ["롤", "패치노트", "솔랭", "메타"]:
            if keyword not in post_tags_ko:
                issues.append({"file": file_label, "type": "seo", "message": f"post_tags.ko에 '{keyword}'가 없습니다."})
        for keyword in ["LoL", "パッチノート", "ソロランク", "メタ"]:
            if keyword not in post_tags_ja:
                issues.append({"file": file_label, "type": "seo", "message": f"post_tags.ja에 '{keyword}'가 없습니다."})

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
