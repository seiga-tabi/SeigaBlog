#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lol_content_utils import (
    REPO_ROOT,
    load_champion_map,
    repo_path,
    write_json,
    write_report,
)
from validate_lol_content_data import CONTENT_QUEUE_PATH, queue_items, validate_item


POSTS_DIR = REPO_ROOT / "_posts"
GENERATED_DATA_DIR = REPO_ROOT / "data" / "lol" / "generated"
DEFAULT_IMAGE = "/assets/images/profile.png"
TIMEZONE = ZoneInfo("Asia/Tokyo")
POSITION_LABELS = {
    "Top": {"ko": "탑", "ja": "トップ"},
    "Jungle": {"ko": "정글", "ja": "ジャングル"},
    "Mid": {"ko": "미드", "ja": "ミッド"},
    "Bot": {"ko": "원딜", "ja": "ADC"},
    "Support": {"ko": "서포터", "ja": "サポート"},
}
TYPE_LABELS = {
    "patch-meta-followup": {"ko": "메타 점검", "ja": "メタ確認"},
    "position-meta": {"ko": "포지션 리포트", "ja": "ロールレポート"},
    "champion-focus": {"ko": "챔피언 분석", "ja": "チャンピオン分析"},
    "riot-dev-update": {"ko": "개발자 업데이트", "ja": "開発者アップデート"},
    "system-guide": {"ko": "시스템 가이드", "ja": "システムガイド"},
}


def log(message: str) -> None:
    print(f"[LoL Content] {message}")


def display_path(path: Path) -> str:
    try:
        return repo_path(path)
    except ValueError:
        return str(path)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or fallback


def version_slug(value: str) -> str:
    return normalize_space(value).replace(".", "-")


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


def render_post(post_data: dict) -> str:
    return "---\n" + "\n".join(yaml_lines(post_data)) + "\n---\n"


