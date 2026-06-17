#!/usr/bin/env python3
from __future__ import annotations

import argparse

from lol_content_utils import (
    load_champion_map,
    localized_line_language,
    post_paths,
    repo_path,
    replace_champion_names,
    write_report,
)


def log(message: str) -> None:
    print(f"[Champion Fix] {message}")


def should_replace_line(line: str) -> bool:
    stripped = line.lstrip()
    protected_prefixes = (
        "source_url:",
        "image:",
        "src:",
        "url:",
        "target_anchor:",
        "source_anchor:",
        "key:",
        "- key:",
    )
    return not stripped.startswith(protected_prefixes)


def fix_post(text: str, name_map: dict) -> tuple[str, list[dict]]:
    lines = text.splitlines(keepends=True)
    current: tuple[str | None, int] = (None, 0)
    changes: list[dict] = []
    fixed_lines: list[str] = []

    for line_no, line in enumerate(lines, start=1):
        current = localized_line_language(line, current)
        lang = current[0]
        if lang in {"ko", "ja"} and should_replace_line(line):
            replaced, line_changes = replace_champion_names(line, lang, name_map)
            fixed_lines.append(replaced)
            for change in line_changes:
                change["line"] = line_no
                changes.append(change)
        else:
            fixed_lines.append(line)

    return "".join(fixed_lines), changes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="블로그 글의 챔피언명을 Data Dragon 공식 locale 명칭으로 보정합니다.")
    parser.add_argument("--dry-run", action="store_true", help="파일을 수정하지 않고 리포트만 생성합니다.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    name_map = load_champion_map()
    report: list[dict] = []

    for path in post_paths():
        original = path.read_text(encoding="utf-8")
        fixed, changes = fix_post(original, name_map)
        if changes and not args.dry_run:
            path.write_text(fixed, encoding="utf-8")
        report.append(
            {
                "file": repo_path(path),
                "changed": original != fixed,
                "change_count": len(changes),
                "changes": changes,
            }
        )

    report_path = write_report("champion-locale-report.json", report)
    total = sum(item["change_count"] for item in report)
    log(f"챔피언명 보정 리포트 저장: {repo_path(report_path)}")
    log(f"보정 항목: {total}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
