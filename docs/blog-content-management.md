# 블로그 콘텐츠 관리 가이드

SeigaBlog는 GitHub Pages용 Jekyll 정적 블로그입니다. 글 목록과 상세 화면은 `_includes/article_card.html`, `_includes/featured_card.html`, `_includes/detail_panel.html`에서 렌더링하며, LoL 패치 글은 Markdown 본문보다 frontmatter 구조를 중심으로 관리합니다.

## 콘텐츠 구조

- 글 위치: `_posts/YYYY-MM-DD-lol-patch-{version-slug}-summary.md`
- 대표 이미지: `assets/images/lol-patch/{version-slug}/`
- 생성 이미지: `assets/images/blog/generated/`
- 챔피언 데이터: `data/lol/champions.json`, `data/lol/champion-name-map.json`
- 최신 패치 구조화 요약: `data/lol/patches/latest-patch-summary.json`
- 후속 콘텐츠 대기열: `data/lol/content_queue.json`
- 후속 콘텐츠 생성 결과: `data/lol/generated/`
- 후속 콘텐츠 검증 리포트: `reports/lol-content/`
- 챔피언 이미지 캐시: `assets/images/lol/champions/{championKey}/`
- 검증 리포트: `reports/`
- 패치 글 AI 프롬프트: `prompts/lol_patch_writer.md`, `prompts/lol_patch_reviewer.md`
- 후속 콘텐츠 프롬프트: `prompts/lol/`
- 후속 콘텐츠 입력 스키마: `schemas/lol_content.schema.json`
- Minecraft Java 데이터: `data/minecraft/java/`
- Minecraft Java 리포트: `reports/minecraft/java/`
- Minecraft Bedrock 데이터: `data/minecraft/bedrock/`
- Minecraft Bedrock 리포트: `reports/minecraft/bedrock/`
- Minecraft Java 프롬프트: `prompts/minecraft/`
- Minecraft Bedrock 프롬프트: `prompts/minecraft/bedrock_writer.md`, `prompts/minecraft/bedrock_reviewer.md`

## LoL 패치 글 규칙

- `slug`는 `lol-patch-26-13-summary` 형식을 사용합니다.
- `category`는 `lol`을 사용합니다.
- `patch_version`, `source_url`, `source_title`, `source_published_at`, `last_checked`는 필수입니다.
- `title`, `excerpt`, `lead`, `body`, `post_tags`, `content_images`, `sections`는 한국어/일본어 구조를 유지합니다.
- `summary_image`는 과거 호환용 선택 필드이며, 운영 글은 `content_images`의 언어별 로컬 이미지를 우선 사용합니다.
- 챔피언명은 Riot Data Dragon의 `ko_KR`, `ja_JP` 공식 locale 데이터를 기준으로 합니다.
- 영어 champion key는 이미지 경로와 내부 데이터 식별에만 사용합니다.
- 운영 글에는 sample, dummy, placeholder, 테스트 문구를 남기지 않습니다.

## 자동화 명령

```bash
npm run sync:lol
npm run validate:lol-content-data
npm run blog:lol-patch
npm run fix:champions
npm run generate:blog-images
npm run validate:blog
npm run build
```

`npm run sync:lol`은 Riot Data Dragon 최신 챔피언명, 태그, 이미지 메타데이터를 동기화합니다.

`npm run blog:lol-patch`는 Riot 공식 패치노트에서 최신 글을 수집하고, 새 패치일 때 `_posts/` 글과 구조화 요약 JSON을 생성합니다. 이미 작성된 패치면 중복 글을 만들지 않습니다.

`npm run fix:champions`는 한국어/일본어 영역의 챔피언명을 Data Dragon 공식명으로 보정합니다. `key`, 이미지 경로, URL 같은 내부 필드는 보정 대상에서 제외합니다.

`npm run generate:blog-images`는 언어별 SVG 인포그래픽과 대표 이미지를 생성합니다.

