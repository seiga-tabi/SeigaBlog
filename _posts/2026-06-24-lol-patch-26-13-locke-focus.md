---
slug: "lol-patch-26-13-locke-focus"
category: "lol"
content_type: "champion-focus"
accent: "green"
read_time: "6 min"
image: "/assets/images/lol/champions/Locke/splash.jpg"
og_image: "/assets/images/lol/champions/Locke/splash.jpg"
date: "2026-06-24"
patch_version: "26.13"
champion_key: "Locke"
source_url: "https://ddragon.leagueoflegends.com/cdn/16.13.1/data/ko_KR/champion/Locke.json"
source_title: "Riot Data Dragon 16.13.1 로크 챔피언 데이터"
source_published_at: "2026-06-24"
last_checked: "2026-06-24T10:35:00+09:00"
description: "LoL 26.13 신규 챔피언 로크의 공식 스킬 구조, 미드 암살자/마법사 역할, 첫날 확인 포인트를 Riot 패치노트와 Data Dragon 기준으로 정리했습니다."
description_i18n:
  ko: "LoL 26.13 신규 챔피언 로크의 공식 스킬 구조, 미드 암살자/마법사 역할, 첫날 확인 포인트를 Riot 패치노트와 Data Dragon 기준으로 정리했습니다."
  ja: "LoL 26.13新チャンピオン ロックの公式スキル構造、ミッドのアサシン/メイジとしての役割、初日の確認点をRiotパッチノートとData Dragon基準で整理しました。"
categories:
  - "League of Legends"
  - "Champion Analysis"
tags:
  - "롤"
  - "리그오브레전드"
  - "LoL"
  - "로크"
  - "챔피언 분석"
  - "26.13"
lol_champions:
  -
    key: "Locke"
    ko: "로크"
    ja: "ロック"
    status: "신규 챔피언"
information_status:
  code: "confirmed"
  label:
    ko: "공식 출시 정보 확인"
    ja: "公式リリース情報確認"
  notice:
    ko: "이 글은 Riot 공식 26.13 패치노트와 Riot Data Dragon 16.13.1 로크 데이터를 기준으로 작성했습니다."
    ja: "この記事はRiot公式26.13パッチノートとRiot Data Dragon 16.13.1のロックデータを基準に作成しました。"
automation_disclosure:
  ko: "이 글은 공식 입력 데이터와 검증 스크립트를 바탕으로 작성했으며, 별도의 승률/픽률/밴률 통계는 포함하지 않았습니다."
  ja: "この記事は公式入力データと検証スクリプトをもとに作成され、勝率・ピック率・BAN率などの外部統計は含んでいません。"
sources:
  -
    url: "https://www.leagueoflegends.com/ko-kr/news/game-updates/league-of-legends-patch-26-13-notes"
    title: "리그 오브 레전드 26.13 패치 노트"
    publisher: "Riot Games"
    published_at: "2026-06-23"
    last_verified_at: "2026-06-24T10:35:00+09:00"
    source_tier: "official"
  -
    url: "https://ddragon.leagueoflegends.com/cdn/16.13.1/data/ko_KR/champion/Locke.json"
    title: "Riot Data Dragon 16.13.1 로크 champion data"
    publisher: "Riot Games"
    published_at: ""
    last_verified_at: "2026-06-24T10:35:00+09:00"
    source_tier: "official_static_data"
update_history:
  -
    date: "2026-06-24"
    ko: "Riot 공식 패치노트와 Data Dragon 16.13.1 기준으로 최초 발행했습니다."
    ja: "Riot公式パッチノートとData Dragon 16.13.1基準で初回公開しました。"
author:
  ko: "세이가"
  ja: "セイガ"
badge:
  ko: "챔피언 분석"
  ja: "チャンピオン分析"
title:
  ko: "LoL 26.13 로크 분석｜신규 미드 암살자/마법사 첫날 체크 포인트"
  ja: "LoL 26.13 ロック分析｜新ミッドアサシン/メイジ初日チェック"
