# 배포 / 피드백 수집 가이드 (노트북 + Cloudflare Tunnel)

> 목적: 발표 전 2~3일간(화 6/23 → 금 6/26) 실사용자에게 주소를 공유해 피드백을
> 수집하고, 그 데이터를 금요일 발표 지표로 사용한다.
> 방식: 클라우드 정식 배포 대신 **노트북을 상시 켜두고 터널로 임시 공개**.
> (정식 클라우드 배포는 발표 후 포트폴리오용으로 별도 진행 예정 — 아래 "추후" 참고)

---

## 0. 왜 이 방식인가 (의사결정 기록)

- 로컬 `db.sqlite3`에 병원 554곳·진료시간·응급실 데이터가 **이미 적재 완료** → 클라우드에
  재적재하는 비용이 큼. 2일 수집엔 노트북+터널이 가장 빠름.
- 데이터는 같은 노트북 SQLite에 계속 누적되므로 영속성 문제 없음.
- 노트북 상시 ON 가능 → 터널 방식의 유일한 약점(가동 시간)이 해소됨.

### 결정적 제약 (왜 그냥 IP로 못 띄우나)
1. **HTTPS 필수** — `frontend/src/stores/location.js`가 `navigator.geolocation` 사용.
   모바일 브라우저는 HTTPS(보안 컨텍스트)에서만 위치 권한을 준다. → 터널이 HTTPS 제공.
2. **카카오맵 도메인 등록 필수** — `frontend/src/utils/kakaoLoader.js`의 지도 SDK는
   카카오 개발자 콘솔에 도메인을 화이트리스트로 등록해야 지도가 뜬다.
3. 프론트가 API를 `baseURL: '/api'` 상대경로로 호출하고 Vite가 Django(:8000)로 프록시 →
   **터널 하나(5173)만 열면 끝.** Django는 외부 노출 불필요, CORS 신경 쓸 필요 없음.

---

## 1. 사전 변경 (코드 — 이미 적용됨, 커밋 대상)

### `frontend/vite.config.js`
터널/외부 기기에서 접속하려면 dev 서버 호스트 설정이 필요하다.
```js
server: {
  host: true,            // 0.0.0.0 바인딩 — 터널/외부 기기 접속 허용
  allowedHosts: true,    // 터널 도메인(*.trycloudflare.com 등) Host 헤더 허용
  proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
}
```
> 이 설정이 없으면 터널 접속 시 `Blocked request. This host is not allowed.` 발생.

---

## 2. 실행 절차 (수집 시작)

### (1회) cloudflared 설치
```powershell
winget install --id Cloudflare.cloudflared
```

### 매번: 터미널 3개 띄우기
```powershell
# 터미널 1 — 백엔드 (내부, 노출 안 함)
cd backend
venv\Scripts\python manage.py runserver        # 127.0.0.1:8000

# 터미널 2 — 프론트 (host 0.0.0.0)
cd frontend
npm run dev                                     # 0.0.0.0:5173

# 터미널 3 — 터널
cloudflared tunnel --url http://localhost:5173
#  → https://xxxx-xxxx.trycloudflare.com 출력됨 (이게 공개 주소)
```

### 카카오 개발자 콘솔에 출력된 주소 등록
- 내 애플리케이션 → 플랫폼 → Web → **사이트 도메인**에
  `https://xxxx-xxxx.trycloudflare.com` 추가
- 등록한 주소를 테스터에게 공유 → 폰에서 접속하면 위치·지도·길찾기 전부 동작

> ⚠️ quick tunnel은 **재시작하면 URL이 바뀐다.** 수집 기간엔 터미널 3을 **끄지 말 것.**
> 끊겨 재시작하면 새 URL을 다시 카카오 콘솔에 등록 + 테스터에게 재공유해야 함.

---

## 3. 3일 무중단 운영 체크리스트

- [ ] **절전 비활성화** (덮개 닫아도 안 자게):
      `powercfg /change standby-timeout-ac 0`
      (필요 시 화면만 꺼지게: `powercfg /change monitor-timeout-ac 10`)
