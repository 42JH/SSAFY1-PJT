# 잇닥 (ITdoc)

증상을 입력하면 **진료과를 추천**하고, **가까운 동네 병원을 거리순으로 추천**하며, 앱 내 **카카오맵**에서 위치를 바로 확인하는 의료 정보 추천 서비스.

> ⚠️ 잇닥의 추천은 진단이 아닌 **참고용 정보**입니다.

## 기술 스택

| 구분 | 기술 |
|---|---|
| Backend | Django 4.2 + DRF |
| Frontend | Vue 3 (Composition API) + Pinia + Vue Router |
| 지도 | 카카오맵 JavaScript SDK (앱 내 임베드) |
| 길찾기 | 카카오모빌리티 길찾기 REST API (백엔드 프록시) |
| 인증 | JWT (djangorestframework-simplejwt) — 회원·건강 로그 |
| DB | SQLite |
| 거리 계산 | Haversine (Python) |

## 실행 방법

### 1. 백엔드 (Django) — http://127.0.0.1:8000

```powershell
cd backend
.\venv\Scripts\Activate.ps1     # 최초 1회: python -m venv venv 후 pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data       # 진료과(HIRA 코드 1:1)·키워드 사전 5,253개(기본+AI전처리 검수분)·응급 키워드·데모 병원
python manage.py runserver
```

### (선택) 심평원 실데이터 적재 — 구미권 병·의원 550여 곳

공공데이터포털에서 **건강보험심사평가원_병원정보서비스** 활용신청 후:

```powershell
python manage.py import_hira --key <일반인증키> --dry-run   # 미리보기
python manage.py import_hira --key <일반인증키>              # 실제 적재 (데모 병원 대체)
# 옵션: --regions 구미시,김천시,칠곡군  --sido-cd 370000  --probe-sido
```

- 진료과목코드(dgsbjtCd) 역방향 조회로 병원↔진료과 M:N을 상세 API 없이 구축
- 치과는 세부과목 코드(50~61)까지 포함해 조회
- 진료시간은 기본값(09:00~18:00) — 의료기관별상세정보서비스 연동 시 실데이터 가능

### 2. 프론트엔드 (Vue) — http://localhost:5173

```powershell
cd frontend
npm install
# .env 에 카카오맵 JavaScript 키 입력
# VITE_KAKAO_JS_KEY=발급받은키
npm run dev
```

