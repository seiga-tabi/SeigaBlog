#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

from lol_daily_intel import (
    DEFAULT_IMAGE,
    REPO_ROOT,
    STATUS_ORDER,
    category_label,
    claims_path,
    generation_report_path,
    localized,
    now_iso,
    normalized_items_path,
    read_json_default,
    read_time,
    render_post,
    safe_slug,
    selected_topic_path,
    status_meta,
    today_string,
    write_daily_markdown_report,
    write_json,
)


POSTS_DIR = REPO_ROOT / "_posts"
GENERATED_DATA_DIR = REPO_ROOT / "data" / "lol" / "generated"


def log(message: str) -> None:
    print(f"[LoL Daily Post] {message}")


def selected_claims(date_value: str, selected: dict[str, Any]) -> list[dict[str, Any]]:
    claims = read_json_default(claims_path(date_value), {"claims": []}).get("claims", [])
    wanted = set(selected.get("selected_claim_ids", []))
    return [claim for claim in claims if claim.get("claim_id") in wanted]


def representative_status(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "rumor"
    return max((claim.get("status", "rumor") for claim in claims), key=lambda status: STATUS_ORDER.get(status, -1))


def title_for(claims: list[dict[str, Any]], selection_type: str) -> dict[str, str]:
    status = representative_status(claims)
    meta = status_meta(status)
    if selection_type == "daily_briefing":
        ko = "오늘의 LoL 개발 소식｜공식 예정·PBE·검토 중 정보 정리"
        ja = "今日のLoL開発ニュース｜公式予定・PBE・検討中情報まとめ"
    else:
        claim = claims[0]
        category = category_label(claim.get("content_category", "other"))
        patch = claim.get("expected_patch")
        if patch:
            ko = f"LoL {patch} {category['ko']} 정보 정리"
            ja = f"LoL {patch} {category['ja']}情報まとめ"
        else:
            ko = f"LoL {category['ko']} 정보 정리"
            ja = f"LoL {category['ja']}情報まとめ"
    return {"ko": f"{meta['prefix']['ko']}{ko}", "ja": f"{meta['prefix']['ja']}{ja}"}


def overview_rows(claims: list[dict[str, Any]]) -> list[dict[str, dict[str, str]]]:
    status = representative_status(claims)
    first = claims[0]
    source = first.get("primary_source", {})
    return [
        {"label": {"ko": "정보 상태", "ja": "情報ステータス"}, "value": status_meta(status)["label"]},
        {"label": {"ko": "콘텐츠 범위", "ja": "対象範囲"}, "value": {"ko": "PC 리그 오브 레전드", "ja": "PC版リーグ・オブ・レジェンド"}},
        {"label": {"ko": "주제 수", "ja": "トピック数"}, "value": {"ko": f"{len(claims)}건", "ja": f"{len(claims)}件"}},
        {"label": {"ko": "대표 출처", "ja": "代表ソース"}, "value": {"ko": source.get("publisher", "Riot Games"), "ja": "Riot Games"}},
        {"label": {"ko": "공식 게시일", "ja": "公式公開日"}, "value": {"ko": source.get("published_at", ""), "ja": source.get("published_at", "")}},
        {"label": {"ko": "마지막 확인", "ja": "最終確認"}, "value": {"ko": now_iso(), "ja": now_iso()}},
    ]


def quick_summary_items(claims: list[dict[str, Any]]) -> list[dict[str, dict[str, str]]]:
    items = []
    for claim in claims[:3]:
        category = category_label(claim.get("content_category", "other"))
        status = status_meta(claim.get("status", "rumor"))["label"]
        items.append(
            {
                "label": {"ko": category["ko"], "ja": category["ja"]},
                "body": {
                    "ko": f"{status['ko']} 상태로 확인된 정보입니다.",
                    "ja": f"{status['ja']}として確認した情報です。",
                },
            }
        )
    if not items:
        items.append({"label": {"ko": "확인 결과", "ja": "確認結果"}, "body": {"ko": "새 글을 만들 정보가 없습니다.", "ja": "新規記事にする情報はありません。"}})
    return items


def section(section_id: str, title_ko: str, title_ja: str, body_ko: list[str], body_ja: list[str], kind: str = "text") -> dict[str, Any]:
    return {
        "id": section_id,
        "kind": kind,
        "title": {"ko": title_ko, "ja": title_ja},
        "body": {"ko": body_ko or ["확인된 내용만 정리합니다."], "ja": body_ja or ["確認できた内容のみ整理します。"]},
    }


def build_sections(claims: list[dict[str, Any]], selection_type: str) -> list[dict[str, Any]]:
    confirmed_ko = []
    confirmed_ja = []
    pending_ko = []
    pending_ja = []
    source_context_ko = []
    source_context_ja = []
    schedule_ko = []
    schedule_ja = []

    for claim in claims:
        status = claim.get("status", "rumor")
        status_name = status_meta(status)["label"]
        topic_ko = localized(claim.get("topic"), "ko")
        topic_ja = localized(claim.get("topic"), "ja")
        if status in {"confirmed", "official_scheduled"}:
            confirmed_ko.append(f"{topic_ko}: {localized(claim.get('claim'), 'ko')}")
            confirmed_ja.append(f"{topic_ja}: {localized(claim.get('claim'), 'ja')}")
        else:
            pending_ko.append(f"{topic_ko}: {status_name['ko']} 상태이므로 실제 적용 전까지 바뀔 수 있습니다.")
            pending_ja.append(f"{topic_ja}: {status_name['ja']}のため、実際の適用前に変わる可能性があります。")
        source = claim.get("primary_source", {})
        source_context_ko.append(f"{source.get('publisher', 'Riot Games')} 출처를 기준으로 확인했습니다.")
        source_context_ja.append("Riot Gamesのソースを基準に確認しました。")
        if claim.get("expected_patch") or claim.get("expected_date"):
            schedule_ko.append(f"확인된 적용 단서: {claim.get('expected_patch') or claim.get('expected_date')}")
            schedule_ja.append(f"確認できた適用手がかり: {claim.get('expected_patch') or claim.get('expected_date')}")

    if selection_type == "daily_briefing":
        return [
            section("quick-summary", "오늘의 3줄 요약", "今日の3行要約", ["공식성과 상태가 확인된 정보만 일일 브리핑으로 묶었습니다."], ["公式性と状態を確認できた情報のみをデイリーブリーフィングにまとめました。"], "quick_summary"),
            section("status-overview", "정보 상태별 한눈에 보기", "情報ステータス早見表", [f"{len(claims)}개 claim을 상태별로 나누어 확인했습니다."], [f"{len(claims)}件のclaimをステータス別に確認しました。"]),
            section("official-confirmed", "공식 확정 및 예정", "公式確定・予定", confirmed_ko, confirmed_ja),
            section("development", "개발 중 및 검토 중", "開発中・検討中", pending_ko, pending_ja),
            section("pbe-testing", "PBE 테스트", "PBEテスト", [item for item in pending_ko if "PBE" in item] or ["PBE 단독 정보는 확정처럼 표현하지 않았습니다."], [item for item in pending_ja if "PBE" in item] or ["PBE単独情報は確定として扱っていません。"]),
            section("reported", "보도 및 미확인 정보", "報道・未確認情報", ["루머 단독 정보는 공개 글 후보에서 제외했습니다."], ["噂単独の情報は公開記事候補から除外しました。"]),
            section("key-checkpoint", "오늘 가장 중요한 체크 포인트", "今日の重要チェックポイント", ["공식 사실과 해석을 분리해서 다음 발표를 재검증합니다."], ["公式事実と解釈を分け、次の発表で再検証します。"]),
            section("source-note", "출처", "出典", source_context_ko, source_context_ja, "source_note"),
            section("faq", "FAQ", "FAQ", ["FAQ는 아래 카드에서 확인하세요."], ["FAQは下のカードで確認してください。"], "faq"),
        ]

    return [
        section("quick-summary", "3줄 요약", "3行要約", ["확인된 출처와 정보 상태를 먼저 분리했습니다."], ["確認できたソースと情報ステータスを先に分けました。"], "quick_summary"),
        section("confirmed-facts", "현재 확인된 사실", "現在確認できた事実", confirmed_ko or [localized(claims[0].get("claim"), "ko")], confirmed_ja or [localized(claims[0].get("claim"), "ja")]),
        section("not-confirmed", "아직 확정되지 않은 내용", "まだ確定していない内容", pending_ko or ["원문에 없는 날짜, 패치 번호, 수치는 추가하지 않았습니다."], pending_ja or ["原文にない日付、パッチ番号、数値は追加していません。"]),
        section("source-context", "원문과 발표 맥락", "原文と発表文脈", source_context_ko, source_context_ja),
        section("expected-timing", "적용 예정 시점", "適用予定時期", schedule_ko or ["원문에서 적용 시점이 확인되지 않으면 추정하지 않습니다."], schedule_ja or ["原文で適用時期が確認できない場合は推測しません。"]),
        section("gameplay-watch", "실제 게임에서 주목할 점", "実際のゲームで注目する点", ["이 부분은 공식 사실이 아니라, 확인된 정보에서 분리한 초기 해석입니다."], ["この部分は公式事実ではなく、確認済み情報から分けた初期解釈です。"]),
        section("change-risk", "변경될 가능성이 있는 부분", "変更される可能性がある部分", ["미확정 상태의 수치와 일정은 다음 공식 발표에서 달라질 수 있습니다."], ["未確定状態の数値や日程は次の公式発表で変わる可能性があります。"]),
        section("next-check", "앞으로 확인해야 할 정보", "今後確認すべき情報", ["다음 실행에서 같은 claim의 상태 변화를 다시 확인합니다."], ["次回実行で同じclaimのステータス変化を再確認します。"]),
        section("source-note", "출처", "出典", source_context_ko, source_context_ja, "source_note"),
        section("faq", "FAQ", "FAQ", ["FAQ는 아래 카드에서 확인하세요."], ["FAQは下のカードで確認してください。"], "faq"),
    ]


def source_notes(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notes = []
    for index, claim in enumerate(claims, start=1):
        source = claim.get("primary_source", {})
        notes.append(
            {
                "label": {"ko": f"대표 출처 {index}", "ja": f"代表ソース {index}"},
                "body": {
                    "ko": f"{source.get('publisher', 'Riot Games')} · 게시일 {source.get('published_at', '')} · 마지막 확인 {source.get('fetched_at', '')}",
                    "ja": f"Riot Games · 公開日 {source.get('published_at', '')} · 最終確認 {source.get('fetched_at', '')}",
                },
                "url": source.get("url", ""),
            }
        )
    return notes


def faq_items(status: str) -> list[dict[str, Any]]:
    meta = status_meta(status)
    return [
        {
            "question": {"ko": "이 정보는 확정인가요?", "ja": "この情報は確定ですか？"},
            "answer": {"ko": meta["notice"]["ko"], "ja": meta["notice"]["ja"]},
        },
        {
            "question": {"ko": "원문에 없는 날짜나 수치도 보강했나요?", "ja": "原文にない日付や数値も補っていますか？"},
            "answer": {"ko": "아니요. 원문과 구조화 claim에 없는 값은 추가하지 않습니다.", "ja": "いいえ。原文と構造化claimにない値は追加しません。"},
        },
        {
            "question": {"ko": "루머도 자동 공개하나요?", "ja": "噂も自動公開しますか？"},
            "answer": {"ko": "아니요. 루머 단독 정보는 공개 PR 대상에서 제외합니다.", "ja": "いいえ。噂単独の情報は公開PR対象から除外します。"},
        },
    ]


def build_post_data(date_value: str, selected: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    selection_type = selected.get("selection_type", "single_topic")
    status = representative_status(claims)
    title = title_for(claims, selection_type)
    slug_base = safe_slug(localized(title, "ko"), f"lol-daily-{date_value}")
    slug = f"lol-daily-{date_value}-{slug_base[:36].strip('-')}"
    first = claims[0]
    source = first.get("primary_source", {})
    sections = build_sections(claims, selection_type)
    summary_src = {
        "ko": f"/assets/images/blog/generated/{slug}-core-notes-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-core-notes-ja.svg",
    }
    post_data: dict[str, Any] = {
        "slug": slug,
        "category": "lol",
        "content_type": "lol-daily-intel",
        "accent": "blue",
        "read_time": "3 min",
        "image": DEFAULT_IMAGE,
        "og_image": DEFAULT_IMAGE,
        "date": date_value,
        "last_checked": now_iso(),
        "description": f"{title['ko']} - 공식 출처와 정보 상태를 분리해 정리했습니다.",
        "categories": ["League of Legends", "Daily Intel"],
        "tags": ["롤", "리그오브레전드", "LoL", "일일정보", "Riot"],
        "author": {"ko": "세이가", "ja": "セイガ"},
        "badge": {"ko": "LoL 인텔", "ja": "LoLインテル"},
        "title": title,
        "excerpt": {
            "ko": "Riot 공식 출처와 claim 상태를 기준으로 오늘 공개할 가치가 있는 LoL 정보를 정리했습니다.",
            "ja": "Riot公式ソースとclaimステータスを基準に、今日公開する価値のあるLoL情報を整理しました。",
        },
        "post_tags": {"ko": ["롤", "LoL", "Riot", "정보 상태"], "ja": ["LoL", "Riot", "情報ステータス"]},
        "lead": {
            "ko": "공식 사실, 개발 중 정보, PBE, 보도, 루머를 분리해 원문에 없는 값은 보태지 않았습니다.",
            "ja": "公式事実、開発中情報、PBE、報道、噂を分け、原文にない値は補っていません。",
        },
        "body": {
            "ko": ["이 글은 일일 수집 파이프라인이 구조화한 claim을 바탕으로 생성했습니다."],
            "ja": ["この記事はデイリー収集パイプラインが構造化したclaimをもとに生成しています。"],
        },
        "information_status": {
            "code": status,
            "label": status_meta(status)["label"],
            "notice": status_meta(status)["notice"],
        },
        "source_url": source.get("url", ""),
        "source_title": first.get("source_title") or localized(first.get("topic"), "ko"),
        "source_published_at": source.get("published_at", ""),
        "sources": [
            {
                "url": claim.get("primary_source", {}).get("url", ""),
                "title": claim.get("source_title", ""),
                "publisher": claim.get("primary_source", {}).get("publisher", "Riot Games"),
                "author": claim.get("primary_source", {}).get("author", ""),
                "published_at": claim.get("primary_source", {}).get("published_at", ""),
                "last_verified_at": claim.get("last_verified_at", ""),
                "source_tier": claim.get("primary_source", {}).get("tier", 1),
            }
            for claim in claims
        ],
        "update_history": [
            {
                "date": date_value,
                "status_from": None,
                "status_to": status,
                "summary": {
                    "ko": "일일 수집 파이프라인에서 새 claim으로 확인했습니다.",
                    "ja": "デイリー収集パイプラインで新しいclaimとして確認しました。",
                },
            }
        ],
        "claim_fingerprints": [claim.get("claim_fingerprint", "") for claim in claims],
        "toc": {"title": {"ko": "목차", "ja": "目次"}, "items": [{"id": item["id"], "title": item["title"]} for item in sections]},
        "overview_table": {"title": {"ko": "한눈에 보는 정보 상태", "ja": "情報ステータス早見表"}, "rows": overview_rows(claims)},
        "sections": sections,
        "quick_summary_items": quick_summary_items(claims),
        "summary_image": {
            "src": summary_src,
            "width": 1200,
            "height": 720,
            "alt": {"ko": "LoL 일일 정보 핵심 요약 이미지", "ja": "LoLデイリー情報要点画像"},
            "caption": {"ko": "상태와 출처를 기준으로 정리한 일일 요약입니다.", "ja": "ステータスとソースを基準に整理したデイリー要約です。"},
        },
        "content_images": [
            {
                "after_section": "quick-summary",
                "src": summary_src,
                "width": 1200,
                "height": 720,
                "alt": {"ko": "LoL 일일 정보 핵심 요약 이미지", "ja": "LoLデイリー情報要点画像"},
                "caption": {"ko": "상태와 출처를 기준으로 정리한 일일 요약입니다.", "ja": "ステータスとソースを基準に整理したデイリー要約です。"},
            }
        ],
        "source_notes": source_notes(claims),
        "faq": faq_items(status),
        "quote": {"ko": "확인되지 않은 정보는 확정처럼 쓰지 않는 것이 이 글의 기준입니다.", "ja": "確認できていない情報を確定のように書かないことが、この記事の基準です。"},
    }
    post_data["read_time"] = read_time(post_data)
    return post_data


def duplicate_post(slug: str) -> Path | None:
    if not POSTS_DIR.exists():
        return None
    for path in POSTS_DIR.glob("*.md"):
        if f"slug: {slug}" in path.read_text(encoding="utf-8", errors="ignore"):
            return path
    return None


def write_post(post_data: dict[str, Any], dry_run: bool) -> Path:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTS_DIR / f"{post_data['date']}-{post_data['slug']}.md"
    if duplicate_post(post_data["slug"]):
        raise FileExistsError(f"이미 같은 slug의 글이 있습니다: {post_data['slug']}")
    if not dry_run:
        path.write_text(render_post(post_data), encoding="utf-8")
        GENERATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        write_json(GENERATED_DATA_DIR / f"{post_data['slug']}.json", post_data)
    return path


def run_patch_generator(dry_run: bool, use_ai: bool) -> tuple[bool, str]:
    command = ["python3", "scripts/generate_lol_patch_post.py"]
    command.append("--use-ai" if use_ai else "--no-ai")
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output[-4000:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="선택된 LoL 일일 claim으로 SeigaBlog 글을 생성합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않습니다.")
    parser.add_argument("--use-ai", action="store_true", help="AI 문장 보강을 요청합니다. 현재 패치 생성기에만 전달합니다.")
    parser.add_argument("--no-ai", action="store_true", help="AI를 사용하지 않습니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    date_value = today_string(args.date)
    selected = read_json_default(selected_topic_path(date_value), {"should_generate": False, "reason": "선택 결과가 없습니다.", "action": "report_only"})
    claims = selected_claims(date_value, selected)
    generated = False
    post_path: Path | None = None
    reason = selected.get("reason", "")
    output = ""

    if not selected.get("should_generate"):
        reason = selected.get("reason", "글 생성 대상이 없습니다.")
    elif selected.get("action") == "patch_post":
        ok, output = run_patch_generator(args.dry_run, args.use_ai and not args.no_ai)
        if not ok:
            report = {"ok": False, "generated": False, "reason": "기존 패치 생성기 실행 실패", "output": output}
            write_json(generation_report_path(date_value), report)
            log("기존 패치 생성기가 실패했습니다.")
            return 1
        generated = not args.dry_run and "이미 작성된 패치 글" not in output
        reason = "공식 새 패치노트를 기존 패치 생성기로 처리했습니다."
    elif claims:
        try:
            post_data = build_post_data(date_value, selected, claims)
            post_path = write_post(post_data, args.dry_run)
            generated = not args.dry_run
            reason = selected.get("reason", "선택된 claim으로 일일 글을 생성했습니다.")
        except FileExistsError as error:
            reason = str(error)
            generated = False
    else:
        reason = "선택된 claim을 찾지 못했습니다."

    report = {
        "ok": True,
        "date": date_value,
        "generated": generated,
        "dry_run": args.dry_run,
        "action": selected.get("action"),
        "reason": reason,
        "post": str(post_path.relative_to(REPO_ROOT)) if post_path else "",
        "selected_claim_ids": selected.get("selected_claim_ids", []),
        "patch_generator_output": output,
    }
    write_json(generation_report_path(date_value), report)
    claim_payload = read_json_default(claims_path(date_value), {"claims": [], "checked_sources": [], "failures": [], "status_counts": {}})
    normalized = read_json_default(normalized_items_path(date_value), {"items": []})
    write_daily_markdown_report(
        date_value,
        {
            "run_started_at": now_iso(),
            "checked_sources": claim_payload.get("checked_sources", []),
            "new_items": [item for item in normalized.get("items", []) if not item.get("duplicate", {}).get("is_duplicate")],
            "duplicates": [item for item in normalized.get("items", []) if item.get("duplicate", {}).get("is_duplicate")],
            "status_counts": claim_payload.get("status_counts", {}),
            "candidates": selected.get("candidates", []),
            "selected": selected,
            "generated": report,
            "failures": claim_payload.get("failures", []),
            "revalidate": claim_payload.get("claims", []),
        },
    )
    if generated:
        log(f"게시글 생성: {post_path.relative_to(REPO_ROOT) if post_path else '기존 패치 생성기'}")
    else:
        log(f"글을 생성하지 않았습니다: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
