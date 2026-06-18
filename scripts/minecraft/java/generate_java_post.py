#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

from normalize_java_release import (
    ASSET_DIR,
    CHANNEL_META,
    DEFAULT_IMAGE,
    POSTS_DIR,
    generation_report_path,
    now_iso,
    read_json,
    read_time,
    render_post,
    repo_path,
    safe_slug,
    selected_topic_path,
    today_string,
    version_slug,
    write_json,
)


def log(message: str) -> None:
    print(f"[Minecraft Java Post] {message}")


def svg_escape(value: str) -> str:
    return html.escape(str(value or ""), quote=False)


def wrap_svg_text(text: str, width: int = 44, max_lines: int = 5) -> list[str]:
    words = re.split(r"\s+", text.strip())
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines[:max_lines]


def write_svg(path: Path, title: str, bullets: list[str], tone: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    colors = {
        "stable": ("#115E59", "#ECFDF5", "#14B8A6"),
        "test": ("#7C2D12", "#FFF7ED", "#F97316"),
        "official": ("#1E3A8A", "#EFF6FF", "#3B82F6"),
    }
    dark, pale, accent = colors.get(tone, colors["official"])
    bullet_lines = []
    y = 210
    for index, bullet in enumerate(bullets[:5], start=1):
        bullet_lines.append(f'<circle cx="76" cy="{y - 8}" r="14" fill="{accent}"/>')
        bullet_lines.append(f'<text x="76" y="{y - 2}" text-anchor="middle" font-size="14" font-weight="800" fill="#FFFFFF">{index}</text>')
        for line_index, line in enumerate(wrap_svg_text(bullet, 64, 2)):
            bullet_lines.append(f'<text x="112" y="{y + line_index * 25}" font-size="23" font-weight="700" fill="#111827">{svg_escape(line)}</text>')
        y += 88
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
  <rect width="1200" height="675" rx="28" fill="{pale}"/>
  <rect x="36" y="36" width="1128" height="603" rx="24" fill="#FFFFFF" stroke="{accent}" stroke-width="3"/>
  <text x="72" y="104" font-size="30" font-weight="900" fill="{accent}">Seiga Blog · Minecraft Java</text>
  <text x="72" y="158" font-size="42" font-weight="900" fill="{dark}">{svg_escape(title)}</text>
  {''.join(bullet_lines)}
</svg>
'''
    path.write_text(svg, encoding="utf-8")


def source(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("source", {})


def localized_original_lines(items: list[str], lang: str, empty: str) -> list[str]:
    if not items:
        return [empty]
    prefix = "공식 원문 항목" if lang == "ko" else "公式原文項目"
    return [f"{prefix}: {item}" for item in items[:6]]


def section(section_id: str, title_ko: str, title_ja: str, body_ko: list[str], body_ja: list[str], kind: str = "text") -> dict[str, Any] | None:
    if not body_ko and not body_ja:
        return None
    return {
        "id": section_id,
        "kind": kind,
        "title": {"ko": title_ko, "ja": title_ja},
        "body": {"ko": body_ko or ["원문에 해당 정보가 없습니다."], "ja": body_ja or ["原文に該当情報はありません。"]},
    }


def build_sections(item: dict[str, Any]) -> list[dict[str, Any]]:
    channel = item.get("release_channel", "")
    is_stable = channel in {"java_stable_release", "java_hotfix"}
    is_test = channel in {"java_snapshot", "java_pre_release", "java_release_candidate"}
    sections: list[dict[str, Any] | None] = []
    if is_test:
        sections.append(section("test-warning", "테스트 버전 상태", "テスト版ステータス", ["이 버전은 정식 업데이트가 아니며, 원문 기준 테스트 단계로 분류했습니다."], ["このバージョンは正式アップデートではなく、原文基準でテスト段階として分類しました。"]))
    sections.append(section("quick-summary", "3줄 요약", "3行要約", [item.get("summary", {}).get("ko", "")], [item.get("summary", {}).get("ja", "")], "quick_summary"))
    if is_stable:
        section_plan = [
            ("release-status", "버전 및 배포 상태", "バージョンと配布状態", [f"버전: {item.get('version') or '원문 확인 필요'}", f"상태: {CHANNEL_META[channel]['badge']['ko']}"], [f"バージョン: {item.get('version') or '原文確認が必要'}", f"状態: {CHANNEL_META[channel]['badge']['ja']}"]),
            ("added", "새로 추가된 기능", "追加された機能", localized_original_lines(item.get("added", []), "ko", ""), localized_original_lines(item.get("added", []), "ja", "")),
            ("changed", "변경된 기능", "変更された機能", localized_original_lines(item.get("changed", []), "ko", ""), localized_original_lines(item.get("changed", []), "ja", "")),
            ("fixed", "주요 버그 수정", "主な不具合修正", localized_original_lines(item.get("fixed", []), "ko", ""), localized_original_lines(item.get("fixed", []), "ja", "")),
            ("technical", "Java Edition 기술 변경", "Java Edition技術変更", localized_original_lines(item.get("technical_changes", []) + item.get("commands", []), "ko", ""), localized_original_lines(item.get("technical_changes", []) + item.get("commands", []), "ja", "")),
            ("packs", "데이터팩·리소스팩 변경", "データパック・リソースパック変更", localized_original_lines(item.get("data_pack_changes", []) + item.get("resource_pack_changes", []), "ko", ""), localized_original_lines(item.get("data_pack_changes", []) + item.get("resource_pack_changes", []), "ja", "")),
            ("server", "서버 운영자가 확인할 내용", "サーバー運営者が確認する内容", localized_original_lines(item.get("server_changes", []), "ko", ""), localized_original_lines(item.get("server_changes", []), "ja", "")),
            ("world", "기존 월드에서 확인할 내용", "既存ワールドで確認する内容", ["월드 호환성은 원문에 명시된 내용만 확인합니다."], ["ワールド互換性は原文で明記された内容のみ確認します。"]),
            ("known-issues", "알려진 문제", "既知の問題", localized_original_lines(item.get("known_issues", []), "ko", ""), localized_original_lines(item.get("known_issues", []), "ja", "")),
            ("checklist", "업데이트 체크리스트", "アップデートチェックリスト", ["공식 원문을 열어 서버, 데이터팩, 리소스팩 항목을 다시 확인하세요."], ["公式原文を開き、サーバー、データパック、リソースパック項目を再確認してください。"],),
        ]
    else:
        section_plan = [
            ("new-in-test", "이번 Snapshot 신규 내용", "今回のテスト版の新内容", localized_original_lines(item.get("added", []), "ko", ""), localized_original_lines(item.get("added", []), "ja", "")),
            ("changed", "이전 테스트판 대비 변경", "前回テスト版からの変更", localized_original_lines(item.get("changed", []), "ko", ""), localized_original_lines(item.get("changed", []), "ja", "")),
            ("experimental", "실험 기능", "実験的な機能", localized_original_lines(item.get("experimental_changes", []), "ko", ""), localized_original_lines(item.get("experimental_changes", []), "ja", "")),
            ("technical", "기술 변경", "技術変更", localized_original_lines(item.get("technical_changes", []) + item.get("commands", []), "ko", ""), localized_original_lines(item.get("technical_changes", []) + item.get("commands", []), "ja", "")),
            ("fixed", "수정된 버그", "修正された不具合", localized_original_lines(item.get("fixed", []), "ko", ""), localized_original_lines(item.get("fixed", []), "ja", "")),
            ("not-final", "아직 확정되지 않은 내용", "まだ確定していない内容", ["테스트 버전 변경점은 정식판 적용 전 달라질 수 있습니다."], ["テスト版の変更点は正式版適用前に変わる可能性があります。"]),
            ("data-server-check", "데이터팩·서버 운영 체크 포인트", "データパック・サーバー運営チェックポイント", localized_original_lines(item.get("data_pack_changes", []) + item.get("server_changes", []), "ko", ""), localized_original_lines(item.get("data_pack_changes", []) + item.get("server_changes", []), "ja", "")),
            ("next-check", "다음 버전에서 확인할 항목", "次バージョンで確認する項目", ["목표 정식 버전은 원문에 명시되지 않으면 추정하지 않습니다."], ["対象の正式バージョンは原文に明記されていない場合は推測しません。"]),
        ]
    for args in section_plan:
        current = section(*args)
        if current and not all(not value for value in current["body"]["ko"]):
            sections.append(current)
    sections.append(section("source-note", "공식 출처", "公式出典", ["아래 출처 카드에서 원문과 마지막 확인 시각을 확인하세요."], ["下の出典カードで原文と最終確認時刻を確認してください。"], "source_note"))
    return [current for current in sections if current]


def toc_from_sections(sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {"title": {"ko": "목차", "ja": "目次"}, "items": [{"id": item["id"], "title": item["title"]} for item in sections]}


def overview_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": {"ko": "에디션", "ja": "エディション"}, "value": {"ko": "Java Edition", "ja": "Java Edition"}},
        {"label": {"ko": "버전", "ja": "バージョン"}, "value": {"ko": item.get("version") or "원문 확인", "ja": item.get("version") or "原文確認"}},
        {"label": {"ko": "상태", "ja": "ステータス"}, "value": CHANNEL_META[item["release_channel"]]["badge"]},
        {"label": {"ko": "공식 게시일", "ja": "公式公開日"}, "value": {"ko": source(item).get("published_at", ""), "ja": source(item).get("published_at", "")}},
        {"label": {"ko": "마지막 확인", "ja": "最終確認"}, "value": {"ko": source(item).get("last_verified_at", ""), "ja": source(item).get("last_verified_at", "")}},
        {"label": {"ko": "출처", "ja": "出典"}, "value": {"ko": source(item).get("publisher", "Mojang Studios"), "ja": "Mojang Studios"}},
    ]


def quick_summary_items(item: dict[str, Any]) -> list[dict[str, Any]]:
    score = item.get("candidate_score", {})
    return [
        {"label": {"ko": "상태", "ja": "状態"}, "body": CHANNEL_META[item["release_channel"]]["badge"]},
        {"label": {"ko": "버전", "ja": "バージョン"}, "body": {"ko": item.get("version") or "원문 기준", "ja": item.get("version") or "原文基準"}},
        {"label": {"ko": "주의", "ja": "注意"}, "body": {"ko": "Bedrock 변경은 제외했습니다.", "ja": "Bedrock変更は除外しています。"}},
        {"label": {"ko": "점수", "ja": "スコア"}, "body": {"ko": str(score.get("total", "")), "ja": str(score.get("total", ""))}},
    ]


def faq_items(item: dict[str, Any]) -> list[dict[str, Any]]:
    is_test = item["release_channel"] in {"java_snapshot", "java_pre_release", "java_release_candidate"}
    return [
        {
            "question": {"ko": "이 글은 Bedrock Edition도 포함하나요?", "ja": "この記事はBedrock Editionも含みますか？"},
            "answer": {"ko": "아니요. Java Edition 공식 원문만 기준으로 작성했습니다.", "ja": "いいえ。Java Edition公式原文のみを基準にしています。"},
        },
        {
            "question": {"ko": "원문에 없는 호환성 정보를 보강했나요?", "ja": "原文にない互換性情報を補いましたか？"},
            "answer": {"ko": "아니요. 서버, 모드, 월드 호환성은 원문에 있는 값만 사용합니다.", "ja": "いいえ。サーバー、Mod、ワールド互換性は原文にある値だけ使用します。"},
        },
        {
            "question": {"ko": "테스트 버전도 정식 업데이트인가요?", "ja": "テスト版も正式アップデートですか？"},
            "answer": {
                "ko": "아니요. Snapshot, Pre-Release, Release Candidate는 정식 업데이트로 표현하지 않습니다." if is_test else "이 글은 공식 정식 배포 또는 핫픽스 여부를 별도 상태로 표시합니다.",
                "ja": "いいえ。Snapshot、Pre-Release、Release Candidateは正式アップデートとして表現しません。" if is_test else "この記事は公式正式配布またはホットフィックスかどうかを別ステータスで示します。",
            },
        },
    ]


def source_notes(item: dict[str, Any]) -> list[dict[str, Any]]:
    src = source(item)
    return [
        {
            "label": {"ko": "Mojang 공식 원문", "ja": "Mojang公式原文"},
            "body": {
                "ko": f"{src.get('publisher', 'Mojang Studios')} · 게시일 {src.get('published_at', '')} · 마지막 확인 {src.get('last_verified_at', '')}",
                "ja": f"Mojang Studios · 公開日 {src.get('published_at', '')} · 最終確認 {src.get('last_verified_at', '')}",
            },
            "url": src.get("url", ""),
        }
    ]


def slug_for(item: dict[str, Any], date_value: str, action: str) -> str:
    channel = item.get("release_channel", "")
    if action == "UPDATE_EXISTING" and channel in {"java_snapshot", "java_pre_release", "java_release_candidate"}:
        target = item.get("target_stable_version")
        return f"minecraft-java-{version_slug(target)}-snapshot-tracker" if target else f"minecraft-java-snapshot-tracker-{date_value[:4]}"
    version = version_slug(item.get("version") or source(item).get("title", "java-update"))
    return f"minecraft-java-{version}-summary"


def title_for(item: dict[str, Any]) -> dict[str, str]:
    meta = CHANNEL_META[item["release_channel"]]
    version = item.get("version") or source(item).get("title", "업데이트")
    if item["release_channel"] == "java_hotfix":
        ko = f"{meta['ko']} Minecraft Java Edition {version} 수정 내용"
        ja = f"{meta['ja']} Minecraft Java Edition {version} 修正内容"
    elif item["release_channel"] in {"java_snapshot", "java_pre_release", "java_release_candidate"}:
        ko = f"{meta['ko']} Minecraft Java Edition {version} 테스트 변경점"
        ja = f"{meta['ja']} Minecraft Java Edition {version} テスト変更点"
    else:
        ko = f"{meta['ko']} Minecraft Java Edition {version} 핵심 변경점"
        ja = f"{meta['ja']} Minecraft Java Edition {version} 主要変更点"
    return {"ko": ko, "ja": ja}


def build_post_data(item: dict[str, Any], date_value: str, action: str, write_assets: bool = True) -> dict[str, Any]:
    slug = slug_for(item, date_value, action)
    title = title_for(item)
    sections = build_sections(item)
    asset_dir = ASSET_DIR / slug
    cover_path = asset_dir / "cover.svg"
    summary_path = asset_dir / "summary.svg"
    details_path = asset_dir / "details.svg"
    tone = "stable" if item["release_channel"] in {"java_stable_release", "java_hotfix"} else "test" if item["release_channel"] in {"java_snapshot", "java_pre_release", "java_release_candidate"} else "official"
    bullets = [item.get("summary", {}).get("ko", ""), f"상태: {CHANNEL_META[item['release_channel']]['badge']['ko']}", "Bedrock 변경은 제외했습니다."]
    if write_assets:
        write_svg(cover_path, title["ko"], bullets, tone)
        write_svg(summary_path, title["ko"], bullets, tone)
        write_svg(details_path, "Java 변경 체크 포인트", [section["title"]["ko"] for section in sections[:5]], tone)
    src = source(item)
    post_data: dict[str, Any] = {
        "slug": slug,
        "category": "minecraft",
        "content_type": "minecraft_java_update",
        "edition": "java",
        "release_channel": item["release_channel"],
        "minecraft_version": item.get("version", ""),
        "release_name": item.get("release_name"),
        "accent": "green",
        "read_time": "3 min",
        "image": f"/{repo_path(cover_path)}",
        "og_image": f"/{repo_path(cover_path)}",
        "date": date_value,
        "last_modified_at": now_iso(),
        "source_url": src.get("url", ""),
        "source_title": src.get("title", ""),
        "source_published_at": src.get("published_at", ""),
        "last_checked": src.get("last_verified_at") or now_iso(),
        "information_status": {
            "code": CHANNEL_META[item["release_channel"]]["status"],
            "label": CHANNEL_META[item["release_channel"]]["badge"],
            "notice": {
                "ko": "공식 Java Edition 원문을 기준으로 분류했습니다.",
                "ja": "公式Java Edition原文を基準に分類しました。",
            },
        },
        "sources": [
            {
                "url": src.get("url", ""),
                "title": src.get("title", ""),
                "publisher": src.get("publisher", "Mojang Studios"),
                "published_at": src.get("published_at", ""),
                "last_verified_at": src.get("last_verified_at", ""),
                "source_tier": 1,
            }
        ],
        "description": f"{title['ko']}을 공식 원문 기준으로 정리했습니다.",
        "description_i18n": {
            "ko": f"{title['ko']}을 공식 원문 기준으로 정리했습니다.",
            "ja": f"{title['ja']}を公式原文基準で整理しました。",
        },
        "categories": ["Minecraft", "Java Edition"],
        "tags": ["Minecraft", "Java Edition", "마인크래프트", "업데이트"],
        "author": {"ko": "세이가", "ja": "セイガ"},
        "badge": CHANNEL_META[item["release_channel"]]["badge"],
        "title": title,
        "excerpt": {
            "ko": "Minecraft Java Edition 공식 변경점을 Bedrock과 분리해 요약했습니다.",
            "ja": "Minecraft Java Edition公式変更点をBedrockと分けて要約しました。",
        },
        "post_tags": {
            "ko": ["마인크래프트", "Java Edition", "업데이트"],
            "ja": ["Minecraft", "Java Edition", "アップデート"],
        },
        "lead": {
            "ko": "공식 원문에 없는 버전, 날짜, 기능, 호환성 정보는 추가하지 않았습니다.",
            "ja": "公式原文にないバージョン、日付、機能、互換性情報は追加していません。",
        },
        "body": {
            "ko": ["이 글은 Minecraft Java Edition 공식 원문을 구조화한 데이터로 생성했습니다."],
            "ja": ["この記事はMinecraft Java Edition公式原文を構造化したデータから生成しています。"],
        },
        "summary_image": {
            "src": f"/{repo_path(summary_path)}",
            "width": 1200,
            "height": 675,
            "alt": {"ko": "Minecraft Java Edition 업데이트 요약 이미지", "ja": "Minecraft Java Editionアップデート要約画像"},
            "caption": {"ko": "Java Edition 전용 공식 변경점 요약입니다.", "ja": "Java Edition専用の公式変更点要約です。"},
        },
        "content_images": [
            {
                "after_section": "quick-summary",
                "src": f"/{repo_path(details_path)}",
                "width": 1200,
                "height": 675,
                "alt": {"ko": "Minecraft Java Edition 변경 체크 포인트 이미지", "ja": "Minecraft Java Edition変更チェックポイント画像"},
                "caption": {"ko": "정식판과 테스트판 상태를 분리해 확인합니다.", "ja": "正式版とテスト版の状態を分けて確認します。"},
            }
        ],
        "toc": toc_from_sections(sections),
        "overview_table": {"title": {"ko": "한눈에 보는 Java 업데이트", "ja": "Javaアップデート早見表"}, "rows": overview_rows(item)},
        "sections": sections,
        "quick_summary_items": quick_summary_items(item),
        "source_notes": source_notes(item),
        "faq": faq_items(item),
        "update_history": [
            {
                "checked_at": now_iso(),
                "release_channel": item["release_channel"],
                "version": item.get("version", ""),
                "source_url": src.get("url", ""),
            }
        ],
        "quote": {
            "ko": "Java Edition 정보는 공식 원문이 확인될 때만 글로 만듭니다.",
            "ja": "Java Edition情報は公式原文を確認できた時だけ記事にします。",
        },
        "automation_disclosure": {
            "ko": "이 글은 Mojang 공식 페이지를 구조화한 데이터와 검증 스크립트를 바탕으로 생성했습니다.",
            "ja": "この記事はMojang公式ページを構造化したデータと検証スクリプトをもとに生成しました。",
        },
    }
    post_data["read_time"] = read_time(post_data)
    return post_data


def duplicate_post(slug: str) -> Path | None:
    for path in POSTS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if f"slug: {slug}" in text or path.stem.endswith(slug):
            return path
    return None


def append_tracker_history(path: Path, item: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    src = source(item)
    block = (
        f"-\n"
        f"  checked_at: {json.dumps(now_iso(), ensure_ascii=False)}\n"
        f"  release_channel: {json.dumps(item.get('release_channel'), ensure_ascii=False)}\n"
        f"  version: {json.dumps(item.get('version', ''), ensure_ascii=False)}\n"
        f"  source_url: {json.dumps(src.get('url', ''), ensure_ascii=False)}\n"
    )
    if "\nupdate_history:\n" not in text:
        text = text.replace("\n---\n", f"\nupdate_history:\n{block}---\n", 1)
    else:
        text = re.sub(r"(\nupdate_history:\n)", r"\1" + block, text, count=1)
    text = re.sub(r"last_modified_at:\s*.+", f"last_modified_at: {json.dumps(now_iso(), ensure_ascii=False)}", text, count=1)
    path.write_text(text, encoding="utf-8")


def write_post(post_data: dict[str, Any], action: str, dry_run: bool) -> tuple[Path, bool]:
    slug = post_data["slug"]
    existing = duplicate_post(slug)
    if existing and action == "UPDATE_EXISTING":
        if not dry_run:
            append_tracker_history(existing, {"release_channel": post_data["release_channel"], "version": post_data["minecraft_version"], "source": {"url": post_data["source_url"]}})
        return existing, False
    path = POSTS_DIR / f"{post_data['date']}-{slug}.md"
    if existing:
        return existing, False
    if not dry_run:
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(render_post(post_data), encoding="utf-8")
    return path, True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="선택된 Minecraft Java 항목으로 Jekyll 글을 생성합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="글 파일을 저장하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    selected_payload = read_json(selected_topic_path(date_value), {})
    item = selected_payload.get("selected")
    action = selected_payload.get("action", "REPORT_ONLY")
    if not item or action == "REPORT_ONLY":
        report = {"ok": True, "generated": False, "updated_existing": False, "reason": selected_payload.get("reason", "생성 대상이 없습니다.")}
        if not args.dry_run:
            write_json(generation_report_path(date_value), report)
        log(report["reason"])
        return 0
    post_data = build_post_data(item, date_value, action, write_assets=not args.dry_run)
    post_path, created = write_post(post_data, action, args.dry_run)
    report = {
        "ok": True,
        "generated": bool(created and not args.dry_run),
        "updated_existing": bool((not created) and action == "UPDATE_EXISTING" and not args.dry_run),
        "dry_run": args.dry_run,
        "action": action,
        "post": repo_path(post_path),
        "slug": post_data["slug"],
        "release_channel": item.get("release_channel"),
    }
    if not args.dry_run:
        write_json(generation_report_path(date_value), report)
    log(f"글 처리 결과: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