excerpt:
  ko: "로크의 공식 역할군, 패시브와 Q/W/E/R 구조, 첫날 랭크 전 확인할 점을 승률 데이터 없이 공식 자료 기준으로 정리했습니다."
  ja: "ロックの公式ロール、固有スキルとQ/W/E/Rの構造、初日のランク前に確認する点を外部勝率データなしで公式資料基準で整理しました。"
post_tags:
  ko:
    - "롤"
    - "로크"
    - "챔피언 분석"
    - "미드"
    - "26.13"
  ja:
    - "LoL"
    - "ロック"
    - "チャンピオン分析"
    - "ミッド"
    - "26.13"
lead:
  ko: "로크는 Data Dragon 기준 암살자/마법사 태그를 가진 신규 챔피언이며, Riot 패치노트에서는 6월 24일 협곡 합류와 미드 라인 중심 소개가 확인됩니다."
  ja: "ロックはData Dragon基準でアサシン/メイジタグを持つ新チャンピオンで、Riotパッチノートでは6月24日の登場とミッド中心の紹介が確認できます。"
body:
  ko:
    - "이 글은 공식 패치노트와 Data Dragon에 있는 스킬 설명만 사용합니다."
    - "빌드, 룬, 상성, 티어 평가는 구조화 입력이 없으므로 작성하지 않습니다."
  ja:
    - "この記事は公式パッチノートとData Dragonにあるスキル説明のみを使用します。"
    - "ビルド、ルーン、相性、ティア評価は構造化入力がないため記載しません。"
toc:
  title:
    ko: "목차"
    ja: "目次"
  items:
    -
      id: "quick-summary"
      title:
        ko: "핵심 요약"
        ja: "要点まとめ"
    -
      id: "official-profile"
      title:
        ko: "공식 프로필"
        ja: "公式プロフィール"
    -
      id: "skill-kit"
      title:
        ko: "스킬 구조"
        ja: "スキル構造"
    -
      id: "first-day-check"
      title:
        ko: "첫날 체크리스트"
        ja: "初日チェックリスト"
    -
      id: "no-data-boundary"
      title:
        ko: "아직 쓰지 않는 정보"
        ja: "まだ扱わない情報"
    -
      id: "faq"
      title:
        ko: "FAQ"
        ja: "FAQ"
    -
      id: "source-note"
      title:
        ko: "출처"
        ja: "出典"
overview_table:
  title:
    ko: "한눈에 보는 로크"
    ja: "ロック早見表"
  rows:
    -
      label:
        ko: "패치"
        ja: "パッチ"
      value:
        ko: "26.13"
        ja: "26.13"
    -
      label:
        ko: "공식 출시"
        ja: "公式登場"
      value:
        ko: "2026-06-24"
        ja: "2026-06-24"
    -
      label:
        ko: "공식명"
        ja: "公式名"
      value:
        ko: "로크"
        ja: "ロック"
    -
      label:
        ko: "칭호"
        ja: "称号"
      value:
        ko: "잿빛 퇴마사"
        ja: "灰の祓魔師"
    -
      label:
        ko: "역할군"
        ja: "ロールタグ"
      value:
        ko: "암살자 / 마법사"
        ja: "アサシン / メイジ"
    -
      label:
        ko: "자원"
        ja: "リソース"
      value:
        ko: "마나"
        ja: "マナ"
    -
      label:
        ko: "핵심 주의"
        ja: "主な注意"
      value:
        ko: "첫날 통계와 빌드 데이터는 아직 별도 입력이 없어 제외"
        ja: "初日の統計とビルドデータは別入力がないため除外"
data_basis:
  patch_version: "26.13"
  champion_key: "Locke"
  ddragon_version: "16.13.1"
  region: ""
  tier_range: ""
  queue: ""
  period:
    ko: "공식 출시 첫날 기준"
    ja: "公式リリース初日基準"
  population:
    ko: "외부 경기 통계 없음"
    ja: "外部試合統計なし"
  metrics_available: false
