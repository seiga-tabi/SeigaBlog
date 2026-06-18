from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[3]
TIMEZONE = ZoneInfo("Asia/Tokyo")

BEDROCK_DIR = REPO_ROOT / "data" / "minecraft" / "bedrock"
RAW_DIR = BEDROCK_DIR / "raw"
PROCESSED_DIR = BEDROCK_DIR / "processed"
RELEASES_DIR = BEDROCK_DIR / "releases"
REPORT_DIR = REPO_ROOT / "reports" / "minecraft" / "bedrock"
POSTS_DIR = REPO_ROOT / "_posts"
IMAGE_DIR = REPO_ROOT / "assets" / "images" / "minecraft" / "bedrock"

SOURCES_PATH = BEDROCK_DIR / "sources.yml"
STATE_PATH = BEDROCK_DIR / "state.json"
SEEN_ITEMS_PATH = BEDROCK_DIR / "seen_items.json"
CONTENT_QUEUE_PATH = BEDROCK_DIR / "content_queue.json"
DEFAULT_IMAGE = "/assets/images/profile.png"

BEDROCK_CHANNELS = {
    "bedrock_stable_release",
    "bedrock_hotfix",
    "bedrock_beta",
    "bedrock_preview",
    "bedrock_official_announcement",
    "bedrock_official_planned",
    "bedrock_platform_specific",
    "bedrock_superseded",
    "bedrock_withdrawn",
}

JAVA_EXCLUSION_TERMS = [
    "Java Edition",
    "Java Snapshot",
    "Snapshot",
    "Pre-Release",
    "Release Candidate",
    "자바 에디션",
    "スナップショット",
]

BEDROCK_INCLUDE_RE = re.compile(
    r"(Minecraft:\s*Bedrock Edition|\(Bedrock\)|Bedrock Hotfix|Beta and Preview|Minecraft Beta\s*&\s*Preview|Minecraft Preview|Bedrock Edition)",
    re.IGNORECASE,
)
BEDROCK_CONTEXT_RE = re.compile(
    r"(Bedrock|Minecraft Preview|Minecraft Beta|Beta and Preview|Add-On|Creator|Realms|Xbox|PlayStation|Nintendo Switch|Windows|Android|iOS)",
    re.IGNORECASE,
)


class ArticleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.paragraphs: list[str] = []
        self.headings: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._tag_stack: list[str] = []
        self._current_link: dict[str, str] | None = None
        self._current_text: list[str] = []
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        self._tag_stack.append(tag)
        if tag == "a" and attrs_dict.get("href"):
            self._current_link = {"url": attrs_dict["href"], "text": ""}
        if tag == "meta":
            key = attrs_dict.get("property") or attrs_dict.get("name")
            value = attrs_dict.get("content")
            if key and value:
                self.meta[key.lower()] = html.unescape(value).strip()
        if tag in {"p", "li", "h1", "h2", "h3", "title"}:
            self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        text = normalize_space(" ".join(self._current_text))
        if tag == "a" and self._current_link:
            self._current_link["text"] = normalize_space(self._current_link.get("text", ""))
            self.links.append(self._current_link)
            self._current_link = None
        elif tag in {"p", "li"} and text:
            self.paragraphs.append(text)
        elif tag in {"h1", "h2", "h3"} and text:
            self.headings.append(text)
        elif tag == "title" and text:
            self.title = text
        if self._tag_stack:
            self._tag_stack.pop()
        if tag in {"p", "li", "h1", "h2", "h3", "title"}:
            self._current_text = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data or "")
        if not text.strip():
            return
        if self._current_link is not None:
            self._current_link["text"] = normalize_space(f"{self._current_link.get('text', '')} {text}")
        if self._tag_stack and self._tag_stack[-1] in {"p", "li", "h1", "h2", "h3", "title"}:
            self._current_text.append(text)


