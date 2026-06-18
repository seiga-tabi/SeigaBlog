# 분석 데이터 연결 가이드

SeigaBlog는 선택적으로 Google Analytics Data API, Google Search Console API, Google AdSense Management API를 사용할 수 있다. 인증정보가 없으면 해당 단계만 건너뛰고 가짜 데이터를 만들지 않는다.

## 필요 설정

```text
GA4_PROPERTY_ID
GSC_SITE_URL
ADSENSE_ACCOUNT_ID
GOOGLE_APPLICATION_CREDENTIALS 또는 안전한 OAuth 설정
```

## 공개 저장소 보호

- 실제 수익 금액을 `reports/`에 공개 커밋하지 않는다.
- Search Console 원본 쿼리 데이터를 공개 커밋하지 않는다.
- OAuth token과 서비스 계정 JSON을 커밋하지 않는다.
- 공개 PR에는 목표 대비 증가/감소, 개선할 콘텐츠 클러스터, 수정 대상 글, 기술 문제만 기록한다.