content_images:
  -
    after_section: "quick-summary"
    src:
      ko: "/assets/images/blog/generated/lol-patch-26-13-locke-focus-core-notes-ko.svg"
      ja: "/assets/images/blog/generated/lol-patch-26-13-locke-focus-core-notes-ja.svg"
    width: 1200
    height: 720
    alt:
      ko: "LoL 26.13 로크 핵심 요약 이미지"
      ja: "LoL 26.13 ロック要点画像"
    caption:
      ko: "공식 스킬 구조와 첫날 확인 포인트만 요약했습니다."
      ja: "公式スキル構造と初日の確認点のみをまとめています。"
sections:
  -
    id: "quick-summary"
    kind: "quick_summary"
    title:
      ko: "핵심 요약"
      ja: "要点まとめ"
    body:
      ko:
        - "로크는 공식 태그 기준 암살자/마법사이며, 미드 라인 중심으로 소개된 신규 챔피언입니다."
      ja:
        - "ロックは公式タグ基準でアサシン/メイジであり、ミッド中心に紹介された新チャンピオンです。"
  -
    id: "official-profile"
    kind: "profile"
    title:
      ko: "공식 프로필"
      ja: "公式プロフィール"
    body:
      ko:
        - "Data Dragon 16.13.1 기준 로크의 칭호는 잿빛 퇴마사입니다."
        - "기본 공격 사거리는 근접 범위이고, 자원은 마나입니다."
        - "Riot 패치노트는 로크가 6월 24일 협곡에 합류한다고 안내했습니다."
      ja:
        - "Data Dragon 16.13.1基準で、ロックの称号は灰の祓魔師です。"
        - "通常攻撃射程は近接範囲で、リソースはマナです。"
        - "Riotパッチノートでは、ロックが6月24日に登場すると案内されています。"
  -
    id: "skill-kit"
    kind: "system_cards"
    title:
      ko: "스킬 구조"
      ja: "スキル構造"
    body:
      ko:
        - "아래 카드는 Data Dragon과 패치노트에 있는 스킬 설명만 요약합니다."
      ja:
        - "下のカードはData Dragonとパッチノートにあるスキル説明のみを要約します。"
  -
    id: "first-day-check"
    kind: "checklist"
    title:
      ko: "첫날 체크리스트"
      ja: "初日チェックリスト"
    body:
      ko:
        - "랭크 전에 공식 스킬 구조와 내 포지션 적합성만 먼저 확인하세요."
      ja:
        - "ランク前に公式スキル構造と自分のロール適性だけを先に確認しましょう。"
  -
    id: "no-data-boundary"
    kind: "boundary"
    title:
      ko: "아직 쓰지 않는 정보"
      ja: "まだ扱わない情報"
    body:
      ko:
        - "승률, 픽률, 밴률, 표본 수, 추천 룬, 아이템, 상성은 이 글에 포함하지 않습니다."
        - "해당 정보는 실제 데이터 기준이 들어온 뒤 별도 후속 글에서만 다룹니다."
      ja:
        - "勝率、ピック率、BAN率、サンプル数、おすすめルーン、アイテム、相性はこの記事に含めません。"
        - "これらは実データ基準が入った後、別のフォローアップ記事でのみ扱います。"
  -
    id: "faq"
    kind: "faq"
    title:
      ko: "FAQ"
      ja: "FAQ"
    body:
      ko:
        - "자주 묻는 질문은 공식 정보와 데이터 경계 중심으로 정리했습니다."
      ja:
        - "よくある質問は公式情報とデータ境界を中心に整理しました。"
  -
    id: "source-note"
    kind: "source_note"
    title:
      ko: "출처"
      ja: "出典"
    body:
      ko:
        - "공식 출처와 마지막 확인 시각은 아래 카드에 정리했습니다."
      ja:
        - "公式出典と最終確認時刻は下のカードに整理しています。"
