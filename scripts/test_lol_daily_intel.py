#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

from classify_lol_claims import classify_status
from lol_daily_intel import STATUS_META, score_claim
from select_daily_lol_topic import select
from validate_blog_content import validate_information_status, validate_sources_block


def claim(
    claim_id: str,
    status: str,
    category: str = "other",
    duplicate: bool = False,
    tier: int = 1,
    published_at: str = "2026-06-18",
    direct_release: bool = False,
) -> dict:
    return {
        "claim_id": claim_id,
        "product": "lol_pc",
        "topic": {"ko": f"주제 {claim_id}", "ja": f"トピック {claim_id}"},
        "claim": {"ko": f"주장 {claim_id}", "ja": f"主張 {claim_id}"},
        "status": status,
        "content_category": category,
        "expected_patch": "26.13" if direct_release else None,
        "expected_date": None,
        "subjects": [],
        "primary_source": {
            "tier": tier,
            "url": f"https://www.leagueoflegends.com/ko-kr/news/{claim_id}",
            "canonical_url": f"https://www.leagueoflegends.com/ko-kr/news/{claim_id}",
            "publisher": "Riot Games",
            "published_at": published_at,
            "fetched_at": "2026-06-18T12:00:00+09:00",
        },
        "corroborating_sources": [{"url": "https://example.com/source"}] if status == "reported" else [],
        "evidence": {
            "direct_release_commitment": direct_release,
            "contains_specific_patch": direct_release,
            "contains_specific_date": False,
        },
        "duplicate": {"is_duplicate": duplicate, "reasons": ["canonical_url"] if duplicate else []},
    }


class LolDailyIntelPolicyTest(unittest.TestCase):
    def test_patch_note_is_confirmed(self) -> None:
        item = {"title": "리그 오브 레전드 26.13 패치 노트", "description": "", "url": "https://example.com/patch-notes", "content_category": "patch"}
        self.assertEqual(classify_status(item), "confirmed")

    def test_pbe_is_not_confirmed(self) -> None:
        item = {"title": "PBE 테스트 서버 챔피언 변경", "description": "", "url": "https://example.com", "content_category": "pbe"}
        self.assertEqual(classify_status(item), "pbe_testing")

    def test_highest_single_topic_selected_once(self) -> None:
        selected = select([
            claim("low", "official_planned", category="other", tier=2),
            claim("high", "confirmed", category="patch", tier=1, direct_release=True),
        ])
        self.assertTrue(selected["should_generate"])
        self.assertEqual(selected["selection_type"], "single_topic")
        self.assertEqual(selected["selected_claim_ids"], ["high"])

    def test_small_official_items_can_be_briefing(self) -> None:
        selected = select([
            claim("a", "official_planned", category="other", tier=2),
            claim("b", "official_planned", category="other", tier=2),
        ])
        self.assertTrue(selected["should_generate"])
        self.assertEqual(selected["selection_type"], "daily_briefing")
        self.assertEqual(len(selected["selected_claim_ids"]), 2)

    def test_no_new_information_creates_report_only(self) -> None:
        selected = select([])
        self.assertFalse(selected["should_generate"])
        self.assertEqual(selected["action"], "report_only")

    def test_single_rumor_is_not_publication_candidate(self) -> None:
        selected = select([claim("rumor", "rumor", category="other")], force_generate=True)
        self.assertFalse(selected["should_generate"])

    def test_duplicate_claim_is_not_selected(self) -> None:
        selected = select([claim("dupe", "confirmed", category="patch", duplicate=True, direct_release=True)])
        self.assertFalse(selected["should_generate"])

    def test_reported_claim_needs_corroboration(self) -> None:
        selected = select([claim("reported", "reported", category="system")])
        self.assertTrue(selected["should_generate"])

    def test_score_contains_expected_components(self) -> None:
        scored = score_claim(claim("score", "confirmed", category="patch", direct_release=True))
        self.assertEqual(set(scored), {"source_reliability", "recency", "novelty", "gameplay_impact", "evidence", "total"})
        self.assertGreaterEqual(scored["total"], 75)

    def test_pbe_title_prefix_is_required(self) -> None:
        frontmatter = """
title:
  ko: LoL PBE 변경안 정리
  ja: LoL PBE変更案まとめ
information_status:
  code: pbe_testing
  label:
    ko: PBE 테스트 중
    ja: PBEテスト中
  notice:
    ko: 현재 테스트 서버에서 확인된 내용입니다.
    ja: 現在テストサーバーで確認された内容です。
"""
        issues = validate_information_status("_posts/test.md", frontmatter)
        self.assertTrue(any(issue["type"] == "information_status" for issue in issues))

    def test_missing_source_url_is_blocking(self) -> None:
        frontmatter = """
source_title: "Riot 공식 출처"
source_published_at: "2026-06-18"
last_checked: "2026-06-18T12:00:00+09:00"
sources:
  -
    title: "Riot 공식 출처"
    publisher: "Riot Games"
    published_at: "2026-06-18"
    last_verified_at: "2026-06-18T12:00:00+09:00"
    source_tier: 1
"""
        issues = validate_sources_block("_posts/test.md", frontmatter)
        self.assertTrue(any("source_url" in issue["message"] for issue in issues))

    def test_rumor_policy_never_creates_pr(self) -> None:
        self.assertFalse(STATUS_META["rumor"]["create_pr"])

    def test_patch_workflow_has_no_schedule(self) -> None:
        workflow = Path(".github/workflows/lol-patch-blog.yml").read_text(encoding="utf-8")
        self.assertNotIn("schedule:", workflow)

    def test_daily_workflow_uses_asia_tokyo_timezone(self) -> None:
        workflow = Path(".github/workflows/lol-daily-intel.yml").read_text(encoding="utf-8")
        self.assertIn('timezone: "Asia/Tokyo"', workflow)


if __name__ == "__main__":
    unittest.main()
