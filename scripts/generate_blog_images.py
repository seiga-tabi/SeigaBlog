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
        cards.append(
            f'''
            <g>
              <rect x="{x}" y="{y}" width="304" height="76" rx="8" fill="#111827" stroke="#334155"/>
              <text x="{x + 20}" y="{y + 32}" font-size="24" font-weight="900" fill="#F8FAFC">{svg_escape(localized_name(entry, "ko"))}</text>
              <text x="{x + 20}" y="{y + 58}" font-size="18" font-weight="700" fill="#93C5FD">{svg_escape(localized_name(entry, "ja"))}</text>
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
        img = f"../../lol/champions/{key}/square.png"
        status = classification_from_text(source_text, localized_name(entry, "ko"))
        color = "#22C55E" if status == "버프" else "#F97316" if status == "너프" else "#60A5FA"
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
    champions = name_map.get("champions", {})
    keys = re.findall(r"^\s*key:\s*['\"]?([^'\"\n]+)['\"]?\s*$", frontmatter, flags=re.MULTILINE)
    result = []
    seen = set()
    for key in keys:
        entry = champions.get(key)
        if entry and key not in seen:
            result.append(entry)
            seen.add(key)
    return result


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
        summary_path.write_text(
            clean_svg(render_summary_svg(title_ko, title_ja, patch_version, champions, build_bullets(frontmatter))),
            encoding="utf-8",
        )
        champions_path.write_text(
            clean_svg(render_champion_grid_svg(title_ko, champions, text)),
            encoding="utf-8",
        )
        report.append(
            {
                "file": repo_path(path),
                "summary_image": repo_path(summary_path),
                "champions_image": repo_path(champions_path),
                "champion_count": len(champions),
            }
        )

    report_path = write_report("blog-image-report.json", report)
    log(f"요약 이미지 생성 리포트 저장: {repo_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
