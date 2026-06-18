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

후속 글도 `category: lol`, 다국어 `title/excerpt/lead/body/post_tags`, `toc`, `overview_table`, `sections`, `faq`, `source_notes`, `content_images`를 사용합니다. `content_images`는 `/assets/images/blog/generated/{slug}-core-notes-{ko|ja}.svg`처럼 언어별 로컬 이미지 경로를 참조합니다.

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
- 빌드 실패: `_includes/detail_panel.html`, `_includes/content_image.html`에서 기대하는 frontmatter 구조가 유지되는지 확인합니다.
