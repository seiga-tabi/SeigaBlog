from __future__ import annotations

import datetime as dt
import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = REPO_ROOT / "_posts"
DATA_DIR = REPO_ROOT / "data" / "lol"
REPORTS_DIR = REPO_ROOT / "reports"
BLOG_IMAGE_DIR = REPO_ROOT / "assets" / "images" / "blog" / "generated"
CHAMPION_IMAGE_DIR = REPO_ROOT / "assets" / "images" / "lol" / "champions"

CHAMPIONS_PATH = DATA_DIR / "champions.json"
CHAMPION_NAME_MAP_PATH = DATA_DIR / "champion-name-map.json"

SAMPLE_PATTERNS = [
    "sample",
    "test",
    "demo",
    "dummy",
    "example",
    "placeholder",
    "lorem",
    "hello-world",
    "샘플",
    "예제",
    "테스트",
    "더미",
    "임시글",
]

TODO_PATTERNS = ["TODO", "작성 예정", "임시", "placeholder"]


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: object) -> None:
    ensure_parent(path)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def post_paths() -> list[Path]:
    if not POSTS_DIR.exists():
        return []
    return sorted(POSTS_DIR.glob("*.md"))


def split_frontmatter(text: str) -> tuple[str, str, str]:
    if not text.startswith("---\n"):
        return "", text, ""
    end = text.find("\n---", 4)
    if end == -1:
        return "", text, ""
    frontmatter = text[4:end]
    body = text[end + len("\n---") :]
    return frontmatter, body, text[: end + len("\n---")]


def extract_scalar(frontmatter: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, flags=re.MULTILINE)
    if not match:
        return ""
    return unquote(match.group(1).strip())


def extract_localized_scalar(frontmatter: str, section: str, lang: str) -> str:
    lines = frontmatter.splitlines()
    in_section = False
    section_indent = 0
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped == f"{section}:":
            in_section = True
            section_indent = indent
            continue
        if in_section and indent <= section_indent and stripped:
            in_section = False
        if in_section:
            match = re.match(rf"\s*{lang}:\s*(.+)$", line)
            if match:
                return unquote(match.group(1).strip())
    return ""


def extract_localized_list(frontmatter: str, section: str, lang: str) -> list[str]:
    lines = frontmatter.splitlines()
    in_section = False
    in_lang = False
    section_indent = 0
    lang_indent = 0
    values: list[str] = []

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped == f"{section}:":
            in_section = True
            in_lang = False
            section_indent = indent
            continue
        if in_section and indent <= section_indent and stripped:
            break
        if in_section and re.match(rf"\s*{lang}:\s*$", line):
            in_lang = True
            lang_indent = indent
            continue
        if in_lang and indent <= lang_indent and stripped:
            break
        if in_lang:
            match = re.match(r"\s*-\s*(.+)$", line)
            if match:
                values.append(unquote(match.group(1).strip()))

    return values


def unquote(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parsed = json.loads(value)
        if isinstance(parsed, str):
            return parsed
    except json.JSONDecodeError:
        pass
    return value.strip("\"'")


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value))
    value = value.lower()
    value = value.replace("’", "'").replace("`", "'")
    value = value.replace("&", "and")
    return re.sub(r"[^0-9a-z가-힣ぁ-んァ-ヶ一-龯々ー]", "", value)


def load_champion_map() -> dict:
    if not CHAMPION_NAME_MAP_PATH.exists():
        raise FileNotFoundError(
            "챔피언명 데이터가 없습니다. 먼저 `npm run sync:lol`을 실행하세요."
        )
    return read_json(CHAMPION_NAME_MAP_PATH)


def champion_entries(name_map: dict) -> list[dict]:
    champions = name_map.get("champions", {})
    if isinstance(champions, dict):
        return list(champions.values())
    return list(champions)


def champion_lookup(name_map: dict) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for entry in champion_entries(name_map):
        for alias in entry.get("aliases", []):
            normalized = normalize_name(alias)
            if normalized:
                lookup[normalized] = entry
    return lookup


