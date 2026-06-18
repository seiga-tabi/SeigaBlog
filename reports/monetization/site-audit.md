# SeigaBlog 수익화/SEO 사전 감사

- 감사일: 2026-06-18
- 기준 시간대: Asia/Tokyo
- 대상 저장소: `seiga-tabi/SeigaBlog`
- 공개 사이트: https://seiga-tabi.github.io/SeigaBlog/
- 감사 범위: `README.md`, `package.json`, `_config.yml`, `index.html`, `AGENTS.md`, `_posts/`, `_layouts/`, `_includes/`, `_data/`, `assets/css/`, `assets/js/`, `scripts/`, `data/lol/`, `reports/`, `docs/`, `.github/workflows/`

## 요약

현재 SeigaBlog는 GitHub Pages/Jekyll 구조를 유지하고 있으며 LoL 26.12 패치 글 1개를 카드/상세 패널 기반으로 렌더링한다. 다만 홈 HTML에 모든 글의 상세 본문, FAQ, 챔피언 카드, 이미지가 함께 포함되어 공개 홈의 다운로드 크기가 약 180KB까지 커져 있다. 글이 늘면 홈 HTML이 선형으로 커지고, 검색엔진이 홈과 글 상세를 중복 콘텐츠로 인식할 가능성이 높다.

개별 글 URL은 `/posts/{slug}/` 형태로 존재하지만, 한국어와 일본어는 같은 URL에서 JavaScript로 전환된다. 검색엔진용 `/ko/`, `/ja/` 독립 URL, `hreflang`, 언어별 canonical은 아직 없다. `sitemap.xml`, `robots.txt`, `feed.xml`, `ads.txt`는 공개 사이트에서 404로 확인됐다.

AdSense, Analytics, Search Console, CMP, 커스텀 도메인, Riot 제품 등록은 아직 준비 상태로 표시할 근거가 없다. 따라서 광고 수익화 상태는 `NOT_READY_FOR_ADSENSE_REVIEW`로 본다.

## 참고한 외부 기준

- 공개 사이트 홈: https://seiga-tabi.github.io/SeigaBlog/
- 공개 사이트 글: https://seiga-tabi.github.io/SeigaBlog/posts/lol-patch-26-12-summary/
- Riot Legal Jibber Jabber: https://www.riotgames.com/en/legal
- Riot Developer Relations General Policies: https://support-developer.riotgames.com/hc/en-us/articles/22698591841939-General-Policies
- Riot Developer API Terms: https://developer.riotgames.com/terms
- GitHub Actions schedule timezone 문서: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule

## 우선순위

| 우선순위 | 문제 | 예상 영향 | 수정 방향 |
|---|---|---|---|
| P0 | 홈이 모든 글 상세 본문을 숨겨진 `detail-stack`으로 렌더링 | 중복 콘텐츠, 크롤링 노이즈, 홈 성능 저하, 글 증가 시 HTML 폭증 | 홈에서는 카드/발췌문만 렌더링하고 글 링크는 `/posts/{slug}/`로 이동 |
| P0 | `sitemap.xml`, `robots.txt`, `feed.xml` 부재 | 색인 발견성 저하, 내부 리포트/초안 제외 정책 부재 | 정적 Jekyll 템플릿 추가 |
| P0 | Riot 공식 고지와 제품 등록/수익화 상태 표시 부재 | Riot 정책 리스크, 광고 수익화 판단 오류 | 정책 페이지 및 공통 푸터 고지 추가 |
| P1 | 한국어/일본어가 동일 URL에서 JS로 전환 | 언어별 검색 색인과 `hreflang` 불가 | `/ko/`, `/ja/`, `/ko/posts/{slug}/`, `/ja/posts/{slug}/` 생성 |
| P1 | About/Contact/Privacy 등 신뢰 페이지 부재 | AdSense 준비도와 사용자 신뢰 저하 | 필수 정책 페이지 추가 |
| P1 | AdSense feature flag와 `ads.txt` 정책 부재 | 승인 전 광고 노출, placeholder publisher ID 위험 | `_data/monetization.yml` 및 광고 include 추가, 기본 비활성화 |
| P1 | 공개 저장소용 수익/트래픽 보호 정책 미흡 | 민감 지표 공개 커밋 위험 | 문서와 검증 스크립트에 비밀/수익 데이터 차단 추가 |
| P2 | 페이지네이션 없음 | 글 증가 시 홈과 카테고리 목록 과대화 | 홈 목록 제한 및 pagination/카테고리 목록 설계 |
| P2 | Lighthouse CI 없음 | 성능/접근성/SEO 회귀 감지 어려움 | PR 품질 workflow에 Lighthouse CI 추가 |

