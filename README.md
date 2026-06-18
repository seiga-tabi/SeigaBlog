# Seiga Blog

Figma의 모바일 블로그 리스트/상세 화면 분위기를 참고해 만든 GitHub Pages용 Jekyll 정적 블로그입니다.

## 폴더 구조

- `_posts/`: 블로그 글 파일
- `_data/ui.yml`: 한국어/일본어 UI 문구와 카테고리 이름
- `_layouts/`: 공통 페이지 레이아웃
- `_includes/`: 카드, 상세 패널처럼 반복되는 HTML 조각
- `data/lol/`: Riot Data Dragon 기준 챔피언명/이미지 메타데이터
- `data/lol/patches/`: 최신 패치노트 구조화 요약 JSON
- `data/lol/content_queue.json`: LoL 후속 콘텐츠 생성 대기열
- `data/lol/generated/`: LoL 후속 콘텐츠 생성 결과 JSON
- `prompts/`: 선택형 AI 글 보강/리뷰 프롬프트
- `prompts/lol/`: LoL 패치 후속 콘텐츠 유형별 작성/리뷰 규칙
- `schemas/`: LoL 콘텐츠 입력 데이터 스키마
- `assets/css/styles.css`: 화면 스타일
- `assets/js/main.js`: 검색, 필터, 언어 전환, 북마크, 상세 패널 전환
- `assets/images/profile.png`: 프로필 이미지
- `assets/images/lol/`: Data Dragon 챔피언 이미지 캐시
- `assets/images/blog/generated/`: 블로그 요약 이미지와 인포그래픽
- `reports/`: 챔피언명 보정, 이미지 생성, 콘텐츠 검증 리포트
- `scripts/`: 롤 패치 글 생성과 콘텐츠 검증 자동화
- `_config.yml`: Jekyll 설정

## 글 추가

`_posts/YYYY-MM-DD-slug.md` 형식으로 파일을 추가합니다. 운영 글에는 샘플/더미/테스트 문구를 남기지 않습니다.

```yaml
---
slug: lol-patch-26-13-summary
category: lol
accent: green
read_time: 4 min
image: /assets/images/lol-patch/26-13/cover.webp
content_images:
  - after_section: quick-summary
    src:
      ko: /assets/images/blog/generated/lol-patch-26-13-summary-core-notes-ko.svg
      ja: /assets/images/blog/generated/lol-patch-26-13-summary-core-notes-ja.svg
    width: 1200
    height: 720
    alt:
      ko: 한국어 이미지 설명
      ja: 日本語の画像説明
author:
  ko: 작성자
  ja: 著者
badge:
  ko: 리포트
  ja: レポート
title:
  ko: 한국어 제목
  ja: 日本語タイトル
excerpt:
  ko: 한국어 요약
  ja: 日本語の要約
post_tags:
  ko:
    - 디자인
  ja:
    - デザイン
lead:
  ko: 한국어 리드 문장
  ja: 日本語のリード文
body:
  ko:
    - 한국어 본문 문단
  ja:
    - 日本語本文の段落
quote:
  ko: 한국어 인용문
  ja: 日本語の引用文
---
```

카테고리를 추가하려면 `_data/ui.yml`의 `category_order`와 `categories`에 한국어/일본어 이름을 추가합니다.

## 롤 콘텐츠 운영

챔피언명은 번역기로 임의 번역하지 않고 Riot Data Dragon의 `ko_KR`, `ja_JP` 공식 locale 데이터를 기준으로 관리합니다.

```bash
npm run sync:lol
npm run fix:champions
npm run generate:blog-images
npm run validate:blog
```

새 롤 패치 글을 생성할 때는 다음 명령을 사용합니다.

```bash
npm run blog:lol-patch
```

OpenAI API 키가 있으면 문장 품질 보강을 선택적으로 시도할 수 있습니다. 키가 없거나 옵션을 쓰지 않으면 기존 규칙 기반 생성이 그대로 동작합니다.

```bash
OPENAI_API_KEY=... npm run blog:lol-patch -- --use-ai
npm run blog:lol-patch -- --no-ai
```

자동화는 `data/lol/patches/latest-patch-summary.json`을 먼저 만들고, AI가 사용할 수 있는 입력도 이 구조화 JSON으로 제한합니다.

패치 적용 후 메타 점검, 포지션별 메타 리포트, 챔피언 집중 분석, Riot 개발자 업데이트, 시스템 변경 가이드는 `data/lol/content_queue.json`에 입력 데이터를 넣은 뒤 다음 명령으로 생성합니다.

```bash
npm run validate:lol-content-data
npm run select:lol-content-topic
npm run blog:lol-content
npm run generate:blog-images
npm run validate:blog
```

후속 콘텐츠 자동화는 입력 JSON에 없는 승률, 픽률, 밴률, 표본 수, 빌드, 룬, 상성을 만들지 않습니다. 생성 글은 기존 `_posts/` frontmatter, 다국어 필드, 카드 렌더링 구조를 그대로 사용합니다.

상세 운영 규칙은 [docs/blog-content-management.md](docs/blog-content-management.md)를 확인합니다.

## 로컬 확인

```bash
npm run build
jekyll serve
```

프로젝트 Pages 경로가 `/SeigaBlog`로 설정되어 있으므로 로컬 서버에서는 `http://127.0.0.1:4000/SeigaBlog/`에서 확인합니다.

GitHub Pages는 Jekyll을 자동으로 빌드하므로 저장소에 올리면 별도 빌드 결과물 없이 배포할 수 있습니다.
배포 URL은 `https://seiga-tabi.github.io/SeigaBlog/`입니다.
