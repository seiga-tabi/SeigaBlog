# champion-focus 작성 규칙

특정 챔피언의 패치 변경과 실제 활용법을 정리한다.

## 필수 입력

- `patch_version`
- `champion_key`
- `champion_name_ko`
- `champion_name_ja`
- `official_changes`
- `riot_context`
- `position`
- `current_metrics`
- `previous_metrics`
- `build_data`
- `rune_data`
- `matchup_data`
- `source_notes`

## 금지

- `build_data`가 없으면 아이템 추천을 생성하지 않는다.
- `rune_data`가 없으면 룬 추천을 생성하지 않는다.
- `matchup_data`가 없으면 유리하거나 불리한 상대를 생성하지 않는다.
- AI의 일반 지식으로 콤보, 빌드, 룬, 상성을 보충하지 않는다.

