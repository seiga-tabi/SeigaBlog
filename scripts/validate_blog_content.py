#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter

from lol_content_utils import (
    CHAMPION_NAME_MAP_PATH,
    REPO_ROOT,
    SAMPLE_PATTERNS,
    TODO_PATTERNS,
    champion_entries,
    extract_localized_list,
    extract_localized_scalar,
    extract_scalar,
    image_srcs_from_frontmatter,
    load_champion_map,
    local_asset_exists,
    localized_line_language,
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
        if in_section and indent == 0 and stripped and not stripped.startswith("-"):
            break
        if in_section:
            selected.append(line)
    return "\n".join(selected)


def top_list_count(frontmatter: str, key: str) -> int:
    section = top_section(frontmatter, key)
    return len(re.findall(r"^(?:-\s|\s{2}-\s)", section, flags=re.MULTILINE))


def top_list_items(frontmatter: str, key: str) -> list[str]:
    section = top_section(frontmatter, key)
    items: list[str] = []
    current: list[str] = []
    base_indent: int | None = None
    for line in section.splitlines()[1:]:
        match = re.match(r"^(?P<indent>\s*)-\s*", line)
        if match and len(match.group("indent")) in {0, 2} and (base_indent is None or len(match.group("indent")) == base_indent):
            base_indent = len(match.group("indent"))
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
    return bool(re.search(rf"^\s*(?:-\s*)?{re.escape(field)}:", block, flags=re.MULTILINE))


def field_value(block: str, field: str) -> str:
    match = re.search(rf"^\s*(?:-\s*)?{re.escape(field)}:\s*(.+)$", block, flags=re.MULTILINE)
    return unquote(match.group(1).strip()) if match else ""


def nested_localized_exists(block: str, field: str, lang: str) -> bool:
    lines = block.splitlines()
    in_field = False
    field_indent = 0
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if re.match(rf"\s*(?:-\s*)?{re.escape(field)}:\s*$", line):
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


def validate_champion_identity(file_label: str, item: str, card_label: str, name_map: dict) -> list[dict]:
    issues: list[dict] = []
    official = name_map.get("champions", {})
    champion_key = field_value(item, "key")
    if not champion_key:
        issues.append({"file": file_label, "type": "champion_card", "message": f"{card_label}에 key 값이 없습니다."})
        return issues

    official_entry = official.get(champion_key)
    if not official_entry:
        issues.append({"file": file_label, "type": "champion_locale", "message": f"{card_label}의 key를 Data Dragon에서 찾지 못했습니다: {champion_key}"})
        return issues

    ko = field_value(item, "ko")
    ja = field_value(item, "ja")
    if ko != official_entry.get("ko"):
        issues.append({"file": file_label, "type": "champion_locale", "message": f"{card_label} 한국어명이 Data Dragon과 다릅니다: {ko} != {official_entry.get('ko')}"})
    if ja != official_entry.get("ja"):
        issues.append({"file": file_label, "type": "champion_locale", "message": f"{card_label} 일본어명이 Data Dragon과 다릅니다: {ja} != {official_entry.get('ja')}"})
    return issues


def validate_mini_cards(
    file_label: str,
    frontmatter: str,
    key: str,
    name_map: dict,
    required_fields: list[str],
) -> list[dict]:
    issues: list[dict] = []
    for index, item in enumerate(top_list_items(frontmatter, key), start=1):
        card_label = f"{key}[{index}]"
        for field in ["key", "ko", "ja", "status_label", "role", "target_anchor", *required_fields]:
            if not field_exists(item, field):
                issues.append({"file": file_label, "type": "mini_card", "message": f"{card_label}에 {field} 값이 없습니다."})
        issues.extend(validate_champion_identity(file_label, item, card_label, name_map))
    return issues


def validate_language_blocks(file_label: str, frontmatter: str) -> list[dict]:
    issues: list[dict] = []
    current: tuple[str | None, int] = (None, 0)
    for index, line in enumerate(frontmatter.splitlines(), start=1):
        current = localized_line_language(line, current)
        if current[0] == "ja" and re.search(r"[가-힣]", line):
            issues.append(
                {
                    "file": file_label,
                    "type": "i18n",
                    "message": f"일본어 영역에 한글이 섞여 있습니다: {index}행",
                }
            )
    return issues


def extract_rendered_post_path(frontmatter: str) -> str:
    slug = extract_scalar(frontmatter, "slug")
    return f"_site/posts/{slug}/index.html" if slug else ""


def validate_built_post_html(file_label: str, frontmatter: str) -> list[dict]:
    issues: list[dict] = []
    rendered_path = extract_rendered_post_path(frontmatter)
    if not rendered_path:
        return issues

    path = REPO_ROOT / rendered_path
    if not path.exists():
        issues.append({"file": rendered_path, "type": "build", "message": "상세 글 빌드 결과가 없습니다."})
        return issues

    html = path.read_text(encoding="utf-8")
    slug = extract_scalar(frontmatter, "slug")
    expected_canonical = f"https://seiga-tabi.github.io/SeigaBlog/posts/{slug}/"

    if f'<link rel="canonical" href="{expected_canonical}"' not in html:
        issues.append({"file": rendered_path, "type": "seo", "message": "상세 글 canonical URL이 없거나 올바르지 않습니다."})
    if 'type="application/ld+json"' not in html or '"@type": "Article"' not in html:
        issues.append({"file": rendered_path, "type": "seo", "message": "Article JSON-LD가 없습니다."})
    if '"@type": "FAQPage"' not in html:
        issues.append({"file": rendered_path, "type": "seo", "message": "FAQ JSON-LD가 없습니다."})
    if '<nav class="post-toc article-toc"' not in html and '<nav class="article-toc post-toc"' not in html:
        issues.append({"file": rendered_path, "type": "toc", "message": "post-toc nav가 없습니다."})

    toc_links = re.findall(r"<a href=\"#([^\"]+)\"[^>]*>", html)
    toc_scope = re.search(r"<nav class=\"(?:post-toc article-toc|article-toc post-toc)\"[\s\S]*?</nav>", html)
    scoped_toc_links = re.findall(r"<a href=\"#([^\"]+)\"[^>]*>", toc_scope.group(0)) if toc_scope else []
    if len(scoped_toc_links) < 8:
        issues.append({"file": rendered_path, "type": "toc", "message": f"목차 링크가 8개 미만입니다: {len(scoped_toc_links)}개"})
    ids = set(re.findall(r"\sid=\"([^\"]+)\"", html))
    missing_toc_targets = sorted({item for item in scoped_toc_links if item not in ids})
    if missing_toc_targets:
        issues.append({"file": rendered_path, "type": "toc", "message": f"목차 href와 실제 id가 맞지 않습니다: {missing_toc_targets}"})

    if html.count("overview-label") < 6 or html.count("overview-value") < 6:
        issues.append({"file": rendered_path, "type": "overview", "message": "overview label/value 렌더링이 부족합니다."})
    if not re.search(r"<dl class=\"overview-grid\"", html):
        issues.append({"file": rendered_path, "type": "overview", "message": "한눈에 보는 패치가 dl 구조로 렌더링되지 않았습니다."})

    hero_match = re.search(r"<div class=\"detail-hero\">\s*<img(?P<attrs>[^>]+)>", html)
    if hero_match:
        attrs = hero_match.group("attrs")
        for required in ['loading="eager"', 'fetchpriority="high"', 'decoding="async"', "width=", "height="]:
            if required not in attrs:
                issues.append({"file": rendered_path, "type": "image", "message": f"hero 이미지에 {required} 속성이 없습니다."})
    else:
        issues.append({"file": rendered_path, "type": "image", "message": "hero 이미지를 찾지 못했습니다."})

    for image_attrs in re.findall(r"<figure class=\"article-figure[^\"]*content-image[^\"]*\">\s*<img([^>]+)>", html):
        for required in ["width=", "height=", 'decoding="async"']:
            if required not in image_attrs:
                issues.append({"file": rendered_path, "type": "image", "message": f"본문 이미지에 {required} 속성이 없습니다."})

    full_keys = re.findall(r"data-card-variant=\"full\"[^>]*data-champion-key=\"([^\"]+)\"", html)
    duplicate_full_cards = sorted(key for key, count in Counter(full_keys).items() if count > 1)
    if duplicate_full_cards:
        issues.append({"file": rendered_path, "type": "champion_card", "message": f"동일 챔피언 풀 카드가 중복 렌더링되었습니다: {duplicate_full_cards}"})

    recommended_scope = re.search(r"<section class=\"content-section\" id=\"recommended-picks\">[\s\S]*?</section>", html)
    watch_scope = re.search(r"<section class=\"content-section\" id=\"watch-picks\">[\s\S]*?</section>", html)
    for section_name, scope in [("recommended-picks", recommended_scope), ("watch-picks", watch_scope)]:
        if scope and 'data-card-variant="full"' in scope.group(0):
            issues.append({"file": rendered_path, "type": "champion_card", "message": f"{section_name} 섹션에 풀 카드 variant가 렌더링되었습니다."})

    image_srcs = [
        src
        for src in re.findall(r"<img[^>]+src=\"([^\"]+)\"", html)
        if not src.startswith("data:")
    ]
    repeated_images = sorted(src for src, count in Counter(image_srcs).items() if count >= 3)
    if repeated_images:
        issues.append({"file": rendered_path, "type": "image", "message": f"같은 이미지 src가 3회 이상 반복됩니다: {repeated_images}"})

    return issues


def validate_built_index_html(post_count: int) -> list[dict]:
    issues: list[dict] = []
    path = REPO_ROOT / "_site" / "index.html"
    if not path.exists():
        issues.append({"file": "_site/index.html", "type": "build", "message": "홈 빌드 결과가 없습니다."})
        return issues

    html = path.read_text(encoding="utf-8")
    if post_count > 0 and "아직 게시된 글이 없습니다" in html:
        issues.append({"file": "_site/index.html", "type": "seo", "message": "글이 있는데 빈 상태 문구가 빌드 결과에 노출됩니다."})
    if re.search(r"href=\"#lol-patch-[^\"]+\"", html):
        issues.append({"file": "_site/index.html", "type": "seo", "message": "글 카드 permalink가 해시 URL만 사용합니다."})
    if "detail-stack" in html and ('aria-hidden="true"' not in html or "inert" not in html):
        issues.append({"file": "_site/index.html", "type": "a11y", "message": "홈 상세 패널 묶음에 aria-hidden/inert가 없습니다."})
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

    issues.extend(validate_language_blocks(file_label, frontmatter))

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

    for key in [
        "toc",
        "overview_table",
        "sections",
        "buff_champion_cards",
        "nerf_champion_cards",
        "recommended_pick_cards",
        "conditional_recommended_cards",
        "watch_pick_cards",
        "faq",
    ]:
        if not top_section(frontmatter, key):
            issues.append({"file": file_label, "type": "structure", "message": f"{key} 섹션이 없습니다."})

    required_section_ids = {
        "quick-summary",
        "buff-champions",
        "nerf-champions",
        "solo-queue-tier-impact",
        "recommended-picks",
        "conditional-picks",
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
    overview_count = top_list_count(frontmatter, "overview_table")
    if overview_count < 6:
        issues.append({"file": file_label, "type": "overview", "message": f"overview_table 항목이 6개 미만입니다: {overview_count}개"})

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
    recommended_count = top_list_count(frontmatter, "recommended_pick_cards")
    conditional_count = top_list_count(frontmatter, "conditional_recommended_cards")
    if recommended_count < 1:
        issues.append({"file": file_label, "type": "champion_card", "message": "추천 픽 카드가 없습니다."})
    if lol_patch and recommended_count != 5:
        issues.append({"file": file_label, "type": "champion_card", "message": f"추천 픽 TOP 5 카드는 정확히 5개여야 합니다: {recommended_count}개"})
    if lol_patch and "추천 픽 TOP 5" in top_section(frontmatter, "sections") and recommended_count != 5:
        issues.append({"file": file_label, "type": "champion_card", "message": "제목에 TOP 5가 있지만 main 추천 카드 수가 5개가 아닙니다."})
    if lol_patch and conditional_count < 1:
        issues.append({"file": file_label, "type": "champion_card", "message": "조건부 추천 픽 카드가 없습니다."})
    if lol_patch and "실시간 승률 데이터가 아님" not in top_section(frontmatter, "sections"):
        issues.append({"file": file_label, "type": "source", "message": "추천 픽 섹션에 실시간 승률 데이터가 아니라는 고지가 없습니다."})
    if lol_patch:
        for card_key in ["buff_champion_cards", "nerf_champion_cards"]:
            issues.extend(validate_champion_cards(file_label, frontmatter, card_key, name_map))
        issues.extend(
            validate_mini_cards(
                file_label,
                frontmatter,
                "recommended_pick_cards",
                name_map,
                ["grade", "reason", "fit_user", "key_change"],
            )
        )
        issues.extend(
            validate_mini_cards(
                file_label,
                frontmatter,
                "conditional_recommended_cards",
                name_map,
                ["condition", "reason", "key_change", "caution"],
            )
        )
        issues.extend(
            validate_mini_cards(
                file_label,
                frontmatter,
                "watch_pick_cards",
                name_map,
                ["first_day_rating", "key_nerf", "usable_condition", "risk"],
            )
        )
        if "Riot Data Dragon" not in frontmatter:
            issues.append({"file": file_label, "type": "source", "message": "Riot Data Dragon 출처 고지가 없습니다."})
        if "실시간 승률 데이터가 아님" not in frontmatter:
            issues.append({"file": file_label, "type": "source", "message": "실시간 승률 데이터가 아니라는 출처 고지가 없습니다."})
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
        else:
            paths = post_paths()
            issues.extend(validate_built_index_html(len(paths)))
            for path in paths:
                frontmatter, _, _ = split_frontmatter(path.read_text(encoding="utf-8"))
                if is_lol_patch_post(frontmatter):
                    issues.extend(validate_built_post_html(repo_path(path), frontmatter))

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
