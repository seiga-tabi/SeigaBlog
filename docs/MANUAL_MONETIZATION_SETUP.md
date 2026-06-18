# 수익화 수동 설정 가이드

이 문서는 Codex나 GitHub Actions가 대신 완료할 수 없는 외부 설정을 정리한다. 아래 항목은 실제 계정, 도메인, DNS, Google, Riot Developer Portal에서 사용자가 직접 처리해야 하며, 완료 전에는 사이트나 자동화가 준비 완료로 표시하면 안 된다.

## 현재 상태

```text
CUSTOM_DOMAIN: blog.seigatabi.com
custom_domain_verified: false
GA4_MEASUREMENT_ID: 미설정
GA4_PROPERTY_ID: 미설정
GOOGLE_SITE_VERIFICATION: 미설정
ADSENSE_CLIENT_ID: 미설정
ADSENSE_ACCOUNT_ID: 미설정
ADSENSE_PUBLISHER_ID: 미설정
ADSENSE_ENABLED: false
RIOT_PRODUCT_REGISTRATION_STATUS: 미설정
```

`custom_domain_verified: false`인 동안에는 AdSense 준비 완료로 표시하지 않는다.

## 필수 수동 단계

1. 커스텀 도메인을 구매한다.
2. GitHub Pages 설정에서 커스텀 도메인을 연결한다.
3. DNS의 `A`, `AAAA`, 또는 `CNAME` 레코드를 설정한다.
4. GitHub Pages에서 HTTPS를 강제한다.
5. Google Search Console에서 도메인을 인증한다.
6. Google Analytics 속성을 생성한다.
7. Google AdSense에서 사이트를 추가하고 인증한다.
8. AdSense 승인 후 실제 publisher ID를 등록한다.
9. Google CMP 또는 승인된 CMP를 설정한다.
10. Riot Developer Portal에서 프로젝트를 등록한다.

## 지원 환경 변수

```text
CUSTOM_DOMAIN
GA4_MEASUREMENT_ID
GA4_PROPERTY_ID
GOOGLE_SITE_VERIFICATION
ADSENSE_CLIENT_ID
ADSENSE_ACCOUNT_ID
ADSENSE_PUBLISHER_ID
ADSENSE_ENABLED
RIOT_PRODUCT_REGISTRATION_STATUS
GSC_SITE_URL
GOOGLE_APPLICATION_CREDENTIALS
```

## 커스텀 도메인 규칙

- 현재 공개 도메인은 `https://blog.seigatabi.com/`이다.
- 커스텀 도메인을 설정한 뒤에는 `_config.yml`의 `url` 또는 GitHub Pages 설정이 실제 도메인과 일치하는지 확인한다.
- Search Console 인증이 끝나기 전에는 `custom_domain_verified`를 `true`로 바꾸지 않는다.

## AdSense 활성화 조건

다음 조건을 모두 충족할 때만 광고를 활성화한다.

```text
CUSTOM_DOMAIN 존재
custom_domain_verified == true
adsense_approved == true
ADSENSE_CLIENT_ID 존재
ADSENSE_PUBLISHER_ID 존재
ADSENSE_ENABLED == true
Privacy 페이지 존재
Cookie/CMP 설정 완료
ads.txt 설정 완료
콘텐츠 품질 검증 통과
```

placeholder publisher ID를 `ads.txt`, `_data/monetization.yml`, workflow 로그, PR 본문에 넣지 않는다.

## Riot Developer Portal

`RIOT_PRODUCT_REGISTRATION_STATUS`가 비어 있으면 다음 상태로 처리한다.

- 공식 패치노트와 공개 정적 자료 기반 글 생성은 계속할 수 있다.
- API 기반 데이터 수익화 준비 상태는 미완료로 표시한다.
- 운영자에게 등록 필요 경고를 남긴다.
- 등록이 완료됐다고 표시하지 않는다.

## 공개 저장소에 커밋하지 않는 정보

- 실제 AdSense 수익
- Search Console 원본 쿼리 데이터
- OAuth token
- 서비스 계정 JSON
- Riot API key
- 사용자 IP 또는 개인 식별 정보