## 감사 항목별 결과

1. 홈과 개별 글의 URL 구조
   - 홈: `/SeigaBlog/`
   - 개별 글: `/SeigaBlog/posts/lol-patch-26-12-summary/`
   - Jekyll `permalink: /posts/:slug/`가 설정되어 있어 기존 글 URL 자체는 적절하다.

2. 홈 HTML에 모든 글의 전체 본문 포함 여부
   - 포함되어 있다. `index.html` 하단의 `detail-stack`이 모든 `site.posts`에 대해 `detail_panel.html`을 렌더링한다.
   - 공개 홈 HTML은 약 179,803 bytes였고 글 1개 기준으로도 상세 페이지 크기와 거의 같다.

3. hash 기반 글 탐색 여부
   - `assets/js/main.js`가 `history.replaceState(null, "", "#${postId}")`를 사용한다.
   - 기존 카드 링크는 `href="{{ post.url | relative_url }}"`를 갖지만 홈 클릭 시 JS가 기본 이동을 막고 hash 상세 패널을 연다.
   - 기존 외부 `#slug` 링크 호환은 유지하되 canonical로 쓰면 안 된다.

4. title, description, canonical, Open Graph
   - 기본 메타와 canonical, OG, Twitter Card가 `_layouts/default.html`에 있다.
   - 홈 description은 아직 LoL 전문 블로그 목적과 맞지 않는 일반 문구다.
   - 언어별 title/description은 없다.

5. sitemap.xml
   - 공개 사이트에서 404다.

6. robots.txt
   - 공개 사이트에서 404다.

7. RSS 또는 Atom feed
   - `feed.xml`이 공개 사이트에서 404다.

8. 구조화 데이터
   - 글 상세에 `Article` JSON-LD와 `FAQPage` JSON-LD가 있다.
   - `BreadcrumbList`, `WebSite`, 언어별 구조화 데이터는 없다.
   - 화면에 보이지 않는 거짓 데이터는 확인되지 않았다.

9. 한국어·일본어 URL 구조
   - 독립 URL이 없다.
   - `data-ko`, `data-ja` 기반 JS 전환만 존재한다.

10. 내부 링크
    - 카드와 추천 글은 같은 글 상세 또는 JS 패널을 향한다.
    - 관련 글은 `button data-open-post`로 되어 있어 실제 URL 내부 링크가 아니다.
    - 글이 1개뿐이라 콘텐츠 클러스터 링크는 아직 약하다.

11. 페이지 로딩 성능
    - 공개 홈이 상세 본문 전체를 포함해 불필요하게 크다.
    - `lucide`를 CDN에서 불러오며, 사용하지 않는 상세 DOM이 홈에 있다.
    - Lighthouse CI는 없다.

12. 이미지 크기 및 레이아웃 이동
    - 상세 hero는 width/height가 있다.
    - 홈 featured/article 이미지에는 width/height 속성이 없다.
    - 광고 슬롯 예약 높이 정책은 아직 없다.

13. 모바일 사용성
    - 기존 모바일 앱형 디자인은 유지되어 있다.
    - 단, 홈에서 숨겨진 상세 패널이 함께 있어 실제 탐색 모델과 URL 모델이 충돌한다.

14. About, Contact, Privacy 페이지 존재 여부
    - 존재하지 않는다.

15. 광고 코드 및 ads.txt 준비 상태
    - AdSense 코드 없음.
    - `ads.txt` 없음.
    - placeholder publisher ID는 발견되지 않았다.

16. Google Analytics 연결 여부
    - `gtag`, `Google Analytics`, `site-verification` 코드는 발견되지 않았다.

17. Search Console 연결 준비 여부
    - `GOOGLE_SITE_VERIFICATION` 반영 구조가 없다.

18. Riot 법적 고지 여부
    - 사이트에 Riot 고지 페이지나 공통 고지가 없다.
    - Riot Legal Jibber Jabber는 팬 프로젝트 고지를 요구하고, Developer Relations General Policies는 제품용 법적 문구를 명시한다.

