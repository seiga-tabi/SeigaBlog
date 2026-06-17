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

from lol_content_utils import load_champion_map, normalize_name


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


def load_optional_name_map() -> dict | None:
    try:
        return load_champion_map()
    except FileNotFoundError:
        return None


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


def official_champion_name(name: str, lang: str, name_map: dict | None) -> str:
    if not name_map:
        return name
    normalized = normalize_name(name)
    for entry in name_map.get("champions", {}).values():
        aliases = [entry.get("key", ""), entry.get("en", ""), entry.get("ko", ""), entry.get("ja", "")]
        aliases.extend(entry.get("aliases", []))
        if normalized in {normalize_name(alias) for alias in aliases if alias}:
            return entry.get(lang) or name
    return name


def official_names_for_class(
    champions: list[ChampionChange],
    classification: str,
    lang: str,
    name_map: dict | None,
    limit: int,
) -> str:
    names = [
        official_champion_name(champion.name, lang, name_map)
        for champion in champions
        if champion.classification == classification
    ]
    return pick_items_ja(names, limit) if lang == "ja" else pick_items(names, limit)


def official_champion_entry(name: str, name_map: dict | None) -> dict:
    fallback = {"key": normalize_name(name), "ko": name, "ja": name}
    if not name_map:
        return fallback

    normalized = normalize_name(name)
    for entry in name_map.get("champions", {}).values():
        aliases = [entry.get("key", ""), entry.get("en", ""), entry.get("ko", ""), entry.get("ja", "")]
        aliases.extend(entry.get("aliases", []))
        if normalized in {normalize_name(alias) for alias in aliases if alias}:
            return {"key": entry["key"], "ko": entry["ko"], "ja": entry["ja"]}
    return fallback


def champion_metadata(champions: list[ChampionChange], name_map: dict | None) -> list[dict]:
    result = []
    for champion in champions:
        entry = official_champion_entry(champion.name, name_map)
        result.append({**entry, "status": champion.classification})
    return result


def status_label(status: str) -> dict:
    if status == "버프":
        return {"ko": "버프", "ja": "強化"}
    if status == "너프":
        return {"ko": "너프", "ja": "弱体化"}
    if status == "추천":
        return {"ko": "추천", "ja": "おすすめ"}
    if status == "주의":
        return {"ko": "주의", "ja": "注意"}
    if status == "조건부 추천":
        return {"ko": "조건부 추천", "ja": "条件付きおすすめ"}
    return {"ko": "조정", "ja": "調整"}


def champion_card_data(champion: ChampionChange, status: str, name_map: dict | None) -> dict:
    entry = official_champion_entry(champion.name, name_map)
    detail = champion_detail(champion, status)
    detail_text = truncate(detail, 120) if detail else "공식 변경 수치는 패치노트 원문에서 확인해야 합니다."
    context = sentence_summary(" ".join(champion.context), max_sentences=1, limit=150)

    if status == "버프":
        impact_ko = "패치 초반에는 주 포지션과 조합 적합도를 먼저 확인하세요."
        impact_ja = "パッチ序盤はメインポジションと構成適性を先に確認しましょう。"
        tip_ko = "상향된 스킬을 중심으로 짧은 교환과 오브젝트 전 교전을 먼저 실험하세요."
        tip_ja = "強化されたスキルを中心に、短いトレードとオブジェクト前の戦闘を試しましょう。"
        caution_ko = "수치가 올랐더라도 라인 상성과 숙련도 조건을 무시하면 효율이 떨어집니다."
        caution_ja = "数値が上がっても、レーン相性と熟練度条件を無視すると効率は落ちます。"
    elif status == "너프":
        impact_ko = "익숙한 픽이라도 교전 기준을 한 단계 보수적으로 잡으세요."
        impact_ja = "慣れたピックでも交戦基準を一段階慎重に見ましょう。"
        tip_ko = "하향된 스킬이 필요한 타이밍을 늦추고, 확정 교전 위주로 운영하세요."
        tip_ja = "弱体化されたスキルが必要なタイミングを遅らせ、確定気味の戦闘を選びましょう。"
        caution_ko = "숙련 픽은 여전히 쓸 수 있지만 패치 첫날에는 과한 선픽을 피하는 편이 안전합니다."
        caution_ja = "熟練ピックならまだ使えますが、パッチ初日は強引な先出しを避ける方が安全です。"
    else:
        impact_ko = "빌드와 역할 변화가 실제 체감으로 이어지는지 확인하세요."
        impact_ja = "ビルドと役割の変化が体感につながるか確認しましょう。"
        tip_ko = "공식 변경 수치를 기준으로 기존 콤보와 빌드 타이밍을 다시 점검하세요."
        tip_ja = "公式変更数値を基準に、既存コンボとビルドタイミングを見直しましょう。"
        caution_ko = "조정 카드는 승률 표본이 쌓이기 전까지 단정하지 않는 편이 좋습니다."
        caution_ja = "調整カードは勝率サンプルが集まるまで断定しない方が安全です。"

    return {
        "key": entry["key"],
        "ko": entry["ko"],
        "ja": entry["ja"],
        "image": f"/assets/images/lol/champions/{entry['key']}/splash.jpg",
        "alt": {
            "ko": f"{entry['ko']} 스플래시 아트",
            "ja": f"{entry['ja']}のスプラッシュアート",
        },
        "status_label": status_label(status),
        "role": {"ko": "주 포지션 확인", "ja": "主ロール確認"},
        "change_summary": {
            "ko": [detail_text],
            "ja": [detail_text],
        },
        "riot_context": {
            "ko": context or "Riot 공식 패치노트의 변경 의도를 기준으로 요약했습니다.",
            "ja": "Riot公式パッチノートの変更意図を基準に整理しています。",
        },
        "solo_queue_impact": {"ko": impact_ko, "ja": impact_ja},
        "play_tip": {"ko": tip_ko, "ja": tip_ja},
        "caution": {"ko": caution_ko, "ja": caution_ja},
        "priority": "medium",
        "priority_label": {"ko": "중간", "ja": "中"},
        "difficulty": "medium",
        "difficulty_label": {"ko": "중간", "ja": "中"},
        "tags": {
            "ko": ["솔랭", "공식 수치", status],
            "ja": ["ソロランク", "公式数値", status_label(status)["ja"]],
        },
        "target_anchor": f"#champion-{entry['key'].lower()}",
        "source_anchor": "#source-note",
    }


