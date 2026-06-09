"""잇닥 핵심 로직: 진료과 추천 엔진 · 응급 분기 · 병원 거리 계산

처리 흐름 (요구사항 3-1)
① 입력 정규화: 공백 제거 + 동의어 치환 (형태소 분석 없이 부분일치 기반)
② 응급 검사: EmergencyKeyword 우선 대조 → 걸리면 119 안내로 강제 분기
③ 사전 매칭: SymptomKeyword 부분일치 → 매칭 키워드·진료과·가중치 수집
④ 점수 합산: 진료과별 가중치 합산 → 상위 1~3개 선정
⑤ 반환: 진료과·점수·매칭 키워드(추천 근거)를 함께 반환
⑥ 폴백: 매칭 0건이면 내과 우선 안내
"""
import math
import re
from collections import defaultdict
from datetime import datetime

from django.utils import timezone

from .models import EmergencyCenter, EmergencyKeyword, SymptomKeyword

# ── ① 입력 정규화 ──────────────────────────────────────────────

# 구어체·동의어 → 사전 표준어 치환 테이블
# 주의: 순차 str.replace 방식이라 치환 결과가 다른 항목의 입력이 될 수 있음.
# 항목 추가 시 (1) 기존 키워드의 부분 문자열인지, (2) 치환 결과가 사전 키워드를
# 포함하는지 확인할 것. (예: "어지러"→"어지럼증"은 "어지럼증" 입력 시
# "어지럼증증"이 되지만 부분일치라 여전히 매칭됨 — 의도된 허용)
SYNONYMS = {
    "배가": "복통",
    "배아": "복통",
    "속이": "속쓰림",
    "머리가": "두통",
    "대가리": "머리",
    "골이": "두통",
    "토할": "구토",
    "토했": "구토",
    "어지러": "어지럼증",
    "메스꺼": "메스꺼움",
    "콧물나": "콧물",
    "기침나": "기침",
    "열나": "발열",
    "열이나": "발열",
    "간지러": "가려움",
    "간지럽": "가려움",
}


def normalize(text: str) -> str:
    """공백 제거 → 동의어 치환. '가슴 통증'과 '가슴통증'을 동일하게 매칭.

    공백을 먼저 제거해야 '열이 나고'(띄어쓰기) 같은 입력에도
    동의어('열이나'→'발열')가 적용된다.
    """
    text = re.sub(r"\s+", "", text.strip().lower())
    for src, dst in SYNONYMS.items():
        text = text.replace(src, dst)
    return text


# ── ② 응급 검사 ────────────────────────────────────────────────

def check_emergency(symptom_text: str):
    """응급 키워드가 하나라도 감지되면 매칭 목록 반환, 없으면 None."""
    norm = normalize(symptom_text)
    matched = []
    for ek in EmergencyKeyword.objects.all():
        if normalize(ek.keyword) in norm:
            matched.append({"keyword": ek.keyword, "category": ek.category})
    return matched or None


# ── ③④⑤⑥ 진료과 추천 ─────────────────────────────────────────

def recommend_departments(symptom_text: str, top_n: int = 3):
    """키워드 사전 매칭 → 진료과별 가중치 점수화 → 1~N순위 랭킹.

    반환: [{department_id, department, score, matched_keywords}, ...] (점수 내림차순)
    """
    norm = normalize(symptom_text)

    dept_scores = defaultdict(int)
    dept_keywords = defaultdict(list)
    dept_names = {}

    for sk in SymptomKeyword.objects.select_related("department"):
        if normalize(sk.keyword) in norm:
            dept_scores[sk.department_id] += sk.weight
            dept_keywords[sk.department_id].append(sk.keyword)
            dept_names[sk.department_id] = sk.department.name

    ranked = sorted(dept_scores.items(), key=lambda kv: (-kv[1], dept_names[kv[0]]))

    return [
        {
            "department_id": dept_id,
            "department": dept_names[dept_id],
            "score": score,
            "matched_keywords": dept_keywords[dept_id],
        }
        for dept_id, score in ranked[:top_n]
    ]


