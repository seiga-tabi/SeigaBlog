# position-meta 작성 규칙

특정 포지션의 솔로랭크 메타 리포트를 작성한다.

## 지원 포지션

- Top
- Jungle
- Mid
- Bot
- Support

## 필수 입력

- `patch_version`
- `position`
- `region`
- `tier_range`
- `queue`
- `sample_period`
- `sample_size`
- `rising_picks`
- `stable_picks`
- `falling_picks`
- `ban_candidates`
- `source_notes`

## 금지

- 입력 데이터에 없는 카운터 관계, 상성, 조합 정보를 만들지 않는다.
- matchup 정보가 있을 때만 상성을 언급한다.
- 추천 밴은 `ban_candidates`에 있는 항목만 사용한다.