`npm run validate:blog`는 frontmatter, 챔피언명, 이미지, 구조화 요약 JSON, 빌드 결과 HTML을 검증합니다.

## LoL 후속 콘텐츠 자동화

패치노트 요약 글을 새로 만들지 않고, 이미 수집된 공식 패치/메타 입력 데이터를 바탕으로 다음 유형의 후속 글을 생성할 수 있습니다.

- `patch-meta-followup`: 패치 적용 후 메타 점검
- `position-meta`: 포지션별 메타 리포트
- `champion-focus`: 챔피언 집중 분석
- `riot-dev-update`: Riot 개발자 업데이트 요약
- `system-guide`: 아이템, 룬, 시스템 변경 가이드

후속 콘텐츠 입력은 `data/lol/content_queue.json`의 `items` 배열에 넣습니다. 각 항목은 `content_type`, 출처, 데이터 기준, 실제 지표나 공식 변경점처럼 글에 사용할 근거만 포함해야 합니다.

```bash
npm run validate:lol-content-data
npm run select:lol-content-topic
npm run blog:lol-content
npm run generate:blog-images
npm run validate:blog
npm run build
```

`npm run validate:lol-content-data`는 콘텐츠 유형별 필수 입력과 Riot Data Dragon 기준 챔피언명 일치 여부를 확인합니다.

`npm run select:lol-content-topic`은 대기열에서 첫 번째 `ready` 또는 `queued` 항목을 `data/lol/processed/selected-topic.json`으로 저장합니다. 대기열이 비어 있으면 성공 상태로 종료하고 리포트만 남깁니다.

`npm run blog:lol-content`는 대기열의 첫 번째 생성 가능 항목을 기존 Jekyll frontmatter 구조로 변환해 `_posts/YYYY-MM-DD-{slug}.md`에 저장합니다. 같은 `slug`의 글이 이미 있으면 중복 생성을 건너뜁니다.

후속 콘텐츠 자동화는 다음 값을 임의로 만들지 않습니다.

- 입력에 없는 승률, 픽률, 밴률, 표본 수
- 입력에 없는 챔피언 변경점
- 입력에 없는 빌드, 룬, 상성, 카운터 관계
- Riot이 확정하지 않은 일정이나 기능

후속 글도 `category: lol`, 다국어 `title/excerpt/lead/body/post_tags`, `toc`, `overview_table`, `sections`, `faq`, `source_notes`, `content_images`를 사용합니다. `content_images`는 `/assets/images/blog/generated/{slug}-{kind}-{ko|ja}.svg`처럼 언어별 로컬 이미지 경로를 참조합니다.

## 선택형 AI 보강

AI 보강은 선택 사항입니다. API 키가 없으면 기존 규칙 기반 생성이 그대로 동작합니다.

```bash
OPENAI_API_KEY=... npm run blog:lol-patch -- --use-ai
npm run blog:lol-patch -- --no-ai
```

AI 입력은 `data/lol/patches/latest-patch-summary.json`과 같은 구조화 JSON으로 제한합니다. 프롬프트는 다음 파일에서 관리합니다.

- `prompts/lol_patch_writer.md`
- `prompts/lol_patch_reviewer.md`
- `prompts/lol/common_rules.md`
- `prompts/lol/patch_meta_followup.md`
- `prompts/lol/position_meta.md`
- `prompts/lol/champion_focus.md`
- `prompts/lol/riot_dev_update.md`
- `prompts/lol/system_guide.md`
- `prompts/lol/reviewer.md`

AI가 생성한 결과는 제목, 요약, 리드, 본문, 섹션 문장, FAQ, 인용문 같은 텍스트 필드에만 제한적으로 병합됩니다. 챔피언 변경 카드, 공식 수치, 이미지 경로, 출처 URL은 AI가 덮어쓰지 않습니다.

## GitHub Actions 운영

