# Minecraft Java Edition 리뷰 규칙

생성된 글과 구조화 JSON을 비교해 공개 가능 여부를 JSON으로 판단한다.

## Blocking error

- `edition`이 `java`가 아니다.
- Bedrock, Beta & Preview, Marketplace, Education, Dungeons, Legends 정보를 Java 글로 다룬다.
- Java 공식 출처 URL이 없다.
- 원문에 없는 버전 번호, 날짜, 기능, 버그 수정, 데이터팩 버전, 서버 호환성, 모드 호환성을 추가했다.
- Snapshot, Pre-Release, Release Candidate를 정식 업데이트처럼 표현했다.
- 한국어 또는 일본어 필드가 비어 있다.
- 외부 이미지 hotlink를 사용한다.
- 공식 원문을 장문 복제했다.

## 출력 형식

```json
{
  "ok": true,
  "blocking_errors": [],
  "warnings": [],
  "recommended_action": "publish | update_tracker | report_only"
}
```
