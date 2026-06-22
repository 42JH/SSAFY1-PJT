import json
import math
import urllib.parse
import urllib.request

from django.conf import settings
from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Department, Hospital, HospitalReview, SymptomLog
from .serializers import (
    DepartmentSerializer,
    HospitalReviewSerializer,
    HospitalReviewWriteSerializer,
    HospitalSerializer,
    RecommendRequestSerializer,
)
from .services import (
    bayesian_rating,
    check_emergency,
    find_emergency_centers,
    find_hospitals,
    recommend_departments,
)


def _global_mean_rating(default: float = 0.0) -> float:
    """전체 병원 후기 평균(베이즈 사전 평균 m). 후기가 하나도 없으면 default."""
    return HospitalReview.objects.aggregate(m=Avg("rating"))["m"] or default

FALLBACK_MESSAGE = "정확한 추천이 어렵습니다. 가까운 내과를 먼저 방문해 보세요."


@api_view(["POST"])
def recommend(request):
    """증상 텍스트 → 응급 분기 또는 진료과 1~3순위 추천 (근거 포함).

    POST /api/recommend/  body: {"symptom_text": "..."}
    """
    serializer = RecommendRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    symptom_text = serializer.validated_data["symptom_text"]

    # ② 응급 검사: 하나라도 걸리면 추천을 건너뛰고 119 안내로 강제 분기
    emergency_matches = check_emergency(symptom_text)
    if emergency_matches:
        return Response({
            "emergency": True,
            "matched_keywords": emergency_matches,
            "message": "응급 상황일 수 있습니다. 즉시 119에 연락하세요.",
        })

    # ③~⑤ 사전 매칭 → 점수 합산 → 랭킹
    results = recommend_departments(symptom_text)

    # F09 건강 로그: 로그인 사용자의 검색 이력 저장 (게스트는 저장 안 함)
    if request.user.is_authenticated:
        SymptomLog.objects.create(
            user=request.user,
            symptom_text=symptom_text,
            recommended_dept=results[0]["department"] if results else "(매칭 없음)",
            score=results[0]["score"] if results else 0,
        )

    # ⑥ 폴백: 매칭 0건
    if not results:
        return Response({
            "emergency": False,
            "results": [],
            "fallback": True,
            "message": FALLBACK_MESSAGE,
        })

    return Response({
        "emergency": False,
        "results": results,
        "fallback": False,
    })


@api_view(["GET"])
def department_list(request):
    """GET /api/departments/ — 전체 진료과 목록"""
    departments = Department.objects.all().order_by("name")
    return Response(DepartmentSerializer(departments, many=True).data)