`.github/workflows/lol-patch-blog.yml`은 매일 1회 실행되며, 변경사항이 있을 때 main에 직접 push하지 않고 `automation/lol-patch-{version}` 브랜치를 만들고 Pull Request를 생성합니다.

`.github/workflows/minecraft-java-daily.yml`은 매일 17:07 `Asia/Tokyo` 기준으로 Minecraft Java Edition 공식 정보를 확인합니다. GitHub Actions cron은 UTC 기준이라 워크플로에는 08:07 UTC로 설정합니다.

`.github/workflows/minecraft-bedrock-daily.yml`은 매일 17:17 `Asia/Tokyo` 기준으로 Minecraft Bedrock Edition 공식 정보를 확인합니다. GitHub Actions cron은 UTC 기준이라 워크플로에는 08:17 UTC로 설정합니다. Java workflow와 같은 `minecraft-content-automation` concurrency 그룹을 사용합니다.

PR 생성 전 실행되는 검증은 다음과 같습니다.

```bash
npm run sync:lol
npm run validate:lol-content-data
npm run blog:lol-patch
npm run fix:champions
npm run generate:blog-images
npm run validate:blog
npm run build
```

검증 실패 시 워크플로가 실패하며 PR 생성 단계까지 가지 않습니다. 수동 실행 시 `use_ai=true`를 선택하면 `OPENAI_API_KEY` secret이 있는 경우에만 AI 보강을 시도합니다.

## Minecraft Java 운영 규칙

- Java 글은 항상 `category: minecraft`, `content_type: minecraft_java_update`, `edition: java`를 사용합니다.
- Java와 Bedrock을 하나의 글로 합치지 않습니다.
- 대표 출처는 `feedback.minecraft.net` 또는 `minecraft.net`의 공식 원문이어야 합니다.
- 제목이나 원문에 Bedrock, Beta & Preview, Marketplace, Education, Dungeons, Legends가 포함된 항목은 Java 글 후보에서 제외합니다.
- Snapshot, Pre-Release, Release Candidate는 정식 업데이트처럼 표현하지 않습니다.
- 작은 Snapshot은 `minecraft-java-snapshot-tracker-{year}` 추적 글에 누적합니다.
- 원문에 없는 버전, 날짜, 기능, 버그 수정, 데이터팩 버전, 서버 호환성, 모드 호환성은 만들지 않습니다.

로컬 실행 순서는 다음과 같습니다.

```bash
npm run daily:minecraft-java
npm run validate:minecraft-java
npm run validate:blog
npm run build
```

검색과 검증만 확인하려면 다음 명령을 사용합니다.

```bash
npm run dry-run:minecraft-java
```

## Minecraft Bedrock 운영 규칙

- Bedrock 글은 항상 `category: minecraft`, `content_type: minecraft_bedrock_update`, `edition: bedrock`을 사용합니다.
- Java와 Bedrock을 하나의 글로 합치지 않습니다.
- 대표 출처는 `feedback.minecraft.net` 또는 `minecraft.net`의 공식 원문이어야 합니다.
- 제목에 Java Edition, Snapshot, Pre-Release, Release Candidate가 포함된 항목은 Bedrock 후보에서 제외합니다.
- Education, Dungeons, Legends, Marketplace, 비공식 Add-On 업데이트, 출처 없는 커뮤니티 루머는 글 후보에서 제외합니다.
- Beta와 Preview는 정식 업데이트처럼 표현하지 않습니다.
- 플랫폼, Realms, Add-On 호환성은 원문에 있는 경우에만 기록합니다.
- 원문에 없는 버전, 날짜, 기능, 버그 수정, 플랫폼 배포 상태, 호환성 정보는 만들지 않습니다.

Bedrock 상태는 다음 값 중 하나로 분류합니다.