> 카카오 키 발급: [Kakao Developers](https://developers.kakao.com) → 앱 생성 → JavaScript 키 복사 → 플랫폼에 `http://localhost:5173` 등록

## API 명세

| Method | URL | 설명 |
|---|---|---|
| POST | `/api/recommend/` | 증상 텍스트 → 응급 분기 또는 진료과 1~3순위 추천 (근거 포함, 로그인 시 검색 이력 저장) |
| GET | `/api/departments/` | 진료과 목록 |
| GET | `/api/hospitals/?lat=&lng=&department_id=&radius=&open_only=` | 위치·진료과 기반 병원 추천 (Haversine 거리·평점 보정 정렬·반경 자동 확장) |
| GET | `/api/hospitals/<id>/` | 병원 상세 (미니맵 좌표 + 후기 평점 요약) |
| GET·POST | `/api/hospitals/<id>/reviews/` | 병원 후기 목록 / 작성·수정 (작성은 로그인 필수, 1인 1병원 1후기) |
| DELETE | `/api/reviews/<id>/` | 내 후기 삭제 |
| GET | `/api/emergency-centers/?lat=&lng=` | 가까운 응급의료기관 거리순 (E-Gen) |
| GET | `/api/directions/?origin_lat=&origin_lng=&dest_lat=&dest_lng=` | 카카오모빌리티 자동차 길찾기 프록시 (경로 좌표·거리·소요시간) |
| POST | `/api/auth/signup/` · `/api/auth/login/` · `/api/auth/refresh/` | 회원가입 / 로그인 / 토큰 갱신 (JWT) |
| GET | `/api/auth/me/` | 내 정보 + 건강 로그 인사이트·최근 검색 이력 |
| DELETE | `/api/auth/logs/<id>/` | 건강 로그 삭제 |
| POST | `/api/auth/logs/<id>/feedback/` | 추천 평가(👍/👎) — 키워드 피드백 보정값 반영 |

### POST /api/recommend/ 응답 예시

```json
// 일반
{"emergency": false, "results": [{"department_id": 2, "department": "이비인후과", "score": 6, "matched_keywords": ["콧물", "인후통"]}], "fallback": false}

// 응급 (keyword=매칭 어간, label=화면 표시용 증상명)
{"emergency": true, "matched_keywords": [{"keyword": "가슴통증", "label": "가슴 통증", "category": "심혈관계"}], "message": "응급 상황일 수 있습니다. 즉시 119에 연락하세요."}

// AI 추론 (규칙 0건 → 런타임 Claude 추론, source=ai)
{"emergency": false, "source": "ai", "results": [{"department_id": 5, "department": "안과", "score": null, "matched_keywords": [], "ai_reason": "복시·초점 조절 장애는 눈의 질환 가능성", "confidence": 0.8}]}

// 폴백 (매칭 0건)
{"emergency": false, "results": [], "fallback": true, "message": "정확한 추천이 어렵습니다. 가까운 내과를 먼저 방문해 보세요."}
```

## 핵심 로직

1. **입력 정규화** — 공백 제거 + 동의어 치환 (부분일치 기반)
2. **응급 검사** — `EmergencyKeyword` 우선 대조, 감지 시 119 안내 + 가까운 응급의료기관(E-Gen) 거리순 안내로 강제 분기
3. **사전 매칭** — `SymptomKeyword`(5,253개, 기본+AI 전처리 검수분) 부분일치 → 진료과별 가중치 합산
4. **피드백 보정** — 사용자 추천 평가(👍/👎)로 누적된 `KeywordFeedback`를 진료과별로 가산 (±5로 클램프, 소수 표가 운영자 사전을 못 뒤집음)
5. **랭킹** — 상위 1~3개 진료과 + 매칭 키워드(근거) 반환 (구어체 토큰은 표시용 증상명 `label`로 노출)
6. **규칙+AI 하이브리드** (`recommend_with_ai`) — 규칙 매칭이 0건이거나 점수가 약할 때(`MIN_CONFIDENT_SCORE` 미만) 런타임 Claude가 진료과 **순위 top-3**를 추론해 보강(confidence-gated, 근거 문장 포함, 응급 의심 시 119 2차 분기). 강한 규칙 매칭은 즉시·무료·결정적으로 처리해 비용·지연 통제. AI까지 실패하면 내과 우선 안내 — 어떤 경우에도 빈 화면 없음
7. **병원 추천** — Haversine 거리 계산 → 영업중 우선·평점 보정 거리순 정렬(후기 베이즈 평균), 결과 없으면 반경 자동 확장 (3km → 최대 20km)

## 화면 흐름

```
홈 → 증상 입력 → [추천 로딩] → (일반) 진료과 추천 결과 / (응급) 응급 안내 → 가까운 응급실 거리순
진료과 카드 선택 → 병원 리스트+지도 → 병원 상세(미니맵·진료시간·후기) → 앱 내 길찾기 / 전화 / 위치 확인
(선택) 로그인 → 마이페이지: 건강 로그(검색 이력·추천 평가)·인사이트 요약
```

## 관리 (Django Admin)

키워드 사전·응급 키워드·병원 데이터는 Django Admin에서 직접 관리합니다.

```powershell
cd backend
python manage.py createsuperuser
# http://127.0.0.1:8000/admin/
```

## 향후 확장 (배포 — 미완)

정식 클라우드 배포는 미진행(포트폴리오용 후속 과제). 발표 기간엔 노트북 + 임시 터널로 운영했고, 영구 배포 시 고려사항:

- 프론트(정적 `dist/`) → Cloudflare Pages / Vercel (무료·영구 HTTPS 도메인, 카카오 콘솔에 1회 등록)
- 백엔드(Django) → Railway / Render / Fly 무료 티어 (정부 외부 API 호출 가능 호스트)
- DB → 영구 볼륨에 `db.sqlite3` 두거나 PostgreSQL 이전
- **제약**: ① `navigator.geolocation`은 HTTPS 필수 ② 카카오맵은 도메인 화이트리스트 등록 필수 ③ 프론트/백엔드 도메인이 갈리면 `CORS_ALLOWED_ORIGINS`에 프론트 도메인 추가
- 트러블슈팅(터널·HTTPS·Host 차단)은 `TROUBLESHOOTING.md` D절 참고
