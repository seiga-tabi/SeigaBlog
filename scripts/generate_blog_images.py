#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import re

from lol_content_utils import (
    BLOG_IMAGE_DIR,
    CHAMPION_IMAGE_DIR,
    detect_champions,
    extract_localized_list,
    extract_localized_scalar,
    extract_scalar,
    load_champion_map,
    localized_name,
    post_paths,
    repo_path,
    split_frontmatter,
    svg_escape,
    wrap_text,
    write_report,
)


SITE_NAME = "Seiga Blog"
LANGS = ("ko", "ja")


def log(message: str) -> None:
    print(f"[Blog Images] {message}")


def classification_from_text(text: str, ko_name: str) -> str:
    if re.search(rf"버프[^.\n]*{re.escape(ko_name)}|{re.escape(ko_name)}[^.\n]*버프", text):
        return "버프"
    if re.search(rf"너프[^.\n]*{re.escape(ko_name)}|{re.escape(ko_name)}[^.\n]*너프", text):
        return "너프"
    return "핵심"


def status_color(status: str) -> str:
    if status == "버프":
        return "#16A34A"
    if status == "너프":
        return "#EA580C"
    if status == "추천":
        return "#2563EB"
    return "#64748B"


def localized_status(status: str, lang: str) -> str:
    labels = {
        "버프": {"ko": "버프", "ja": "強化"},
        "너프": {"ko": "너프", "ja": "弱体化"},
        "추천": {"ko": "추천", "ja": "おすすめ"},
        "핵심": {"ko": "핵심", "ja": "要点"},
    }
    return labels.get(status, labels["핵심"]).get(lang, status)


def image_href(key: str, image_type: str = "square") -> str:
    filename = "splash.jpg" if image_type == "splash" else "square.png"
    path = CHAMPION_IMAGE_DIR / key / filename
    if path.exists():
        mime = "image/jpeg" if filename.endswith(".jpg") else "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    return f"../../lol/champions/{key}/{filename}"


def entry_status(entry: dict, source_text: str = "") -> str:
    status = entry.get("status", "")
    if status:
        return status
    if source_text:
        return classification_from_text(source_text, localized_name(entry, "ko"))
    return "핵심"


def text_lines(value: str, x: int, y: int, size: int, width: int, fill: str, weight: int = 700) -> str:
    parts = []
    for index, line in enumerate(wrap_text(value, width)):
        parts.append(
            f'<text x="{x}" y="{y + index * int(size * 1.45)}" '
            f'font-size="{size}" font-weight="{weight}" fill="{fill}">{svg_escape(line)}</text>'
        )
    return "\n".join(parts)


