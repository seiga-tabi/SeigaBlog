# Seiga Blog

Figma의 모바일 블로그 리스트/상세 화면 분위기를 참고해 만든 GitHub Pages용 Jekyll 정적 블로그입니다.

## 폴더 구조

- `_posts/`: 블로그 글 파일
- `_data/ui.yml`: 한국어/일본어 UI 문구와 카테고리 이름
- `_layouts/`: 공통 페이지 레이아웃
- `_includes/`: 카드, 상세 패널처럼 반복되는 HTML 조각
- `assets/css/styles.css`: 화면 스타일
- `assets/js/main.js`: 검색, 필터, 언어 전환, 북마크, 상세 패널 전환
- `assets/images/profile.png`: 프로필 이미지
- `_config.yml`: Jekyll 설정

## 글 추가

`_posts/YYYY-MM-DD-slug.md` 형식으로 파일을 추가합니다.

```yaml
---
slug: example-post
category: lol
accent: green
read_time: 4 min
image: https://example.com/image.jpg
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

## 로컬 확인

```bash
jekyll build
jekyll serve
```

프로젝트 Pages 경로가 `/SeigaBlog`로 설정되어 있으므로 로컬 서버에서는 `http://127.0.0.1:4000/SeigaBlog/`에서 확인합니다.

GitHub Pages는 Jekyll을 자동으로 빌드하므로 저장소에 올리면 별도 빌드 결과물 없이 배포할 수 있습니다.
배포 URL은 `https://seiga-tabi.github.io/SeigaBlog/`입니다.
