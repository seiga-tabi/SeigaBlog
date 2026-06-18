#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[3]
JAVA_DIR = REPO_ROOT / "data" / "minecraft" / "java"
RAW_DIR = JAVA_DIR / "raw"
PROCESSED_DIR = JAVA_DIR / "processed"
RELEASES_DIR = JAVA_DIR / "releases"
REPORT_DIR = REPO_ROOT / "reports" / "minecraft" / "java"
POSTS_DIR = REPO_ROOT / "_posts"
ASSET_DIR = REPO_ROOT / "assets" / "images" / "minecraft" / "java"
STATE_PATH = JAVA_DIR / "state.json"
SEEN_ITEMS_PATH = JAVA_DIR / "seen_items.json"
QUEUE_PATH = JAVA_DIR / "content_queue.json"
SOURCES_PATH = JAVA_DIR / "sources.yml"
DEFAULT_IMAGE = "/assets/images/profile.png"
TIMEZONE = ZoneInfo("Asia/Tokyo")
USER_AGENT = "SeigaBlog Minecraft Java automation (https://github.com/seiga-tabi/SeigaBlog)"

BEDROCK_TERMS = [
    "bedrock edition",
    "bedrock",
    "beta & preview",
    "beta and preview",
    "(bedrock)",
    "marketplace",
    "education",
    "dungeons",
    "legends",
]
JAVA_HINTS = [
    "minecraft java edition",
    "java edition",
    "snapshot",
    "pre-release",
    "pre release",
    "pre-release",
    "release candidate",
    "java hotfix",
]
CHANNELS = {
    "java_stable_release",
    "java_hotfix",
    "java_snapshot",
    "java_pre_release",
    "java_release_candidate",
    "java_official_announcement",
    "java_official_planned",
    "java_superseded",
    "java_withdrawn",
}
CHANNEL_META = {
    "java_stable_release": {
        "ko": "[Java 정식 업데이트]",
        "ja": "[Java正式アップデート]",
        "badge": {"ko": "Java 업데이트", "ja": "Javaアップデート"},
        "status": "confirmed",
    },
    "java_hotfix": {
        "ko": "[Java 핫픽스]",
        "ja": "[Javaホットフィックス]",
        "badge": {"ko": "Java 핫픽스", "ja": "Javaホットフィックス"},
        "status": "confirmed",
    },
    "java_snapshot": {
        "ko": "[Java 스냅샷]",
        "ja": "[Javaスナップショット]",
        "badge": {"ko": "Java 스냅샷", "ja": "Javaスナップショット"},
        "status": "testing",
    },
    "java_pre_release": {
        "ko": "[Java 프리릴리스]",
        "ja": "[Javaプレリリース]",
        "badge": {"ko": "Java 프리릴리스", "ja": "Javaプレリリース"},
        "status": "testing",
    },
    "java_release_candidate": {
        "ko": "[Java 릴리스 후보]",
        "ja": "[Javaリリース候補]",
        "badge": {"ko": "Java 릴리스 후보", "ja": "Javaリリース候補"},
        "status": "testing",
    },
    "java_official_announcement": {
        "ko": "[Java 공식 발표]",
        "ja": "[Java公式発表]",
        "badge": {"ko": "Java 공식 발표", "ja": "Java公式発表"},
        "status": "official",
    },
    "java_official_planned": {
        "ko": "[Java 개발 예정]",
        "ja": "[Java開発予定]",
        "badge": {"ko": "Java 개발 예정", "ja": "Java開発予定"},
        "status": "planned",
    },
    "java_superseded": {
        "ko": "[Java 대체됨]",
        "ja": "[Java更新済み]",
        "badge": {"ko": "Java 대체됨", "ja": "Java更新済み"},
        "status": "superseded",
    },
    "java_withdrawn": {
        "ko": "[Java 철회]",
        "ja": "[Java撤回]",
        "badge": {"ko": "Java 철회", "ja": "Java撤回"},
        "status": "withdrawn",
    },
}


def log(message: str) -> None:
    print(f"[Minecraft Java] {message}", file=sys.stderr)


