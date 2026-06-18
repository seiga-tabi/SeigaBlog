from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from lol_content_utils import REPO_ROOT, ensure_parent, extract_scalar, post_paths, split_frontmatter, write_json


TIMEZONE = ZoneInfo("Asia/Tokyo")
INTEL_DIR = REPO_ROOT / "data" / "lol" / "intel"
INTEL_DAILY_DIR = INTEL_DIR / "daily"
CLAIMS_DIR = INTEL_DIR / "claims"
REPORTS_INTEL_DIR = REPO_ROOT / "reports" / "lol-intel"
STATE_PATH = INTEL_DIR / "state.json"
SEEN_ITEMS_PATH = INTEL_DIR / "seen_items.json"
INTEL_QUEUE_PATH = INTEL_DIR / "content_queue.json"
SOURCES_PATH = INTEL_DIR / "sources.yml"
DEFAULT_IMAGE = "/assets/images/profile.png"

STATUS_ORDER = {
    "confirmed": 8,
    "official_scheduled": 7,
    "official_planned": 6,
    "official_considering": 5,
    "pbe_testing": 4,
    "reported": 3,
    "rumor": 2,
    "rejected": 1,
    "superseded": 0,
}

STATUS_META = {
    "confirmed": {
        "prefix": {"ko": "", "ja": ""},
        "label": {"ko": "공식 확정", "ja": "公式確定"},
        "notice": {
            "ko": "Riot 공식 출처에서 확인된 라이브 또는 확정 정보입니다.",
            "ja": "Riot公式ソースで確認されたライブまたは確定情報です。",
        },
        "create_post": True,
        "create_pr": True,
    },
    "official_scheduled": {
        "prefix": {"ko": "[공식 예정] ", "ja": "【公式予定】"},
        "label": {"ko": "공식 예정", "ja": "公式予定"},
        "notice": {
            "ko": "Riot 공식 출처가 적용 패치나 날짜를 명시한 정보입니다.",
            "ja": "Riot公式ソースが適用パッチまたは日付を示した情報です。",
        },
        "create_post": True,
        "create_pr": True,
    },
    "official_planned": {
        "prefix": {"ko": "[개발 중] ", "ja": "【開発中】"},
        "label": {"ko": "개발 중", "ja": "開発中"},
        "notice": {
            "ko": "Riot이 계획 또는 개발 방향을 설명했지만 적용 시점은 달라질 수 있습니다.",
            "ja": "Riotが計画または開発方針を説明していますが、適用時期は変わる可能性があります。",
        },
        "create_post": True,
        "create_pr": True,
    },
    "official_considering": {
        "prefix": {"ko": "[검토 중] ", "ja": "【検討中】"},
        "label": {"ko": "검토 중", "ja": "検討中"},
        "notice": {
            "ko": "검토나 실험 수준의 언급으로, 실제 적용은 확정되지 않았습니다.",
            "ja": "検討または実験段階の言及で、実際の適用は確定していません。",
        },
        "create_post": False,
        "create_pr": False,
    },
    "pbe_testing": {
        "prefix": {"ko": "[PBE 테스트] ", "ja": "【PBEテスト】"},
        "label": {"ko": "PBE 테스트 중", "ja": "PBEテスト中"},
        "notice": {
            "ko": "현재 테스트 서버에서 확인된 내용으로, 수치와 적용 시점이 변경되거나 철회될 수 있습니다.",
            "ja": "現在テストサーバーで確認された内容で、数値や適用時期が変更または撤回される可能性があります。",
        },
        "create_post": True,
        "create_pr": True,
    },
    "reported": {
        "prefix": {"ko": "[보도] ", "ja": "【報道】"},
        "label": {"ko": "보도 기반", "ja": "報道ベース"},
        "notice": {
            "ko": "신뢰 가능한 보도 기반 정보이지만 Riot 공식 확인은 아닙니다.",
            "ja": "信頼できる報道に基づく情報ですが、Riot公式確認ではありません。",
        },
        "create_post": True,
        "create_pr": True,
    },
    "rumor": {
        "prefix": {"ko": "[미확인] ", "ja": "【未確認】"},
        "label": {"ko": "미확인", "ja": "未確認"},
        "notice": {
            "ko": "공식 확인이나 충분한 교차 검증이 없어 공개 PR 대상이 아닙니다.",
            "ja": "公式確認または十分なクロスチェックがないため、公開PR対象ではありません。",
        },
        "create_post": False,
        "create_pr": False,
    },
    "rejected": {
        "prefix": {"ko": "[철회·반박] ", "ja": "【撤回・否定】"},
        "label": {"ko": "철회·반박", "ja": "撤回・否定"},
        "notice": {
            "ko": "이전 정보가 공식적으로 부인되었거나 철회된 상태입니다.",
            "ja": "以前の情報が公式に否定または撤回された状態です。",
        },
        "create_post": False,
        "create_pr": False,
    },
    "superseded": {
        "prefix": {"ko": "[갱신됨] ", "ja": "【更新済み】"},
        "label": {"ko": "대체됨", "ja": "置き換え済み"},
        "notice": {
            "ko": "더 새로운 공식 발표나 변경안으로 대체된 정보입니다.",
            "ja": "より新しい公式発表または変更案に置き換えられた情報です。",
        },
        "create_post": False,
        "create_pr": False,
    },
}