- [ ] Django / Vite / cloudflared **세 프로세스 계속 유지** (창 닫지 말기)
- [ ] **수집 기간 DB 초기화 금지** — `seed_data`·`import_*` 재실행 시 `db.sqlite3`가
      덮어써질 수 있음. 수집 중엔 절대 실행하지 말 것.
- [ ] **매일 1회 DB 백업**: `copy backend\db.sqlite3 backend\db.backup.YYYYMMDD.sqlite3`
- [ ] 발표 직전 최종 백업 후 지표 집계

---

## 4. ⚠️ 데이터 수집 전 반드시 확인 — 로그인 필요

지표가 되는 데이터를 만드는 엔드포인트는 **로그인 필수**다 (게스트는 검색만 되고 저장 안 됨):

| 지표 데이터 | 엔드포인트 | 위치 |
|---|---|---|
| 추천 평가 👍/👎 | `log_feedback` | `backend/api/auth_views.py:113` (`IsAuthenticated`) |
| 병원 후기·평점 | 후기 POST | `backend/api/views.py:266` (미로그인 401) |
| 검색 이력·인사이트 | `logs`, `me` | `IsAuthenticated` |

→ **테스터에게 "평가·후기를 남기려면 회원가입 후 사용"하도록 안내할 것.**
   (게스트도 전 기능 체험은 가능. 가입자 수 자체도 발표 지표가 됨.)

---

## 5. 발표 지표 집계 (금요일)

수집 종료 후 아래 한 줄이면 지표가 출력된다.
```powershell
cd backend
venv\Scripts\python manage.py metrics --since 2026-06-23

# 마크다운 파일로 저장하려면:
venv\Scripts\python manage.py metrics --since 2026-06-23 --md > ..\METRICS_RESULT.md
```

집계 항목 (`backend/api/management/commands/metrics.py`):
- 총 가입자 수 / 수집 기간 신규 가입
- 증상 검색 건수, **AI가 구제한 검색(규칙 0건→AI 추론) 건수·비율**, 추천 평가 수(👍/👎), **추천 만족도(👍 비율)**
- 최다 추천 진료과 Top N
- 병원 후기 수 / 평균 별점 / 후기 많은 병원 Top N
- 👍👎 누적 피드백 보정값(KeywordFeedback) 변동 Top N

---

## 6. 참고 산출물

| 파일 | 내용 |
|---|---|
| `backend/default_hours_hospitals.md` | 진료시간 기본값(09~18시) 처리된 병원 330곳 목록 |
| `backend/verify_hours_result.md` | 위 330곳 API 재검증 결과 (미신고 318 / 우연일치 12) |
| `backend/api/management/commands/metrics.py` | 발표 지표 집계 커맨드 |

### 영업시간 미신고 현황 (검증 완료)
- 전체 554곳 중 **진료시간 미신고 318곳(57.4%)** → 기본값 09~18시 적용
- 신고됨 236곳 (SCRUM 기재 수치와 일치 확인)
- 미신고는 입력 실수가 아니라 **심평원 API 자체에 데이터 없음** → "방문 전 전화 확인" 고지로 대응

---

## 7. 추후: 클라우드 정식 배포 (발표 후, 포트폴리오용)

노트북 의존 없는 영구 배포로 전환 시:
- 프론트(정적 `dist/`) → **Cloudflare Pages / Vercel** (무료·영구 HTTPS 도메인, 카카오에 1회 등록)
- 백엔드(Django) → **Railway / Render / Fly** 무료 티어 (외부 정부 API 호출 가능한 호스트)
- DB 영속성 → 영구 볼륨에 `db.sqlite3` 두거나 무료 PostgreSQL로 이전
- 주의: 프론트/백엔드가 다른 도메인이 되면 **CORS 설정**(`backend/config/settings.py`의
  `CORS_ALLOWED_ORIGINS`)에 프론트 도메인 추가 필요. (현재는 localhost만 허용)
