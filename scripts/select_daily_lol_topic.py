#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from typing import Any

from lol_daily_intel import (
    REPO_ROOT,
    claims_path,
    ensure_intel_tree,
    localized,
    normalized_items_path,
    publication_allowed,
    read_json_default,
    score_claim,
    selected_topic_path,
    today_string,
    now_iso,
    write_daily_markdown_report,
    write_json,
)


def log(message: str) -> None:
    print(f"[LoL Intel Select] {message}")


def candidate_reason(claim: dict[str, Any], score: dict[str, int]) -> str:
    if claim.get("duplicate", {}).get("is_duplicate"):
        return "기존 글 또는 이전 claim과 중복입니다."
    if claim.get("status") == "rumor":
        return "루머 단독 정보는 공개 글 후보가 아닙니다."
    if not publication_allowed(claim.get("status", ""), len(claim.get("corroborating_sources", []))):
        return "상태별 발행 정책상 단독 글 생성 대상이 아닙니다."
    if score["total"] < 55:
        return "점수가 55점 미만입니다."
    return "발행 후보입니다."


def select(claims: list[dict[str, Any]], force_generate: bool = False) -> dict[str, Any]:
    scored = []
    for claim in claims:
        score = score_claim(claim)
        scored.append({**claim, "score": score, "selection_reason": candidate_reason(claim, score)})
    scored.sort(key=lambda item: item["score"]["total"], reverse=True)

    eligible = [
        item
        for item in scored
        if not item.get("duplicate", {}).get("is_duplicate")
        and item.get("product") == "lol_pc"
        and item.get("status") != "rumor"
        and publication_allowed(item.get("status", ""), len(item.get("corroborating_sources", [])))
    ]
    threshold = 55 if force_generate else 75

    if not eligible:
        return {
            "should_generate": False,
            "action": "report_only",
            "selection_type": "none",
            "selected_claim_ids": [],
            "reason": "중복이 아니면서 발행 정책을 통과한 후보가 없습니다.",
            "candidates": scored,
        }

    top = eligible[0]
    if top["score"]["total"] >= threshold:
        action = "patch_post" if top.get("status") == "confirmed" and top.get("content_category") == "patch" else "daily_post"
        return {
            "should_generate": True,
            "action": action,
            "selection_type": "single_topic",
            "selected_claim_ids": [top["claim_id"]],
            "score": top["score"],
            "reason": f"최상위 후보가 {top['score']['total']}점으로 기준을 충족했습니다.",
            "candidates": scored,
        }

    briefing_candidates = [item for item in eligible if item["score"]["total"] >= 55]
    if len(briefing_candidates) >= 2:
        selected = briefing_candidates[:4]
        return {
            "should_generate": True,
            "action": "daily_post",
            "selection_type": "daily_briefing",
            "selected_claim_ids": [item["claim_id"] for item in selected],
            "score": {"total": max(item["score"]["total"] for item in selected)},
            "reason": "55점 이상 공식성 후보가 2개 이상이어서 일일 브리핑으로 묶습니다.",
            "candidates": scored,
        }

    return {
        "should_generate": False,
        "action": "report_only",
        "selection_type": "none",
        "selected_claim_ids": [],
        "reason": "최고 점수가 글 생성 기준에 미달했습니다.",
        "candidates": scored,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오늘 작성할 LoL 정보 주제를 선택합니다.")
    parser.add_argument("--date", help="대상 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--force-generate", action="store_true", help="55점 이상 후보를 글 생성 대상으로 허용합니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일 저장 없이 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_intel_tree()
    date_value = today_string(args.date)
    claim_payload = read_json_default(claims_path(date_value), {"claims": [], "checked_sources": [], "failures": []})
    normalized = read_json_default(normalized_items_path(date_value), {"items": []})
    claims = claim_payload.get("claims", [])
    selected = select(claims, args.force_generate)
    status_counts = Counter(claim.get("status") for claim in claims)
    duplicates = [
        {
            "claim_id": claim.get("claim_id"),
            "title": claim.get("source_title") or localized(claim.get("topic"), "ko"),
            "reason": ", ".join(claim.get("duplicate", {}).get("reasons", [])) or "중복",
        }
        for claim in claims
        if claim.get("duplicate", {}).get("is_duplicate")
    ]
    payload = {
        "ok": True,
        "date": date_value,
        **selected,
        "status_counts": dict(status_counts),
    }
    report_payload = {
        "run_started_at": now_iso(),
        "checked_sources": claim_payload.get("checked_sources", []),
        "new_items": [item for item in normalized.get("items", []) if not item.get("duplicate", {}).get("is_duplicate")],
        "duplicates": duplicates,
        "status_counts": dict(status_counts),
        "candidates": selected.get("candidates", []),
        "selected": selected,
        "generated": {"generated": False, "reason": selected.get("reason")},
        "failures": claim_payload.get("failures", []),
        "revalidate": claims,
    }

    if args.dry_run:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        output_path = selected_topic_path(date_value)
        write_json(output_path, payload)
        report_path = write_daily_markdown_report(date_value, report_payload)
        log(f"선택 결과 저장: {output_path.relative_to(REPO_ROOT)}")
        log(f"일일 리포트 저장: {report_path.relative_to(REPO_ROOT)}")
        log(payload["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