def recommended_card_data(champion: ChampionChange, name_map: dict | None) -> dict:
    card = champion_card_data(champion, "버프", name_map)
    card["status_label"] = status_label("추천")
    card["summary"] = {
        "ko": "상향 폭, 솔랭 적응 난이도, 조합 유연성을 함께 볼 때 먼저 연습할 만합니다.",
        "ja": "強化幅、ソロランクでの適応難度、構成への柔軟性を考えると先に練習する価値があります。",
    }
    card["solo_queue_impact"] = {
        "ko": "주 포지션과 맞는다면 패치 초반 우선 실험하세요.",
        "ja": "メインポジションに合うならパッチ序盤に優先して試しましょう。",
    }
    card["recommendation_grade"] = "A"
    card["recommended_line"] = card["role"]
    card["recommend_reason"] = {
        "ko": "공식 상향 수치가 있고 솔랭 적응 난도가 과하게 높지 않은 후보입니다.",
        "ja": "公式強化数値があり、ソロランクでの適応難度も高すぎない候補です。",
    }
    card["recommended_for"] = {
        "ko": "해당 포지션을 꾸준히 플레이하고 패치 초반 실험을 좋아하는 유저",
        "ja": "該当ロールを継続して使い、パッチ序盤の試行が好きなプレイヤー",
    }
    card["matchup_caution"] = {
        "ko": "추천 카드라도 라인 상성과 조합 조건이 맞지 않으면 우선순위를 낮추세요.",
        "ja": "おすすめカードでもレーン相性と構成条件が合わない場合は優先度を下げましょう。",
    }
    card["grade"] = "A"
    card["reason"] = card["recommend_reason"]
    card["fit_user"] = card["recommended_for"]
    card["key_change"] = {
        "ko": card["change_summary"]["ko"][0],
        "ja": card["change_summary"]["ja"][0],
    }
    card["alt"] = {
        "ko": f"{card['ko']} 추천 픽 스플래시 아트",
        "ja": f"{card['ja']}おすすめピックのスプラッシュアート",
    }
    return card


def conditional_card_data(champion: ChampionChange, name_map: dict | None) -> dict:
    card = recommended_card_data(champion, name_map)
    card["status_label"] = status_label("조건부 추천")
    card["grade"] = "B"
    card["condition"] = {
        "ko": "주 포지션 숙련도와 조합 조건이 맞을 때",
        "ja": "メインロールの熟練度と構成条件が合う時",
    }
    card["reason"] = card["key_change"]
    card["caution"] = {
        "ko": "상향 수치만 보고 선픽하면 라인 상성에 흔들릴 수 있습니다.",
        "ja": "強化数値だけを見て先出しすると、レーン相性に左右されやすいです。",
    }
    return card


def watch_card_data(champion: ChampionChange, name_map: dict | None) -> dict:
    card = champion_card_data(champion, "너프", name_map)
    card["status_label"] = status_label("주의")
    card["alt"] = {
        "ko": f"{card['ko']} 주의 픽 스플래시 아트",
        "ja": f"{card['ja']}注意ピックのスプラッシュアート",
    }
    card["first_day_rating"] = {"ko": "첫날 보수적", "ja": "初日は慎重"}
    card["key_nerf"] = {
        "ko": card["change_summary"]["ko"][0],
        "ja": card["change_summary"]["ja"][0],
    }
    card["usable_condition"] = {
        "ko": "숙련도가 높고 조합 조건이 맞을 때만 랭크 첫날 사용을 고려하세요.",
        "ja": "熟練度が高く構成条件が合う時だけ、ランク初日の使用を考えましょう。",
    }
    card["risk"] = card["caution"]
    return card


def build_toc() -> dict:
    return {
        "title": {"ko": "목차", "ja": "目次"},
        "items": [
            {"id": "patch-overview", "title": {"ko": "한눈에 보는 패치", "ja": "パッチ早見表"}},
            {"id": "quick-summary", "title": {"ko": "30초 핵심 요약", "ja": "30秒で分かる要点"}},
            {"id": "buff-champions", "title": {"ko": "버프 챔피언 총정리", "ja": "強化チャンピオン総まとめ"}},
            {"id": "nerf-champions", "title": {"ko": "너프 챔피언 총정리", "ja": "弱体化チャンピオン総まとめ"}},
            {"id": "solo-queue-tier-impact", "title": {"ko": "라인별 솔랭 영향", "ja": "ロール別ソロランク影響"}},
            {"id": "recommended-picks", "title": {"ko": "추천 픽 TOP 5", "ja": "おすすめピックTOP5"}},
            {"id": "conditional-picks", "title": {"ko": "조건부 추천 픽", "ja": "条件付きおすすめピック"}},
            {"id": "watch-picks", "title": {"ko": "주의해야 할 픽", "ja": "注意したいピック"}},
            {"id": "item-rune-system", "title": {"ko": "시스템/모드 변경", "ja": "システム/モード変更"}},
            {"id": "patch-day-checklist", "title": {"ko": "패치 첫날 체크리스트", "ja": "パッチ初日チェックリスト"}},
            {"id": "faq", "title": {"ko": "FAQ", "ja": "FAQ"}},
            {"id": "source-note", "title": {"ko": "공식 출처 및 이미지 출처", "ja": "公式ソースと画像出典"}},
        ],
    }


