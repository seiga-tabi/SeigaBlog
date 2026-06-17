#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_URL = "https://www.leagueoflegends.com"
PATCH_LIST_URL = f"{BASE_URL}/ko-kr/news/tags/patch-notes/"
POSTS_DIR = Path("_posts")
IMAGE_ROOT = Path("assets/images/lol-patch")
DEFAULT_IMAGE = "/assets/images/profile.png"
TIMEZONE = ZoneInfo("Asia/Tokyo")
USER_AGENT = (
    "SeigaBlog LoL patch automation "
    "(https://github.com/seiga-tabi/SeigaBlog)"
)


class LolPatchError(RuntimeError):
    pass


@dataclass
class PatchListing:
    title: str
    version: str
    url: str
    published_at: str
    description: str
    image_url: str | None


@dataclass
class TextEvent:
    tag: str
    text: str
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class ChampionChange:
    name: str
    context: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    classification: str = "조정"


@dataclass
class SectionSummary:
    title: str
    snippets: list[str] = field(default_factory=list)


class RichTextParser(HTMLParser):
    """Riot 패치노트 HTML에서 제목과 문장 단위 텍스트만 가볍게 추출한다."""

    TARGET_TAGS = {"h2", "h3", "h4", "p", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[TextEvent] = []
        self._stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            for item in self._stack:
                item["text"].append(" ")  # type: ignore[index, union-attr]
            return

        if tag in self.TARGET_TAGS:
            self._stack.append(
                {
                    "tag": tag,
                    "attrs": {key: value or "" for key, value in attrs},
                    "text": [],
                }
            )

    def handle_data(self, data: str) -> None:
        if not self._stack:
            return
        for item in self._stack:
            item["text"].append(data)  # type: ignore[index, union-attr]

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.TARGET_TAGS:
            return

        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag:
                item = self._stack.pop(index)
                text = normalize_space("".join(item["text"]))  # type: ignore[arg-type]
                if text:
                    self.events.append(
                        TextEvent(
                            tag=tag,
                            text=text,
                            attrs=item["attrs"],  # type: ignore[arg-type]
                        )
                    )
                return


def log(message: str) -> None:
    print(f"[LoL Patch] {message}")


def normalize_space(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def truncate(value: str, limit: int = 170) -> str:
    value = normalize_space(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def strip_trailing_ellipsis(value: str) -> str:
    return normalize_space(value).rstrip("…").rstrip()


def sentence_summary(value: str, max_sentences: int = 2, limit: int = 190) -> str:
    value = normalize_space(value)
    sentences = re.findall(r"[^.!?。]+[.!?。]?", value)
    summary = ""
    for sentence in sentences[:max_sentences]:
        candidate = normalize_space(f"{summary} {sentence}")
        if len(candidate) > limit:
            break
        summary = candidate

    if not summary:
        summary = truncate(value, limit)
    summary = strip_trailing_ellipsis(summary)
    if summary and summary[-1] not in ".!?。":
        summary += "."
    return summary


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.URLError as error:
        raise LolPatchError(f"공식 페이지 요청 실패: {url} ({error})") from error


def fetch_binary(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type()
            return response.read(), content_type
    except urllib.error.URLError as error:
        raise LolPatchError(f"이미지 다운로드 실패: {url} ({error})") from error


def extract_next_data(page_html: str) -> dict:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        page_html,
        flags=re.DOTALL,
    )
    if not match:
        raise LolPatchError("Riot 공식 페이지에서 __NEXT_DATA__를 찾지 못했습니다.")
    return json.loads(html.unescape(match.group(1)))


def page_payload(page_html: str) -> dict:
    data = extract_next_data(page_html)
    try:
        return data["props"]["pageProps"]["page"]
    except KeyError as error:
        raise LolPatchError("Riot 공식 페이지 데이터 구조가 예상과 다릅니다.") from error


def find_blade(page: dict, blade_type: str) -> dict:
    for blade in page.get("blades", []):
        if blade.get("type") == blade_type:
            return blade
    raise LolPatchError(f"Riot 공식 페이지에서 {blade_type} 블록을 찾지 못했습니다.")


def absolute_url(url: str) -> str:
    return urllib.parse.urljoin(BASE_URL, url)


def parse_patch_version(title: str) -> str:
    match = re.search(r"(\d{1,2})[.-](\d{1,2})", title)
    if not match:
        raise LolPatchError(f"패치 버전을 제목에서 찾지 못했습니다: {title}")
    return f"{int(match.group(1))}.{int(match.group(2))}"


def version_slug(version: str) -> str:
    return version.replace(".", "-")


def clean_html_text(raw_html: str) -> str:
    parser = RichTextParser()
    parser.feed(raw_html)
    return normalize_space(" ".join(event.text for event in parser.events))


def find_latest_patch() -> PatchListing:
    log("Riot 공식 패치노트 목록을 확인합니다.")
    page = page_payload(fetch_text(PATCH_LIST_URL))
    grid = find_blade(page, "articleCardGrid")
    items = grid.get("items", [])

    for item in sorted(items, key=lambda value: value.get("publishedAt", ""), reverse=True):
        title = normalize_space(item.get("title", ""))
        if "패치 노트" not in title:
            continue

        version = parse_patch_version(title)
        action_url = item.get("action", {}).get("payload", {}).get("url")
        if not action_url:
            continue

        description = item.get("description", {}).get("body", "")
        media = item.get("media") or item.get("imageMedia") or {}
        listing = PatchListing(
            title=title,
            version=version,
            url=absolute_url(action_url),
            published_at=item.get("publishedAt", ""),
            description=clean_html_text(description),
            image_url=media.get("url"),
        )
        log(f"최신 패치 감지: {listing.version} ({listing.title})")
        return listing

    raise LolPatchError("공식 패치노트 목록에서 리그 오브 레전드 패치 글을 찾지 못했습니다.")


def duplicate_post(version: str) -> Path | None:
    slug = f"lol-patch-{version_slug(version)}"
    if not POSTS_DIR.exists():
        return None

    version_pattern = re.compile(
        rf"patch_version:\s*['\"]?{re.escape(version)}['\"]?", flags=re.IGNORECASE
    )
    for post_path in POSTS_DIR.glob("*.md"):
        text = post_path.read_text(encoding="utf-8", errors="ignore")
        if version_pattern.search(text) or slug in post_path.stem:
            return post_path
    return None


def parse_article(listing: PatchListing) -> tuple[dict, list[TextEvent]]:
    log("최신 패치노트 본문을 수집합니다.")
    page = page_payload(fetch_text(listing.url))
    masthead = find_blade(page, "articleMasthead")
    rich_text = find_blade(page, "patchNotesRichText").get("richText", {}).get("body")
    if not rich_text:
        raise LolPatchError("패치노트 본문 HTML을 찾지 못했습니다.")

    parser = RichTextParser()
    parser.feed(rich_text)
    return masthead, parser.events


def extract_intro(events: list[TextEvent], fallback: str) -> str:
    for event in events:
        if event.tag == "h2":
            break
        if event.tag == "p" and len(event.text) > 40:
            intro = re.split(r"리그 오브 레전드의 모든 것|다른 패치 노트", event.text)[0]
            return truncate(intro, 260)
    return fallback or "이번 패치의 주요 변경점을 공식 패치노트 기준으로 정리했습니다."


def classify_champion(context: str, changes: str) -> str:
    combined = f"{context} {changes}"
    nerf_terms = [
        "하향",
        "낮추",
        "감소",
        "약화",
        "너무 강력",
        "강력한 모습",
        "위력을 낮",
        "톤다운",
    ]
    buff_terms = [
        "상향",
        "높여",
        "증가",
        "강화",
        "보완",
        "개선",
        "되돌리",
        "힘을 실어",
        "위력을 전반적으로 상향",
    ]
    nerf_score = sum(term in combined for term in nerf_terms)
    buff_score = sum(term in combined for term in buff_terms)
    numeric_score = numeric_change_score(changes)
    if numeric_score > 0:
        buff_score += numeric_score * 2
    elif numeric_score < 0:
        nerf_score += abs(numeric_score) * 2

    if nerf_score > buff_score:
        return "너프"
    if buff_score > nerf_score:
        return "버프"
    return "조정"


def numeric_change_score(changes: str) -> int:
    return sum(change_direction_score(change) for change in changes.split(" | "))


def change_direction_score(change: str) -> int:
    lower_is_better_terms = [
        "마나 소모량",
        "소모량",
        "재사용 대기시간",
        "대기시간",
        "비전투 상태 타이머",
        "타이머",
    ]

    if "⇒" not in change:
        return 0

    left, right = change.split("⇒", 1)
    before = first_number(left)
    after = first_number(right)
    if before is None or after is None or before == after:
        return 0

    lower_is_better = any(term in change for term in lower_is_better_terms)
    if lower_is_better:
        return 1 if after < before else -1
    return 1 if after > before else -1


def champion_detail(champion: ChampionChange, classification: str) -> str:
    target_score = 1 if classification == "버프" else -1 if classification == "너프" else 0
    for change in champion.changes:
        score = change_direction_score(change)
        if target_score and score == target_score:
            return change
    if champion.changes:
        return champion.changes[0]
    if champion.context:
        return champion.context[0]
    return ""


def first_number(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def extract_champions(events: list[TextEvent]) -> list[ChampionChange]:
    champions: list[ChampionChange] = []
    current_section = ""
    current_champion: ChampionChange | None = None

    for event in events:
        if event.tag == "h2":
            current_section = event.text
            current_champion = None
            continue

        if current_section != "챔피언":
            continue

        if event.tag == "h3":
            current_champion = ChampionChange(name=event.text)
            champions.append(current_champion)
            continue

        if not current_champion:
            continue

        if event.tag == "p" and len(event.text) > 25:
            current_champion.context.append(truncate(event.text, 210))
        elif event.tag == "li":
            current_champion.changes.append(truncate(event.text, 140))

    for champion in champions:
        champion.classification = classify_champion(
            " ".join(champion.context),
            " | ".join(champion.changes),
        )
    return champions


def extract_sections(events: list[TextEvent]) -> list[SectionSummary]:
    excluded = {"챔피언", "앞으로 나올 스킨 및 크로마", "버그 수정 및 편의성 개선"}
    sections: list[SectionSummary] = []
    current: SectionSummary | None = None

    for event in events:
        if event.tag == "h2":
            current = None
            if event.text not in excluded:
                current = SectionSummary(title=event.text)
                sections.append(current)
            continue

        if not current or len(current.snippets) >= 4:
            continue

        if event.tag in {"p", "li"} and len(event.text) > 10:
            current.snippets.append(truncate(event.text, 135))

    return [section for section in sections if section.snippets]


def pick_items(values: list[str], limit: int) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return "공식 패치노트에서 세부 변경을 확인해 주세요"
    if len(filtered) <= limit:
        return ", ".join(filtered)
    return ", ".join(filtered[:limit]) + f" 외 {len(filtered) - limit}개"


def summarize_champions(champions: list[ChampionChange], classification: str) -> str:
    selected = [champion for champion in champions if champion.classification == classification]
    if not selected:
        return "이번 패치에서 뚜렷하게 분류할 수 있는 챔피언 변경은 많지 않습니다."

    snippets: list[str] = []
    for champion in selected[:6]:
        detail = champion_detail(champion, classification)
        snippets.append(f"{champion.name}({truncate(detail, 54)})")
    return pick_items(snippets, 6)


def relevant_sections(sections: list[SectionSummary]) -> list[SectionSummary]:
    keywords = ["아이템", "룬", "체계", "시스템", "소환사", "무작위", "아레나"]
    preferred = [
        section
        for section in sections
        if any(keyword in section.title for keyword in keywords)
    ]
    return preferred or [
        section for section in sections if section.title not in {"패치 하이라이트"}
    ]


def summarize_system_sections(sections: list[SectionSummary]) -> str:
    selected = relevant_sections(sections)
    snippets = [
        f"{section.title}({truncate(section.snippets[0], 62)})"
        for section in selected[:3]
    ]
    return pick_items(snippets, 3)


def section_title_summary(sections: list[SectionSummary]) -> str:
    titles = [section.title for section in relevant_sections(sections)]
    return pick_items(titles, 3)


def champ_name_summary(champions: list[ChampionChange], classification: str, limit: int = 5) -> str:
    names = [champion.name for champion in champions if champion.classification == classification]
    return pick_items(names, limit)


def pick_items_ja(values: list[str], limit: int) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return "公式パッチノートをご確認ください"
    if len(filtered) <= limit:
        return "、".join(filtered)
    return "、".join(filtered[:limit]) + f" ほか{len(filtered) - limit}件"


def champ_name_summary_ja(champions: list[ChampionChange], classification: str, limit: int = 5) -> str:
    names = [champion.name for champion in champions if champion.classification == classification]
    return pick_items_ja(names, limit)


def build_post_data(
    listing: PatchListing,
    masthead: dict,
    events: list[TextEvent],
    image_path: str,
    checked_at: dt.datetime,
) -> dict:
    version = listing.version
    champions = extract_champions(events)
    sections = extract_sections(events)
    intro = extract_intro(events, listing.description)

    buff_champions = [champion.name for champion in champions if champion.classification == "버프"]
    nerf_champions = [champion.name for champion in champions if champion.classification == "너프"]
    adjusted_champions = [champion.name for champion in champions if champion.classification == "조정"]

    buff_summary = summarize_champions(champions, "버프")
    nerf_summary = summarize_champions(champions, "너프")
    system_summary = summarize_system_sections(sections)
    changed_area_summary = section_title_summary(sections)
    publish_date = parse_iso_date(listing.published_at)
    today = checked_at.date().isoformat()

    ko_title = f"리그오브레전드 {version} 패치노트 핵심 정리"
    ja_title = f"リーグ・オブ・レジェンド {version} パッチノート要点まとめ"
    ko_description = (
        f"LoL {version} 패치의 챔피언 변경, 아이템/시스템 조정, "
        "솔랭 메타 영향을 쉽게 정리했습니다."
    )
    ja_description = (
        f"LoL {version} パッチのチャンピオン変更、アイテムやシステム調整、"
        "ソロランクへの影響を整理しました。"
    )

    ko_body = [
        f"패치 요약: {sentence_summary(intro, max_sentences=2, limit=210)}",
        (
            f"핵심 변경점: 챔피언 변경은 버프 {len(buff_champions)}명, "
            f"너프 {len(nerf_champions)}명, 기타 조정 {len(adjusted_champions)}명입니다. "
            f"비챔피언 변경은 {changed_area_summary} 중심입니다."
        ),
        f"챔피언 버프: {buff_summary}",
        f"챔피언 너프: {nerf_summary}",
        f"아이템/룬/시스템 변경: {system_summary}",
        (
            "솔랭 메타 영향: 상향 챔피언은 패치 초반 픽률이 빠르게 오를 수 있고, "
            f"{pick_items(nerf_champions, 4)} 같은 하향 챔피언은 초반 교전력이나 주도권을 다시 점검해야 합니다."
        ),
        (
            f"추천/주의할 챔피언: 추천 후보는 {pick_items(buff_champions, 4)}이며, "
            f"주의해서 다룰 챔피언은 {pick_items(nerf_champions, 4)}입니다."
        ),
        (
            f"마무리 요약: {version} 패치는 특정 챔피언 하나를 크게 뒤집기보다 "
            "상위권과 솔랭에서 눈에 띈 선택지를 다듬는 성격이 강합니다."
        ),
        f"공식 출처: {listing.url}",
        "이미지 출처: Riot Games 공식 리그 오브 레전드 패치노트 이미지입니다.",
    ]

    ja_body = [
        f"パッチ概要: {version} はチャンピオン調整とモード/システム更新が中心です。",
        (
            f"主な変更点: 強化 {len(buff_champions)}名、弱体化 {len(nerf_champions)}名、"
            f"その他調整 {len(adjusted_champions)}名です。"
        ),
        f"チャンピオン強化: {champ_name_summary_ja(champions, '버프', 6)}",
        f"チャンピオン弱体化: {champ_name_summary_ja(champions, '너프', 6)}",
        f"アイテム/ルーン/システム変更: {pick_items_ja([section.title for section in relevant_sections(sections)], 3)}",
        (
            "ソロランクへの影響: 強化されたチャンピオンは序盤に使用率が上がりやすく、"
            f"{pick_items_ja(nerf_champions, 4)} はレーン戦や集団戦の基準を見直す必要があります。"
        ),
        (
            f"おすすめ/注意チャンピオン: おすすめ候補は {pick_items_ja(buff_champions, 4)}、"
            f"注意したい候補は {pick_items_ja(nerf_champions, 4)} です。"
        ),
        (
            f"まとめ: {version} パッチはメタ全体を大きく壊すより、"
            "目立っていた選択肢を整える調整が中心です。"
        ),
        f"公式ソース: {listing.url}",
        "画像出典: Riot Games公式リーグ・オブ・レジェンドパッチノート画像です。",
    ]

    return {
        "slug": f"lol-patch-{version_slug(version)}-summary",
        "category": "lol",
        "accent": "blue",
        "read_time": "5 min",
        "image": image_path,
        "date": today,
        "patch_version": version,
        "source_url": listing.url,
        "source_title": listing.title,
        "source_published_at": publish_date,
        "last_checked": checked_at.isoformat(timespec="seconds"),
        "description": ko_description,
        "categories": ["League of Legends", "Patch Notes"],
        "tags": ["롤", "리그오브레전드", "LoL", "패치노트", "솔랭", "메타"],
        "author": {"ko": "세이가", "ja": "セイガ"},
        "badge": {"ko": "LOL 패치", "ja": "LoLパッチ"},
        "title": {"ko": ko_title, "ja": ja_title},
        "excerpt": {"ko": ko_description, "ja": ja_description},
        "post_tags": {
            "ko": ["롤", "패치노트", "솔랭", "메타"],
            "ja": ["LoL", "パッチノート", "ソロランク", "メタ"],
        },
        "lead": {
            "ko": f"{listing.title}를 공식 패치노트 기준으로 읽기 쉽게 요약했습니다.",
            "ja": f"リーグ・オブ・レジェンド {version} パッチノートを公式情報に基づいて整理しました。",
        },
        "body": {"ko": ko_body, "ja": ja_body},
        "quote": {
            "ko": "이번 패치는 상향 챔피언의 실험 가치와 하향 챔피언의 숙련도 점검이 함께 필요한 업데이트입니다.",
            "ja": "今回のパッチは、強化チャンピオンの試用価値と弱体化チャンピオンの熟練度確認が同時に求められる更新です。",
        },
        "image_credit": {
            "ko": "Riot Games 공식 패치노트 이미지",
            "ja": "Riot Games公式パッチノート画像",
        },
    }


def parse_iso_date(value: str) -> str:
    if not value:
        return ""
    try:
        normalized = value.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        return value


def optimized_image_url(image_url: str) -> str:
    parsed = urllib.parse.urlparse(image_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "w": "1200",
            "h": "675",
            "fm": "webp",
            "fit": "crop",
            "crop": "center",
            "q": "82",
        }
    )
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def image_extension(content_type: str, fallback_url: str) -> str:
    if content_type == "image/webp":
        return "webp"
    if content_type == "image/png":
        return "png"
    if content_type in {"image/jpeg", "image/jpg"}:
        return "jpg"
    path_suffix = Path(urllib.parse.urlparse(fallback_url).path).suffix.lower().lstrip(".")
    if path_suffix in {"webp", "png", "jpg", "jpeg"}:
        return "jpg" if path_suffix == "jpeg" else path_suffix
    return "jpg"


def download_cover_image(listing: PatchListing, dry_run: bool) -> tuple[str, list[Path]]:
    if not listing.image_url:
        log("대표 이미지를 찾지 못해 기본 썸네일을 사용합니다.")
        return DEFAULT_IMAGE, []

    patch_dir = IMAGE_ROOT / version_slug(listing.version)
    image_url = optimized_image_url(listing.image_url)
    generated_paths: list[Path] = []

    if dry_run:
        log(f"대표 이미지 다운로드 예정: {image_url}")
        return f"/{patch_dir.as_posix()}/cover.webp", []

    try:
        binary, content_type = fetch_binary(image_url)
        extension = image_extension(content_type, image_url)
    except LolPatchError as error:
        log(f"{error}")
        log("이미지 수집에 실패해 기본 썸네일을 사용합니다.")
        return DEFAULT_IMAGE, []

    patch_dir.mkdir(parents=True, exist_ok=True)
    image_path = patch_dir / f"cover.{extension}"
    if image_path.exists():
        log(f"기존 이미지를 덮어쓰지 않고 재사용합니다: {image_path}")
    else:
        image_path.write_bytes(binary)
        generated_paths.append(image_path)
        log(f"대표 이미지 저장: {image_path}")

    return f"/{image_path.as_posix()}", generated_paths


def yaml_scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_lines(value: object, indent: int = 0) -> list[str]:
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


def render_post(post_data: dict) -> str:
    frontmatter = "\n".join(yaml_lines(post_data))
    return (
        "---\n"
        f"{frontmatter}\n"
        "---\n\n"
        "<!-- 이 글은 scripts/generate_lol_patch_post.py로 자동 생성되었습니다. -->\n"
    )


def write_post(post_data: dict, checked_at: dt.datetime, dry_run: bool) -> Path:
    post_date = checked_at.date().isoformat()
    post_path = POSTS_DIR / f"{post_date}-{post_data['slug']}.md"
    if post_path.exists():
        raise LolPatchError(f"기존 글을 덮어쓰지 않습니다: {post_path}")

    if dry_run:
        log(f"게시글 생성 예정: {post_path}")
        return post_path

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    post_path.write_text(render_post(post_data), encoding="utf-8")
    log(f"게시글 저장: {post_path}")
    return post_path


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise LolPatchError(f"git {' '.join(args)} 실패: {message}")
    return result


def git_status(paths: list[Path] | None = None) -> str:
    args = ["status", "--short"]
    if paths:
        args.append("--")
        args.extend(path.as_posix() for path in paths)
    return run_git(args).stdout.strip()


def commit_and_push(version: str, paths: list[Path], no_push: bool) -> None:
    if not paths:
        log("새로 저장된 파일이 없어 commit/push를 건너뜁니다.")
        return

    log("git status를 확인합니다.")
    scoped_status = git_status(paths)
    if not scoped_status:
        log("변경 파일이 없어 commit/push를 건너뜁니다.")
        return

    log(scoped_status)
    run_git(["add", "--", *[path.as_posix() for path in paths]])
    diff = run_git(["diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        log("스테이징된 변경이 없어 commit/push를 건너뜁니다.")
        return

    message = f"blog: add LoL patch {version} summary"
    log(f"commit 생성: {message}")
    run_git(["commit", "-m", message])

    if no_push:
        log("--no-push 옵션으로 push를 건너뜁니다.")
        return

    log("원격 저장소로 push합니다.")
    push = run_git(["push", "origin", "HEAD"], check=False)
    if push.returncode != 0:
        reason = push.stderr.strip() or push.stdout.strip()
        raise LolPatchError(f"git push 실패: {reason}")
    log("push 완료")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Riot 공식 리그 오브 레전드 최신 패치노트를 Jekyll 블로그 글로 생성합니다."
    )
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 수집 결과만 확인합니다.")
    parser.add_argument("--skip-git", action="store_true", help="git commit/push 단계를 건너뜁니다.")
    parser.add_argument("--no-push", action="store_true", help="commit은 만들고 push만 건너뜁니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skip_git = args.skip_git or os.getenv("LOL_PATCH_SKIP_GIT") == "1"
    checked_at = dt.datetime.now(TIMEZONE)

    try:
        listing = find_latest_patch()
        duplicate = duplicate_post(listing.version)
        if duplicate:
            log(f"이미 작성된 패치입니다: {listing.version} ({duplicate})")
            return 0

        masthead, events = parse_article(listing)
        image_path, image_files = download_cover_image(listing, args.dry_run)
        post_data = build_post_data(listing, masthead, events, image_path, checked_at)
        post_path = write_post(post_data, checked_at, args.dry_run)

        if args.dry_run:
            log("dry-run 완료: 파일, commit, push 모두 수행하지 않았습니다.")
            return 0

        generated_paths = [post_path, *image_files]
        if skip_git:
            log("git 자동화는 건너뛰었습니다.")
            return 0

        commit_and_push(listing.version, generated_paths, args.no_push)
        return 0
    except LolPatchError as error:
        print(f"[LoL Patch] 오류: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
