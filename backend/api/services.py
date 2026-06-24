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

from .models import (
    Department,
    EmergencyCenter,
    EmergencyKeyword,
    KeywordFeedback,
    SymptomKeyword,
)

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
    # "간지러/간지럽 → 가려움"은 전역 치환이라 "코가 간지러"·"목이 간지러"까지
    # 피부과(가려움)로 끌고 가, 부위가 붙은 이비인후과 키워드(코가간지·목간지)를 가렸다.
    # 그래서 동의어는 빼고, 일반 가려움 활용형은 피부과 키워드("간지러","간지럽")로 직접 매칭한다.
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

# 진료과별 누적 사용자 피드백이 추천 점수에 주는 영향 상한(±). 소수 표가 운영자
# 사전(SymptomKeyword.weight)을 뒤집지 못하도록 클램프해 추천을 둔감하게 유지한다.
FEEDBACK_CAP = 5


def recommend_departments(symptom_text: str, top_n: int = 3):
    """키워드 사전 매칭 → 진료과별 가중치 점수화 → 사용자 피드백 보정 → 1~N순위 랭킹.

    반환: [{department_id, department, score, matched_keywords}, ...] (점수 내림차순)
    """
    norm = normalize(symptom_text)

    dept_scores = defaultdict(int)
    dept_keywords = defaultdict(list)
    dept_names = {}
    matched_norm = set()

    for sk in SymptomKeyword.objects.select_related("department"):
        kw_norm = normalize(sk.keyword)
        if kw_norm in norm:
            dept_scores[sk.department_id] += sk.weight
            # 근거에는 구어체 토큰("배가아")이 아니라 표준 증상명("복통")을 노출, 중복 제거
            display = sk.label or sk.keyword
            if display not in dept_keywords[sk.department_id]:
                dept_keywords[sk.department_id].append(display)
            dept_names[sk.department_id] = sk.department.name
            matched_norm.add(kw_norm)

    # 사용자 추천 평가(👍/👎) 피드백 보정(ML 학습 아님): 매칭 키워드의 피드백을 진료과별로
    # 합산해 ±FEEDBACK_CAP로 클램프 후 가산. 👍/👎는 기존 후보 과의 순위만 조정한다.
    if matched_norm and dept_scores:
        fb_by_dept = defaultdict(int)
        for fb in KeywordFeedback.objects.filter(keyword__in=matched_norm):
            fb_by_dept[fb.department_id] += fb.score
        for dept_id in list(dept_scores):
            adj = max(-FEEDBACK_CAP, min(FEEDBACK_CAP, fb_by_dept.get(dept_id, 0)))
            dept_scores[dept_id] = max(0, dept_scores[dept_id] + adj)

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


def apply_recommendation_feedback(symptom_text: str, dept_name: str, delta: int) -> None:
    """추천 평가(👍/👎)를 (매칭 키워드 → 진료과) 보정 점수에 반영.

    delta: 적용할 변화량(신규 👍=+1, 👍→👎=-2, 👎 취소=+1 …). 해당 증상에서 그 진료과에
    매칭됐던 키워드 각각의 KeywordFeedback.score를 delta만큼 가감한다.
    """
    if not delta:
        return
    dept = Department.objects.filter(name=dept_name).first()
    if dept is None:
        return  # 폴백("(매칭 없음)" 등)이거나 삭제된 진료과 → 보정 대상 아님

    norm = normalize(symptom_text)
    for sk in SymptomKeyword.objects.filter(department=dept):
        kw_norm = normalize(sk.keyword)
        if kw_norm in norm:
            fb, _ = KeywordFeedback.objects.get_or_create(keyword=kw_norm, department=dept)
            fb.score += delta
            fb.save(update_fields=["score", "updated_at"])


# ── AI 폴백: 규칙 사전이 못 잡는 증상을 LLM이 진료과로 직접 추론 ──
#
# recommend_departments(규칙)가 0건일 때만 호출된다. 사전에 잡히는 일반 케이스는 LLM을
# 거치지 않아 비용·지연을 통제한다. 응급은 호출 전 check_emergency로 1차 필터되며, LLM이
# 응급을 의심하면 is_emergency=True로 2차 안전망을 제공한다. 키 부재·네트워크 오류·무효
# 응답은 모두 None을 반환해, 호출부가 기존 내과 폴백으로 안전하게 착지하도록 한다.

