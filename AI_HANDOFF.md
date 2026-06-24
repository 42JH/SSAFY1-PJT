# AI 활용 보강 — 진행 상황 인수인계

> 목표: 채점표의 "AI 데이터 전처리 / AI와의 유기적 연결" 축 보강. 데드라인 금요일(6/26).
> 약점 진단: 추천이 규칙 기반(문자열 매칭)이라 런타임에 AI가 없었고, 전처리 증거가 약했음.

---

## ✅ 완료 (Day 1~3)

### Day 1 — 런타임 AI 연결 (완료·검증됨)
규칙 사전 매칭이 **0건일 때만** Claude가 진료과를 직접 추론하는 폴백을 추가.
- `backend/api/services.py` → `classify_symptom_with_ai()` (16과 강제, 응급 2차분기, 실패 시 None→안전폴백)
- `backend/api/views.py` → 폴백 분기에서 호출, 응답에 `source`(rule|ai)
- `backend/api/models.py` + migration 0009 → `SymptomLog.source`
- `backend/config/settings.py` → `RECOMMEND_AI_MODEL`(기본 claude-haiku-4-5)
- `frontend` → ResultView "✨ AI 추론" 배지, store `source`
- **검증**: 라이브 키로 end-to-end 확인. "글자가 두 개로 보이고 초점이 안 맞아요"→안과(AI), "콧물 나고 기침나요"→이비인후과(규칙).

### Day 2 — 전처리 증거 + 정직한 재포장 (완료)
- `metrics.py` → "AI가 구제한 검색"(source=ai) 건수·비율 집계
- **"학습"→"피드백 보정" 전면 리네이밍** (README/PRESENTATION/DEMO/SCRUM/DEPLOY + 코드·verbose_name migration 0010). KeywordFeedback은 ML이 아닌 ±5 클램프 카운터 → 과장 제거. (잔존 "학습"은 'ML 학습 아님' 면책 문구뿐)
- **적중률 평가**: `eval_symptoms.csv`(40케이스) + `manage.py eval_recommend` → `EVAL_RESULT.md`
  - 규칙: Top-1 75% / Top-3 85% → 규칙+AI: **Top-1 80% / Top-3 90%**, AI 구제 2/2
- **전처리 증거**: `manage.py keyword_stats` → `KEYWORD_STATS.md` (사전 562 = 기본511 + LLM채택51)
- PRESENTATION S3/S6·DEMO 시나리오4(AI 구제 킬러장면)·Q&A에 AI 반영

### Day 3 — 질병정보 API 연동 (코드 완성, 실행만 남음)
건강보험심사평가원_질병정보서비스(data.go.kr B551182/diseaseInfoService1) 연동.
- `import_disease` → 질병명+KCD코드 적재 → `data/disease_codes.csv`
- `disease_to_keywords` → LLM이 질병→구어체 증상표현+진료과 → `data/keyword_candidates.csv`
- `settings`/`.env.example`에 `HIRA_DISEASE_SERVICE_KEY` 추가
- 샘플(`disease_codes.sample.csv` 12개 KCD)로 LLM 단계 검증 완료 → 후보 23개, 진료과오류 0

---

## ⛔ 지금 막힌 것 (집에서 풀 것)

**HIRA 질병정보 서버가 `resultCode 99`(서버측 DB 커넥션 장애)로 다운.**
- 우리 키는 유효함 (틀린 키는 "Unauthorized"가 뜨는데, 우리 키는 HTTP 200 + resultCode 99).
- 우리가 못 고침. 보통 일시적이니 **나중에 다시 실행하면 됨.**

---

## 🏠 집에서 할 일 (순서대로)

### 0. 키 .env에 넣기 (아직이면)
`backend/.env`:
```
ANTHROPIC_API_KEY=sk-ant-...                 # 이미 넣었으면 OK
HIRA_DISEASE_SERVICE_KEY=2f97edfe...         # 질병정보 일반 인증키
```
> ⚠️ 채팅에 붙여넣었던 첫 Anthropic 키는 폐기하고 새 키 썼는지 확인.

### 1. 서버 살아났는지 확인
```powershell
cd backend
.\venv\Scripts\python.exe manage.py import_disease --max-rows 5
```
- `resultCode 99`면 → 아직 서버 다운. 나중에 재시도.
- 질병 5건이 `data/disease_codes.csv`에 저장되면 → 서버 복구됨. 다음 단계로.

### 2. 전체 적재 → LLM 전처리 → 검수 → 반영
```powershell
.\venv\Scripts\python.exe manage.py import_disease                 # 질병 전체 적재
.\venv\Scripts\python.exe manage.py disease_to_keywords --limit 50 # LLM 전처리(우선 50개로 비용 확인)
# data/keyword_candidates.csv 열어 사람 검수 → 좋은 행을 data/keywords_approved.csv 에 추가
.\venv\Scripts\python.exe manage.py seed_data                      # 사전에 반영
```

### 3. 효과 재측정 (발표 숫자 갱신)
```powershell
.\venv\Scripts\python.exe manage.py keyword_stats --md   # 사전 구성 갱신
.\venv\Scripts\python.exe manage.py eval_recommend --with-ai --md   # 적중률 갱신
```

### 4. 커밋
아직 커밋 안 함. 작업물 전체를 커밋하면 됨. (브랜치 분리 권장)

---

## ⚠️ 발표 정확성 (채점관 Q&A 대비)

1. **이 질병 API는 "증상"이 아니라 "질병명+KCD코드"를 준다.** 정직한 표현:
   *"공공 질병정보를 받아와 **LLM으로 환자 증상표현+진료과로 전처리**했다"* ← AI 데이터 전처리 핵심.
2. **심평원 API ≠ 증상 키워드 출처.** 심평원은 병원·진료과·질병만 제공. 증상→진료과 사전은 직접 구축.
3. **KeywordFeedback은 "학습"이 아니라 "피드백 보정"** (±5 클램프 규칙 보정, ML 아님).

---

## 📁 변경/신규 파일

**신규**: `import_disease.py`, `disease_to_keywords.py`, `eval_recommend.py`, `keyword_stats.py`,
`eval_symptoms.csv`, `disease_codes.sample.csv`, `keyword_candidates.sample.csv`,
migration `0009`(SymptomLog.source)·`0010`(verbose_name), `EVAL_RESULT.md`, `KEYWORD_STATS.md`

**수정**: `services.py`, `views.py`, `models.py`, `settings.py`, `requirements.txt`, `metrics.py`,
`generate_keywords.py`(퍼널 로깅), `admin.py`, `auth_views.py`, 프론트(`ResultView.vue`·`recommend.js`·`client.js`·`MyPageView.vue`),
문서(`README`·`PRESENTATION`·`DEMO`·`SCRUM`·`DEPLOY`)
