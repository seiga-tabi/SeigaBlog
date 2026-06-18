#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from bedrock_common import (
    DEFAULT_IMAGE,
    IMAGE_DIR,
    POSTS_DIR,
    RELEASES_DIR,
    classified_items_path,
    extract_scalar,
    existing_bedrock_posts_by_slug,
    generation_report_path,
    now_iso,
    read_json_default,
    render_post,
    safe_slug,
    selected_topic_path,
    today_string,
    write_json,
)


CHANNEL_TITLE = {
    "bedrock_stable_release": {"ko": "[Bedrock 정식 업데이트]", "ja": "[Bedrock正式アップデート]"},
    "bedrock_hotfix": {"ko": "[Bedrock 핫픽스]", "ja": "[Bedrockホットフィックス]"},
    "bedrock_beta": {"ko": "[Bedrock 베타]", "ja": "[Bedrockベータ]"},
    "bedrock_preview": {"ko": "[Bedrock 프리뷰]", "ja": "[Bedrockプレビュー]"},
    "bedrock_official_announcement": {"ko": "[Bedrock 공식 발표]", "ja": "[Bedrock公式発表]"},
    "bedrock_official_planned": {"ko": "[Bedrock 개발 예정]", "ja": "[Bedrock開発予定]"},
    "bedrock_platform_specific": {"ko": "[플랫폼 한정]", "ja": "[プラットフォーム限定]"},
}

CHANNEL_LABEL = {
    "bedrock_stable_release": {"ko": "Bedrock 정식 업데이트", "ja": "Bedrock正式アップデート"},
    "bedrock_hotfix": {"ko": "Bedrock 핫픽스", "ja": "Bedrockホットフィックス"},
    "bedrock_beta": {"ko": "Bedrock 베타", "ja": "Bedrockベータ"},
    "bedrock_preview": {"ko": "Bedrock 프리뷰", "ja": "Bedrockプレビュー"},
    "bedrock_official_announcement": {"ko": "Bedrock 공식 발표", "ja": "Bedrock公式発表"},
    "bedrock_official_planned": {"ko": "Bedrock 개발 예정", "ja": "Bedrock開発予定"},
    "bedrock_platform_specific": {"ko": "플랫폼 한정", "ja": "プラットフォーム限定"},
}


def log(message: str) -> None:
    print(f"[Minecraft Bedrock Generate] {message}")


def localized_title(item: dict[str, Any]) -> dict[str, str]:
    channel = item.get("release_channel")
    prefix = CHANNEL_TITLE.get(channel, CHANNEL_TITLE["bedrock_official_announcement"])
    version = item.get("version") or ""
    if channel == "bedrock_stable_release":
        ko = f"{prefix['ko']} Minecraft Bedrock Edition {version} 핵심 변경점".strip()
        ja = f"{prefix['ja']} Minecraft Bedrock Edition {version} 主な変更点".strip()
    elif channel == "bedrock_hotfix":
        ko = f"{prefix['ko']} Minecraft Bedrock Edition {version} 수정 내용".strip()
        ja = f"{prefix['ja']} Minecraft Bedrock Edition {version} 修正内容".strip()
    elif channel in {"bedrock_beta", "bedrock_preview"}:
        ko = f"{prefix['ko']} Minecraft Beta & Preview {version} 테스트 변경점".strip()
        ja = f"{prefix['ja']} Minecraft Beta & Preview {version} テスト変更点".strip()
    else:
        source_title = item.get("source", {}).get("title", "Minecraft Bedrock Edition 공식 발표")
        ko = f"{prefix['ko']} {source_title}"
        ja = f"{prefix['ja']} {source_title}"
    return {"ko": ko.replace("  ", " "), "ja": ja.replace("  ", " ")}


def section(section_id: str, title_ko: str, title_ja: str, body_ko: list[str], body_ja: list[str] | None = None, kind: str = "text") -> dict[str, Any]:
    body_ja = body_ja or body_ko
    return {
        "id": section_id,
        "kind": kind,
        "title": {"ko": title_ko, "ja": title_ja},
        "body": {"ko": body_ko, "ja": body_ja},
    }


def fallback_platform_note(item: dict[str, Any]) -> list[str]:
    if item.get("supported_platforms"):
        joined = ", ".join(item["supported_platforms"])
        return [f"공식 원문에서 확인된 플랫폼 단서: {joined}"]
    return ["플랫폼별 배포 상태는 공식 원문에서 추가 확인이 필요합니다."]