def build_overview_table(
    version: str,
    source_published_at: str,
    last_checked: str,
    buff_count: int,
    nerf_count: int,
    adjusted_count: int,
    changed_area_summary: str,
) -> dict:
    return {
        "title": {"ko": "한눈에 보는 패치", "ja": "パッチ早見表"},
        "rows": [
            {"label": {"ko": "패치 버전", "ja": "パッチバージョン"}, "value": {"ko": version, "ja": version}},
            {"label": {"ko": "공식 게시일", "ja": "公式公開日"}, "value": {"ko": source_published_at, "ja": source_published_at}},
            {"label": {"ko": "블로그 확인일", "ja": "ブログ確認日"}, "value": {"ko": last_checked, "ja": last_checked}},
            {
                "label": {"ko": "챔피언 조정", "ja": "チャンピオン調整"},
                "value": {
                    "ko": f"버프 카드 {buff_count}장 / 너프 카드 {nerf_count}장 / 조정 카드 {adjusted_count}장",
                    "ja": f"強化カード{buff_count}枚 / 弱体化カード{nerf_count}枚 / 調整カード{adjusted_count}枚",
                },
            },
            {
                "label": {"ko": "핵심 방향", "ja": "主な方針"},
                "value": {
                    "ko": "대회 전 선택지 다양성과 솔랭 체감 조정",
                    "ja": "大会前の選択肢多様性とソロランク体感の調整",
                },
            },
            {
                "label": {"ko": "핵심 상향", "ja": "主な強化"},
                "value": {
                    "ko": "상향 카드는 풀 카드에서 공식 수치와 조건을 확인",
                    "ja": "強化カードはフルカードで公式数値と条件を確認",
                },
            },
            {
                "label": {"ko": "핵심 하향", "ja": "主な弱体化"},
                "value": {
                    "ko": "하향 카드는 피해량, 체급, 유지력 변화를 분리 확인",
                    "ja": "弱体化カードはダメージ、基礎性能、サステインを分けて確認",
                },
            },
            {
                "label": {"ko": "가장 큰 솔랭 포인트", "ja": "最大のソロランク要点"},
                "value": {
                    "ko": "추천 미니 카드와 주의 미니 카드를 먼저 비교",
                    "ja": "おすすめミニカードと注意ミニカードを先に比較",
                },
            },
            {
                "label": {"ko": "추천 독자", "ja": "おすすめ読者"},
                "value": {
                    "ko": "패치 첫날 랭크 전에 핵심 수치만 빠르게 확인할 유저",
                    "ja": "パッチ初日のランク前に主な数値を素早く確認したいプレイヤー",
                },
            },
            {
                "label": {"ko": "비챔피언 변경", "ja": "非チャンピオン変更"},
                "value": {
                    "ko": changed_area_summary,
                    "ja": "システム、ルーン、モード変更を確認",
                },
            },
        ],
    }


def build_sections(version: str, intro: str) -> list[dict]:
    return [
        {
            "id": "quick-summary",
            "kind": "quick_summary",
            "title": {"ko": "30초 핵심 요약", "ja": "30秒で分かる要点"},
            "body": {
                "ko": [
                    f"{version} 패치의 방향을 먼저 보면 챔피언 카드의 의미가 더 빨리 잡힙니다.",
                ],
                "ja": [
                    f"{version}パッチの方針を先に見ると、各カードの意味がつかみやすくなります。",
                ],
            },
        },
        {
            "id": "buff-champions",
            "kind": "buff_cards",
            "title": {"ko": "버프 챔피언 총정리", "ja": "強化チャンピオン総まとめ"},
            "body": {
                "ko": [
                    "상향 카드는 공식 변경 수치와 솔랭 활용 조건을 함께 확인해야 합니다.",
                ],
                "ja": [
                    "強化カードは公式変更数値とソロランクでの使いどころを合わせて確認しましょう。",
                ],
            },
        },
        {
            "id": "nerf-champions",
            "kind": "nerf_cards",
            "title": {"ko": "너프 챔피언 총정리", "ja": "弱体化チャンピオン総まとめ"},
            "body": {
                "ko": [
                    "하향 카드는 성능이 내려간 지점과 그래도 쓸 수 있는 조건을 나눠 봐야 합니다.",
                ],
                "ja": [
                    "弱体化カードは落ちた性能と、それでも使える条件を分けて見るのが重要です。",
                ],
            },
        },
        {
            "id": "solo-queue-tier-impact",
            "kind": "lane_impact",
            "title": {"ko": "라인별 솔랭 영향", "ja": "ロール別ソロランク影響"},
            "body": {
                "ko": [
                    "자기 포지션에 해당하는 카드만 먼저 읽어도 패치 첫날 판단이 쉬워집니다.",
                ],
                "ja": [
                    "自分のロールに関係するカードだけ先に読んでも、パッチ初日の判断がしやすくなります。",
                ],
            },
        },
        {
            "id": "recommended-picks",
            "kind": "recommended_cards",
            "title": {"ko": "추천 픽 TOP 5", "ja": "おすすめピックTOP5"},
            "body": {
                "ko": [
                    "이 추천은 공식 변경 수치와 솔랭 적용 난도를 바탕으로 한 패치 초반 예상입니다. 실시간 승률 데이터가 아님을 전제로 참고하세요.",
                ],
                "ja": [
                    "このおすすめは公式変更数値とソロランクでの扱いやすさをもとにしたパッチ序盤の予想です。リアルタイム勝率データを反映したティア表ではありません。",
                ],
            },
        },
        {
            "id": "conditional-picks",
            "kind": "conditional_cards",
            "title": {"ko": "조건부 추천 픽", "ja": "条件付きおすすめピック"},
            "body": {
                "ko": [
                    "TOP 5에는 넣지 않았지만, 조건이 맞으면 패치 초반 실험 가치가 있는 선택지입니다.",
                ],
                "ja": [
                    "TOP5には入れていませんが、条件が合えばパッチ序盤に試す価値がある候補です。",
                ],
            },
        },
        {
            "id": "watch-picks",
            "kind": "watch_cards",
            "title": {"ko": "주의해야 할 픽", "ja": "注意したいピック"},
            "body": {
                "ko": [
                    "너프를 받았어도 숙련도나 조합 조건이 맞으면 완전히 버릴 필요는 없습니다.",
                ],
                "ja": [
                    "弱体化されても、熟練度や構成条件が合えば完全に捨てる必要はありません。",
                ],
            },
        },
        {
            "id": "item-rune-system",
            "kind": "system_cards",
            "title": {"ko": "시스템/모드 변경", "ja": "システム/モード変更"},
            "body": {
                "ko": [
                    "협곡 유저와 모드 유저가 체감할 지점을 나눠 요약했습니다.",
                ],
                "ja": [
                    "サモナーズリフト勢とモード勢が体感しやすい点を分けてまとめています。",
                ],
            },
        },
        {
            "id": "patch-day-checklist",
            "kind": "checklist",
            "title": {"ko": "패치 첫날 체크리스트", "ja": "パッチ初日チェックリスト"},
            "body": {
                "ko": ["랭크에 들어가기 전 아래 항목만 확인해도 실험 비용을 줄일 수 있습니다."],
                "ja": ["ランクに入る前に下の項目だけ確認しても、試行コストを抑えられます。"],
            },
        },
        {
            "id": "faq",
            "kind": "faq",
            "title": {"ko": "FAQ", "ja": "FAQ"},
            "body": {
                "ko": ["자주 묻는 질문은 패치 초반 판단에 필요한 내용만 짧게 정리했습니다."],
                "ja": ["よくある質問はパッチ序盤の判断に必要な内容だけを短く整理しました。"],
            },
        },
        {
            "id": "source-note",
            "kind": "source_note",
            "title": {"ko": "공식 출처 및 이미지 출처", "ja": "公式ソースと画像出典"},
            "body": {
                "ko": ["본문 수치와 챔피언 명칭은 공식 패치노트와 Riot Data Dragon 기준으로 확인했습니다."],
                "ja": ["本文の数値とチャンピオン名称は、公式パッチノートとRiot Data Dragonを基準に確認しています。"],
            },
        },
    ]


