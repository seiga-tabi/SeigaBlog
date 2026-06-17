#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re

from lol_content_utils import (
    BLOG_IMAGE_DIR,
    REPO_ROOT,
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


def image_href(key: str, image_type: str = "square") -> str:
    filename = "splash.jpg" if image_type == "splash" else "square.png"
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


def render_summary_svg(title_ko: str, title_ja: str, patch_version: str, champions: list[dict], bullets: list[str]) -> str:
    cards = []
    for index, entry in enumerate(champions[:6]):
        x = 78 + (index % 3) * 342
        y = 304 + (index // 3) * 108
        status = entry_status(entry)
        color = status_color(status)
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="304" height="76" rx="8" fill="#111827" stroke="#334155"/>
              <text x="{x + 20}" y="{y + 32}" font-size="24" font-weight="900" fill="#F8FAFC">{svg_escape(localized_name(entry, "ko"))}</text>
              <text x="{x + 20}" y="{y + 58}" font-size="18" font-weight="700" fill="#93C5FD">{svg_escape(localized_name(entry, "ja"))}</text>
              <text x="{x + 240}" y="{y + 33}" font-size="17" font-weight="900" fill="{color}">{svg_escape(status)}</text>
            </g>'''
        )

    bullet_nodes = []
    for index, bullet in enumerate(bullets[:4]):
        bullet_nodes.append(
            f'<text x="78" y="{494 + index * 32}" font-size="22" font-weight="700" fill="#DDE7F3">• {svg_escape(bullet)}</text>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img">
  <title>{svg_escape(title_ko)}</title>
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
  {text_lines(title_ko, 78, 172, 48, 30, "#FFFFFF", 900)}
  <text x="78" y="254" font-size="26" font-weight="800" fill="#BFDBFE">{svg_escape(title_ja)}</text>
  {''.join(cards)}
  {''.join(bullet_nodes)}
</svg>
'''


def render_champion_grid_svg(title_ko: str, champions: list[dict], source_text: str) -> str:
    cards = []
    for index, entry in enumerate(champions[:12]):
        x = 64 + (index % 3) * 356
        y = 158 + (index // 3) * 144
        key = entry["key"]
        img = image_href(key)
        status = entry_status(entry, source_text)
        color = status_color(status)
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="318" height="104" rx="8" fill="#0B1220" stroke="#1F2937"/>
              <image href="{img}" x="{x + 16}" y="{y + 16}" width="72" height="72" preserveAspectRatio="xMidYMid slice"/>
              <text x="{x + 106}" y="{y + 42}" font-size="25" font-weight="900" fill="#F8FAFC">{svg_escape(localized_name(entry, "ko"))}</text>
              <text x="{x + 106}" y="{y + 70}" font-size="18" font-weight="700" fill="#CBD5E1">{svg_escape(localized_name(entry, "ja"))}</text>
              <text x="{x + 250}" y="{y + 68}" font-size="17" font-weight="900" fill="{color}">{svg_escape(status)}</text>
            </g>'''
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800" role="img">
  <title>{svg_escape(title_ko)} 챔피언 요약</title>
  <rect width="1200" height="800" fill="#F6F8FB"/>
  <rect x="40" y="40" width="1120" height="720" rx="18" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="64" y="102" font-size="42" font-weight="900" fill="#111827">{svg_escape(title_ko)}</text>
  <text x="64" y="132" font-size="22" font-weight="800" fill="#64748B">공식 Data Dragon 명칭 기준 챔피언 요약</text>
  {''.join(cards)}
</svg>
'''


def render_group_svg(title_ko: str, title_ja: str, champions: list[dict], status: str) -> str:
    selected = [entry for entry in champions if entry_status(entry) == status]
    if not selected:
        selected = champions[:4]

    cards = []
    columns = 4 if len(selected) > 6 else 3
    card_width = 252 if columns == 4 else 326
    card_height = 210
    start_x = 64
    start_y = 176
    gap_x = 24
    gap_y = 26
    color = status_color(status)

    for index, entry in enumerate(selected[:8]):
        x = start_x + (index % columns) * (card_width + gap_x)
        y = start_y + (index // columns) * (card_height + gap_y)
        image_width = card_width - 28
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="12" fill="#FFFFFF" stroke="#D7E0EA"/>
              <image href="{image_href(entry["key"], "splash")}" x="{x + 14}" y="{y + 14}" width="{image_width}" height="118" preserveAspectRatio="xMidYMid slice"/>
              <rect x="{x + 14}" y="{y + 146}" width="70" height="26" rx="13" fill="{color}"/>
              <text x="{x + 49}" y="{y + 165}" text-anchor="middle" font-size="15" font-weight="900" fill="#FFFFFF">{svg_escape(status)}</text>
              <text x="{x + 96}" y="{y + 165}" font-size="22" font-weight="900" fill="#0F172A">{svg_escape(localized_name(entry, "ko"))}</text>
              <text x="{x + 96}" y="{y + 190}" font-size="16" font-weight="800" fill="#64748B">{svg_escape(localized_name(entry, "ja"))}</text>
            </g>'''
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img">
  <title>{svg_escape(title_ko)}</title>
  <rect width="1200" height="720" fill="#F6F8FB"/>
  <rect x="40" y="40" width="1120" height="640" rx="18" fill="#FFFFFF" stroke="#E2E8F0"/>
  <text x="64" y="104" font-size="42" font-weight="900" fill="#111827">{svg_escape(title_ko)}</text>
  <text x="64" y="138" font-size="23" font-weight="800" fill="#64748B">{svg_escape(title_ja)}</text>
  {''.join(cards)}
</svg>
'''


def render_topic_svg(title_ko: str, title_ja: str, bullets: list[str], tone: str) -> str:
    colors = {
        "tier": ("#E0F2FE", "#0369A1"),
        "source": ("#ECFDF5", "#047857"),
    }
    bg, accent = colors.get(tone, ("#EFF6FF", "#2563EB"))
    nodes = []
    for index, bullet in enumerate(bullets[:5]):
        y = 180 + index * 88
        nodes.append(
            f'''
            <g>
              <rect x="74" y="{y}" width="1052" height="58" rx="10" fill="#FFFFFF" stroke="#D7E0EA"/>
              <circle cx="112" cy="{y + 29}" r="16" fill="{accent}"/>
              <text x="112" y="{y + 36}" text-anchor="middle" font-size="18" font-weight="900" fill="#FFFFFF">{index + 1}</text>
              {text_lines(bullet, 148, y + 35, 22, 62, "#1F2937", 800)}
            </g>'''
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img">
  <title>{svg_escape(title_ko)}</title>
  <rect width="1200" height="720" fill="{bg}"/>
  <rect x="40" y="40" width="1120" height="640" rx="18" fill="#F8FAFC" stroke="#CBD5E1"/>
  <text x="74" y="104" font-size="42" font-weight="900" fill="#0F172A">{svg_escape(title_ko)}</text>
  <text x="74" y="138" font-size="23" font-weight="800" fill="{accent}">{svg_escape(title_ja)}</text>
  {''.join(nodes)}
</svg>
'''


def render_recommended_svg(title_ko: str, title_ja: str, champions: list[dict]) -> str:
    selected = [entry for entry in champions if entry_status(entry) == "버프"][:4] or champions[:4]
    cards = []
    for index, entry in enumerate(selected):
        x = 74 + index * 270
        y = 210
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="238" height="300" rx="14" fill="#FFFFFF" stroke="#BFDBFE"/>
              <image href="{image_href(entry["key"], "splash")}" x="{x + 14}" y="{y + 14}" width="210" height="168" preserveAspectRatio="xMidYMid slice"/>
              <text x="{x + 20}" y="{y + 224}" font-size="25" font-weight="900" fill="#0F172A">{svg_escape(localized_name(entry, "ko"))}</text>
              <text x="{x + 20}" y="{y + 254}" font-size="18" font-weight="800" fill="#64748B">{svg_escape(localized_name(entry, "ja"))}</text>
              <text x="{x + 20}" y="{y + 282}" font-size="17" font-weight="900" fill="#2563EB">추천 픽</text>
            </g>'''
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img">
  <title>{svg_escape(title_ko)}</title>
  <rect width="1200" height="720" fill="#EFF6FF"/>
  <rect x="40" y="40" width="1120" height="640" rx="18" fill="#F8FAFC" stroke="#BFDBFE"/>
  <text x="74" y="110" font-size="44" font-weight="900" fill="#0F172A">{svg_escape(title_ko)}</text>
  <text x="74" y="146" font-size="23" font-weight="800" fill="#2563EB">{svg_escape(title_ja)}</text>
  <text x="74" y="176" font-size="20" font-weight="800" fill="#475569">패치 초반에는 숙련도와 조합 적합도를 함께 확인하세요.</text>
  {''.join(cards)}
</svg>
'''


def clean_svg(svg: str) -> str:
    return "\n".join(line.rstrip() for line in svg.splitlines()) + "\n"


def build_bullets(frontmatter: str) -> list[str]:
    values = extract_localized_list(frontmatter, "body", "ko")
    bullets = []
    for value in values:
        cleaned = re.sub(r"^[^:：]{1,20}[:：]\s*", "", value)
        bullets.append(cleaned[:58])
    return bullets[:4]


def explicit_champions(frontmatter: str, name_map: dict) -> list[dict]:
    return explicit_champion_items(frontmatter, name_map)


def explicit_champion_items(frontmatter: str, name_map: dict) -> list[dict]:
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
        if indent == 0 and stripped == "lol_champions:":
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

        id_match = re.match(r"\s*-\s*id:\s*['\"]?([^'\"\n]+)['\"]?", line)
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="블로그 글별 요약 SVG 이미지를 생성합니다.")
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
        title_ko = extract_localized_scalar(frontmatter, "title", "ko") or slug
        title_ja = extract_localized_scalar(frontmatter, "title", "ja") or title_ko
        patch_version = extract_scalar(frontmatter, "patch_version")
        champions = explicit_champions(frontmatter, name_map) or detect_champions(frontmatter, name_map)
        if not champions:
            champions = detect_champions(text, name_map)

        summary_path = BLOG_IMAGE_DIR / f"{slug}-summary.svg"
        champions_path = BLOG_IMAGE_DIR / f"{slug}-champions.svg"
        buff_path = BLOG_IMAGE_DIR / f"{slug}-buff-group.svg"
        nerf_path = BLOG_IMAGE_DIR / f"{slug}-nerf-group.svg"
        tier_path = BLOG_IMAGE_DIR / f"{slug}-tier-impact.svg"
        picks_path = BLOG_IMAGE_DIR / f"{slug}-recommended-picks.svg"
        source_path = BLOG_IMAGE_DIR / f"{slug}-source-note.svg"
        summary_path.write_text(
            clean_svg(render_summary_svg(title_ko, title_ja, patch_version, champions, build_bullets(frontmatter))),
            encoding="utf-8",
        )
        champions_path.write_text(
            clean_svg(render_champion_grid_svg(title_ko, champions, text)),
            encoding="utf-8",
        )
        buff_path.write_text(
            clean_svg(render_group_svg(f"LoL {patch_version} 버프 챔피언 카드", f"LoL {patch_version} 強化チャンピオンカード", champions, "버프")),
            encoding="utf-8",
        )
        nerf_path.write_text(
            clean_svg(render_group_svg(f"LoL {patch_version} 너프 챔피언 카드", f"LoL {patch_version} 弱体化チャンピオンカード", champions, "너프")),
            encoding="utf-8",
        )
        tier_bullets = section_body(frontmatter, "solo-queue-tier-impact", "ko") or build_bullets(frontmatter)
        tier_path.write_text(
            clean_svg(render_topic_svg(f"LoL {patch_version} 솔랭 티어 영향", f"LoL {patch_version} ソロランクティア影響", tier_bullets, "tier")),
            encoding="utf-8",
        )
        picks_path.write_text(
            clean_svg(render_recommended_svg(f"LoL {patch_version} 추천 픽", f"LoL {patch_version} おすすめピック", champions)),
            encoding="utf-8",
        )
        source_url = extract_scalar(frontmatter, "source_url")
        source_bullets = [
            "공식 패치노트를 기준으로 요약했습니다.",
            "챔피언명은 Riot Data Dragon 한국어/일본어 데이터를 사용했습니다.",
            "챔피언 이미지는 로컬 저장된 Riot Data Dragon 스플래시 아트를 참조합니다.",
            f"공식 출처: {source_url}" if source_url else "공식 출처는 글 하단에서 확인할 수 있습니다.",
        ]
        source_path.write_text(
            clean_svg(render_topic_svg(f"LoL {patch_version} 공식 출처 안내", f"LoL {patch_version} 公式ソース案内", source_bullets, "source")),
            encoding="utf-8",
        )
        report.append(
            {
                "file": repo_path(path),
                "summary_image": repo_path(summary_path),
                "champions_image": repo_path(champions_path),
                "buff_group_image": repo_path(buff_path),
                "nerf_group_image": repo_path(nerf_path),
                "tier_impact_image": repo_path(tier_path),
                "recommended_picks_image": repo_path(picks_path),
                "source_note_image": repo_path(source_path),
                "champion_count": len(champions),
            }
        )

    report_path = write_report("blog-image-report.json", report)
    log(f"요약 이미지 생성 리포트 저장: {repo_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