def build_sections(item: dict[str, Any]) -> list[dict[str, Any]]:
    channel = item.get("release_channel")
    sections = [
        section(
            "quick-summary",
            "3줄 요약",
            "3行要約",
            [
                item.get("summary", {}).get("ko", "공식 원문에서 확인된 Bedrock 정보만 정리했습니다."),
                "원문에 없는 플랫폼, Realms, Add-On 호환성은 추측하지 않았습니다.",
                "Java Edition 항목은 이 글의 범위에서 제외했습니다.",
            ],
            [
                item.get("summary", {}).get("ja", "公式原文で確認できたBedrock情報のみ整理しました。"),
                "原文にないプラットフォーム、Realms、Add-On互換性は推測していません。",
                "Java Edition項目はこの記事の対象外です。",
            ],
            "quick_summary",
        ),
        section(
            "release-status",
            "버전 및 배포 상태",
            "バージョンと配信状態",
            [
                f"분류: {CHANNEL_LABEL.get(channel, CHANNEL_LABEL['bedrock_official_announcement'])['ko']}",
                f"버전: {item.get('version') or '공식 원문에서 추가 확인 필요'}",
                f"대표 출처: {item.get('source', {}).get('title', '')}",
            ],
            [
                f"分類: {CHANNEL_LABEL.get(channel, CHANNEL_LABEL['bedrock_official_announcement'])['ja']}",
                f"バージョン: {item.get('version') or '公式原文で追加確認が必要'}",
                f"代表出典: {item.get('source', {}).get('title', '')}",
            ],
        ),
    ]
    if channel in {"bedrock_beta", "bedrock_preview"}:
        sections.insert(
            0,
            section(
                "preview-warning",
                "Beta/Preview 경고",
                "Beta/Preview注意",
                ["이 글은 정식 업데이트가 아닌 테스트 채널 변경점입니다. 정식판 적용 여부와 시점은 원문에서 확정된 경우에만 기록합니다."],
                ["この記事は正式アップデートではなく、テストチャンネルの変更点です。正式版への適用有無と時期は原文で確定している場合のみ記録します。"],
            ),
        )
    section_map = [
        ("added", "새로 추가된 기능", "新しく追加された内容"),
        ("changed", "변경된 기능", "変更された内容"),
        ("fixed", "주요 버그 수정", "主な不具合修正"),
        ("experimental_features", "실험 기능", "実験機能"),
        ("platform_changes", "플랫폼별 변경", "プラットフォーム別変更"),
        ("touch_control_changes", "터치 조작 변경", "タッチ操作の変更"),
        ("realms_changes", "Realms 관련 변경", "Realms関連の変更"),
        ("add_on_changes", "Add-On 및 Creator 변경", "Add-On・Creator関連の変更"),
        ("technical_changes", "기술 변경", "技術的変更"),
        ("known_issues", "알려진 문제", "既知の問題"),
    ]
    for key, title_ko, title_ja in section_map:
        values = item.get(key, [])
        if values:
            sections.append(section(key.replace("_", "-"), title_ko, title_ja, values))
    sections.append(section("platform-check", "플랫폼 확인", "プラットフォーム確認", fallback_platform_note(item)))
    sections.append(
        section(
            "official-source",
            "공식 출처",
            "公式出典",
            [f"{item.get('source', {}).get('title', '')}: {item.get('source', {}).get('canonical_url', '')}"],
        )
    )
    sections.append(section("last-checked", "마지막 확인 시각", "最終確認時刻", [item.get("source", {}).get("last_verified_at", now_iso())]))
    return sections


def read_time(sections: list[dict[str, Any]]) -> str:
    text = " ".join(paragraph for section_item in sections for paragraph in section_item.get("body", {}).get("ko", []))
    return f"{max(3, (len(text) + 399) // 400)} min"


def tracker_slug(item: dict[str, Any], date_value: str) -> str:
    target = item.get("target_stable_version")
    if target:
        return f"minecraft-bedrock-{safe_slug(target, target)}-preview-tracker"
    return f"minecraft-bedrock-preview-tracker-{date_value[:4]}"


def post_slug(item: dict[str, Any], date_value: str, action: str) -> str:
    if action == "UPDATE_EXISTING":
        return tracker_slug(item, date_value)
    version = safe_slug(item.get("version", ""), "")
    if not version:
        version = safe_slug(item.get("source", {}).get("title", ""), item.get("id", "latest"))[:48]
    return f"minecraft-bedrock-{version}-summary"