def build_faq() -> list[dict]:
    return [
        {
            "question": {"ko": "패치 직후 바로 랭크를 돌려도 괜찮나요?", "ja": "パッチ直後にすぐランクを回しても大丈夫ですか？"},
            "answer": {
                "ko": "가능하지만 체감과 실제 승률이 다르게 움직일 수 있어, 주 포지션 카드부터 2~3판씩 점검하는 편이 안전합니다.",
                "ja": "可能ですが、体感と実際の勝率がずれることがあるため、メインポジションのカードから数試合ずつ確認するのが安全です。",
            },
        },
        {
            "question": {"ko": "버프 카드는 모두 추천 픽인가요?", "ja": "強化カードはすべておすすめピックですか？"},
            "answer": {
                "ko": "아닙니다. 상향을 받았더라도 조합, 라인 상성, 숙련도에 따라 효율이 크게 갈리므로 추천 픽 카드를 따로 분리했습니다.",
                "ja": "いいえ。強化されても構成、レーン相性、熟練度で効率が大きく変わるため、おすすめピックカードを別に分けています。",
            },
        },
        {
            "question": {"ko": "추천 픽은 어떤 기준으로 고르나요?", "ja": "おすすめピックはどんな基準で選びますか？"},
            "answer": {
                "ko": "공식 상향 수치, 솔랭 적응 난도, 조합 유연성, 과대평가 위험을 함께 봅니다. 단순히 버프를 받았다는 이유만으로 추천하지 않습니다.",
                "ja": "公式の強化数値、ソロランクでの適応難度、構成柔軟性、過大評価リスクを合わせて見ます。強化されたという理由だけではおすすめしません。",
            },
        },
        {
            "question": {"ko": "너프 카드는 바로 피해야 하나요?", "ja": "弱体化カードはすぐ避けるべきですか？"},
            "answer": {
                "ko": "숙련도가 높은 픽은 여전히 쓸 수 있습니다. 다만 초반 체급이나 핵심 피해량이 낮아진 경우에는 교전 타이밍을 더 보수적으로 잡아야 합니다.",
                "ja": "熟練度が高いピックはまだ使えます。ただし序盤性能や主要ダメージが下がった場合は、交戦タイミングをより慎重に取る必要があります。",
            },
        },
        {
            "question": {"ko": "챔피언 이름은 어떤 기준으로 표기했나요?", "ja": "チャンピオン名はどの基準で表記していますか？"},
            "answer": {
                "ko": "한국어와 일본어 모두 Riot Data Dragon의 공식 champion.json 데이터를 기준으로 표기했습니다.",
                "ja": "韓国語と日本語の両方をRiot Data Dragon公式のchampion.jsonデータに基づいて表記しています。",
            },
        },
        {
            "question": {"ko": "공식 출처는 어디에서 확인하나요?", "ja": "公式ソースはどこで確認できますか？"},
            "answer": {
                "ko": "글 하단의 공식 출처 링크에서 Riot Games 패치노트 원문을 확인할 수 있습니다. 이미지와 챔피언명은 Riot Data Dragon 기준으로 맞춥니다.",
                "ja": "記事末尾の公式ソースリンクからRiot Gamesのパッチノート原文を確認できます。画像とチャンピオン名はRiot Data Dragon基準でそろえます。",
            },
        },
    ]