# ── 병원 추천: Haversine 거리 · 영업상태 · 반경 확장 ──────────────

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이 거리(km)를 Haversine 공식으로 계산."""
    rlat1, rlng1, rlat2, rlng2 = map(math.radians, (lat1, lng1, lat2, lng2))
    dlat = rlat2 - rlat1
    dlng = rlng2 - rlng1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def is_open_now(hospital, now: datetime = None) -> bool:
    """현재 시각·요일 기준 진료 중인지 판단 (자정 넘김 영업도 처리).

    평일: open_time~close_time / 토·일: 전용 필드 (없으면 휴진).
    USE_TZ=True이므로 서버가 UTC여도 KST 기준이 되도록 localtime 사용.
    """
    now_dt = now or timezone.localtime()
    weekday = now_dt.weekday()  # 0=월 ... 5=토, 6=일

    if weekday == 5:
        open_t, close_t = hospital.sat_open_time, hospital.sat_close_time
    elif weekday == 6:
        open_t, close_t = hospital.sun_open_time, hospital.sun_close_time
    else:
        open_t, close_t = hospital.open_time, hospital.close_time

    if open_t is None or close_t is None:
        return False  # 해당 요일 휴진

    now_t = now_dt.time()
    if open_t <= close_t:
        return open_t <= now_t <= close_t
    return now_t >= open_t or now_t <= close_t


def find_hospitals(queryset, user_lat: float, user_lng: float,
                   radius_km: float = 3.0, max_radius_km: float = 20.0,
                   limit: int = 20, open_only: bool = False):
    """거리 계산 → (영업중 필터) → 반경 필터(결과 없으면 자동 확장) → 정렬.

    반환: (병원 dict 리스트, 최종 적용 반경 km, 반경이 확장되었는지 여부)
    """
    candidates = []
    for h in queryset.prefetch_related("departments"):
        dist = haversine_km(user_lat, user_lng, h.latitude, h.longitude)
        open_now = is_open_now(h)  # 요일·시각 판정은 후보당 1회만 계산
        if open_only and not open_now:
            continue
        candidates.append((h, dist, open_now))

    applied_radius = radius_km
    within = [c for c in candidates if c[1] <= applied_radius]
    expanded = False
    # ⑥ 반경 내 결과가 없으면 반경을 자동 확장해 빈 화면 방지
    # (×2와 +1 중 큰 쪽으로 늘려 radius가 0에 가까워도 루프가 반드시 전진)
    while not within and applied_radius < max_radius_km:
        applied_radius = min(max(applied_radius * 2, applied_radius + 1), max_radius_km)
        expanded = True
        within = [c for c in candidates if c[1] <= applied_radius]

    # 영업중 우선 → 거리 가까운 순
    within.sort(key=lambda c: (not c[2], c[1]))

    results = []
    for h, dist, open_now in within[:limit]:
        reasons = []
        if dist <= 1.0:
            reasons.append("가까움")
        if open_now:
            reasons.append("영업중")
        results.append({
            "id": h.id,
            "name": h.name,
            "address": h.address,
            "latitude": h.latitude,
            "longitude": h.longitude,
            "phone": h.phone,
            "open_time": h.open_time.strftime("%H:%M"),
            "close_time": h.close_time.strftime("%H:%M"),
            "departments": [d.name for d in h.departments.all()],
            "distance_km": round(dist, 2),
            "is_open": open_now,
            "reasons": reasons,
        })
    return results, applied_radius, expanded


# ── 응급의료기관: 거리순 안내 ──────────────────────────────────

def find_emergency_centers(user_lat: float, user_lng: float, limit: int = 10):
    """가까운 응급의료기관을 거리순으로 반환 (응급실은 24시간이라 영업 필터 없음)."""
    scored = []
    for c in EmergencyCenter.objects.all():
        dist = haversine_km(user_lat, user_lng, c.latitude, c.longitude)
        scored.append((c, dist))
    scored.sort(key=lambda cd: cd[1])

    return [
        {
            "id": c.id,
            "name": c.name,
            "address": c.address,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "phone": c.phone,
            "er_phone": c.er_phone,
            "type": c.emcls_name,
            "distance_km": round(dist, 2),
        }
        for c, dist in scored[:limit]
    ]