CATEGORY_LABELS = {
    "patch": {"ko": "패치노트", "ja": "パッチノート"},
    "champion": {"ko": "챔피언", "ja": "チャンピオン"},
    "system": {"ko": "시스템", "ja": "システム"},
    "ranked": {"ko": "랭크", "ja": "ランク"},
    "pbe": {"ko": "PBE", "ja": "PBE"},
    "esports": {"ko": "e스포츠", "ja": "eスポーツ"},
    "dev": {"ko": "개발자 업데이트", "ja": "開発者アップデート"},
    "other": {"ko": "기타", "ja": "その他"},
}


def now_jst() -> dt.datetime:
    return dt.datetime.now(TIMEZONE)


def today_string(value: str | None = None) -> str:
    return value or now_jst().date().isoformat()


def now_iso() -> str:
    return now_jst().isoformat(timespec="seconds")


def ensure_intel_tree() -> None:
    for path in [
        INTEL_DAILY_DIR,
        CLAIMS_DIR / "active",
        CLAIMS_DIR / "confirmed",
        CLAIMS_DIR / "rejected",
        CLAIMS_DIR / "archived",
        REPORTS_INTEL_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_json_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def daily_path(date_value: str, suffix: str) -> Path:
    return INTEL_DAILY_DIR / f"{date_value}-{suffix}.json"


def raw_items_path(date_value: str) -> Path:
    return daily_path(date_value, "raw-items")


def normalized_items_path(date_value: str) -> Path:
    return daily_path(date_value, "normalized-items")


def claims_path(date_value: str) -> Path:
    return daily_path(date_value, "claims")


def selected_topic_path(date_value: str) -> Path:
    return daily_path(date_value, "selected-topic")


def generation_report_path(date_value: str) -> Path:
    return daily_path(date_value, "generation-report")


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def strip_html(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return normalize_space(value)


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", html.unescape(value or "")).lower()
    normalized = re.sub(r"[\s\-_·|｜:：]+", " ", normalized)
    return re.sub(r"[^0-9a-z가-힣ぁ-んァ-ヶ一-龯々ー. ]", "", normalized).strip()


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept = [(key, value) for key, value in query if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urllib.parse.urlencode(kept),
            "",
        )
    )


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = dt.datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TIMEZONE)
    return parsed.astimezone(TIMEZONE)


def format_date(value: str | None) -> str:
    parsed = parse_iso(value)
    if parsed:
        return parsed.date().isoformat()
    return normalize_space(value or "")


def existing_post_source_urls() -> set[str]:
    urls: set[str] = set()
    for path in post_paths():
        frontmatter, _, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        url = extract_scalar(frontmatter, "source_url")
        if url:
            urls.add(canonical_url(url))
        for match in re.finditer(r"^\s*url:\s*(.+)$", frontmatter, flags=re.MULTILINE):
            urls.add(canonical_url(match.group(1).strip().strip("\"'")))
    return urls


def existing_post_slugs() -> set[str]:
    slugs: set[str] = set()
    for path in post_paths():
        frontmatter, _, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        slug = extract_scalar(frontmatter, "slug")
        if slug:
            slugs.add(slug)
    return slugs


def existing_claim_fingerprints() -> set[str]:
    values: set[str] = set()
    for path in post_paths():
        frontmatter, _, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        for match in re.finditer(r"^\s*-\s*([a-f0-9]{16,64})\s*$", top_section(frontmatter, "claim_fingerprints"), flags=re.MULTILINE):
            values.add(match.group(1))
    return values


