#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from lol_content_utils import (
    CHAMPION_IMAGE_DIR,
    CHAMPION_NAME_MAP_PATH,
    CHAMPIONS_PATH,
    DATA_DIR,
    REPO_ROOT,
    detect_champions,
    now_iso,
    post_paths,
    repo_path,
    write_json,
)


DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_CDN = "https://ddragon.leagueoflegends.com/cdn"
USER_AGENT = "SeigaBlog LoL content sync"


def log(message: str) -> None:
    print(f"[LoL Sync] {message}")


def fetch_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_binary(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def champion_url(version: str, locale: str) -> str:
    return f"{DDRAGON_CDN}/{version}/data/{locale}/champion.json"


def aliases_for(en_item: dict, ko_item: dict, ja_item: dict) -> list[str]:
    aliases = {
        en_item["id"],
        en_item["name"],
        ko_item["name"],
        ja_item["name"],
        en_item["name"].replace("'", ""),
        en_item["name"].replace(" ", ""),
        en_item["id"].replace("MonkeyKing", "Wukong"),
    }
    if en_item["id"] == "MonkeyKing":
        aliases.update({"Wukong", "오공", "ウーコン"})
    return sorted(alias for alias in aliases if alias)


def build_maps(version: str) -> tuple[dict, dict]:
    log(f"Data Dragon {version} champion.json을 내려받습니다.")
    en_data = fetch_json(champion_url(version, "en_US"))["data"]
    ko_data = fetch_json(champion_url(version, "ko_KR"))["data"]
    ja_data = fetch_json(champion_url(version, "ja_JP"))["data"]

    champions: dict[str, dict] = {}
    for key, en_item in sorted(en_data.items()):
        ko_item = ko_data[key]
        ja_item = ja_data[key]
        champions[key] = {
            "key": key,
            "numeric_key": en_item["key"],
            "en": en_item["name"],
            "ko": ko_item["name"],
            "ja": ja_item["name"],
            "title": {
                "en": en_item.get("title", ""),
                "ko": ko_item.get("title", ""),
                "ja": ja_item.get("title", ""),
            },
            "tags": en_item.get("tags", []),
            "aliases": aliases_for(en_item, ko_item, ja_item),
            "assets": {
                "square": f"/assets/images/lol/champions/{key}/square.png",
                "loading": f"/assets/images/lol/champions/{key}/loading.jpg",
                "splash": f"/assets/images/lol/champions/{key}/splash.jpg",
            },
            "source_assets": {
                "square": f"{DDRAGON_CDN}/{version}/img/champion/{key}.png",
                "loading": f"{DDRAGON_CDN}/img/champion/loading/{key}_0.jpg",
                "splash": f"{DDRAGON_CDN}/img/champion/splash/{key}_0.jpg",
            },
        }

    base = {
        "version": version,
        "updated_at": now_iso(),
        "source": {
            "versions": DDRAGON_VERSIONS_URL,
            "en_US": champion_url(version, "en_US"),
            "ko_KR": champion_url(version, "ko_KR"),
            "ja_JP": champion_url(version, "ja_JP"),
        },
        "champions": champions,
    }
    return base, base


def preserve_updated_at(path: Path, data: dict, compare_keys: list[str]) -> dict:
    if not path.exists():
        return data
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return data

    if all(current.get(key) == data.get(key) for key in compare_keys):
        data["updated_at"] = current.get("updated_at", data["updated_at"])
    return data


def detect_post_champion_keys(name_map: dict) -> list[str]:
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in post_paths())
    return [entry["key"] for entry in detect_champions(text, name_map)]


def download_assets(name_map: dict, keys: list[str], asset_types: list[str]) -> list[dict]:
    results: list[dict] = []
    champions = name_map["champions"]

    for key in keys:
        entry = champions.get(key)
        if not entry:
            continue
        for asset_type in asset_types:
            src = entry["source_assets"][asset_type]
            dest = REPO_ROOT / entry["assets"][asset_type].lstrip("/")
            status = "skipped"
            error = ""
            if not dest.exists():
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(fetch_binary(src))
                    status = "downloaded"
                except urllib.error.URLError as exc:
                    status = "failed"
                    error = str(exc)
            results.append(
                {
                    "champion": key,
                    "asset_type": asset_type,
                    "path": repo_path(dest),
                    "status": status,
                    "error": error,
                }
            )

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Riot Data Dragon 챔피언 locale/이미지 데이터를 동기화합니다.")
    parser.add_argument("--all-images", action="store_true", help="모든 챔피언 이미지를 캐싱합니다.")
    parser.add_argument(
        "--asset-types",
        default="square,loading,splash",
        help="캐싱할 이미지 종류입니다. 기본값: square,loading,splash",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        versions = fetch_json(DDRAGON_VERSIONS_URL)
        version = versions[0]
        champions_data, name_map = build_maps(version)
        champions_data = preserve_updated_at(CHAMPIONS_PATH, champions_data, ["version", "champions", "source"])
        name_map = preserve_updated_at(CHAMPION_NAME_MAP_PATH, name_map, ["version", "champions", "source"])
        write_json(CHAMPIONS_PATH, champions_data)
        write_json(CHAMPION_NAME_MAP_PATH, name_map)
        log(f"챔피언명 맵 저장: {repo_path(CHAMPION_NAME_MAP_PATH)}")

        keys = sorted(name_map["champions"]) if args.all_images else detect_post_champion_keys(name_map)
        asset_types = [item.strip() for item in args.asset_types.split(",") if item.strip()]
        results = download_assets(name_map, keys, asset_types)
        report_path = DATA_DIR / "sync-report.json"
        report = preserve_updated_at(
            report_path,
            {
                "version": version,
                "updated_at": now_iso(),
                "champion_count": len(name_map["champions"]),
                "asset_results": results,
            },
            ["version", "champion_count", "asset_results"],
        )
        write_json(report_path, report)
        downloaded = sum(1 for item in results if item["status"] == "downloaded")
        failed = sum(1 for item in results if item["status"] == "failed")
        log(f"이미지 캐싱 완료: 신규 {downloaded}개, 실패 {failed}개")
        if failed:
            log("일부 이미지 다운로드 실패는 리포트에만 기록하고 작업은 계속 진행합니다.")
        return 0
    except urllib.error.URLError as exc:
        print(f"[LoL Sync] 오류: Data Dragon 요청 실패: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
