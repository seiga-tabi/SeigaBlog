# 블로그 콘텐츠 관리 가이드

이 저장소는 GitHub Pages용 Jekyll 정적 블로그입니다. 블로그 글은 `_posts/`에 있으며, 목록과 상세 화면은 `_includes/article_card.html`, `_includes/featured_card.html`, `_includes/detail_panel.html`에서 렌더링합니다.

## 콘텐츠 구조

- 글 위치: `_posts/YYYY-MM-DD-slug.md`
- 이미지 위치: `assets/images/`
- 롤 챔피언 데이터: `data/lol/champions.json`, `data/lol/champion-name-map.json`
- 롤 챔피언 이미지 캐시: `assets/images/lol/champions/{championKey}/`
- 생성 이미지: `assets/images/blog/generated/`
- 검증 리포트: `reports/`

## 챔피언명 기준

리그 오브 레전드 챔피언명은 Riot Data Dragon 공식 locale 데이터를 기준으로 합니다.

- 한국어: `ko_KR`
- 일본어: `ja_JP`
- 식별용 key: `en_US`의 champion `id`

영어 key와 slug는 파일 경로나 asset 식별자에만 사용합니다. 사용자에게 보이는 제목, 설명, 태그, 본문, alt, caption은 한국어/일본어 공식명을 사용합니다.

## 운영 명령어

```bash
npm run sync:lol
npm run fix:champions
npm run generate:blog-images
npm run validate:blog
npm run build
```

`npm run sync:lol`은 Riot Data Dragon 최신 버전을 확인하고 현재 글에서 필요한 챔피언 이미지만 로컬에 캐싱합니다. 없는 파일만 다운로드하며 실패 내역은 `data/lol/sync-report.json`에 남깁니다.

`npm run fix:champions`는 다국어 frontmatter의 한국어/일본어 영역에서 챔피언명을 공식명으로 보정하고 `reports/champion-locale-report.json`을 생성합니다.

`npm run generate:blog-images`는 각 글의 요약 SVG와 챔피언 카드 SVG를 생성합니다.

`npm run validate:blog`는 샘플/더미 글, frontmatter 누락, 챔피언명 locale 혼용, 이미지 경로, alt/caption, Jekyll 빌드를 확인합니다.

## 새 글 작성 규칙

- 샘플, 더미, 테스트, placeholder 문구를 운영 글에 남기지 않습니다.
- 대표 이미지는 `image`에 넣고 로컬 `assets/images/` 경로를 사용합니다.
- 요약 이미지는 `summary_image`에 넣고 `alt.ko`, `alt.ja`, `caption.ko`, `caption.ja`를 작성합니다.
- 긴 글은 `content_images`를 사용해 본문 중간에 이미지를 삽입합니다.
- 챔피언 중심 글은 `lol_champions`에 `key`, `ko`, `ja`, `status`를 남깁니다.
- Riot 이미지 사용 시 글 하단 또는 caption에 Riot 공식 출처임을 남깁니다.

## 실패 시 확인할 부분

- Data Dragon 네트워크 요청 실패: 네트워크 권한 또는 `https://ddragon.leagueoflegends.com` 접근 가능 여부를 확인합니다.
- 이미지 검증 실패: frontmatter의 `/assets/...` 경로와 실제 파일 위치가 일치하는지 확인합니다.
- 챔피언명 검증 실패: `npm run sync:lol` 후 `npm run fix:champions`를 다시 실행합니다.
- 빌드 실패: `_includes/content_image.html`에 전달되는 `summary_image` 또는 `content_images` 구조를 확인합니다.