quick_summary_items:
  -
    label:
      ko: "공식 역할"
      ja: "公式ロール"
    body:
      ko: "Data Dragon 태그는 암살자/마법사이며, Riot 소개 문맥은 미드 라인 중심입니다."
      ja: "Data Dragonタグはアサシン/メイジで、Riotの紹介文脈はミッド中心です。"
  -
    label:
      ko: "핵심 구조"
      ja: "主な構造"
    body:
      ko: "Q 표식, W 자기 피해 후 회복, E 순간이동/추격, R 표식과 처형형 봉인 구조를 가집니다."
      ja: "Qのマーク、Wの自傷後回復、Eのテレポート/追撃、Rのマークと処刑型封印構造を持ちます。"
  -
    label:
      ko: "첫날 판단"
      ja: "初日の判断"
    body:
      ko: "공식 스킬 구조만으로 빌드나 티어를 단정하지 않습니다."
      ja: "公式スキル構造だけでビルドやティアを断定しません。"
system_change_cards:
  -
    title:
      ko: "패시브: 은빛 말뚝"
      ja: "固有スキル: シルバー・ステイク"
    badge:
      ko: "기본 공격"
      ja: "通常攻撃"
    target:
      ko: "기본 공격 적중 시 추가 마법 피해"
      ja: "通常攻撃命中時の追加魔法ダメージ"
    change_summary:
      ko:
        - "적중 시 추가 마법 피해를 주며, 대상의 잃은 체력에 따라 피해가 증가합니다."
      ja:
        - "命中時に追加魔法ダメージを与え、対象の減少体力に応じてダメージが増加します。"
    immediate_check:
      ko:
        - "체력이 낮은 대상에게 기본 공격을 넣는 마무리 구조를 확인합니다."
      ja:
        - "体力が低い対象に通常攻撃を入れる締めの構造を確認します。"
    judgment:
      ko: "스킬 적중 뒤 기본 공격 연결이 중요해 보입니다."
      ja: "スキル命中後の通常攻撃接続が重要に見えます。"
    less_important:
      ko: "단순 원거리 포킹 챔피언처럼 보는 판단"
      ja: "単純な遠距離ポークチャンピオンとして見る判断"
  -
    title:
      ko: "Q: 의식용 대못"
      ja: "Q: リチュアル・ネイル"
    badge:
      ko: "표식"
      ja: "マーク"
    target:
      ko: "영혼의 대못 투척과 표식 소모"
      ja: "魂の釘の投擲とマーク消費"
    change_summary:
      ko:
        - "대못을 던져 피해와 표식을 남기고, 기본 공격으로 표식을 소모해 추가 피해를 줍니다."
        - "대못 적중 수에 따라 둔화 효과가 중첩됩니다."
      ja:
        - "釘を投げてダメージとマークを付与し、通常攻撃でマークを消費して追加ダメージを与えます。"
        - "釘の命中数に応じてスロウ効果が重なります。"
    immediate_check:
      ko:
        - "Q 적중 후 기본 공격을 연결할 수 있는 거리와 타이밍을 확인합니다."
      ja:
        - "Q命中後に通常攻撃をつなげられる距離とタイミングを確認します。"
    judgment:
      ko: "로크의 교전 시작과 피해 누적을 함께 담당하는 스킬입니다."
      ja: "ロックの戦闘開始とダメージ蓄積を同時に担うスキルです。"
    less_important:
      ko: "표식 소모 없이 Q만 던지는 운영"
      ja: "マーク消費なしでQだけを投げる運用"
  -
    title:
      ko: "W: 영혼 점화"
      ja: "W: ソウル・イグニッション"
    badge:
      ko: "속도/회복"
      ja: "速度/回復"
    target:
      ko: "공격 속도와 이동 속도 증가, 자기 피해 후 회복"
      ja: "攻撃速度と移動速度増加、自傷後回復"
    change_summary:
      ko:
        - "공격 속도와 이동 속도를 얻지만 자신에게 피해를 입습니다."
        - "지속시간이 끝나면 효과 중 받은 피해 일부를 회복합니다."
      ja:
        - "攻撃速度と移動速度を得る一方で、自身にダメージを与えます。"
        - "効果終了時、効果中に受けたダメージの一部を回復します。"
    immediate_check:
      ko:
        - "교전 시작용인지, 교전 중 버티기용인지 상황을 나눠 봅니다."
      ja:
        - "戦闘開始用か、戦闘中の耐久用かを状況で分けて見ます。"
    judgment:
      ko: "자기 피해가 있는 만큼 무리한 선사용은 위험할 수 있습니다."
      ja: "自傷があるため、無理な先使用は危険になり得ます。"
    less_important:
      ko: "항상 먼저 누르는 고정 사용"
      ja: "常に先に使う固定運用"
  -
    title:
      ko: "E: 잿빛 추격"
      ja: "E: 灰塵の追撃"
    badge:
      ko: "이동"
      ja: "移動"
    target:
      ko: "지정 위치 순간이동 후 다음 대상 추격"
      ja: "指定地点へのテレポート後、次の対象を追撃"
    change_summary:
      ko:
        - "지정 위치로 순간이동하고 주변 적에게 피해를 줍니다."
        - "다음 기본 공격에서 대상에게 돌진하며 경로상의 적에게 피해를 줍니다."
        - "처치 관여 시 재사용 대기시간이 초기화됩니다."
      ja:
        - "指定地点にテレポートし、周囲の敵にダメージを与えます。"
        - "次の通常攻撃で対象へダッシュし、経路上の敵にダメージを与えます。"
        - "キルまたはアシスト時にクールダウンが解消されます。"
    immediate_check:
      ko:
        - "진입 후 빠져나올 수 있는지, 처치 관여 조건을 만들 수 있는지 확인합니다."
      ja:
        - "入った後に離脱できるか、キル/アシスト条件を作れるかを確認します。"
    judgment:
      ko: "첫날에는 E 초기화 기대보다 진입 실패 비용을 더 크게 봐야 합니다."
      ja: "初日はEリセット期待より、失敗時のコストを大きく見ます。"
    less_important:
      ko: "초기화만 보고 무조건 깊게 들어가는 판단"
      ja: "リセットだけを見て深く入りすぎる判断"
  -
    title:
      ko: "R: 연옥"
      ja: "R: 煉獄"
    badge:
      ko: "표식/처형"
      ja: "マーク/処刑"
    target:
      ko: "구속 유물 투척, 표식, 조건부 처형과 영구 강화"
      ja: "束縛アーティファクト、マーク、条件付き処刑と恒久強化"
    change_summary:
      ko:
        - "유물을 던져 범위 피해와 둔화를 주고 적에게 표식을 남깁니다."
        - "표식이 남은 적 챔피언이 기준 체력 아래로 내려가면 봉인됩니다."
        - "로크가 떨어진 유물을 획득하면 봉인 수에 따라 처형 기준치가 영구 증가합니다."
      ja:
        - "アーティファクトを投げて範囲ダメージとスロウを与え、敵にマークを付与します。"
        - "マークされた敵チャンピオンが基準体力未満になると封印されます。"
        - "落ちたアーティファクトを拾うと、封印数に応じて処刑基準値が恒久的に増加します。"
    immediate_check:
      ko:
        - "표식 지속시간 안에 마무리할 수 있는 상황인지 확인합니다."
      ja:
        - "マーク時間内に仕留められる状況か確認します。"
    judgment:
      ko: "궁극기는 단발 피해보다 표식 유지와 봉인 후 회수까지 포함해 봐야 합니다."
      ja: "アルティメットは単発ダメージより、マーク維持と封印後の回収まで含めて見ます。"
    less_important:
      ko: "처형 문구만 보고 확정 마무리기로 단정하는 판단"
      ja: "処刑という文言だけで確定フィニッシュと断定する判断"