def write_summary_image(slug: str, title: dict[str, str], dry_run: bool) -> str:
    path = IMAGE_DIR / f"{slug}-summary.svg"
    rel = f"/assets/images/minecraft/bedrock/{path.name}"
    if dry_run:
        return rel
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
  <rect width="1200" height="675" fill="#eaf5ff"/>
  <rect x="72" y="72" width="1056" height="531" rx="28" fill="#ffffff" stroke="#d8e3ee"/>
  <text x="108" y="164" font-family="Arial, sans-serif" font-size="38" font-weight="700" fill="#15171c">Minecraft Bedrock Edition</text>
  <text x="108" y="235" font-family="Arial, sans-serif" font-size="30" fill="#2f855a">{title['ko'][:54]}</text>
  <text x="108" y="307" font-family="Arial, sans-serif" font-size="24" fill="#53606f">Official source based · Korean / Japanese</text>
  <circle cx="980" cy="330" r="118" fill="#39b887" opacity="0.18"/>
  <rect x="900" y="260" width="160" height="160" rx="18" fill="#39b887"/>
  <rect x="932" y="292" width="96" height="96" rx="12" fill="#ffffff" opacity="0.9"/>
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    return rel


def build_post_data(item: dict[str, Any], date_value: str, action: str, dry_run: bool) -> dict[str, Any]:
    slug = post_slug(item, date_value, action)
    title = localized_title(item)
    sections = build_sections(item)
    image = write_summary_image(slug, title, dry_run)
    label = CHANNEL_LABEL.get(item.get("release_channel"), CHANNEL_LABEL["bedrock_official_announcement"])
    source = item.get("source", {})
    post_data = {
        "slug": slug,
        "category": "minecraft",
        "content_type": "minecraft_bedrock_update",
        "edition": "bedrock",
        "release_channel": item.get("release_channel"),
        "minecraft_version": item.get("version") or None,
        "release_name": item.get("release_name"),
        "accent": "green",
        "read_time": read_time(sections),
        "image": image,
        "og_image": image,
        "date": date_value,
        "last_modified_at": now_iso(),
        "source_url": source.get("canonical_url"),
        "source_title": source.get("title"),
        "source_published_at": source.get("published_at"),
        "last_checked": source.get("last_verified_at"),
        "information_status": {
            "code": item.get("release_channel"),
            "label": label,
            "notice": {
                "ko": "Mojang Studios 공식 원문에서 확인된 Bedrock Edition 정보입니다.",
                "ja": "Mojang Studios公式原文で確認したBedrock Edition情報です。",
            },
        },
        "sources": [
            {
                "url": source.get("canonical_url"),
                "title": source.get("title"),
                "publisher": source.get("publisher", "Mojang Studios"),
                "published_at": source.get("published_at"),
                "last_verified_at": source.get("last_verified_at"),
            }
        ],
        "supported_platforms": item.get("supported_platforms", []),
        "author": {"ko": "세이가", "ja": "セイガ"},
        "badge": {"ko": "Minecraft", "ja": "Minecraft"},
        "title": title,
        "description": f"{title['ko']} - Mojang 공식 원문을 기준으로 Bedrock Edition 변경점만 정리했습니다.",
        "excerpt": item.get("summary"),
        "post_tags": {
            "ko": ["Minecraft", "Bedrock", "마인크래프트", "패치노트"],
            "ja": ["Minecraft", "Bedrock", "マインクラフト", "パッチノート"],
        },
        "lead": {
            "ko": "이 글은 Minecraft Bedrock Edition 공식 원문을 구조화한 뒤, Java Edition 항목과 추측 정보를 제외하고 작성했습니다.",
            "ja": "この記事はMinecraft Bedrock Edition公式原文を構造化し、Java Edition項目と推測情報を除外して作成しています。",
        },
        "body": {
            "ko": ["아래 내용은 원문에서 확인된 Bedrock Edition 정보만 요약한 것입니다."],
            "ja": ["以下は原文で確認できたBedrock Edition情報のみを要約したものです。"],
        },
        "summary_image": {
            "src": {"ko": image, "ja": image},
            "width": 1200,
            "height": 675,
            "alt": {"ko": f"{title['ko']} 요약 이미지", "ja": f"{title['ja']} 要約画像"},
            "caption": {"ko": "공식 원문 기반 Bedrock 업데이트 요약입니다.", "ja": "公式原文に基づくBedrockアップデート要約です。"},
        },
        "content_images": [
            {
                "after_section": "quick-summary",
                "src": {"ko": image, "ja": image},
                "width": 1200,
                "height": 675,
                "alt": {"ko": f"{title['ko']} 요약 이미지", "ja": f"{title['ja']} 要約画像"},
                "caption": {"ko": "외부 이미지를 hotlink하지 않고 로컬 SVG를 사용합니다.", "ja": "外部画像をhotlinkせず、ローカルSVGを使用します。"},
            }
        ],
        "toc": {"title": {"ko": "목차", "ja": "目次"}, "items": [{"id": section_item["id"], "title": section_item["title"]} for section_item in sections]},
        "overview_table": {
            "title": {"ko": "업데이트 정보", "ja": "アップデート情報"},
            "rows": [
                {"label": {"ko": "에디션", "ja": "エディション"}, "value": {"ko": "Bedrock Edition", "ja": "Bedrock Edition"}},
                {"label": {"ko": "분류", "ja": "分類"}, "value": label},
                {"label": {"ko": "버전", "ja": "バージョン"}, "value": {"ko": item.get("version") or "원문 추가 확인 필요", "ja": item.get("version") or "原文で追加確認が必要"}},
                {"label": {"ko": "마지막 확인", "ja": "最終確認"}, "value": {"ko": source.get("last_verified_at"), "ja": source.get("last_verified_at")}},
            ],
        },
        "sections": sections,
        "update_history": [
            {
                "date": date_value,
                "status_from": None,
                "status_to": item.get("release_channel"),
                "summary": {"ko": "Bedrock 자동 수집 파이프라인에서 공식 원문을 확인했습니다.", "ja": "Bedrock自動収集パイプラインで公式原文を確認しました。"},
            }
        ],
        "quote": {"ko": "Bedrock 글은 공식 원문에 없는 플랫폼과 호환성 정보를 추측하지 않습니다.", "ja": "Bedrock記事では公式原文にないプラットフォームや互換性情報を推測しません。"},
    }
    return post_data