```text
bedrock_stable_release
bedrock_hotfix
bedrock_beta
bedrock_preview
bedrock_official_announcement
bedrock_official_planned
bedrock_platform_specific
bedrock_superseded
bedrock_withdrawn
```

정식 업데이트와 핫픽스는 단독 글 후보가 됩니다. Beta/Preview는 신규 몹, 바이옴, 블록, 아이템군, 터치 조작, 렌더링, 월드 생성, Realms, Add-On API처럼 영향이 큰 변경일 때만 단독 글을 고려합니다. 작은 Beta/Preview 변경은 `minecraft-bedrock-{target-version}-preview-tracker` 또는 `minecraft-bedrock-preview-tracker-{year}` 글을 갱신합니다.

로컬 실행 순서는 다음과 같습니다.

```bash
npm run daily:minecraft-bedrock
npm run validate:minecraft-bedrock
npm run validate:blog
npm run build
```

검색과 검증만 확인하려면 다음 명령을 사용합니다.

```bash
npm run dry-run:minecraft-bedrock
```

`reports/minecraft/bedrock/YYYY-MM-DD-daily-report.md`에는 실행 이벤트, 확인한 공식 페이지, 발견한 Bedrock 버전, 제외한 Java 항목, 플랫폼 확인 정보, 최종 주제, 후보 점수, 생성 여부, 검증 결과를 기록합니다. 리포트만 바뀐 경우에는 PR을 만들지 않습니다.

## LoL 일일 정보 자동화

`.github/workflows/daily-lol-content.yml`은 매일 12:00 `Asia/Tokyo` 기준으로 실행됩니다. 기존 `.github/workflows/lol-patch-blog.yml`와 `.github/workflows/lol-daily-intel.yml`은 수동 실행만 유지하므로, 예약된 일일 검색이 서로 겹치지 않습니다.

실행 흐름은 다음 순서입니다.

```bash
npm run sync:lol
npm run collect:lol-intel
npm run normalize:lol-intel
npm run classify:lol-intel
npm run revalidate:lol-intel
npm run select:lol-topic
npm run generate:lol-daily
npm run fix:champions
npm run generate:blog-images
npm run validate:blog
npm run build
```

수집 출처는 `data/lol/intel/sources.yml`에서 관리합니다. 기본값은 Riot 공식 패치노트, Riot 공식 게임 업데이트, Riot 개발자 글입니다. PC 리그 오브 레전드(`product: lol_pc`)만 글 후보로 사용하며, 와일드 리프트, 전략적 팀 전투, 레전드 오브 룬테라, 발로란트, 단순 홍보성 정보는 기본 발행 범위에서 제외합니다.

수집 결과는 바로 글이 되지 않습니다. `scripts/classify_lol_claims.py`가 claim 단위 JSON으로 나누고 다음 상태 중 하나로 분류합니다.

- `confirmed`: 라이브 서버에 적용됐거나 공식 라이브 패치노트에 포함된 정보
- `official_scheduled`: 적용 패치나 날짜가 Riot 공식 출처에 명시된 정보
- `official_planned`: Riot이 개발 또는 도입 계획을 직접 발표했지만 일정이 확정되지 않은 정보
- `official_considering`: 검토, 실험, 가능성 탐색 수준의 정보
- `pbe_testing`: PBE 또는 테스트 환경에서 확인됐지만 라이브 적용이 확정되지 않은 정보
- `reported`: 신뢰할 수 있는 출처의 보도이지만 Riot 공식 확인이 없는 정보
- `rumor`: 공식 확인과 충분한 교차 검증이 없는 주장
- `rejected`: Riot이 부인했거나 철회된 정보
- `superseded`: 더 새로운 공식 발표나 변경안으로 대체된 정보

주제 선정은 출처 신뢰도, 최신성, 기존 콘텐츠와의 차별성, 게임 플레이 영향도, 근거 완성도를 합산해 하루 최대 1개만 선택합니다. 75점 이상이면 단일 주제 글을 만들고, 55~74점 후보가 2개 이상이면 공식성 있는 일일 브리핑으로 묶습니다. 55점 미만이거나 중복이면 글을 만들지 않습니다.