checklist_items:
  -
    label:
      ko: "스킬명과 역할 먼저 확인"
      ja: "スキル名とロールを先に確認"
    body:
      ko: "로크는 암살자/마법사 태그와 마나 자원을 가진 신규 챔피언입니다."
      ja: "ロックはアサシン/メイジタグとマナリソースを持つ新チャンピオンです。"
  -
    label:
      ko: "Q 표식 후 기본 공격 연결"
      ja: "Qマーク後の通常攻撃接続"
    body:
      ko: "공식 설명상 Q 표식은 기본 공격으로 소모하므로 거리 관리가 핵심입니다."
      ja: "公式説明上、Qマークは通常攻撃で消費するため、距離管理が重要です。"
  -
    label:
      ko: "E 진입 실패 비용"
      ja: "E失敗時のコスト"
    body:
      ko: "처치 관여 초기화가 있어도 첫 진입이 실패하면 손해가 커질 수 있습니다."
      ja: "キル/アシストでリセットされても、最初の入りが失敗すると損失が大きくなり得ます。"
  -
    label:
      ko: "빌드와 룬 단정 금지"
      ja: "ビルドとルーンを断定しない"
    body:
      ko: "이 글에는 공식 스킬 정보만 있으며 추천 빌드 데이터는 없습니다."
      ja: "この記事には公式スキル情報のみがあり、おすすめビルドデータはありません。"