def collect_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(collect_text(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(collect_text(item))
        return result
    return []


def read_time(post_data: dict) -> str:
    text = " ".join(collect_text(post_data.get("title", {}).get("ko", "")))
    text += " " + " ".join(collect_text(post_data.get("body", {}).get("ko", [])))
    text += " " + " ".join(collect_text(post_data.get("sections", [])))
    chars = len(re.sub(r"\s+", "", text))
    return f"{max(3, (chars + 499) // 500)} min"


def has_hangul(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value))


def localized(value: Any, lang: str, fallback: str = "") -> str:
    if isinstance(value, dict):
        current = value.get(lang)
        if current:
            return normalize_space(current)
        if lang == "ko" and value.get("ja"):
            return normalize_space(value["ja"])
    if isinstance(value, str):
        text = normalize_space(value)
        if lang == "ja" and has_hangul(text):
            return fallback
        return text
    return fallback


def localized_list(value: Any, lang: str, fallback_prefix: str) -> list[str]:
    if isinstance(value, list):
        result = []
        for index, item in enumerate(value, start=1):
            fallback = f"{fallback_prefix} {index}"
            text = localized(item, lang, fallback)
            if text:
                result.append(text)
        return result
    text = localized(value, lang, fallback_prefix)
    return [text] if text else []


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def champion_entry(key: str, name_map: dict) -> dict | None:
    return name_map.get("champions", {}).get(key)


def champion_name(item: dict, lang: str, name_map: dict) -> str:
    key = item.get("key") or item.get("champion_key")
    if key and (entry := champion_entry(str(key), name_map)):
        return entry.get(lang, key)
    if lang == "ko":
        return item.get("ko") or item.get("champion_name_ko") or str(key or "")
    return item.get("ja") or item.get("champion_name_ja") or str(key or "")


def champion_key(item: dict) -> str:
    return str(item.get("key") or item.get("champion_key") or "")


def metric_parts(metrics: dict, lang: str) -> list[str]:
    labels = {
        "win_rate": {"ko": "승률", "ja": "勝率"},
        "pick_rate": {"ko": "픽률", "ja": "ピック率"},
        "ban_rate": {"ko": "밴률", "ja": "BAN率"},
        "sample_size": {"ko": "표본", "ja": "サンプル"},
    }
    parts = []
    for key, label in labels.items():
        if key in metrics and metrics[key] not in {"", None}:
            parts.append(f"{label[lang]} {metrics[key]}")
    return parts


def metric_sentence(item: dict, lang: str, name_map: dict) -> str:
    name = champion_name(item, lang, name_map)
    metrics = item.get("current_metrics") if isinstance(item.get("current_metrics"), dict) else item
    parts = metric_parts(metrics, lang)
    if not parts:
        return f"{name}: " + ("제공된 지표만 확인했습니다." if lang == "ko" else "提供された指標のみ確認しました。")
    return f"{name}: " + ", ".join(parts)


def source_notes(item: dict) -> list[dict]:
    notes = []
    for index, note in enumerate(item.get("source_notes", []), start=1):
        if isinstance(note, dict):
            label_ko = localized(note.get("label") or note.get("title"), "ko", f"출처 {index}")
            label_ja = localized(note.get("label") or note.get("title"), "ja", f"出典 {index}")
            body_ko = localized(note.get("body") or note.get("summary") or note.get("url"), "ko", "입력 데이터 기준입니다.")
            body_ja = localized(note.get("body") or note.get("summary") or note.get("url"), "ja", "入力データを基準にしています。")
            notes.append({"label": {"ko": label_ko, "ja": label_ja}, "body": {"ko": body_ko, "ja": body_ja}, "url": note.get("url", "")})
        elif isinstance(note, str):
            notes.append(
                {
                    "label": {"ko": f"출처 {index}", "ja": f"出典 {index}"},
                    "body": {"ko": normalize_space(note), "ja": "入力データを基準にしています。"},
                }
            )
    if item.get("source_url"):
        notes.insert(
            0,
            {
                "label": {"ko": item.get("source_title") or "Riot 공식 출처", "ja": item.get("source_title") or "Riot公式ソース"},
                "body": {"ko": item.get("source_published_at") or "공식 발표 기준입니다.", "ja": item.get("source_published_at") or "公式発表を基準にしています。"},
                "url": item["source_url"],
            },
        )
    return notes


def data_basis_rows(item: dict) -> list[dict]:
    mapping = [
        ("patch_version", "패치", "パッチ"),
        ("current_patch", "현재 패치", "現在のパッチ"),
        ("previous_patch", "이전 패치", "前パッチ"),
        ("region", "지역", "地域"),
        ("tier_range", "티어 범위", "ティア範囲"),
        ("queue", "큐", "キュー"),
        ("sample_period", "분석 기간", "分析期間"),
        ("sample_size", "표본 수", "サンプル数"),
        ("position", "포지션", "ロール"),
        ("applicable_patch", "적용 패치", "適用パッチ"),
    ]
    rows = []
    for key, ko_label, ja_label in mapping:
        if key not in item or is_empty(item[key]):
            continue
        value = item[key]
        if isinstance(value, dict):
            value_text = " ~ ".join(str(v) for v in value.values() if v)
        else:
            value_text = str(value)
        if key == "position" and value_text in POSITION_LABELS:
            rows.append({"label": {"ko": ko_label, "ja": ja_label}, "value": POSITION_LABELS[value_text]})
        else:
            rows.append({"label": {"ko": ko_label, "ja": ja_label}, "value": {"ko": value_text, "ja": value_text}})
    return rows


def section(section_id: str, title_ko: str, title_ja: str, body_ko: list[str], body_ja: list[str], kind: str = "text") -> dict:
    return {
        "id": section_id,
        "kind": kind,
        "title": {"ko": title_ko, "ja": title_ja},
        "body": {"ko": body_ko or ["입력 데이터 기준으로 확인합니다."], "ja": body_ja or ["入力データを基準に確認します。"]},
    }


def section_from_items(section_id: str, title_ko: str, title_ja: str, values: list[dict], name_map: dict, empty_ko: str, empty_ja: str) -> dict:
    if values:
        return section(
            section_id,
            title_ko,
            title_ja,
            [metric_sentence(value, "ko", name_map) for value in values],
            [metric_sentence(value, "ja", name_map) for value in values],
        )
    return section(section_id, title_ko, title_ja, [empty_ko], [empty_ja])


def quick_summary(content_type: str, item: dict, name_map: dict) -> list[dict]:
    if content_type == "champion-focus":
        champ = {"key": item.get("champion_key"), "ko": item.get("champion_name_ko"), "ja": item.get("champion_name_ja")}
        return [
            {"label": {"ko": "대상", "ja": "対象"}, "body": {"ko": champion_name(champ, "ko", name_map), "ja": champion_name(champ, "ja", name_map)}},
            {"label": {"ko": "포지션", "ja": "ロール"}, "body": POSITION_LABELS.get(item.get("position"), {"ko": str(item.get("position", "")), "ja": str(item.get("position", ""))})},
            {"label": {"ko": "데이터", "ja": "データ"}, "body": {"ko": "입력된 현재/이전 지표만 사용했습니다.", "ja": "入力された現在/過去指標のみ使用しています。"}},
        ]
    if content_type == "riot-dev-update":
        return [
            {"label": {"ko": "확정", "ja": "確定"}, "body": {"ko": f"확정 발표 {len(item.get('confirmed_changes', []))}건", "ja": f"確定発表 {len(item.get('confirmed_changes', []))}件"}},
            {"label": {"ko": "예정", "ja": "予定"}, "body": {"ko": f"개발/적용 예정 {len(item.get('planned_changes', []))}건", "ja": f"開発/適用予定 {len(item.get('planned_changes', []))}件"}},
            {"label": {"ko": "보류", "ja": "未確定"}, "body": {"ko": "확정되지 않은 내용은 별도 구분했습니다.", "ja": "未確定の内容は分けて整理しています。"}},
        ]
    return [
        {"label": {"ko": "기준", "ja": "基準"}, "body": {"ko": "입력 데이터와 출처만 사용했습니다.", "ja": "入力データと出典のみ使用しています。"}},
        {"label": {"ko": "범위", "ja": "範囲"}, "body": {"ko": str(item.get("region") or item.get("applicable_patch") or item.get("patch_version") or "공식 입력"), "ja": str(item.get("region") or item.get("applicable_patch") or item.get("patch_version") or "公式入力")}},
        {"label": {"ko": "주의", "ja": "注意"}, "body": {"ko": "없는 수치는 추정하지 않았습니다.", "ja": "ない数値は推測していません。"}},
    ]


def system_cards(content_type: str, item: dict, name_map: dict) -> list[dict]:
    cards = [
        {
            "title": {"ko": "데이터 기준", "ja": "データ基準"},
            "badge": {"ko": TYPE_LABELS[content_type]["ko"], "ja": TYPE_LABELS[content_type]["ja"]},
            "target": {"ko": "본문 전체", "ja": "記事全体"},
            "change_summary": {
                "ko": [f"{row['label']['ko']}: {row['value']['ko']}" for row in data_basis_rows(item)[:4]],
                "ja": [f"{row['label']['ja']}: {row['value']['ja']}" for row in data_basis_rows(item)[:4]],
            },
            "immediate_check": {"ko": ["입력 출처", "누락 수치 여부"], "ja": ["入力ソース", "欠損指標の有無"]},
            "less_important": {"ko": "입력에 없는 외부 추정", "ja": "入力にない外部推測"},
            "judgment": {"ko": "제공된 범위 안에서만 판단합니다.", "ja": "提供された範囲内でのみ判断します。"},
        }
    ]
    if content_type == "system-guide":
        cards.append(
            {
                "title": {"ko": "변경 전/후", "ja": "変更前/後"},
                "badge": {"ko": "시스템", "ja": "システム"},
                "target": {"ko": localized(item.get("system_name"), "ko", "시스템"), "ja": localized(item.get("system_name"), "ja", "システム")},
                "change_summary": {
                    "ko": localized_list(item.get("official_changes"), "ko", "공식 변경"),
                    "ja": localized_list(item.get("official_changes"), "ja", "公式変更"),
                },
                "immediate_check": {
                    "ko": localized_list(item.get("after_state"), "ko", "변경 후"),
                    "ja": localized_list(item.get("after_state"), "ja", "変更後"),
                },
                "less_important": {"ko": localized(item.get("before_state"), "ko", "변경 전 상태 확인"), "ja": localized(item.get("before_state"), "ja", "変更前の状態を確認")},
                "judgment": {"ko": "공식 변경과 실제 플레이 체크 포인트를 분리합니다.", "ja": "公式変更と実プレイの確認点を分けます。"},
            }
        )
    return cards


def faq_items(content_type: str) -> list[dict]:
    common = [
        {
            "question": {"ko": "이 글은 어떤 데이터를 기준으로 하나요?", "ja": "この記事はどのデータを基準にしていますか？"},
            "answer": {"ko": "입력 JSON의 데이터 기준과 출처에 포함된 값만 사용합니다.", "ja": "入力JSONのデータ基準と出典に含まれる値のみ使用します。"},
        },
        {
            "question": {"ko": "없는 승률이나 픽률도 보정하나요?", "ja": "ない勝率やピック率も補いますか？"},
            "answer": {"ko": "아니요. 제공되지 않은 수치는 추정하거나 생성하지 않습니다.", "ja": "いいえ。提供されていない数値は推測も生成もしません。"},
        },
        {
            "question": {"ko": "챔피언명은 어떤 기준인가요?", "ja": "チャンピオン名はどの基準ですか？"},
            "answer": {"ko": "Riot Data Dragon 공식 한국어/일본어 명칭을 사용합니다.", "ja": "Riot Data Dragon公式の韓国語/日本語名を使用します。"},
        },
    ]
    if content_type == "riot-dev-update":
        common.append(
            {
                "question": {"ko": "예정 내용은 확정인가요?", "ja": "予定内容は確定ですか？"},
                "answer": {"ko": "Riot이 확정한 내용과 개발 중인 내용은 본문에서 구분합니다.", "ja": "Riotが確定した内容と開発中の内容は本文で分けています。"},
            }
        )
    return common


def content_sections(content_type: str, item: dict, name_map: dict) -> list[dict]:
    basis_ko = [f"{row['label']['ko']}: {row['value']['ko']}" for row in data_basis_rows(item)]
    basis_ja = [f"{row['label']['ja']}: {row['value']['ja']}" for row in data_basis_rows(item)]

    if content_type == "patch-meta-followup":
        metrics = [m for m in item.get("champion_metrics", []) if isinstance(m, dict)]
        rising = [m for m in metrics if str(m.get("trend", "")).lower() in {"rising", "up", "상승"}]
        stable = [m for m in metrics if str(m.get("trend", "")).lower() in {"stable", "flat", "보합"}]
        falling = [m for m in metrics if str(m.get("trend", "")).lower() in {"falling", "down", "하락"}]
        pending = [m for m in metrics if m.get("sample_warning") or str(m.get("trend", "")).lower() in {"pending", "보류"}]
        return [
            section("quick-summary", "3줄 요약", "3行要約", ["입력된 패치 후 지표만 기준으로 메타 변화를 점검합니다."], ["入力されたパッチ後指標のみを基準にメタ変化を確認します。"], "quick_summary"),
            section("data-basis", "데이터 기준", "データ基準", basis_ko, basis_ja, "system_cards"),
            section("expected-vs-actual", "패치노트 예상과 실제 결과", "パッチノート予想と実結果", localized_list(item.get("expected_vs_actual"), "ko", "입력 비교 데이터 기준입니다."), localized_list(item.get("expected_vs_actual"), "ja", "入力された比較データを基準にしています。")),
            section_from_items("rising-champions", "예상보다 상승한 챔피언", "予想以上に上がったチャンピオン", rising, name_map, "상승으로 분류된 입력 지표가 없습니다.", "上昇として分類された入力指標はありません。"),
            section_from_items("stable-champions", "기대보다 변화가 적었던 챔피언", "期待より変化が小さいチャンピオン", stable, name_map, "변화가 적은 챔피언 입력이 없습니다.", "変化が小さいチャンピオン入力はありません。"),
            section_from_items("falling-champions", "하락한 챔피언", "下がったチャンピオン", falling, name_map, "하락으로 분류된 입력 지표가 없습니다.", "低下として分類された入力指標はありません。"),
            section_from_items("pending-champions", "표본이 부족해 판단을 보류할 챔피언", "サンプル不足で保留するチャンピオン", pending, name_map, "판단 보류 입력이 없습니다.", "判断保留の入力はありません。"),
            section("position-checkpoints", "포지션별 체크 포인트", "ロール別確認点", localized_list(item.get("position_checkpoints"), "ko", "포지션별 입력을 확인합니다."), localized_list(item.get("position_checkpoints"), "ja", "ロール別入力を確認します。")),
            section_from_items("practice-picks", "지금 연습할 만한 픽", "今練習したいピック", item.get("practice_picks", []) if isinstance(item.get("practice_picks"), list) else rising, name_map, "연습 추천 입력이 없습니다.", "練習候補の入力はありません。"),
            section_from_items("caution-picks", "주의해야 할 픽", "注意したいピック", item.get("caution_picks", []) if isinstance(item.get("caution_picks"), list) else falling, name_map, "주의 픽 입력이 없습니다.", "注意ピックの入力はありません。"),
            section("conclusion", "결론", "結論", ["입력된 지표 범위 안에서만 후속 판단을 업데이트했습니다."], ["入力された指標の範囲内でのみ判断を更新しました。"]),
            section("source-note", "출처", "出典", ["아래 출처 카드에서 데이터 기준을 확인하세요."], ["下の出典カードでデータ基準を確認してください。"], "source_note"),
        ]

    if content_type == "position-meta":
        position = POSITION_LABELS.get(item.get("position"), {"ko": str(item.get("position")), "ja": str(item.get("position"))})
        return [
            section("quick-summary", "3줄 요약", "3行要約", [f"{position['ko']} 포지션의 입력 지표만 기준으로 정리했습니다."], [f"{position['ja']}ロールの入力指標のみを基準に整理しました。"], "quick_summary"),
            section("data-basis", "데이터 기준", "データ基準", basis_ko, basis_ja, "system_cards"),
            section("position-change-reason", "이번 패치에서 해당 포지션이 달라진 이유", "このパッチでロールが変わった理由", localized_list(item.get("change_reasons"), "ko", "입력된 변화 이유만 확인합니다."), localized_list(item.get("change_reasons"), "ja", "入力された変化理由のみ確認します。")),
            section_from_items("safe-blind-picks", "선픽하기 좋은 챔피언", "先出ししやすいチャンピオン", item.get("blind_picks", []) or item.get("stable_picks", []), name_map, "선픽 후보 입력이 없습니다.", "先出し候補の入力はありません。"),
            section_from_items("counter-picks", "후픽 가치가 높은 챔피언", "後出し価値が高いチャンピオン", item.get("counter_picks", []), name_map, "후픽 후보 입력이 없습니다.", "後出し候補の入力はありません。"),
            section_from_items("easy-picks", "숙련도가 낮아도 사용할 만한 챔피언", "習熟度が低くても使いやすいチャンピオン", item.get("easy_picks", []), name_map, "쉬운 픽 입력이 없습니다.", "使いやすいピック入力はありません。"),
            section_from_items("expert-picks", "숙련자에게 유리한 챔피언", "熟練者向けチャンピオン", item.get("expert_picks", []) or item.get("rising_picks", []), name_map, "숙련자 픽 입력이 없습니다.", "熟練者向け入力はありません。"),
            section_from_items("ban-candidates", "추천 밴", "おすすめBAN", item.get("ban_candidates", []), name_map, "밴 후보 입력이 없습니다.", "BAN候補の入力はありません。"),
            section_from_items("trap-picks", "함정 픽 또는 표본 주의 픽", "罠ピックまたはサンプル注意ピック", item.get("trap_picks", []) or item.get("falling_picks", []), name_map, "주의 픽 입력이 없습니다.", "注意ピック入力はありません。"),
            section("conclusion", "결론", "結論", ["상성이나 조합 정보는 입력된 matchup 데이터가 있을 때만 해석합니다."], ["相性や構成情報は入力されたmatchupデータがある時だけ解釈します。"]),
            section("source-note", "출처", "出典", ["아래 출처 카드에서 데이터 기준을 확인하세요."], ["下の出典カードでデータ基準を確認してください。"], "source_note"),
        ]

    if content_type == "champion-focus":
        champ = {"key": item.get("champion_key"), "ko": item.get("champion_name_ko"), "ja": item.get("champion_name_ja")}
        ko = champion_name(champ, "ko", name_map)
        ja = champion_name(champ, "ja", name_map)
        return [
            section("quick-summary", "3줄 요약", "3行要約", [f"{ko}의 공식 변경과 입력 지표만 정리했습니다."], [f"{ja}の公式変更と入力指標のみ整理しました。"], "quick_summary"),
            section("data-basis", "데이터 기준", "データ基準", basis_ko, basis_ja, "system_cards"),
            section("official-changes", "공식 변경점", "公式変更点", localized_list(item.get("official_changes"), "ko", "공식 변경"), localized_list(item.get("official_changes"), "ja", "公式変更")),
            section("what-changed", "무엇이 달라졌는가", "何が変わったか", localized_list(item.get("riot_context"), "ko", "Riot 공식 문맥 기준입니다."), localized_list(item.get("riot_context"), "ja", "Riot公式文脈を基準にしています。")),
            section("early-game", "라인전 또는 초반 운영", "レーン戦または序盤運用", localized_list(item.get("early_game"), "ko", "초반 운영 입력이 없습니다."), localized_list(item.get("early_game"), "ja", "序盤運用の入力はありません。")),
            section("mid-game", "중반 운영", "中盤運用", localized_list(item.get("mid_game"), "ko", "중반 운영 입력이 없습니다."), localized_list(item.get("mid_game"), "ja", "中盤運用の入力はありません。")),
            section("teamfight-role", "한타에서의 역할", "集団戦での役割", localized_list(item.get("teamfight_role"), "ko", "한타 역할 입력이 없습니다."), localized_list(item.get("teamfight_role"), "ja", "集団戦役割の入力はありません。")),
            section("recommended-items", "추천 아이템", "おすすめアイテム", localized_list(item.get("build_data"), "ko", "build_data가 없어 아이템 추천을 생성하지 않았습니다."), localized_list(item.get("build_data"), "ja", "build_dataがないためアイテムおすすめは生成していません。")),
            section("recommended-runes", "추천 룬", "おすすめルーン", localized_list(item.get("rune_data"), "ko", "rune_data가 없어 룬 추천을 생성하지 않았습니다."), localized_list(item.get("rune_data"), "ja", "rune_dataがないためルーンおすすめは生成していません。")),
            section("matchups", "유리하거나 불리한 상대", "有利または不利な相手", localized_list(item.get("matchup_data"), "ko", "matchup_data가 없어 상성을 생성하지 않았습니다."), localized_list(item.get("matchup_data"), "ja", "matchup_dataがないため相性は生成していません。")),
            section("recommended-users", "추천 대상", "おすすめ対象", localized_list(item.get("recommended_for"), "ko", "추천 대상 입력이 없습니다."), localized_list(item.get("recommended_for"), "ja", "おすすめ対象の入力はありません。")),
            section("cautions", "주의할 점", "注意点", localized_list(item.get("caution"), "ko", "입력 데이터 밖의 빌드와 상성은 추가하지 않았습니다."), localized_list(item.get("caution"), "ja", "入力データ外のビルドと相性は追加していません。")),
            section("conclusion", "결론", "結論", [f"{ko} 판단은 공식 변경과 제공 지표가 함께 있을 때만 업데이트합니다."], [f"{ja}の判断は公式変更と提供指標がそろう時だけ更新します。"]),
            section("source-note", "출처", "出典", ["아래 출처 카드에서 데이터 기준을 확인하세요."], ["下の出典カードでデータ基準を確認してください。"], "source_note"),
        ]

    if content_type == "riot-dev-update":
        return [
            section("quick-summary", "30초 요약", "30秒要約", localized_list(item.get("official_announcements"), "ko", "공식 발표"), localized_list(item.get("official_announcements"), "ja", "公式発表"), "quick_summary"),
            section("confirmed", "Riot이 확정해서 발표한 내용", "Riotが確定発表した内容", localized_list(item.get("confirmed_changes"), "ko", "확정 발표"), localized_list(item.get("confirmed_changes"), "ja", "確定発表")),
            section("planned", "개발 중이거나 적용 예정인 내용", "開発中または適用予定の内容", localized_list(item.get("planned_changes"), "ko", "개발/적용 예정"), localized_list(item.get("planned_changes"), "ja", "開発/適用予定")),
            section("undecided", "아직 확정되지 않은 내용", "まだ確定していない内容", localized_list(item.get("undecided_topics"), "ko", "미확정"), localized_list(item.get("undecided_topics"), "ja", "未確定")),
            section("user-impact", "일반 유저에게 미치는 영향", "一般プレイヤーへの影響", localized_list(item.get("user_impact"), "ko", "영향 입력이 없습니다."), localized_list(item.get("user_impact"), "ja", "影響の入力はありません。")),
            section("release-schedule", "적용 예정 시점", "適用予定時期", localized_list(item.get("release_schedule"), "ko", "일정"), localized_list(item.get("release_schedule"), "ja", "日程")),
            section("faq", "자주 묻는 질문", "FAQ", ["FAQ는 아래 접이식 카드에서 확인하세요."], ["FAQは下の折りたたみカードで確認してください。"], "faq"),
            section("source-note", "출처", "出典", ["Riot 공식 발표와 입력된 출처만 사용했습니다."], ["Riot公式発表と入力された出典のみ使用しました。"], "source_note"),
        ]

    return [
        section("quick-summary", "핵심 요약", "要点まとめ", localized_list(item.get("official_changes"), "ko", "공식 변경"), localized_list(item.get("official_changes"), "ja", "公式変更"), "quick_summary"),
        section("before-after", "변경 전과 변경 후", "変更前と変更後", localized_list(item.get("before_state"), "ko", "변경 전") + localized_list(item.get("after_state"), "ko", "변경 후"), localized_list(item.get("before_state"), "ja", "変更前") + localized_list(item.get("after_state"), "ja", "変更後"), "system_cards"),
        section("affected-positions", "어떤 포지션이 영향을 받는가", "影響を受けるロール", localized_list(item.get("affected_positions"), "ko", "포지션 입력"), localized_list(item.get("affected_positions"), "ja", "ロール入力")),
        section_from_items("affected-champions", "어떤 챔피언이 영향을 받는가", "影響を受けるチャンピオン", item.get("affected_champions", []), name_map, "영향 챔피언 입력이 없어 생성하지 않았습니다.", "影響チャンピオンの入力がないため生成していません。"),
        section("play-impact", "실제 플레이에서 달라지는 점", "実際のプレイで変わる点", localized_list(item.get("examples"), "ko", "플레이 예시"), localized_list(item.get("examples"), "ja", "プレイ例")),
        section("common-mistakes", "자주 하는 실수", "よくあるミス", localized_list(item.get("common_mistakes"), "ko", "실수 입력이 없습니다."), localized_list(item.get("common_mistakes"), "ja", "ミス入力はありません。")),
        section("checkpoints", "확인해야 할 사항", "確認すべきこと", localized_list(item.get("checkpoints"), "ko", "공식 변경과 실제 적용 범위를 확인하세요."), localized_list(item.get("checkpoints"), "ja", "公式変更と実際の適用範囲を確認しましょう。")),
        section("faq", "FAQ", "FAQ", ["FAQ는 아래 접이식 카드에서 확인하세요."], ["FAQは下の折りたたみカードで確認してください。"], "faq"),
        section("source-note", "출처", "出典", ["아래 출처 카드에서 데이터 기준을 확인하세요."], ["下の出典カードでデータ基準を確認してください。"], "source_note"),
    ]


def title_and_slug(content_type: str, item: dict, name_map: dict) -> tuple[dict, str]:
    patch = str(item.get("patch_version") or item.get("applicable_patch") or "")
    date_slug = dt.datetime.now(TIMEZONE).date().isoformat()
    if content_type == "patch-meta-followup":
        title = {
            "ko": f"LoL {patch} 패치 후 메타 점검｜{item.get('region')} {item.get('tier_range')}",
            "ja": f"LoL {patch} パッチ後メタ確認｜{item.get('region')} {item.get('tier_range')}",
        }
        slug = f"lol-patch-{version_slug(patch)}-meta-followup"
    elif content_type == "position-meta":
        pos = POSITION_LABELS[item["position"]]
        title = {"ko": f"LoL {patch} {pos['ko']} 메타 리포트", "ja": f"LoL {patch} {pos['ja']}メタレポート"}
        slug = f"lol-patch-{version_slug(patch)}-{item['position'].lower()}-meta"
    elif content_type == "champion-focus":
        champ = {"key": item.get("champion_key"), "ko": item.get("champion_name_ko"), "ja": item.get("champion_name_ja")}
        title = {"ko": f"LoL {patch} {champion_name(champ, 'ko', name_map)} 집중 분석", "ja": f"LoL {patch} {champion_name(champ, 'ja', name_map)}集中分析"}
        slug = f"lol-patch-{version_slug(patch)}-{slugify(str(item.get('champion_key')), 'champion')}-focus"
    elif content_type == "riot-dev-update":
        source_title = normalize_space(item.get("source_title", "riot-dev-update"))
        title = {"ko": f"LoL 개발자 업데이트 요약｜{source_title}", "ja": f"LoL開発者アップデート要約｜{source_title}"}
        slug = f"lol-dev-update-{slugify(source_title, date_slug)}"
    else:
        system_name_ko = localized(item.get("system_name"), "ko", "시스템")
        system_name_ja = localized(item.get("system_name"), "ja", "システム")
        title = {"ko": f"LoL {patch} {system_name_ko} 변경 가이드", "ja": f"LoL {patch} {system_name_ja}変更ガイド"}
        slug = f"lol-system-{version_slug(patch)}-{slugify(system_name_ko, 'system-guide')}"
    return title, slug


def post_image(content_type: str, item: dict, name_map: dict) -> str:
    if content_type == "champion-focus":
        key = str(item.get("champion_key", ""))
        if entry := champion_entry(key, name_map):
            return entry.get("assets", {}).get("splash", DEFAULT_IMAGE)
    patch = str(item.get("patch_version") or item.get("applicable_patch") or "")
    if patch:
        cover = REPO_ROOT / "assets" / "images" / "lol-patch" / version_slug(patch) / "cover.webp"
        if cover.exists():
            return "/" + repo_path(cover)
    return DEFAULT_IMAGE


def content_image(slug: str) -> list[dict]:
    return [
        {
            "after_section": "quick-summary",
            "src": {
                "ko": f"/assets/images/blog/generated/{slug}-core-notes-ko.svg",
                "ja": f"/assets/images/blog/generated/{slug}-core-notes-ja.svg",
            },
            "width": 1200,
            "height": 720,
            "alt": {"ko": "LoL 콘텐츠 핵심 요약 이미지", "ja": "LoLコンテンツ要点画像"},
            "caption": {"ko": "입력 데이터 기준 핵심 요약입니다.", "ja": "入力データ基準の要点まとめです。"},
        }
    ]


def champion_metadata(item: dict, name_map: dict) -> list[dict]:
    keys: list[str] = []
    for value in collect_textual_champion_items(item):
        key = champion_key(value)
        if key and key not in keys:
            keys.append(key)
    result = []
    for key in keys:
        if entry := champion_entry(key, name_map):
            result.append({"key": key, "ko": entry["ko"], "ja": entry["ja"], "status": "분석"})
    return result


def collect_textual_champion_items(item: Any) -> list[dict]:
    result: list[dict] = []
    if isinstance(item, dict):
        if item.get("key") or item.get("champion_key"):
            result.append(item)
        for value in item.values():
            result.extend(collect_textual_champion_items(value))
    elif isinstance(item, list):
        for value in item:
            result.extend(collect_textual_champion_items(value))
    return result


def build_post_data(item: dict, name_map: dict) -> dict:
    content_type = item["content_type"]
    now = dt.datetime.now(TIMEZONE).isoformat(timespec="seconds")
    today = dt.datetime.now(TIMEZONE).date().isoformat()
    title, slug = title_and_slug(content_type, item, name_map)
    image = post_image(content_type, item, name_map)
    notes = source_notes(item)
    sections = content_sections(content_type, item, name_map)
    body_ko = ["입력 데이터와 공식 출처에 포함된 정보만 사용해 정리했습니다."]
    body_ja = ["入力データと公式ソースに含まれる情報のみを使用して整理しました。"]
    description = title["ko"]
    patch = item.get("patch_version") or item.get("applicable_patch")

    post_data: dict[str, Any] = {
        "slug": slug,
        "category": "lol",
        "content_type": content_type,
        "accent": "blue",
        "read_time": "3 min",
        "image": image,
        "og_image": image,
        "date": today,
        "last_checked": item.get("last_checked") or now,
        "description": description,
        "categories": ["League of Legends"],
        "tags": ["롤", "리그오브레전드", "LoL", "메타"],
        "author": {"ko": "세이가", "ja": "セイガ"},
        "badge": TYPE_LABELS[content_type],
        "title": title,
        "excerpt": {
            "ko": f"{TYPE_LABELS[content_type]['ko']} 콘텐츠를 입력 데이터 기준으로 정리했습니다.",
            "ja": f"{TYPE_LABELS[content_type]['ja']}コンテンツを入力データ基準で整理しました。",
        },
        "post_tags": {
            "ko": ["롤", "LoL", TYPE_LABELS[content_type]["ko"]],
            "ja": ["LoL", TYPE_LABELS[content_type]["ja"]],
        },
        "lead": {
            "ko": "입력 JSON에 없는 수치나 상성은 추가하지 않았습니다.",
            "ja": "入力JSONにない数値や相性は追加していません。",
        },
        "body": {"ko": body_ko, "ja": body_ja},
        "toc": {
            "title": {"ko": "목차", "ja": "目次"},
            "items": [{"id": current["id"], "title": current["title"]} for current in sections],
        },
        "overview_table": {"title": {"ko": "한눈에 보는 기준", "ja": "基準早見表"}, "rows": data_basis_rows(item)[:10]},
        "sections": sections,
        "quick_summary_items": quick_summary(content_type, item, name_map),
        "system_change_cards": system_cards(content_type, item, name_map),
        "checklist_items": [
            {"label": {"ko": "입력 데이터 확인", "ja": "入力データ確認"}, "body": {"ko": "지역, 기간, 표본 같은 기준을 먼저 확인하세요.", "ja": "地域、期間、サンプルなどの基準を先に確認しましょう。"}},
            {"label": {"ko": "없는 수치 제외", "ja": "ない数値は除外"}, "body": {"ko": "제공되지 않은 수치는 본문에서 만들지 않습니다.", "ja": "提供されていない数値は本文で作りません。"}},
        ],
        "faq": faq_items(content_type),
        "source_notes": notes or [{"label": {"ko": "출처", "ja": "出典"}, "body": {"ko": "입력 데이터 기준입니다.", "ja": "入力データを基準にしています。"}}],
        "quote": {"ko": "없는 데이터는 쓰지 않는 것이 이 자동화의 기본 원칙입니다.", "ja": "ないデータを書かないことが、この自動化の基本原則です。"},
        "content_images": content_image(slug),
        "data_basis": {
            "region": item.get("region", ""),
            "tier_range": item.get("tier_range", ""),
            "queue": item.get("queue", ""),
            "sample_period": item.get("sample_period", ""),
            "sample_size": item.get("sample_size", ""),
        },
    }
    if patch:
        post_data["patch_version"] = str(patch)
    if item.get("source_url"):
        post_data["source_url"] = item["source_url"]
    if item.get("source_title"):
        post_data["source_title"] = item["source_title"]
    if item.get("source_published_at"):
        post_data["source_published_at"] = item["source_published_at"]
    champions = champion_metadata(item, name_map)
    if champions:
        post_data["lol_champions"] = champions
    post_data["read_time"] = read_time(post_data)
    return post_data


def load_input(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = queue_items(data)
    for item in items:
        status = str(item.get("status", "ready")).lower()
        if status in {"ready", "queued"}:
            return item
    if isinstance(data, dict) and data.get("content_type"):
        return data
    raise ValueError("생성 가능한 ready/queued 항목이 없습니다.")


def duplicate_post(slug: str) -> Path | None:
    for path in POSTS_DIR.glob("*.md"):
        if f"slug: {slug}" in path.read_text(encoding="utf-8", errors="ignore") or path.stem.endswith(slug):
            return path
    return None


def write_post(post_data: dict, dry_run: bool, force: bool) -> Path:
    slug = post_data["slug"]
    path = POSTS_DIR / f"{post_data['date']}-{slug}.md"
    existing = duplicate_post(slug)
    if existing and not force:
        raise FileExistsError(f"이미 같은 slug의 글이 있습니다: {repo_path(existing)}")
    if dry_run:
        log(f"dry-run: 게시글 저장 예정 {repo_path(path)}")
        return path
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(render_post(post_data), encoding="utf-8")
    GENERATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(GENERATED_DATA_DIR / f"{slug}.json", post_data)
    log(f"게시글 저장: {repo_path(path)}")
    log(f"생성 데이터 저장: {repo_path(GENERATED_DATA_DIR / f'{slug}.json')}")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LoL 후속 콘텐츠 입력 JSON으로 SeigaBlog 글을 생성합니다.")
    parser.add_argument("--input", help="단일 입력 JSON 또는 content_queue.json 경로입니다.")
    parser.add_argument("--from-queue", action="store_true", help="data/lol/content_queue.json에서 첫 ready 항목을 사용합니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 검증만 수행합니다.")
    parser.add_argument("--force", action="store_true", help="동일 slug가 있어도 새 파일을 씁니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input) if args.input else CONTENT_QUEUE_PATH
    if not input_path.is_absolute():
        input_path = REPO_ROOT / input_path
    if not args.from_queue and not args.input:
        log("--input 또는 --from-queue 중 하나를 지정하세요.")
        return 1
    if not input_path.exists():
        log(f"입력 파일이 없습니다: {input_path}")
        return 1

    name_map = load_champion_map()
    try:
        item = load_input(input_path)
    except ValueError as error:
        report_path = write_report("lol-content/generation-report.json", {"ok": True, "generated": False, "reason": str(error)})
        log(f"{error} 리포트: {repo_path(report_path)}")
        return 0

    issues = validate_item(item, 1, display_path(input_path), name_map)
    if issues:
        report_path = write_report("lol-content/generation-report.json", {"ok": False, "generated": False, "issues": issues})
        for issue in issues:
            log(f"{issue['type']}: {issue['message']}")
        log(f"생성을 중단했습니다. 리포트: {repo_path(report_path)}")
        return 1

    try:
        post_data = build_post_data(item, name_map)
        post_path = write_post(post_data, args.dry_run, args.force)
    except FileExistsError as error:
        report_path = write_report("lol-content/generation-report.json", {"ok": True, "generated": False, "reason": str(error)})
        log(f"{error} 리포트: {repo_path(report_path)}")
        return 0

    report_path = write_report(
        "lol-content/generation-report.json",
        {
            "ok": True,
            "generated": not args.dry_run,
            "dry_run": args.dry_run,
            "post": repo_path(post_path),
            "content_type": post_data["content_type"],
            "slug": post_data["slug"],
        },
    )
    log(f"생성 리포트 저장: {repo_path(report_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