def ensure_tree() -> None:
    for path in [RAW_DIR, PROCESSED_DIR, RELEASES_DIR, REPORT_DIR, ASSET_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def now_jst() -> dt.datetime:
    return dt.datetime.now(TIMEZONE)


def now_iso() -> str:
    return now_jst().isoformat(timespec="seconds")


def today_string(value: str | None = None) -> str:
    return value or now_jst().date().isoformat()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def dated_path(directory: Path, date_value: str, suffix: str) -> Path:
    return directory / f"{date_value}-{suffix}.json"


def raw_items_path(date_value: str) -> Path:
    return dated_path(RAW_DIR, date_value, "raw-items")


def normalized_items_path(date_value: str) -> Path:
    return dated_path(PROCESSED_DIR, date_value, "normalized-items")


def classified_items_path(date_value: str) -> Path:
    return dated_path(PROCESSED_DIR, date_value, "classified-items")


def selected_topic_path(date_value: str) -> Path:
    return dated_path(PROCESSED_DIR, date_value, "selected-topic")


def generation_report_path(date_value: str) -> Path:
    return dated_path(PROCESSED_DIR, date_value, "generation-report")


def validation_report_path(date_value: str) -> Path:
    return dated_path(PROCESSED_DIR, date_value, "validation-report")


def daily_report_path(date_value: str) -> Path:
    return REPORT_DIR / f"{date_value}-daily-report.md"


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def strip_html(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|li|h1|h2|h3|h4)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    lines = [normalize_space(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept = [(key, value) for key, value in query if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(kept), ""))


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_iso(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
            try:
                parsed = dt.datetime.strptime(str(value)[:32], fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TIMEZONE)
    return parsed.astimezone(TIMEZONE)


def format_date(value: str | None) -> str:
    parsed = parse_iso(value)
    return parsed.date().isoformat() if parsed else normalize_space(value or "")


def safe_slug(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or fallback


def version_slug(version: str | None) -> str:
    return safe_slug(version or "", "unknown-version")


def lower_text(value: str) -> str:
    return unicodedata.normalize("NFKC", html.unescape(value or "")).lower()


def has_bedrock_context(text: str) -> bool:
    lowered = lower_text(text)
    return any(term in lowered for term in BEDROCK_TERMS)


def is_java_candidate(title: str, url: str = "", body: str = "") -> bool:
    joined = lower_text(" ".join([title, url, body[:1000]]))
    if has_bedrock_context(title) or "beta & preview" in joined or "beta and preview" in joined:
        return False
    if "feedback.minecraft.net/hc/en-us/articles" in joined and "minecraft -" in joined and "java" not in joined:
        return False
    return any(hint in joined for hint in JAVA_HINTS)


def classify_channel(title: str, body: str = "") -> str:
    text = lower_text(f"{title}\n{body[:3000]}")
    if "withdrawn" in text or "removed from testing" in text:
        return "java_withdrawn"
    if "superseded" in text or "replaced by" in text:
        return "java_superseded"
    if "hotfix" in text:
        return "java_hotfix"
    if "release candidate" in text:
        return "java_release_candidate"
    if "pre-release" in text or "pre release" in text or "pre-release" in text:
        return "java_pre_release"
    if "snapshot" in text:
        return "java_snapshot"
    if "java edition" in text and re.search(r"\b\d+(?:\.\d+)+(?:\b|[^0-9])", text):
        return "java_stable_release"
    if any(term in text for term in ["planned", "coming", "preview of", "future"]):
        return "java_official_planned"
    return "java_official_announcement"


def extract_version(title: str, body: str = "") -> str:
    text = f"{title}\n{body[:1000]}"
    patterns = [
        r"(?:java edition\s*-?\s*|minecraft[: ]+java edition\s*-?\s*)([0-9][0-9A-Za-z.\- ]*(?:snapshot|pre-release|pre release|release candidate)?\s*\d*)",
        r"\b(\d{2}w\d{2}[a-z])\b",
        r"\b(\d+(?:\.\d+){1,3}(?:\s*(?:pre-release|pre release|release candidate)\s*\d+)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return normalize_space(match.group(1).replace("Pre release", "Pre-Release"))
    return ""


def extract_title(page_html: str, fallback: str = "") -> str:
    for pattern in [
        r"<h1[^>]*>(.*?)</h1>",
        r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
        r"<title[^>]*>(.*?)</title>",
    ]:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            title = normalize_space(strip_html(match.group(1)))
            return re.sub(r"\s*\|\s*Minecraft.*$", "", title).strip()
    return fallback


def extract_published_at(page_html: str, fallback: str = "") -> str:
    patterns = [
        r'<meta\s+property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']',
        r'<time[^>]+datetime=["\']([^"\']+)["\']',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE)
        if match:
            return format_date(match.group(1))
    return format_date(fallback)


def extract_article_text(page_html: str) -> str:
    article_match = re.search(r"(?is)<article[^>]*>(.*?)</article>", page_html)
    if article_match:
        return strip_html(article_match.group(1))
    main_match = re.search(r"(?is)<main[^>]*>(.*?)</main>", page_html)
    if main_match:
        return strip_html(main_match.group(1))
    return strip_html(page_html)


def list_items_by_heading(text: str) -> dict[str, list[str]]:
    result = {
        "added": [],
        "changed": [],
        "fixed": [],
        "removed": [],
        "experimental_changes": [],
        "technical_changes": [],
        "data_pack_changes": [],
        "resource_pack_changes": [],
        "commands": [],
        "server_changes": [],
        "known_issues": [],
    }
    current = "changed"
    for raw_line in text.splitlines():
        line = normalize_space(raw_line.strip(" -*•"))
        if not line:
            continue
        lowered = lower_text(line)
        if len(line) < 3 or any(term in lowered for term in ["table of contents", "follow minecraft", "manage consent"]):
            continue
        if re.fullmatch(r"[A-Za-z /&-]{3,80}", line):
            if "new" in lowered or "added" in lowered or "features" in lowered:
                current = "added"
            elif "change" in lowered or "update" in lowered or "tweak" in lowered:
                current = "changed"
            elif "fix" in lowered or "bug" in lowered:
                current = "fixed"
            elif "remove" in lowered:
                current = "removed"
            elif "experiment" in lowered:
                current = "experimental_changes"
            elif "technical" in lowered:
                current = "technical_changes"
            elif "data pack" in lowered or "datapack" in lowered:
                current = "data_pack_changes"
            elif "resource pack" in lowered:
                current = "resource_pack_changes"
            elif "command" in lowered:
                current = "commands"
            elif "server" in lowered:
                current = "server_changes"
            elif "known issue" in lowered:
                current = "known_issues"
            continue
        if len(line) > 220:
            continue
        if "data pack" in lowered or "datapack" in lowered:
            bucket = "data_pack_changes"
        elif "resource pack" in lowered:
            bucket = "resource_pack_changes"
        elif "command" in lowered:
            bucket = "commands"
        elif "server" in lowered:
            bucket = "server_changes"
        elif "known issue" in lowered:
            bucket = "known_issues"
        elif "fixed" in lowered or re.search(r"\bmc-\d+\b", lowered):
            bucket = "fixed"
        else:
            bucket = current
        if line not in result[bucket] and len(result[bucket]) < 12:
            result[bucket].append(line)
    return result


def bug_ids(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bMC-\d+\b", text, flags=re.IGNORECASE)))[:50]


def summarize_items(items: list[str], fallback: str) -> str:
    if items:
        return normalize_space(items[0])
    return fallback


def normalize_raw_item(raw_item: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    url = raw_item.get("url") or raw_item.get("canonical_url")
    if not url:
        return None, {"url": "", "error": "URL이 없습니다."}
    try:
        page_html = fetch_text(url)
    except (urllib.error.URLError, TimeoutError) as error:
        return None, {"url": url, "error": f"원문 접근 실패: {error}"}

    title = extract_title(page_html, raw_item.get("title", ""))
    article_text = extract_article_text(page_html)
    if not is_java_candidate(title, url, article_text):
        return None, {"url": url, "error": "Java Edition 확정 후보가 아닙니다."}

    channel = classify_channel(title, article_text)
    version = extract_version(title, article_text)
    sections = list_items_by_heading(article_text)
    canonical = canonical_url(url)
    published_at = extract_published_at(page_html, raw_item.get("published_at", ""))
    normalized = {
        "product": "minecraft",
        "edition": "java",
        "release_channel": channel,
        "version": version,
        "release_name": None,
        "source": {
            "url": url,
            "canonical_url": canonical,
            "title": title,
            "publisher": raw_item.get("publisher") or "Mojang Studios",
            "published_at": published_at,
            "last_verified_at": now_iso(),
        },
        "summary": {
            "ko": f"{title} 원문을 기준으로 Java Edition 변경점을 정리합니다.",
            "ja": f"{title}の原文を基準にJava Editionの変更点を整理します。",
        },
        "added": sections["added"],
        "changed": sections["changed"],
        "fixed": sections["fixed"],
        "removed": sections["removed"],
        "experimental_changes": sections["experimental_changes"],
        "technical_changes": sections["technical_changes"],
        "data_pack_changes": sections["data_pack_changes"],
        "resource_pack_changes": sections["resource_pack_changes"],
        "commands": sections["commands"],
        "server_changes": sections["server_changes"],
        "known_issues": sections["known_issues"],
        "bug_ids": bug_ids(article_text),
        "previous_version": None,
        "target_stable_version": None,
        "requires_new_world": None,
        "world_compatibility": None,
        "server_compatibility": None,
        "mod_compatibility": None,
        "raw_item_id": raw_item.get("raw_item_id") or stable_hash(canonical),
        "fetched_text_fingerprint": stable_hash(article_text, 24),
    }
    return normalized, None


def importance_flags(item: dict[str, Any]) -> list[str]:
    text = lower_text(json.dumps(item, ensure_ascii=False))
    rules = {
        "new_mob": ["new mob", "mob"],
        "new_biome": ["new biome", "biome"],
        "new_block_or_item": ["new block", "new item", "blocks", "items"],
        "world_generation": ["world generation", "terrain", "biome"],
        "combat_or_movement": ["combat", "movement", "sprint", "jump", "mount"],
        "data_pack": ["data pack", "datapack"],
        "resource_pack": ["resource pack"],
        "commands": ["command"],
        "server": ["server"],
    }
    return [name for name, terms in rules.items() if any(term in text for term in terms)]


def score_item(item: dict[str, Any], duplicate: bool = False) -> dict[str, Any]:
    channel = item.get("release_channel", "")
    official = 30 if item.get("source", {}).get("url", "").startswith(("https://feedback.minecraft.net", "https://www.minecraft.net")) else 0
    release_score = {
        "java_stable_release": 20,
        "java_hotfix": 16,
        "java_snapshot": 10,
        "java_pre_release": 8,
        "java_release_candidate": 9,
        "java_official_announcement": 8,
        "java_official_planned": 6,
    }.get(channel, 0)
    flags = importance_flags(item)
    impact = 20 if channel in {"java_stable_release", "java_hotfix"} else min(20, 8 + len(flags) * 3)
    distinct = 0 if duplicate else 15
    change_count = sum(len(item.get(key, [])) for key in ["added", "changed", "fixed", "technical_changes", "data_pack_changes", "resource_pack_changes", "commands", "server_changes"])
    scale = min(10, change_count)
    i18n = 5 if item.get("source", {}).get("title") else 0
    total = official + release_score + impact + distinct + scale + i18n
    if channel == "java_snapshot" and not flags:
        total = min(total, 78)
    action = "NEW_POST" if total >= 85 else "UPDATE_EXISTING" if total >= 70 else "REPORT_ONLY"
    return {
        "total": total,
        "action": action,
        "components": {
            "official_source": official,
            "release_importance": release_score,
            "java_user_impact": impact,
            "distinctness": distinct,
            "change_scale": scale,
            "i18n_possible": i18n,
        },
        "importance_flags": flags,
    }


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
            elif item is None:
                lines.append(f"{prefix}{key}: null")
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            elif item is None:
                lines.append(f"{prefix}- null")
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
        result: list[str] = []
        for item in value.values():
            result.extend(collect_text_values(item))
        return result
    return []


def read_time(post_data: dict[str, Any]) -> str:
    text = " ".join(collect_text_values(post_data.get("title", {})) + collect_text_values(post_data.get("sections", [])))
    chars = len(re.sub(r"\s+", "", text))
    return f"{max(3, (chars + 499) // 500)} min"


def write_daily_report(date_value: str, payload: dict[str, Any]) -> Path:
    ensure_tree()
    path = daily_report_path(date_value)
    lines = [
        f"# {date_value} Minecraft Java 일일 실행 리포트",
        "",
        f"- 실행 이벤트: {payload.get('event', 'local')}",
        f"- 실행 시각: {payload.get('run_started_at') or now_iso()}",
        f"- 확인한 Java 공식 페이지: {len(payload.get('checked_sources', []))}개",
        f"- 발견한 Java 버전: {', '.join(payload.get('found_versions', []) or ['없음'])}",
        f"- 제외한 Bedrock 항목: {len(payload.get('excluded_bedrock', []))}개",
        f"- 중복 항목: {len(payload.get('duplicates', []))}개",
        f"- 최종 주제: {payload.get('selected_title') or '없음'}",
        f"- 후보 점수: {payload.get('score', '없음')}",
        f"- 처리 결과: {payload.get('action', 'REPORT_ONLY')}",
        f"- 글 생성하지 않은 이유: {payload.get('reason', '')}",
        f"- 검증 결과: {payload.get('validation', '미실행')}",
        "",
        "## 확인한 출처",
        "",
    ]
    for source in payload.get("checked_sources", []):
        lines.append(f"- {source.get('id', source.get('url'))}: {source.get('url')}")
    if payload.get("excluded_bedrock"):
        lines.extend(["", "## 제외한 Bedrock 항목", ""])
        for item in payload["excluded_bedrock"][:20]:
            lines.append(f"- {item.get('title', '')} ({item.get('url', '')})")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minecraft Java raw item을 구조화 JSON으로 정규화합니다.")
    parser.add_argument("--date", help="처리 날짜입니다. 기본값은 Asia/Tokyo 오늘입니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 저장하지 않고 결과만 출력합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_tree()
    date_value = today_string(args.date)
    raw_payload = read_json(raw_items_path(date_value), {"items": []})
    normalized: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for raw_item in raw_payload.get("items", []):
        item, failure = normalize_raw_item(raw_item)
        if item:
            normalized.append(item)
        elif failure:
            failures.append(failure)
    payload = {
        "ok": True,
        "date": date_value,
        "normalized_at": now_iso(),
        "item_count": len(normalized),
        "items": normalized,
        "failures": failures,
    }
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        write_json(normalized_items_path(date_value), payload)
        log(f"정규화 결과 저장: {repo_path(normalized_items_path(date_value))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
