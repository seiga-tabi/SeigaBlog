from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "_site"


@unittest.skipUnless(SITE_ROOT.exists(), "_site가 없어 정적 사이트 테스트를 건너뜁니다.")
class SiteStructureTest(unittest.TestCase):
    def test_home_does_not_render_detail_stack(self) -> None:
        html = (SITE_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("detail-stack", html)
        self.assertNotIn("champion-card-grid", html)

    def test_existing_post_url_exists(self) -> None:
        path = SITE_ROOT / "posts" / "lol-patch-26-12-summary" / "index.html"
        self.assertTrue(path.exists())

    def test_ads_disabled_by_default(self) -> None:
        html = "\n".join(path.read_text(encoding="utf-8") for path in SITE_ROOT.rglob("*.html"))
        self.assertNotIn("adsbygoogle", html)
        self.assertNotIn("pagead/js/adsbygoogle.js", html)

    def test_no_hash_canonical(self) -> None:
        for path in SITE_ROOT.rglob("*.html"):
            html = path.read_text(encoding="utf-8")
            match = re.search(r'<link rel="canonical" href="([^"]+)"', html)
            self.assertIsNotNone(match, str(path))
            self.assertNotIn("#", match.group(1))


if __name__ == "__main__":
    unittest.main()