def unique_champion_changes(champions: list[ChampionChange]) -> list[ChampionChange]:
    result: list[ChampionChange] = []
    seen: set[str] = set()
    for champion in champions:
        key = normalize_name(champion.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(champion)
    return result


def build_post_data(
    listing: PatchListing,
    masthead: dict,
    events: list[TextEvent],
    image_path: str,
    checked_at: dt.datetime,
) -> dict:
    version = listing.version
    champions = extract_champions(events)
    name_map = load_optional_name_map()
    sections = extract_sections(events)
    intro = extract_intro(events, listing.description)

    buff_changes = [champion for champion in champions if champion.classification == "버프"]
    nerf_changes = [champion for champion in champions if champion.classification == "너프"]
    adjusted_changes = [champion for champion in champions if champion.classification == "조정"]
    changed_area_summary = section_title_summary(sections)
    publish_date = parse_iso_date(listing.published_at)
    today = checked_at.date().isoformat()

    slug = f"lol-patch-{version_slug(version)}-summary"
    summary_src = {
        "ko": f"/assets/images/blog/generated/{slug}-summary-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-summary-ja.svg",
    }
    core_notes_src = {
        "ko": f"/assets/images/blog/generated/{slug}-core-notes-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-core-notes-ja.svg",
    }
    buff_group_src = {
        "ko": f"/assets/images/blog/generated/{slug}-buff-group-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-buff-group-ja.svg",
    }
    nerf_group_src = {
        "ko": f"/assets/images/blog/generated/{slug}-nerf-group-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-nerf-group-ja.svg",
    }
    tier_impact_src = {
        "ko": f"/assets/images/blog/generated/{slug}-tier-impact-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-tier-impact-ja.svg",
    }
    recommended_src = {
        "ko": f"/assets/images/blog/generated/{slug}-recommended-picks-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-recommended-picks-ja.svg",
    }
    source_note_src = {
        "ko": f"/assets/images/blog/generated/{slug}-source-note-ko.svg",
        "ja": f"/assets/images/blog/generated/{slug}-source-note-ja.svg",
    }
    ko_title = f"리그오브레전드 {version} 패치노트 핵심 정리"
    ja_title = f"リーグ・オブ・レジェンド {version} パッチノート要点まとめ"
    ko_description = (
        f"LoL {version} 패치의 버프·너프 챔피언, 솔랭 추천 픽, "
        "시스템 조정과 메타 영향을 공식 수치 카드로 정리했습니다."
    )
    ja_description = (
        f"LoL {version} パッチのチャンピオン変更、アイテムやシステム調整、"
        "ソロランクへの影響をカードと表で整理しました。"
    )

    ko_body = [
        "공식 패치노트를 기준으로 핵심 변경 방향, 솔랭 영향, 추천 픽을 카드와 표 중심으로 정리했습니다.",
        "챔피언명과 이미지는 Riot Data Dragon 공식 한국어/일본어 데이터를 기준으로 맞췄습니다.",
        "상세 수치와 원문 맥락은 글 하단 공식 출처 링크에서 다시 확인할 수 있습니다.",
    ]

    ja_body = [
        "公式パッチノートを基準に、主な変更方針、ソロランクへの影響、おすすめピックをカードと表で整理しました。",
        "チャンピオン名と画像はRiot Data Dragon公式の韓国語/日本語データに合わせています。",
        "詳細な数値と原文の文脈は、記事末尾の公式ソースから確認できます。",
    ]
    structured_sections = build_sections(version, intro)
    for section in structured_sections:
        if section["id"] == "closing-summary":
            section["body"]["ko"].extend(
                [
                    f"공식 출처: {listing.url}",
                    "이미지 출처: Riot Games 공식 패치노트 및 Riot Data Dragon 챔피언 이미지입니다.",
                ]
            )
            section["body"]["ja"].extend(
                [
                    f"公式ソース: {listing.url}",
                    "画像出典: Riot Games公式パッチノートおよびRiot Data Dragonチャンピオン画像です。",
                ]
            )

    recommendation_pool = unique_champion_changes(buff_changes + adjusted_changes + champions)
    recommended_changes = recommendation_pool[:5]
    recommended_names = {normalize_name(champion.name) for champion in recommended_changes}
    conditional_changes = [
        champion
        for champion in unique_champion_changes(buff_changes + adjusted_changes)
        if normalize_name(champion.name) not in recommended_names
    ][:2]
    watch_changes = nerf_changes[:6]

    return {
        "slug": slug,
        "category": "lol",
        "accent": "blue",
        "read_time": "7 min",
        "image": image_path,
        "og_image": summary_src["ko"],
        "date": today,
        "patch_version": version,
        "source_url": listing.url,
        "source_title": listing.title,
        "source_published_at": publish_date,
        "last_checked": checked_at.isoformat(timespec="seconds"),
        "description": ko_description,
        "categories": ["League of Legends", "Patch Notes"],
        "tags": ["롤", "리그오브레전드", "LoL", "패치노트", "솔랭", "메타"],
        "lol_champions": champion_metadata(champions, name_map),
        "summary_image": {
            "src": summary_src,
            "width": 1200,
            "height": 630,
            "alt": {
                "ko": f"리그오브레전드 {version} 패치 핵심 요약 인포그래픽",
                "ja": f"リーグ・オブ・レジェンド {version} パッチ要点インフォグラフィック",
            },
            "caption": {
                "ko": "패치 방향, 챔피언 조정 수, 솔랭 영향을 한 장으로 정리했습니다.",
                "ja": "チャンピオン変更とソロランクへの影響を一枚に整理しました。",
            },
        },
        "content_images": [
            {
                "after_section": "quick-summary",
                "src": core_notes_src,
                "width": 1200,
                "height": 720,
                "alt": {
                    "ko": f"리그오브레전드 {version} 패치 핵심노트 정리 이미지",
                    "ja": f"リーグ・オブ・レジェンド {version} パッチ要点ノートまとめ画像",
                },
                "caption": {
                    "ko": "핵심 변경점은 언어별 전용 이미지로 분리해 겹침 없이 볼 수 있게 정리했습니다.",
                    "ja": "主な変更点は言語別の専用画像に分け、重なりなく確認できるよう整理しました。",
                },
            },
            {
                "after_section": "buff-champions",
                "src": buff_group_src,
                "width": 1200,
                "height": 720,
                "alt": {
                    "ko": f"리그오브레전드 {version} 패치 버프 챔피언 그룹 이미지",
                    "ja": f"リーグ・オブ・レジェンド {version} パッチ強化チャンピオングループ画像",
                },
                "caption": {
                    "ko": "상향 카드는 라인전 보강, 교전 가치, 픽률 변화를 중심으로 읽으면 좋습니다.",
                    "ja": "強化カードはレーン戦補強、戦闘価値、ピック率変化を中心に確認すると分かりやすいです。",
                },
            },
            {
                "after_section": "nerf-champions",
                "src": nerf_group_src,
                "width": 1200,
                "height": 720,
                "alt": {
                    "ko": f"리그오브레전드 {version} 패치 너프 챔피언 그룹 이미지",
                    "ja": f"リーグ・オブ・レジェンド {version} パッチ弱体化チャンピオングループ画像",
                },
                "caption": {
                    "ko": "하향 카드는 초반 체급, 스킬 피해량, 성장 기대값을 다시 보는 용도로 정리했습니다.",
                    "ja": "弱体化カードは序盤の耐久、スキルダメージ、成長期待値の見直しに使えます。",
                },
            },
            {
                "after_section": "solo-queue-tier-impact",
                "src": tier_impact_src,
                "width": 1200,
                "height": 720,
                "alt": {
                    "ko": f"리그오브레전드 {version} 패치 솔랭 티어 영향 이미지",
                    "ja": f"リーグ・オブ・レジェンド {version} パッチソロランクティア影響画像",
                },
                "caption": {
                    "ko": "솔랭에서는 초반 체급 변화와 숙련도 요구치가 티어 변동의 핵심입니다.",
                    "ja": "ソロランクでは序盤性能と熟練度要求の変化がティア変動の中心です。",
                },
            },
            {
                "after_section": "recommended-picks",
                "src": recommended_src,
                "width": 1200,
                "height": 720,
                "alt": {
                    "ko": f"리그오브레전드 {version} 패치 추천 픽 이미지",
                    "ja": f"リーグ・オブ・レジェンド {version} パッチおすすめピック画像",
                },
                "caption": {
                    "ko": "추천 픽은 패치 초반 실험 가치와 조작 난이도를 함께 고려했습니다.",
                    "ja": "おすすめピックはパッチ序盤の試用価値と操作難度を合わせて整理しました。",
                },
            },
            {
                "after_section": "source-note",
                "src": source_note_src,
                "width": 1200,
                "height": 720,
                "alt": {
                    "ko": f"리그오브레전드 {version} 패치 공식 출처 및 이미지 출처 안내",
                    "ja": f"リーグ・オブ・レジェンド {version} パッチ公式ソースと画像出典案内",
                },
                "caption": {
                    "ko": "공식 패치노트와 Riot Data Dragon 기준으로 명칭과 이미지를 맞췄습니다.",
                    "ja": "公式パッチノートとRiot Data Dragon基準で名称と画像をそろえました。",
                },
            },
        ],
        "author": {"ko": "세이가", "ja": "セイガ"},
        "badge": {"ko": "LOL 패치", "ja": "LoLパッチ"},
        "title": {"ko": ko_title, "ja": ja_title},
        "excerpt": {"ko": ko_description, "ja": ja_description},
        "post_tags": {
            "ko": ["롤", "패치노트", "솔랭", "메타"],
            "ja": ["LoL", "パッチノート", "ソロランク", "メタ"],
        },
        "lead": {
            "ko": f"{listing.title}를 공식 패치노트와 Riot Data Dragon 기준으로 읽기 쉽게 요약했습니다.",
            "ja": f"リーグ・オブ・レジェンド {version} パッチノートを公式情報とRiot Data Dragon基準で読みやすく整理しました。",
        },
        "body": {"ko": ko_body, "ja": ja_body},
        "toc": build_toc(),
        "overview_table": build_overview_table(
            version,
            publish_date,
            today,
            len(buff_changes),
            len(nerf_changes),
            len(adjusted_changes),
            changed_area_summary,
        ),
        "sections": structured_sections,
        "quick_summary_items": [
            {
                "label": {"ko": "Riot 의도", "ja": "Riotの意図"},
                "body": {
                    "ko": "공식 패치노트의 변경 의도를 기준으로 선택지와 과한 성능을 함께 조정한 패치입니다.",
                    "ja": "公式パッチノートの変更意図を基準に、選択肢と過剰性能を同時に調整するパッチです。",
                },
            },
            {
                "label": {"ko": "솔랭 영향", "ja": "ソロランク影響"},
                "body": {
                    "ko": "상향/하향 카드 모두 숙련도와 라인 상성에 따라 체감 차이가 크게 갈릴 수 있습니다.",
                    "ja": "強化/弱体化カードはいずれも、熟練度とレーン相性で体感差が大きく分かれます。",
                },
            },
            {
                "label": {"ko": "실험 가치", "ja": "試す価値"},
                "body": {
                    "ko": "추천 픽은 공식 수치와 솔랭 적응 난도를 함께 보고 우선순위를 잡는 편이 안전합니다.",
                    "ja": "おすすめピックは公式数値とソロランクでの適応難度を合わせて優先度を決めるのが安全です。",
                },
            },
            {
                "label": {"ko": "모드 영향", "ja": "モード影響"},
                "body": {
                    "ko": "시스템과 모드 변경은 협곡 외 플레이 경험에도 영향을 줄 수 있습니다.",
                    "ja": "システムとモード変更はサモナーズリフト以外の体感にも影響する可能性があります。",
                },
            },
        ],
        "buff_champion_cards": [champion_card_data(champion, "버프", name_map) for champion in buff_changes],
        "nerf_champion_cards": [champion_card_data(champion, "너프", name_map) for champion in nerf_changes],
        "lane_impact_cards": [
            {
                "lane": {"ko": "탑", "ja": "トップ"},
                "summary": {"ko": "상향/하향 카드가 탑 라인 교환과 사이드 운영에 미치는 영향을 확인하세요.", "ja": "強化/弱体化カードがトップのトレードとサイド運用に与える影響を確認しましょう。"},
                "priority": {"ko": "매치업 확인", "ja": "対面確認"},
                "points": {
                    "ko": ["상향 카드는 라인 상성과 숙련도 조건을 함께 봐야 합니다.", "하향 카드는 초반 체급과 갱킹 대응을 먼저 점검하세요."],
                    "ja": ["強化カードはレーン相性と熟練度条件を合わせて見ましょう。", "弱体化カードは序盤性能とガンク対応を先に確認しましょう。"],
                },
            },
            {
                "lane": {"ko": "정글", "ja": "ジャングル"},
                "summary": {"ko": "정글은 초반 교전 설계와 오브젝트 전 성장 안정성이 핵심입니다.", "ja": "ジャングルは序盤戦闘設計とオブジェクト前の成長安定が重要です。"},
                "priority": {"ko": "리스크 관리", "ja": "リスク管理"},
                "points": {
                    "ko": ["하향 정글은 첫 갱킹 실패 후 복구 난도를 확인하세요.", "상향 정글은 캠프 속도와 교전 타이밍을 직접 체감해보세요."],
                    "ja": ["弱体化ジャングルは最初のガンク失敗後の立て直しを確認しましょう。", "強化ジャングルはクリア速度と戦闘タイミングを体感しましょう。"],
                },
            },
            {
                "lane": {"ko": "미드", "ja": "ミッド"},
                "summary": {"ko": "미드는 라인 안정성, 로밍 타이밍, 한타 설계가 티어 변동을 가릅니다.", "ja": "ミッドはレーン安定性、ロームタイミング、集団戦設計がティア変動を分けます。"},
                "priority": {"ko": "숙련도 우선", "ja": "熟練度優先"},
                "points": {
                    "ko": ["메이지와 암살자 모두 변경 수치가 실제 콤보에 미치는 영향을 확인하세요.", "초반 체급이 낮아진 픽은 웨이브 위치를 더 보수적으로 잡으세요."],
                    "ja": ["メイジもアサシンも、変更数値が実際のコンボに与える影響を確認しましょう。", "序盤性能が落ちたピックはウェーブ位置をより慎重に取りましょう。"],
                },
            },
            {
                "lane": {"ko": "원딜", "ja": "ADC"},
                "summary": {"ko": "원딜은 라인 주도권과 오브젝트 전 합류 가치가 중요합니다.", "ja": "ADCはレーン主導権とオブジェクト前の寄り価値が重要です。"},
                "priority": {"ko": "조합 의존", "ja": "構成依存"},
                "points": {
                    "ko": ["상향 픽은 서포터 연계와 포탑 압박 능력을 함께 보세요.", "하향 픽은 포킹 화력과 라인 유지력을 분리해서 확인하세요."],
                    "ja": ["強化ピックはサポート連携とタワー圧を合わせて見ましょう。", "弱体化ピックはポーク火力とレーン維持力を分けて確認しましょう。"],
                },
            },
            {
                "lane": {"ko": "서포터", "ja": "サポート"},
                "summary": {"ko": "서포터는 라인 주도권과 성장형 딜러 보조 가치가 갈립니다.", "ja": "サポートはレーン主導権と成長型キャリー支援の価値が分かれます。"},
                "priority": {"ko": "듀오 조건 확인", "ja": "デュオ条件確認"},
                "points": {
                    "ko": ["보조술사 상향은 원딜 성장 타이밍과 함께 봐야 합니다.", "라인전 약점이 있는 조합은 첫 귀환 전 교전을 줄이세요."],
                    "ja": ["エンチャンター強化はADCの成長タイミングと一緒に見ましょう。", "レーン戦に弱点がある構成は最初のリコール前の交戦を減らしましょう。"],
                },
            },
        ],
        "recommended_pick_cards": [recommended_card_data(champion, name_map) for champion in recommended_changes],
        "conditional_recommended_cards": [conditional_card_data(champion, name_map) for champion in conditional_changes],
        "watch_pick_cards": [watch_card_data(champion, name_map) for champion in watch_changes],
        "system_change_cards": [
            {
                "title": {"ko": "협곡 운영", "ja": "サモナーズリフト運用"},
                "badge": {"ko": "협곡", "ja": "サモナーズリフト"},
                "target": {"ko": "랭크와 일반 협곡 유저", "ja": "ランクと通常サモナーズリフトのプレイヤー"},
                "change_summary": {
                    "ko": [summarize_system_sections(sections)],
                    "ja": ["公式パッチノートのシステム/モード変更を確認してください。"],
                },
                "immediate_check": {
                    "ko": ["라인 복귀와 합류 타이밍", "오브젝트 전 교전 기준"],
                    "ja": ["レーン復帰と合流タイミング", "オブジェクト前の戦闘基準"],
                },
                "less_important": {
                    "ko": "패치 전 감각만으로 고정하는 운영",
                    "ja": "パッチ前の感覚だけに固定する運用",
                },
                "judgment": {
                    "ko": "공식 변경 수치가 직접 플레이 흐름에 닿는지 먼저 확인하세요.",
                    "ja": "公式変更数値が実際の試合展開に影響するかを先に確認しましょう。",
                },
            },
            {
                "title": {"ko": "모드 변경", "ja": "モード変更"},
                "badge": {"ko": "ARAM/이벤트", "ja": "ARAM/イベント"},
                "target": {"ko": "협곡 외 모드 유저", "ja": "サモナーズリフト以外のモードプレイヤー"},
                "change_summary": {
                    "ko": ["공식 패치노트의 모드 변경 항목을 별도로 확인해야 합니다."],
                    "ja": ["公式パッチノートのモード変更項目を別途確認してください。"],
                },
                "immediate_check": {
                    "ko": ["새 증강 또는 규칙 변경", "삭제된 빌드와 반복 플레이 패턴"],
                    "ja": ["新しいオーグメントやルール変更", "削除されたビルドと反復プレイパターン"],
                },
                "less_important": {
                    "ko": "이전 패치의 고정 빌드만 반복하는 판단",
                    "ja": "以前のパッチの固定ビルドだけを繰り返す判断",
                },
                "judgment": {
                    "ko": "모드 변경은 익숙한 빌드보다 새 조합 실험 가치가 먼저 커집니다.",
                    "ja": "モード変更では慣れたビルドより新しい組み合わせを試す価値が先に高まります。",
                },
            },
            {
                "title": {"ko": "아이템/룬 점검", "ja": "アイテム/ルーン確認"},
                "badge": {"ko": "빌드", "ja": "ビルド"},
                "target": {"ko": "빌드 영향을 받는 모든 포지션", "ja": "ビルド影響を受ける全ロール"},
                "change_summary": {
                    "ko": ["아이템, 룬, 시스템 변경은 챔피언 카드와 분리해서 확인합니다."],
                    "ja": ["アイテム、ルーン、システム変更はチャンピオンカードと分けて確認します。"],
                },
                "immediate_check": {
                    "ko": ["핵심 아이템 완성 타이밍", "룬 선택과 초반 교전 기준"],
                    "ja": ["主要アイテム完成タイミング", "ルーン選択と序盤戦闘基準"],
                },
                "less_important": {
                    "ko": "승률 표본 없이 모든 빌드를 단정하는 판단",
                    "ja": "勝率サンプルなしに全ビルドを断定する判断",
                },
                "judgment": {
                    "ko": "빌드 변화는 실시간 승률 데이터가 쌓이기 전까지 보수적으로 해석하세요.",
                    "ja": "ビルド変化はリアルタイム勝率データが集まるまでは慎重に解釈しましょう。",
                },
            }
        ],
        "checklist_items": [
            {
                "label": {"ko": "주 포지션 카드 먼저 확인", "ja": "メインロールのカードを先に確認"},
                "body": {"ko": "라인별 영향 카드에서 내 포지션의 상승 후보와 주의 픽을 먼저 고르세요.", "ja": "ロール別影響カードで自分のロールの上昇候補と注意ピックを先に選びましょう。"},
            },
            {
                "label": {"ko": "변경 수치가 큰 스킬 연습", "ja": "変更幅の大きいスキルを練習"},
                "body": {"ko": "수치가 직접 바뀐 스킬은 일반 게임에서 체감한 뒤 랭크에 들어가세요.", "ja": "数値が直接変わったスキルはノーマルで体感してからランクに入りましょう。"},
            },
            {
                "label": {"ko": "너프 픽은 첫날 보수적으로", "ja": "弱体化ピックは初日慎重に"},
                "body": {"ko": "익숙한 픽이라도 교전 기준을 한 단계 보수적으로 잡으세요.", "ja": "慣れたピックでも戦闘基準を一段慎重にしましょう。"},
            },
        ],
        "source_notes": [
            {
                "label": {"ko": "공식 패치노트", "ja": "公式パッチノート"},
                "body": {"ko": "본문 변경 수치는 Riot Games 공식 패치노트 기준입니다.", "ja": "本文の変更数値はRiot Games公式パッチノート基準です。"},
                "url": listing.url,
            },
            {
                "label": {"ko": "게시일", "ja": "公開日"},
                "body": {"ko": publish_date, "ja": publish_date},
            },
            {
                "label": {"ko": "블로그 확인일", "ja": "ブログ確認日"},
                "body": {"ko": today, "ja": today},
            },
            {
                "label": {"ko": "Riot Data Dragon 기준", "ja": "Riot Data Dragon基準"},
                "body": {"ko": "챔피언명과 이미지는 Riot Data Dragon 공식 데이터를 기준으로 저장합니다.", "ja": "チャンピオン名と画像はRiot Data Dragon公式データを基準に保存します。"},
                "url": "https://ddragon.leagueoflegends.com",
            },
            {
                "label": {"ko": "메타 해석 고지", "ja": "メタ解釈の注記"},
                "body": {
                    "ko": "본문 메타 평가는 공식 수치를 바탕으로 한 솔랭 해석이며, 실시간 승률 데이터가 아님을 밝힙니다.",
                    "ja": "本文のメタ評価は公式数値をもとにしたソロランク向けの解釈であり、リアルタイム勝率データではありません。",
                },
            },
        ],
        "faq": build_faq(),
        "quote": {
            "ko": "이번 패치는 카드별 체감 차이를 빠르게 읽고, 내 포지션에 맞는 실험 픽을 고르는 것이 핵심입니다.",
            "ja": "今回のパッチはカードごとの体感差を早く読み、自分のポジションに合う試用ピックを選ぶことが重要です。",
        },
        "image_credit": {
            "ko": "Riot Games 공식 패치노트 및 Riot Data Dragon 챔피언 이미지",
            "ja": "Riot Games公式パッチノートおよびRiot Data Dragonチャンピオン画像",
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


def generated_blog_image_paths(slug: str) -> list[Path]:
    image_dir = Path("assets/images/blog/generated")
    kinds = [
        "summary",
        "champions",
        "core-notes",
        "buff-group",
        "nerf-group",
        "tier-impact",
        "recommended-picks",
        "source-note",
    ]
    localized = [image_dir / f"{slug}-{kind}-{lang}.svg" for kind in kinds for lang in ["ko", "ja"]]
    default_aliases = [image_dir / f"{slug}-{kind}.svg" for kind in kinds]
    return [*localized, *default_aliases]


def generate_blog_images(slug: str) -> list[Path]:
    log("패치 인포그래픽과 중간 이미지를 생성합니다.")
    result = subprocess.run(
        [sys.executable, "scripts/generate_blog_images.py"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout.strip():
        log(result.stdout.strip())
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise LolPatchError(f"블로그 이미지 생성 실패: {message}")
    return [path for path in generated_blog_image_paths(slug) if path.exists()]


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

        blog_image_files = generate_blog_images(post_data["slug"])
        generated_paths = [post_path, *image_files, *blog_image_files]
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