def classify_symptom_with_ai(symptom_text: str, model: str = None):
    """규칙 매칭 실패 시 Claude로 진료과를 추론. 실패하면 None(=호출부 기존 폴백).

    반환:
      - {"is_emergency": True}                         응급 의심 → 호출부가 119 분기
      - {"is_emergency": False, "department_id", "department", "reason", "confidence"}
      - None                                            키 없음·오류·환각(목록 밖 진료과)
    """
    from django.conf import settings

    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return None
    try:
        import anthropic
        from pydantic import BaseModel
    except ImportError:
        return None

    departments = list(Department.objects.all())
    if not departments:
        return None
    dept_by_name = {d.name: d for d in departments}
    dept_lines = "\n".join(
        f"- {d.name}: {d.description or '(설명 없음)'}" for d in departments
    )

    class AIClassification(BaseModel):
        department: str   # 반드시 아래 목록에 있는 진료과명
        reason: str       # 환자가 이해할 한국어 한 문장 근거
        is_emergency: bool
        confidence: float  # 0~1

    system = (
        "너는 한국 1차 의료 진료과 안내 도우미다. 환자의 증상 설명을 읽고 주어진 진료과 "
        "목록 중 가장 적합한 단 하나를 고른다. 반드시 목록에 있는 진료과명을 그대로 써라"
        "(새 이름을 만들지 마라). 생명을 위협하는 응급 징후(의식소실·심한 호흡곤란·가슴을 "
        "쥐어짜는 통증·대량 출혈·갑작스러운 마비 등)가 의심되면 is_emergency=true로 표시하라. "
        "reason은 왜 그 진료과인지 환자가 이해할 한국어 한 문장으로 적어라."
    )
    prompt = (
        f"증상 설명: {symptom_text}\n\n"
        f"진료과 목록:\n{dept_lines}\n\n"
        "위 목록에서 가장 적합한 진료과 하나를 선택하라."
    )
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=8.0)
        resp = client.messages.parse(
            model=model or settings.RECOMMEND_AI_MODEL,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=AIClassification,
        )
    except Exception:
        return None  # 네트워크·타임아웃·인증 등 모든 런타임 오류 → 안전 폴백

    out = resp.parsed_output
    if out.is_emergency:
        return {"is_emergency": True}
    dept = dept_by_name.get(out.department.strip())
    if dept is None:
        return None  # 목록 밖 진료과(환각) → 폐기
    return {
        "is_emergency": False,
        "department_id": dept.id,
        "department": dept.name,
        "reason": out.reason.strip(),
        "confidence": round(max(0.0, min(1.0, out.confidence)), 2),
    }


# ── 병원 추천: Haversine 거리 · 영업상태 · 반경 확장 · 평점 보정 ──

EARTH_RADIUS_KM = 6371.0

# 후기 평점이 추천 순위에 미치는 영향. 거리 우선 구조를 유지하기 위해 작게 둔다.
# effective_distance = dist * (1 - RATING_ALPHA * quality)  (quality∈[0,1])
# 0.15이면 만점(★5) 병원이 실제 거리보다 최대 15% 가깝게 평가됨.
RATING_ALPHA = 0.15
# 베이즈 평균의 사전 표본 수(C). 후기가 이 수에 못 미치면 전체 평균 쪽으로 끌어당겨
# '리뷰 1개 ★5'가 '리뷰 200개 ★4.3'을 이기는 표본 편향을 막는다.
RATING_PRIOR_COUNT = 5
RATING_HIGH_THRESHOLD = 4.0  # 이 이상이면 추천 근거에 '평점높음' 표시


def bayesian_rating(avg: float, count: int, global_mean: float,
                    prior: int = RATING_PRIOR_COUNT) -> float:
    """베이즈 평균: (C*m + n*avg) / (C + n). 후기 적은 병원의 평점을 보수적으로 추정.

    avg/count: 해당 병원의 단순 평균·후기 수, global_mean(m): 전체 병원 평균 평점.
    후기가 없으면(count=0) 전체 평균을 반환한다.
    """
    if count <= 0:
        return global_mean
    return (prior * global_mean + count * avg) / (prior + count)


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
                   limit: int = 20, open_only: bool = False,
                   global_mean: float = 0.0):
    """거리 계산 → (영업중 필터) → 반경 필터(결과 없으면 자동 확장) → 정렬.

    정렬은 영업중 우선 → '평점 보정 거리'(가까운 순). 평점이 높을수록 실제 거리보다
    가깝게 평가되지만(RATING_ALPHA), 후기 없는 병원도 base 거리로 그대로 노출된다.
    평점 집계를 쓰려면 queryset에 review_avg/review_count를 annotate하고 global_mean을
    함께 전달한다(없으면 보정 계수는 1로 동작).

    반환: (병원 dict 리스트, 최종 적용 반경 km, 반경이 확장되었는지 여부)
    """
    candidates = []
    for h in queryset.prefetch_related("departments"):
        dist = haversine_km(user_lat, user_lng, h.latitude, h.longitude)
        open_now = is_open_now(h)  # 요일·시각 판정은 후보당 1회만 계산
        if open_only and not open_now:
            continue
        # annotate 안 된 queryset에서도 안전하도록 getattr 기본값 사용
        review_count = getattr(h, "review_count", 0) or 0
        review_avg = getattr(h, "review_avg", None) or 0.0
        rating = bayesian_rating(review_avg, review_count, global_mean)
        # 평점 1~5 → 품질 0~1로 정규화 후 거리 보정 (후기 0건이면 quality 0 취급)
        quality = (rating - 1) / 4 if review_count else 0.0
        eff_dist = dist * (1 - RATING_ALPHA * quality)
        candidates.append((h, dist, open_now, rating, review_count, eff_dist))

    applied_radius = radius_km
    within = [c for c in candidates if c[1] <= applied_radius]
    expanded = False
    # ⑥ 반경 내 결과가 없으면 반경을 자동 확장해 빈 화면 방지
    # (×2와 +1 중 큰 쪽으로 늘려 radius가 0에 가까워도 루프가 반드시 전진)
    while not within and applied_radius < max_radius_km:
        applied_radius = min(max(applied_radius * 2, applied_radius + 1), max_radius_km)
        expanded = True
        within = [c for c in candidates if c[1] <= applied_radius]

    # 영업중 우선 → 평점 보정 거리(가까운 순). 반경 필터는 실제 거리(c[1]) 기준 유지.
    within.sort(key=lambda c: (not c[2], c[5]))

    results = []
    for h, dist, open_now, rating, review_count, _eff in within[:limit]:
        reasons = []
        if dist <= 1.0:
            reasons.append("가까움")
        if open_now:
            reasons.append("영업중")
        if review_count and rating >= RATING_HIGH_THRESHOLD:
            reasons.append("평점높음")
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
            "rating": round(rating, 1) if review_count else None,
            "review_count": review_count,
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
