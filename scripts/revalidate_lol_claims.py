#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter

from lol_daily_intel import CLAIMS_DIR, INTEL_DAILY_DIR, REPO_ROOT, ensure_intel_tree, read_json_default, today_string, write_json


VALID_STATUSES = {
    "confirmed",
    "official_scheduled",
    "official_planned",
    "official_considering",
    "pbe_testing",
    "reported",
    "rumor",
    "rejected",
    "superseded",
}


def log(message: str) -> None:
    print(f"[LoL Intel Revalidate] {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="활성 LoL claim의 상태와 필수 필드를 재검증합니다.")
    parser.add_argument("--date", help="리포트 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_intel_tree()
    date_value = today_string(args.date)
    issues: list[dict] = []
    claims = []

    for path in sorted((CLAIMS_DIR / "active").glob("*.json")):
        claim = read_json_default(path, {})
        claims.append(claim)
        label = claim.get("claim_id") or path.name
        for field in ["claim_id", "product", "topic", "claim", "status", "primary_source", "first_seen_at", "last_verified_at"]:
            if not claim.get(field):
                issues.append({"claim_id": label, "field": field, "message": "필수 값이 없습니다."})
        if claim.get("product") != "lol_pc":
            issues.append({"claim_id": label, "field": "product", "message": "PC LoL claim이 아닙니다."})
        if claim.get("status") not in VALID_STATUSES:
            issues.append({"claim_id": label, "field": "status", "message": f"지원하지 않는 상태입니다: {claim.get('status')}"})
        source = claim.get("primary_source", {})
        for field in ["url", "canonical_url", "publisher", "published_at", "fetched_at"]:
            if not source.get(field):
                issues.append({"claim_id": label, "field": f"primary_source.{field}", "message": "출처 필수 값이 없습니다."})

    report = {
        "ok": not issues,
        "date": date_value,
        "active_claim_count": len(claims),
        "status_counts": dict(Counter(claim.get("status") for claim in claims)),
        "issue_count": len(issues),
        "issues": issues,
    }
    output_path = INTEL_DAILY_DIR / f"{date_value}-revalidation-report.json"
    write_json(output_path, report)
    log(f"재검증 리포트 저장: {output_path.relative_to(REPO_ROOT)}")
    if issues:
        for issue in issues:
            log(f"{issue['claim_id']}: {issue['field']} - {issue['message']}")
        return 1
    log("활성 claim 재검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