def top_section(frontmatter: str, key: str) -> str:
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


def claim_fingerprint(value: dict[str, Any]) -> str:
    subject_keys = ",".join(sorted(str(item.get("key", "")) for item in value.get("subjects", [])))
    basis = "|".join(
        [
            normalize_title(localized(value.get("topic"), "ko")),
            normalize_title(localized(value.get("claim"), "ko")),
            subject_keys,
            str(value.get("expected_patch") or ""),
            str(value.get("expected_date") or ""),
        ]
    )
    return stable_hash(basis, 24)


def localized(value: Any, lang: str, fallback: str = "") -> str:
    if isinstance(value, dict):
        current = value.get(lang)
        if isinstance(current, str) and current:
            return normalize_space(current)
    if isinstance(value, str):
        return normalize_space(value)
    return fallback


def source_reliability_score(tier: int | str | None) -> int:
    try:
        tier_int = int(tier or 3)
    except ValueError:
        tier_int = 3
    if tier_int <= 1:
        return 40
    if tier_int == 2:
        return 30
    if tier_int == 3:
        return 20
    return 10


def recency_score(published_at: str | None, now: dt.datetime | None = None) -> int:
    current = now or now_jst()
    parsed = parse_iso(published_at)
    if not parsed:
        return 8
    age_hours = max(0.0, (current - parsed).total_seconds() / 3600)
    if age_hours <= 24:
        return 20
    if age_hours <= 36:
        return 18
    if age_hours <= 72:
        return 14
    if age_hours <= 168:
        return 10
    return 4


def impact_score(category: str, status: str) -> int:
    if category in {"patch", "champion", "system", "ranked"}:
        return 15
    if category in {"pbe", "dev"}:
        return 12
    if status in {"confirmed", "official_scheduled"}:
        return 10
    if category == "esports":
        return 8
    return 5


def evidence_score(claim: dict[str, Any]) -> int:
    evidence = claim.get("evidence", {})
    score = 0
    if evidence.get("direct_release_commitment"):
        score += 4
    if evidence.get("contains_specific_patch"):
        score += 3
    if evidence.get("contains_specific_date"):
        score += 3
    if claim.get("status") == "confirmed":
        score = max(score, 8)
    return min(score, 10)


def score_claim(claim: dict[str, Any]) -> dict[str, int]:
    source = claim.get("primary_source", {})
    duplicate = bool(claim.get("duplicate", {}).get("is_duplicate"))
    components = {
        "source_reliability": source_reliability_score(source.get("tier")),
        "recency": recency_score(source.get("published_at")),
        "novelty": 0 if duplicate else 15,
        "gameplay_impact": impact_score(str(claim.get("content_category", "other")), str(claim.get("status", ""))),
        "evidence": evidence_score(claim),
    }
    components["total"] = sum(components.values())
    return components


def publication_allowed(status: str, corroborating_count: int = 0) -> bool:
    if status == "reported":
        return corroborating_count >= 1
    return bool(STATUS_META.get(status, {}).get("create_post"))


def yaml_scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def render_post(post_data: dict[str, Any]) -> str:
    return "---\n" + "\n".join(yaml_lines(post_data)) + "\n---\n"