def ensure_tree() -> None:
    for path in [RAW_DIR, PROCESSED_DIR, RELEASES_DIR, REPORT_DIR, IMAGE_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def now_jst() -> dt.datetime:
    return dt.datetime.now(TIMEZONE)


def now_iso() -> str:
    return now_jst().isoformat(timespec="seconds")


def today_string(value: str | None = None) -> str:
    return value or now_jst().date().isoformat()


def read_json_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    kept = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith(("utm_", "fbclid", "gclid"))
    ]
    path = re.sub(r"/+$", "", parsed.path) or "/"
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(kept), "")
    )


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def safe_slug(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or fallback


def fetch_url(url: str, timeout: int = 25) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SeigaBlogBot/1.0 (+https://blog.seigatabi.com/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
    return final_url, body


def parse_html(body: str) -> ArticleHTMLParser:
    parser = ArticleHTMLParser()
    parser.feed(body)
    return parser


def parse_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in SOURCES_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line == "sources:":
            continue
        if line.startswith("- "):
            if current:
                sources.append(current)
            current = {}
            line = line[2:].strip()
            if line:
                key, _, value = line.partition(":")
                current[key.strip()] = value.strip()
            continue
        if current is not None and ":" in line:
            key, _, value = line.partition(":")
            parsed_value: Any = value.strip()
            if parsed_value.isdigit():
                parsed_value = int(parsed_value)
            current[key.strip()] = parsed_value
    if current:
        sources.append(current)
    return sources


def has_java_exclusion(text: str) -> bool:
    return any(term.lower() in text.lower() for term in JAVA_EXCLUSION_TERMS)


def is_bedrock_candidate(title: str, text: str = "") -> bool:
    combined = f"{title}\n{text}"
    if has_java_exclusion(title):
        return False
    return bool(BEDROCK_INCLUDE_RE.search(combined) or BEDROCK_CONTEXT_RE.search(combined))


def post_paths() -> list[Path]:
    return sorted(POSTS_DIR.glob("*.md")) if POSTS_DIR.exists() else []


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1], parts[2]


def extract_scalar(frontmatter: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip("\"'")


def existing_bedrock_source_urls() -> set[str]:
    urls: set[str] = set()
    for path in post_paths():
        frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if extract_scalar(frontmatter, "edition") != "bedrock":
            continue
        source_url = extract_scalar(frontmatter, "source_url")
        if source_url:
            urls.add(canonical_url(source_url))
    return urls


def existing_bedrock_slugs() -> set[str]:
    slugs: set[str] = set()
    for path in post_paths():
        frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if extract_scalar(frontmatter, "edition") == "bedrock":
            slug = extract_scalar(frontmatter, "slug")
            if slug:
                slugs.add(slug)
    return slugs


def existing_bedrock_posts_by_slug() -> dict[str, Path]:
    posts: dict[str, Path] = {}
    for path in post_paths():
        frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
        if extract_scalar(frontmatter, "edition") != "bedrock":
            continue
        slug = extract_scalar(frontmatter, "slug")
        if slug:
            posts[slug] = path
    return posts


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
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


def raw_items_path(date_value: str) -> Path:
    return RAW_DIR / f"{date_value}-raw-items.json"


def normalized_items_path(date_value: str) -> Path:
    return PROCESSED_DIR / f"{date_value}-normalized-items.json"


def classified_items_path(date_value: str) -> Path:
    return PROCESSED_DIR / f"{date_value}-classified-items.json"


def selected_topic_path(date_value: str) -> Path:
    return PROCESSED_DIR / f"{date_value}-selected-topic.json"


def generation_report_path(date_value: str) -> Path:
    return PROCESSED_DIR / f"{date_value}-generation-report.json"


def validation_report_path(date_value: str) -> Path:
    return PROCESSED_DIR / f"{date_value}-validation-report.json"


def daily_report_path(date_value: str) -> Path:
    return REPORT_DIR / f"{date_value}-daily-report.md"