글을 만들지 않아도 `reports/lol-intel/YYYY-MM-DD-daily-report.md`는 항상 저장합니다. 리포트에는 실행 시각, 확인한 출처 수, 신규 항목, 중복 제외 항목, 상태별 claim 수, 후보 점수, 생성 여부와 이유, 수집 실패 출처, 다음 실행에서 재검증할 항목이 포함됩니다.

상태별 발행 정책은 다음과 같습니다.

| 상태 | 글 생성 | PR 생성 | 사람 승인 |
|---|---:|---:|---:|
| `confirmed` | 예 | 예 | 필요 |
| `official_scheduled` | 예 | 예 | 필요 |
| `official_planned` | 예 | 예 | 필요 |
| `official_considering` | 브리핑만 | 조건부 | 필요 |
| `pbe_testing` | 예 | 예 | 필요 |
| `reported` | 조건부 | 조건부 | 필요 |
| `rumor` | 내부 초안만 | 아니요 | 필수 |

미확정 정보 제목에는 `[공식 예정]`, `[개발 중]`, `[검토 중]`, `[PBE 테스트]`, `[보도]`, `[미확인]`, `[철회·반박]` 접두어를 붙입니다. 상세 화면에는 `information_status` 배너가 제목 직후에 표시됩니다.

같은 주제의 기존 글이 있으면 새 글 대신 기존 slug와 URL을 유지한 채 갱신하는 방향을 우선합니다. 갱신 시 `last_checked`, `sources`, `update_history`를 함께 업데이트해야 하며, 이전 내용을 조용히 삭제하지 않습니다.

API 키 fallback은 다음 기준을 따릅니다.

- `OPENAI_API_KEY`가 없으면 규칙 기반 생성과 리포트 생성만 수행합니다.
- `WEB_SEARCH_API_KEY`가 없으면 공식 Riot 웹페이지 수집은 계속하고 보도 교차 검증 확장만 건너뜁니다.
- `YOUTUBE_API_KEY`가 없으면 YouTube 수집기만 건너뜁니다.
- `X_BEARER_TOKEN`이 없으면 X 수집기만 건너뜁니다.
- 선택 수집기 실패는 전체 공식 Riot 수집 실패로 처리하지 않습니다.

## 리뷰 체크리스트

- 공식 패치노트 수치가 맞는지 확인합니다.
- 챔피언명 ko/ja가 Riot Data Dragon 공식명인지 확인합니다.
- 승률, 픽률, 밴률, 표본 수를 임의로 만들지 않았는지 확인합니다.
- 추천 픽 표현이 과장되지 않았는지 확인합니다.
- 이미지 alt/caption과 Riot 출처 표기가 있는지 확인합니다.
- 모바일에서 목차, 요약표, 카드가 읽기 쉬운지 확인합니다.

## 실패 시 확인할 부분

- Data Dragon 요청 실패: 네트워크 또는 `https://ddragon.leagueoflegends.com` 접근 가능 여부를 확인합니다.
- 패치노트 요청 실패: Riot 공식 페이지 구조 변경 여부를 확인합니다.
- 이미지 검증 실패: frontmatter의 `/assets/...` 경로와 실제 파일 위치가 일치하는지 확인합니다.
- 구조화 JSON 검증 실패: `data/lol/patches/latest-patch-summary.json`의 필수 필드와 금지 지표 수치를 확인합니다.
- 일일 정보 실패: `data/lol/intel/daily/`, `reports/lol-intel/`, `data/lol/intel/claims/active/`를 확인합니다.
- 빌드 실패: `_includes/detail_panel.html`, `_includes/content_image.html`에서 기대하는 frontmatter 구조가 유지되는지 확인합니다.