def existing_date_from_path(path: Path) -> str | None:
    frontmatter_parts = path.read_text(encoding="utf-8", errors="ignore").split("---", 2)
    if len(frontmatter_parts) >= 3:
        date_value = extract_scalar(frontmatter_parts[1], "date")
        if date_value:
            return date_value[:10]
    name_date = path.name[:10]
    return name_date if len(name_date) == 10 else None


def write_post(post_data: dict[str, Any], dry_run: bool, action: str) -> Path:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    existing_path = existing_bedrock_posts_by_slug().get(post_data["slug"])
    path = POSTS_DIR / f"{post_data['date']}-{post_data['slug']}.md"
    if existing_path and existing_path != path:
        if action != "UPDATE_EXISTING":
            raise FileExistsError(f"이미 같은 Bedrock slug가 있습니다: {post_data['slug']}")
        original_date = existing_date_from_path(existing_path)
        if original_date:
            post_data["date"] = original_date
        path = existing_path
    if not dry_run:
        path.write_text(render_post(post_data), encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="선택된 Bedrock 구조화 JSON으로 Jekyll 글을 생성합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="글 파일과 이미지를 쓰지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    selected_payload = read_json_default(selected_topic_path(date_value), {"selected": {"should_generate": False, "reason": "선택 결과가 없습니다."}})
    classified = read_json_default(classified_items_path(date_value), {"items": []})
    selected = selected_payload.get("selected", {})
    generated = False
    post_path: Path | None = None
    reason = selected.get("reason", "")
    action = selected.get("action", "REPORT_ONLY")

    if selected.get("should_generate"):
        item = next((value for value in classified.get("items", []) if value.get("id") == selected.get("item_id")), None)
        if not item:
            reason = "선택된 item을 찾지 못했습니다."
        else:
            try:
                post_data = build_post_data(item, date_value, action, args.dry_run)
                post_path = write_post(post_data, args.dry_run, action)
                if not args.dry_run:
                    write_json(RELEASES_DIR / f"{post_data['slug']}.json", item)
                generated = not args.dry_run
                reason = reason or "Bedrock 글을 생성했습니다."
            except FileExistsError as error:
                reason = str(error)
    report = {
        "ok": True,
        "date": date_value,
        "dry_run": args.dry_run,
        "generated": generated,
        "action": action,
        "reason": reason,
        "post": str(post_path.relative_to(POSTS_DIR.parent)) if post_path else "",
        "selected_item_id": selected.get("item_id"),
    }
    write_json(generation_report_path(date_value), report)
    if generated:
        log(f"게시글 생성: {report['post']}")
    else:
        log(f"글을 생성하지 않았습니다: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