@api_view(["GET"])
def hospital_list(request):
    """위치·진료과 기반 병원 추천.

    GET /api/hospitals/?lat=&lng=&department_id=&radius=
    lat/lng 없으면 거리 계산 없이 전체 목록 반환.
    """
    # 후기 평균·개수를 미리 집계해 정렬 시 N+1 쿼리 없이 평점 보정에 사용
    queryset = Hospital.objects.annotate(
        review_avg=Avg("reviews__rating"),
        review_count=Count("reviews"),
    )

    department_id = request.query_params.get("department_id")
    if department_id:
        queryset = queryset.filter(departments__id=department_id).distinct()

    lat = request.query_params.get("lat")
    lng = request.query_params.get("lng")

    if lat is None or lng is None:
        return Response({
            "hospitals": HospitalSerializer(queryset, many=True).data,
            "radius_km": None,
            "expanded": False,
        })

    try:
        user_lat, user_lng = float(lat), float(lng)
        radius = float(request.query_params.get("radius", 3.0))
    except ValueError:
        return Response(
            {"detail": "lat/lng/radius는 숫자여야 합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # nan/inf는 float() 파싱을 통과하므로 별도 검증 (비교 연산이 모두 False가 되어 빈 결과 유발)
    if not all(math.isfinite(v) for v in (user_lat, user_lng, radius)):
        return Response(
            {"detail": "lat/lng/radius는 유한한 숫자여야 합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # radius=0·음수는 반경 확장 루프가 진행되지 않으므로 안전 범위로 클램프
    radius = min(max(radius, 0.1), 20.0)

    open_only = request.query_params.get("open_only") in ("1", "true")
    hospitals, applied_radius, expanded = find_hospitals(
        queryset, user_lat, user_lng, radius_km=radius, open_only=open_only,
        global_mean=_global_mean_rating(),
    )
    return Response({
        "hospitals": hospitals,
        "radius_km": applied_radius,
        "expanded": expanded,
        "open_only": open_only,
    })


@api_view(["GET"])
def directions(request):
    """카카오모빌리티 자동차 길찾기 프록시 (REST 키 보호를 위해 백엔드 경유).

    GET /api/directions/?origin_lat=&origin_lng=&dest_lat=&dest_lng=
    반환: {path: [[lat,lng],...], distance_m, duration_s}
    """
    try:
        o_lat = float(request.query_params["origin_lat"])
        o_lng = float(request.query_params["origin_lng"])
        d_lat = float(request.query_params["dest_lat"])
        d_lng = float(request.query_params["dest_lng"])
        if not all(math.isfinite(v) for v in (o_lat, o_lng, d_lat, d_lng)):
            raise ValueError
    except (KeyError, ValueError):
        return Response(
            {"detail": "origin/dest 좌표(lat,lng)가 필요합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = urllib.parse.urlencode({
        "origin": f"{o_lng},{o_lat}",        # 카카오모빌리티는 'lng,lat' 순서
        "destination": f"{d_lng},{d_lat}",
        "priority": "RECOMMEND",
    })
    req = urllib.request.Request(
        f"https://apis-navi.kakaomobility.com/v1/directions?{qs}",
        headers={"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return Response(
            {"detail": "길찾기 API 호출에 실패했습니다."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    routes = data.get("routes") or []
    if not routes or routes[0].get("result_code") != 0:
        msg = routes[0].get("result_msg") if routes else "경로 없음"
        return Response({"detail": f"경로를 찾을 수 없습니다. ({msg})"},
                        status=status.HTTP_404_NOT_FOUND)

    route = routes[0]
    path = []
    for section in route.get("sections", []):
        for road in section.get("roads", []):
            v = road.get("vertexes", [])
            # vertexes는 [lng, lat, lng, lat, ...] 평탄 배열
            for i in range(0, len(v) - 1, 2):
                path.append([v[i + 1], v[i]])

    return Response({
        "path": path,
        "distance_m": route["summary"]["distance"],
        "duration_s": route["summary"]["duration"],
    })


@api_view(["GET"])
def emergency_center_list(request):
    """위치 기반 가까운 응급의료기관 목록.

    GET /api/emergency-centers/?lat=&lng=
    """
    lat = request.query_params.get("lat")
    lng = request.query_params.get("lng")
    try:
        user_lat, user_lng = float(lat), float(lng)
        if not all(math.isfinite(v) for v in (user_lat, user_lng)):
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {"detail": "lat/lng(유한한 숫자)가 필요합니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"centers": find_emergency_centers(user_lat, user_lng)})


@api_view(["GET"])
def hospital_detail(request, pk):
    """GET /api/hospitals/<id>/ — 병원 상세 (미니맵 좌표 + 후기 평점 요약 포함)"""
    try:
        hospital = Hospital.objects.prefetch_related("departments").get(pk=pk)
    except Hospital.DoesNotExist:
        return Response({"detail": "병원을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    agg = hospital.reviews.aggregate(avg=Avg("rating"), cnt=Count("id"))
    count = agg["cnt"] or 0
    data = HospitalSerializer(hospital).data
    data["rating"] = round(agg["avg"], 1) if count else None
    data["bayes_rating"] = (
        round(bayesian_rating(agg["avg"] or 0, count, _global_mean_rating()), 1)
        if count else None
    )
    data["review_count"] = count
    return Response(data)


@api_view(["GET", "POST"])
def hospital_reviews(request, pk):
    """GET  /api/hospitals/<id>/reviews/  — 후기 목록 (최신순)
    POST /api/hospitals/<id>/reviews/  — 후기 작성/수정 (로그인 필수, 1인 1병원 1후기)
    """
    try:
        hospital = Hospital.objects.get(pk=pk)
    except Hospital.DoesNotExist:
        return Response({"detail": "병원을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        reviews = hospital.reviews.select_related("user", "department")
        return Response(
            HospitalReviewSerializer(reviews, many=True, context={"request": request}).data
        )

    # POST — 로그인 필수
    if not request.user.is_authenticated:
        return Response({"detail": "로그인이 필요합니다."}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = HospitalReviewWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    vd = serializer.validated_data

    department = None
    dept_id = vd.get("department_id")
    if dept_id:
        department = Department.objects.filter(pk=dept_id).first()

    # 1인 1병원 1후기 — 이미 있으면 수정(upsert)
    review, created = HospitalReview.objects.update_or_create(
        hospital=hospital,
        user=request.user,
        defaults={
            "rating": vd["rating"],
            "content": vd.get("content", ""),
            "department": department,
        },
    )
    return Response(
        HospitalReviewSerializer(review, context={"request": request}).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_review(request, pk):
    """DELETE /api/reviews/<id>/ — 내 후기 삭제"""
    deleted, _ = HospitalReview.objects.filter(pk=pk, user=request.user).delete()
    if not deleted:
        return Response({"detail": "후기를 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