def detect_champions(text: str, name_map: dict) -> list[dict]:
    normalized_text = normalize_name(text)
    found: list[dict] = []
    seen: set[str] = set()

    for entry in champion_entries(name_map):
        aliases = sorted(entry.get("aliases", []), key=len, reverse=True)
        for alias in aliases:
            normalized_alias = normalize_name(alias)
            if len(normalized_alias) < 2:
                continue
            if is_ascii_name(alias):
                matched = bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE))
            else:
                matched = normalized_alias in normalized_text
            if matched:
                key = entry["key"]
                if key not in seen:
                    found.append(entry)
                    seen.add(key)
                break

    return found


def localized_name(entry: dict, lang: str) -> str:
    return entry.get(lang) or entry.get("en") or entry.get("key", "")


def replace_champion_names(text: str, lang: str, name_map: dict) -> tuple[str, list[dict]]:
    result = text
    changes: list[dict] = []
    aliases: list[tuple[str, dict]] = []

    for entry in champion_entries(name_map):
        official = localized_name(entry, lang)
        for alias in entry.get("aliases", []):
            if not alias or alias == official:
                continue
            aliases.append((alias, entry))

    aliases.sort(key=lambda item: len(item[0]), reverse=True)

    for alias, entry in aliases:
        official = localized_name(entry, lang)
        before = result
        if is_ascii_name(alias):
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", re.IGNORECASE)
            result = pattern.sub(official, result)
        else:
            result = result.replace(alias, official)
        if result != before:
            changes.append(
                {
                    "alias": alias,
                    "official": official,
                    "key": entry["key"],
                    "lang": lang,
                }
            )

    return result, changes


def is_ascii_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9 .'\-&]+", value))


def localized_line_language(line: str, current: tuple[str | None, int]) -> tuple[str | None, int]:
    current_lang, current_indent = current
    indent = len(line) - len(line.lstrip(" "))
    stripped = line.strip()

    if not stripped:
        return current

    if re.match(r"^\s*ko:\s*", line):
        return "ko", indent
    if re.match(r"^\s*ja:\s*", line):
        return "ja", indent
    if current_lang and indent <= current_indent and not stripped.startswith("-"):
        return None, 0
    return current


def svg_escape(value: str) -> str:
    return html.escape(value, quote=True)


def wrap_text(value: str, width: int) -> list[str]:
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return []

    lines: list[str] = []
    current = ""
    for word in re.findall(r"\S+", value):
        if visual_length(word) > width:
            if current:
                lines.append(current)
                current = ""
            chunk = ""
            for char in word:
                candidate = f"{chunk}{char}"
                if visual_length(candidate) > width and chunk:
                    lines.append(chunk)
                    chunk = char
                else:
                    chunk = candidate
            if chunk:
                current = chunk
            continue

        candidate = word if not current else f"{current} {word}"
        if visual_length(candidate) > width and current:
            lines.append(current.strip())
            current = word
        else:
            current = candidate
    if current:
        lines.append(current.strip())
    return lines


def visual_length(value: str) -> int:
    total = 0
    for char in value:
        total += 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
    return total


def local_asset_exists(src: str) -> bool:
    if src.startswith("http://") or src.startswith("https://"):
        return True
    if not src.startswith("/"):
        return False
    return (REPO_ROOT / src.lstrip("/")).exists()


def image_srcs_from_frontmatter(frontmatter: str) -> list[str]:
    srcs = []
    for pattern in [r"^[ \t]*image:[ \t]*(.+)$", r"^og_image:[ \t]*(.+)$", r"^[ \t]*src:[ \t]*(.+)$"]:
        for match in re.finditer(pattern, frontmatter, flags=re.MULTILINE):
            srcs.append(unquote(match.group(1).strip()))
    for match in re.finditer(r"['\"](/assets/images/[^'\"]+)['\"]", frontmatter):
        srcs.append(match.group(1))
    return unique([src for src in srcs if src])


def write_report(name: str, data: object) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / name
    write_json(path, data)
    return path


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