faq:
  -
    question:
      ko: "로크는 어느 포지션 챔피언인가요?"
      ja: "ロックはどのロールのチャンピオンですか？"
    answer:
      ko: "Riot 소개 문맥은 미드 라인이고, Data Dragon 태그는 암살자/마법사입니다."
      ja: "Riotの紹介文脈はミッドで、Data Dragonタグはアサシン/メイジです。"
  -
    question:
      ko: "로크 추천 빌드나 룬도 포함했나요?"
      ja: "ロックのおすすめビルドやルーンも含めていますか？"
    answer:
      ko: "아니요. 공식 스킬 정보만 사용했고 빌드와 룬 데이터는 포함하지 않았습니다."
      ja: "いいえ。公式スキル情報のみを使用し、ビルドとルーンデータは含めていません。"
  -
    question:
      ko: "로크가 바로 랭크에서 좋은 픽인가요?"
      ja: "ロックはすぐランクで強いピックですか？"
    answer:
      ko: "이 글은 티어를 단정하지 않습니다. 첫날에는 스킬 구조와 진입 실패 비용을 먼저 확인하세요."
      ja: "この記事はティアを断定しません。初日はスキル構造と入り失敗時のコストを先に確認しましょう。"
source_notes:
  -
    label:
      ko: "Riot 공식 패치노트"
      ja: "Riot公式パッチノート"
    body:
      ko: "26.13 패치의 로크 출시일, 스킬 요약, 랭크 관련 변경을 확인했습니다."
      ja: "26.13パッチのロック登場日、スキル要約、ランク関連変更を確認しました。"
    url: "https://www.leagueoflegends.com/ko-kr/news/game-updates/league-of-legends-patch-26-13-notes"
  -
    label:
      ko: "Riot Data Dragon"
      ja: "Riot Data Dragon"
    body:
      ko: "로크의 공식 한국어/일본어명, 칭호, 역할군, 스킬 설명, 이미지 경로를 확인했습니다."
      ja: "ロックの公式韓国語/日本語名、称号、ロールタグ、スキル説明、画像パスを確認しました。"
    url: "https://ddragon.leagueoflegends.com/cdn/16.13.1/data/ko_KR/champion/Locke.json"
quote:
  ko: "로크는 첫날부터 빌드 정답을 찾기보다, Q 표식과 E 진입, R 봉인 구조를 먼저 이해해야 하는 챔피언입니다."
  ja: "ロックは初日からビルドの正解を探すより、Qマーク、Eの入り、Rの封印構造を先に理解すべきチャンピオンです。"
---