def render_summary_svg(title: str, patch_version: str, champions: list[dict], bullets: list[str], lang: str) -> str:
    buff_count = sum(1 for entry in champions if entry_status(entry) == "버프")
    nerf_count = sum(1 for entry in champions if entry_status(entry) == "너프")
    count_label = (
        f"버프 {buff_count} / 너프 {nerf_count}"
        if lang == "ko"
        else f"強化 {buff_count} / 弱体化 {nerf_count}"
    )
    cards = []
    for index, entry in enumerate(champions[:6]):
        x = 78 + (index % 3) * 342
        y = 292 + (index // 3) * 106
        status = entry_status(entry)
        color = status_color(status)
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="304" height="76" rx="8" fill="#111827" stroke="#334155"/>
              <text x="{x + 20}" y="{y + 35}" font-size="25" font-weight="900" fill="#F8FAFC">{svg_escape(localized_name(entry, lang))}</text>
              <text x="{x + 238}" y="{y + 35}" font-size="17" font-weight="900" fill="{color}">{svg_escape(localized_status(status, lang))}</text>
            </g>'''
        )

    bullet_nodes = []
    for index, bullet in enumerate(bullets[:4]):
        bullet_nodes.append(
            f'<text x="78" y="{494 + index * 32}" font-size="22" font-weight="700" fill="#DDE7F3">• {svg_escape(bullet)}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="630" viewBox="0 0 1200 630" role="img">
  <title>{svg_escape(title)}</title>
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#07111F"/>
      <stop offset="0.52" stop-color="#102A43"/>
      <stop offset="1" stop-color="#0F172A"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="42" y="42" width="1116" height="546" rx="18" fill="none" stroke="#2F80ED" stroke-width="2"/>
  <text x="78" y="102" font-size="28" font-weight="900" fill="#7DD3FC">{svg_escape(SITE_NAME)} · LoL Patch {svg_escape(patch_version)}</text>
  <text x="900" y="102" font-size="28" font-weight="900" fill="#FDE68A">{svg_escape(count_label)}</text>
  {text_lines(title, 78, 172, 48, 31, "#FFFFFF", 900)}
  {''.join(cards)}
  {''.join(bullet_nodes)}
</svg>
'''


def render_champion_grid_svg(title: str, champions: list[dict], source_text: str, lang: str) -> str:
    cards = []
    subtitle = "공식 Data Dragon 명칭 기준 챔피언 요약" if lang == "ko" else "Data Dragon公式名称に基づくチャンピオン要約"
    for index, entry in enumerate(champions[:12]):
        x = 64 + (index % 3) * 356
        y = 158 + (index // 3) * 144
        status = entry_status(entry, source_text)
        color = status_color(status)
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="318" height="104" rx="8" fill="#0B1220" stroke="#1F2937"/>
              <image href="{image_href(entry["key"])}" xlink:href="{image_href(entry["key"])}" x="{x + 16}" y="{y + 16}" width="72" height="72" preserveAspectRatio="xMidYMid slice"/>
              <text x="{x + 106}" y="{y + 47}" font-size="25" font-weight="900" fill="#F8FAFC">{svg_escape(localized_name(entry, lang))}</text>
              <text x="{x + 248}" y="{y + 72}" font-size="17" font-weight="900" fill="{color}">{svg_escape(localized_status(status, lang))}</text>
            </g>'''
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="800" viewBox="0 0 1200 800" role="img">
  <title>{svg_escape(title)}</title>
  <rect width="1200" height="800" fill="#F6F8FB"/>
  <rect x="40" y="40" width="1120" height="720" rx="18" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="64" y="102" font-size="42" font-weight="900" fill="#111827">{svg_escape(title)}</text>
  <text x="64" y="132" font-size="22" font-weight="800" fill="#64748B">{svg_escape(subtitle)}</text>
  {''.join(cards)}
</svg>
'''


def render_group_svg(title: str, champions: list[dict], status: str, lang: str) -> str:
    selected = [entry for entry in champions if entry_status(entry) == status]
    if not selected:
        selected = champions[:4]

    cards = []
    columns = 4 if len(selected) > 6 else 3
    card_width = 252 if columns == 4 else 326
    card_height = 202
    start_x = 64
    start_y = 176
    gap_x = 24
    gap_y = 30
    color = status_color(status)

    for index, entry in enumerate(selected[:8]):
        x = start_x + (index % columns) * (card_width + gap_x)
        y = start_y + (index // columns) * (card_height + gap_y)
        image_width = card_width - 28
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="12" fill="#FFFFFF" stroke="#D7E0EA"/>
              <image href="{image_href(entry["key"], "splash")}" xlink:href="{image_href(entry["key"], "splash")}" x="{x + 14}" y="{y + 14}" width="{image_width}" height="118" preserveAspectRatio="xMidYMid slice"/>
              <rect x="{x + 14}" y="{y + 146}" width="80" height="26" rx="13" fill="{color}"/>
              <text x="{x + 54}" y="{y + 165}" text-anchor="middle" font-size="15" font-weight="900" fill="#FFFFFF">{svg_escape(localized_status(status, lang))}</text>
              <text x="{x + 108}" y="{y + 166}" font-size="22" font-weight="900" fill="#0F172A">{svg_escape(localized_name(entry, lang))}</text>
            </g>'''
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="720" viewBox="0 0 1200 720" role="img">
  <title>{svg_escape(title)}</title>
  <rect width="1200" height="720" fill="#F6F8FB"/>
  <rect x="40" y="40" width="1120" height="640" rx="18" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="64" y="112" font-size="42" font-weight="900" fill="#111827">{svg_escape(title)}</text>
  {''.join(cards)}
</svg>
'''


def render_topic_svg(title: str, bullets: list[str], tone: str) -> str:
    colors = {
        "core": ("#FFF7ED", "#C2410C"),
        "tier": ("#E0F2FE", "#0369A1"),
        "source": ("#ECFDF5", "#047857"),
    }
    bg, accent = colors.get(tone, ("#EFF6FF", "#2563EB"))
    nodes = []
    for index, bullet in enumerate(bullets[:5]):
        y = 178 + index * 92
        nodes.append(
            f'''
            <g>
              <rect x="74" y="{y}" width="1052" height="64" rx="10" fill="#FFFFFF" stroke="#D7E0EA"/>
              <circle cx="112" cy="{y + 32}" r="16" fill="{accent}"/>
              <text x="112" y="{y + 39}" text-anchor="middle" font-size="18" font-weight="900" fill="#FFFFFF">{index + 1}</text>
              {text_lines(bullet, 148, y + 38, 22, 62, "#1F2937", 800)}
            </g>'''
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="720" viewBox="0 0 1200 720" role="img">
  <title>{svg_escape(title)}</title>
  <rect width="1200" height="720" fill="{bg}"/>
  <rect x="40" y="40" width="1120" height="640" rx="18" fill="#F8FAFC" stroke="#CBD5E1"/>
  <text x="74" y="116" font-size="42" font-weight="900" fill="#0F172A">{svg_escape(title)}</text>
  {''.join(nodes)}
</svg>
'''


def render_recommended_svg(title: str, champions: list[dict], lang: str) -> str:
    selected = champions[:5]
    note = "패치 초반에는 숙련도와 조합 적합도를 함께 확인하세요." if lang == "ko" else "パッチ序盤は熟練度と構成適性を一緒に確認しましょう。"
    cards = []
    for index, entry in enumerate(selected):
        x = 72 + (index % 5) * 214
        y = 214
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="190" height="306" rx="14" fill="#FFFFFF" stroke="#BFDBFE"/>
              <image href="{image_href(entry["key"], "splash")}" xlink:href="{image_href(entry["key"], "splash")}" x="{x + 12}" y="{y + 12}" width="166" height="162" preserveAspectRatio="xMidYMid slice"/>
              <text x="{x + 20}" y="{y + 218}" font-size="22" font-weight="900" fill="#0F172A">{svg_escape(localized_name(entry, lang))}</text>
              <text x="{x + 20}" y="{y + 258}" font-size="16" font-weight="900" fill="#2563EB">{index + 1}. {svg_escape(localized_status("추천", lang))}</text>
            </g>'''
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="720" viewBox="0 0 1200 720" role="img">
  <title>{svg_escape(title)}</title>
  <rect width="1200" height="720" fill="#EFF6FF"/>
  <rect x="40" y="40" width="1120" height="640" rx="18" fill="#F8FAFC" stroke="#BFDBFE"/>
  <text x="74" y="110" font-size="44" font-weight="900" fill="#0F172A">{svg_escape(title)}</text>
  <text x="74" y="154" font-size="20" font-weight="800" fill="#475569">{svg_escape(note)}</text>
  {''.join(cards)}
</svg>
'''


def clean_svg(svg: str) -> str:
    return "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"


def build_bullets(frontmatter: str, lang: str) -> list[str]:
    values = extract_localized_list(frontmatter, "body", lang)
    bullets = []
    for value in values:
        cleaned = re.sub(r"^[^:：]{1,20}[:：]\s*", "", value)
        bullets.append(cleaned[:76])
    return bullets[:4]


def localized_nested_values(frontmatter: str, section_key: str, field_key: str, lang: str) -> list[str]:
    section = top_level_section(frontmatter, section_key)
    values: list[str] = []
    lines = section.splitlines()
    in_field = False
    in_lang = False
    field_indent = 0
    lang_indent = 0

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if re.match(rf"\s*{re.escape(field_key)}:\s*$", line):
            in_field = True
            in_lang = False
            field_indent = indent
            continue
        if in_field and indent <= field_indent and stripped:
            in_field = False
            in_lang = False
        if in_field and re.match(rf"\s*{lang}:\s*", line):
            value = re.sub(rf"^\s*{lang}:\s*", "", line).strip()
            if value:
                values.append(value.strip("\"'"))
            in_lang = True
            lang_indent = indent
            continue
        if in_lang and indent <= lang_indent and stripped:
            in_lang = False
        if in_lang:
            match = re.match(r"\s*-\s*(.+)$", line)
            if match:
                values.append(match.group(1).strip("\"'"))
    return values


def top_level_section(frontmatter: str, key: str) -> str:
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


def explicit_champions(frontmatter: str, name_map: dict) -> list[dict]:
    return explicit_champion_items(frontmatter, name_map, "lol_champions")


def explicit_champion_items(frontmatter: str, name_map: dict, section_name: str = "lol_champions") -> list[dict]:
    champions = name_map.get("champions", {})
    result = []
    seen = set()
    current: dict[str, str] | None = None
    in_section = False

    def append_current() -> None:
        if not current:
            return
        key = current.get("key", "")
        if not key or key in seen:
            return
        entry = champions.get(key)
        if not entry:
            return
        enriched = dict(entry)
        if current.get("status"):
            enriched["status"] = current["status"]
        result.append(enriched)
        seen.add(key)

    for line in frontmatter.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped == f"{section_name}:":
            in_section = True
            continue
        if in_section and indent == 0 and stripped:
            append_current()
            break
        if not in_section:
            continue

        inline_key = re.match(r"\s*-\s*key:\s*['\"]?([^'\"\n]+)['\"]?", line)
        if inline_key:
            append_current()
            current = {"key": inline_key.group(1)}
            continue

        if re.match(r"\s*-\s*$", line):
            append_current()
            current = {}
            continue

        if current is None:
            continue
        match = re.match(r"\s*(key|status):\s*['\"]?(.+?)['\"]?\s*$", line)
        if match:
            current[match.group(1)] = match.group(2).strip("\"'")

    append_current()
    return result


def section_body(frontmatter: str, section_id: str, lang: str) -> list[str]:
    lines = frontmatter.splitlines()
    in_sections = False
    in_target = False
    in_body = False
    in_lang = False
    body_indent = 0
    lang_indent = 0
    values: list[str] = []

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped == "sections:":
            in_sections = True
            continue
        if in_sections and indent == 0 and stripped:
            break
        if not in_sections:
            continue

        id_match = re.match(r"\s*(?:-\s*)?id:\s*['\"]?([^'\"\n]+)['\"]?", line)
        if id_match:
            in_target = id_match.group(1) == section_id
            in_body = False
            in_lang = False
            continue

        if not in_target:
            continue
        if re.match(r"\s*body:\s*$", line):
            in_body = True
            body_indent = indent
            continue
        if in_body and indent <= body_indent and stripped:
            in_body = False
            in_lang = False
        if in_body and re.match(rf"\s*{lang}:\s*$", line):
            in_lang = True
            lang_indent = indent
            continue
        if in_lang and indent <= lang_indent and stripped:
            in_lang = False
        if in_lang:
            match = re.match(r"\s*-\s*['\"]?(.+?)['\"]?\s*$", line)
            if match:
                values.append(match.group(1).strip("\"'"))

    return values


def image_path(slug: str, kind: str, lang: str | None = None):
    suffix = f"-{lang}" if lang else ""
    return BLOG_IMAGE_DIR / f"{slug}-{kind}{suffix}.svg"


def referenced_generated_kinds(frontmatter: str, slug: str, known_kinds: list[str]) -> list[str]:
    matched = [kind for kind in known_kinds if f"{slug}-{kind}" in frontmatter]
    return matched or known_kinds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="블로그 글별 언어별 SVG 이미지를 생성합니다.")
    return parser.parse_args()


def main() -> int:
    parse_args()
    name_map = load_champion_map()
    BLOG_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    report = []

    for path in post_paths():
        text = path.read_text(encoding="utf-8")
        frontmatter, _, _ = split_frontmatter(text)
        slug = extract_scalar(frontmatter, "slug") or path.stem
        patch_version = extract_scalar(frontmatter, "patch_version")
        content_type = extract_scalar(frontmatter, "content_type")
        display_label = (
            patch_version
            or extract_scalar(frontmatter, "applicable_patch")
            or {
                "patch-meta-followup": "메타 점검",
                "position-meta": "포지션 리포트",
                "champion-focus": "챔피언 분석",
                "riot-dev-update": "개발자 업데이트",
                "system-guide": "시스템 가이드",
            }.get(content_type, "LoL")
        )
        champions = explicit_champions(frontmatter, name_map) or detect_champions(frontmatter, name_map)
        recommended_champions = explicit_champion_items(frontmatter, name_map, "recommended_pick_cards")
        if not champions:
            champions = detect_champions(text, name_map)
        if not recommended_champions:
            recommended_champions = [entry for entry in champions if entry_status(entry) == "버프"][:5] or champions[:5]

        known_kinds = [
            "champions",
            "core-notes",
            "buff-group",
            "nerf-group",
            "recommended-picks",
        ]
        target_kinds = referenced_generated_kinds(frontmatter, slug, known_kinds)
        generated: dict[str, dict[str, str]] = {kind: {} for kind in target_kinds}

        for lang in LANGS:
            title = extract_localized_scalar(frontmatter, "title", lang) or slug
            core_title = f"LoL {display_label} 핵심노트 정리" if lang == "ko" else f"LoL {display_label} 要点ノートまとめ"
            buff_title = f"LoL {display_label} 버프 챔피언 카드" if lang == "ko" else f"LoL {display_label} 強化チャンピオンカード"
            nerf_title = f"LoL {display_label} 너프 챔피언 카드" if lang == "ko" else f"LoL {display_label} 弱体化チャンピオンカード"
            picks_title = f"LoL {display_label} 추천 픽" if lang == "ko" else f"LoL {display_label} おすすめピック"

            core_bullets = (
                localized_nested_values(frontmatter, "quick_summary_items", "body", lang)
                or section_body(frontmatter, "quick-summary", lang)
                or section_body(frontmatter, "key-changes", lang)
                or build_bullets(frontmatter, lang)
            )

            outputs = {
                "champions": render_champion_grid_svg(title, champions, text, lang),
                "core-notes": render_topic_svg(core_title, core_bullets, "core"),
                "buff-group": render_group_svg(buff_title, champions, "버프", lang),
                "nerf-group": render_group_svg(nerf_title, champions, "너프", lang),
                "recommended-picks": render_recommended_svg(picks_title, recommended_champions, lang),
            }

            for kind in target_kinds:
                svg = outputs[kind]
                out_path = image_path(slug, kind, lang)
                out_path.write_text(clean_svg(svg), encoding="utf-8")
                generated[kind][lang] = repo_path(out_path)
                if lang == "ko":
                    alias_path = image_path(slug, kind)
                    alias_path.write_text(clean_svg(svg), encoding="utf-8")
                    generated[kind]["default"] = repo_path(alias_path)

        report.append(
            {
                "file": repo_path(path),
                "images": generated,
                "champion_count": len(champions),
            }
        )

    report_path = write_report("blog-image-report.json", report)
    log(f"언어별 이미지 생성 리포트 저장: {repo_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