19. 자동 생성 콘텐츠 고지 여부
    - 글 본문에 Data Dragon/공식 패치노트 기준 설명은 있으나, AI/자동화 사용 고지 전용 페이지와 공통 노출은 없다.

20. 중복 콘텐츠 가능성
    - 홈과 글 상세가 거의 같은 상세 본문을 포함하므로 높다.
    - ko/ja가 동일 URL에서 바뀌는 구조도 언어별 중복/혼합 색인 가능성이 있다.

21. 현재 글 수와 콘텐츠 클러스터 구성
    - `_posts/` 기준 공개 글 1개.
    - LoL 패치 허브 성격의 글은 있으나, 패치 후속 메타/챔피언 집중/시스템 가이드/PBE 팩트체크 클러스터는 아직 본격 구성 전이다.

22. 기존 workflow의 main 직접 push 여부
    - `.github/workflows/pages.yml`은 `main` push를 배포 트리거로 사용한다.
    - 콘텐츠 생성 workflow는 브랜치 생성 후 PR을 만들도록 되어 있고 main 직접 push는 확인되지 않았다.
    - `lol-daily-intel.yml`은 매일 12:00 `Asia/Tokyo` 스케줄을 사용한다. GitHub Docs 기준 2026년 현재 `timezone` 필드는 지원된다.

23. API 키나 개인정보 노출 여부
    - 저장소 텍스트 검색에서 실제 API 키, OAuth token, 서비스 계정 JSON, publisher ID는 발견되지 않았다.
    - README와 workflow에는 Secret 이름만 노출되어 있으며 이는 허용 가능한 수준이다.

## Phase 1 수정 권고

1. `index.html`에서 `detail-stack` 제거.
2. `assets/js/main.js`에서 홈 카드 클릭을 hash 패널이 아니라 실제 글 URL 이동으로 변경하고, 기존 `#slug` 접근 시 `/posts/{slug}/`로 리디렉션.
3. `sitemap.xml`, `robots.txt`, `feed.xml` 추가.
4. SEO include를 분리하고 `BreadcrumbList`, `WebSite`, 기본 `hreflang` 기반을 추가.
5. About, Contact, Privacy, Editorial Policy, Automation Disclosure, Sources and Corrections, Riot Disclaimer 페이지 추가.
6. `_data/growth.yml`, `_data/monetization.yml`을 추가하되 광고는 기본 비활성화.
7. `docs/MANUAL_MONETIZATION_SETUP.md`를 추가해 사람이 해야 하는 외부 설정을 완료로 표시하지 않게 한다.
8. `AGENTS.md`에 수익화/광고/SEO/리뷰 차단 규칙을 확장한다.

## AdSense 내부 준비도

| 항목 | 배점 | 현재 점수 | 근거 |
|---|---:|---:|---|
| 독창적이고 완성된 콘텐츠 | 25 | 8 | 완성도 있는 LoL 글은 있으나 1개뿐이며 클러스터 부족 |
| 사이트 탐색 및 URL 구조 | 15 | 4 | 개별 URL은 있으나 홈 상세 중복과 언어별 URL 부재 |
| 작성자·출처·정정 정책 | 15 | 3 | 글 출처는 있으나 정책 페이지 부재 |
| Privacy·Contact·About | 15 | 0 | 페이지 부재 |
| 모바일·성능·접근성 | 10 | 4 | 디자인은 있으나 홈 HTML 과대화와 Lighthouse 미검증 |
| 중복·얇은 콘텐츠 없음 | 10 | 2 | 홈/상세 중복 렌더링 |
| 커스텀 도메인·HTTPS | 10 | 2 | GitHub Pages HTTPS는 있으나 커스텀 도메인 미확인 |
| 합계 | 100 | 23 | 내부 운영 점수이며 Google 공식 승인 점수가 아님 |

현재 상태: `NOT_READY_FOR_ADSENSE_REVIEW`

## 수익 목표 메모

월 200 USD는 KPI이며 보장 수익이 아니다. 실제 AdSense 데이터가 없으므로 실제 수익 예측을 표시하면 안 된다. Page RPM 시나리오는 반드시 `가정값`으로만 표시해야 한다.