def collect_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(collect_text_values(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(collect_text_values(item))
        return result
    return []


def read_time(post_data: dict[str, Any]) -> str:
    text = " ".join(
        collect_text_values(post_data.get("title", {}).get("ko", ""))
        + collect_text_values(post_data.get("lead", {}).get("ko", ""))
        + collect_text_values(post_data.get("body", {}).get("ko", []))
        + collect_text_values(post_data.get("sections", []))
    )
    chars = len(re.sub(r"\s+", "", text))
    return f"{max(3, (chars + 499) // 500)} min"


def status_meta(status: str) -> dict[str, Any]:
    return STATUS_META.get(status, STATUS_META["rumor"])


def status_label(status: str) -> dict[str, str]:
    return status_meta(status)["label"]


def category_label(category: str) -> dict[str, str]:
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS["other"])


def safe_slug(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or fallback


def write_daily_markdown_report(date_value: str, payload: dict[str, Any]) -> Path:
    ensure_intel_tree()
    path = REPORTS_INTEL_DIR / f"{date_value}-daily-report.md"
    checked_sources = payload.get("checked_sources", [])
    new_items = payload.get("new_items", [])
    duplicates = payload.get("duplicates", [])
    status_counts = payload.get("status_counts", {})
    candidates = payload.get("candidates", [])
    failures = payload.get("failures", [])
    selected = payload.get("selected", {})
    generated = payload.get("generated", {})

    lines = [
        f"# {date_value} LoL 일일 정보 검색 리포트",
        "",
        f"- 실행 시각: {payload.get('run_started_at') or now_iso()}",
        f"- 확인한 출처 수: {len(checked_sources)}",
        f"- 발견한 신규 항목 수: {len(new_items)}",
        f"- 중복 제외 항목 수: {len(duplicates)}",
        "",
        "## 상태별 claim 수",
        "",
    ]
    if status_counts:
        for status, count in sorted(status_counts.items()):
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- 없음")

    lines.extend(["", "## 최종 후보와 점수", ""])
    if candidates:
        for candidate in candidates[:10]:
            title = localized(candidate.get("topic"), "ko", candidate.get("claim_id", ""))
            score = candidate.get("score", {}).get("total", 0)
            lines.append(f"- {title}: {score}점 ({candidate.get('status')})")
    else:
        lines.append("- 생성 가능한 후보 없음")

    reason = selected.get("reason") or generated.get("reason") or "선택 결과 없음"
    lines.extend(
        [
            "",
            "## 생성 판단",
            "",
            f"- 글 생성 여부: {'예' if generated.get('generated') else '아니요'}",
            f"- 이유: {reason}",
        ]
    )
    if generated.get("post"):
        lines.append(f"- 생성 또는 갱신된 글: {generated['post']}")

    lines.extend(["", "## 중복으로 제외한 항목", ""])
    if duplicates:
        for item in duplicates[:20]:
            lines.append(f"- {item.get('title') or item.get('claim_id')}: {item.get('reason', '중복')}")
    else:
        lines.append("- 없음")

    lines.extend(["", "## 수집 실패 출처", ""])
    if failures:
        for failure in failures:
            lines.append(f"- {failure.get('id') or failure.get('url')}: {failure.get('error')}")
    else:
        lines.append("- 없음")

    lines.extend(["", "## 다음 실행에서 재검증할 항목", ""])
    revalidate = payload.get("revalidate", [])
    if revalidate:
        for item in revalidate[:20]:
            lines.append(f"- {item.get('claim_id')}: {localized(item.get('topic'), 'ko')}")
    else:
        lines.append("- 활성 claim 없음")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def update_seen_items(normalized_items: Iterable[dict[str, Any]], claims: Iterable[dict[str, Any]]) -> None:
    seen = read_json_default(SEEN_ITEMS_PATH, {"urls": [], "platform_ids": [], "title_hashes": [], "content_hashes": [], "claim_fingerprints": []})
    for key in ["urls", "platform_ids", "title_hashes", "content_hashes", "claim_fingerprints"]:
        if key not in seen or not isinstance(seen[key], list):
            seen[key] = []

    for item in normalized_items:
        append_unique(seen["urls"], item.get("canonical_url"))
        append_unique(seen["platform_ids"], item.get("platform_id"))
        append_unique(seen["title_hashes"], item.get("title_hash"))
        append_unique(seen["content_hashes"], item.get("content_hash"))
    for claim in claims:
        append_unique(seen["claim_fingerprints"], claim.get("claim_fingerprint"))
    write_json(SEEN_ITEMS_PATH, seen)


def append_unique(values: list[Any], value: Any) -> None:
    if value and value not in values:
        values.append(value)


def write_claim_files(claims: list[dict[str, Any]], dry_run: bool = False) -> list[str]:
    written: list[str] = []
    for claim in claims:
        claim_id = claim["claim_id"]
        active_path = CLAIMS_DIR / "active" / f"{claim_id}.json"
        if not dry_run:
            write_json(active_path, claim)
        written.append(str(active_path.relative_to(REPO_ROOT)))
        status = claim.get("status")
        if status == "confirmed":
            path = CLAIMS_DIR / "confirmed" / f"{claim_id}.json"
            if not dry_run:
                write_json(path, claim)
            written.append(str(path.relative_to(REPO_ROOT)))
        if status == "rejected":
            path = CLAIMS_DIR / "rejected" / f"{claim_id}.json"
            if not dry_run:
                write_json(path, claim)
            written.append(str(path.relative_to(REPO_ROOT)))
    return written


def write_text(path: Path, value: str) -> None:
    ensure_parent(path)
    path.write_text(value, encoding="utf-8")
