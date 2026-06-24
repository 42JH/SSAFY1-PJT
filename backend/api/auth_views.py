"""회원가입·로그인(JWT)·마이페이지 API

기존 Django User 모델 활용 (username=email, first_name=nickname).
핵심 흐름은 비로그인(게스트)으로 동작하고, 로그인 시 검색 이력이 저장된다.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SymptomLog
from .services import apply_recommendation_feedback


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128)
    nickname = serializers.CharField(max_length=30)

    def validate_email(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {"email": user.username, "nickname": user.first_name},
    }


@api_view(["POST"])
def signup(request):
    """POST /api/auth/signup/  {email, password, nickname} → 가입 + 즉시 로그인"""
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    user = User.objects.create_user(
        username=data["email"], email=data["email"],
        password=data["password"], first_name=data["nickname"],
    )
    return Response(issue_tokens(user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def login(request):
    """POST /api/auth/login/  {email, password} → JWT 발급"""
    email = request.data.get("email", "")
    password = request.data.get("password", "")
    user = authenticate(username=email, password=password)
    if user is None:
        return Response(
            {"detail": "이메일 또는 비밀번호가 올바르지 않습니다."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response(issue_tokens(user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/auth/me/ → 프로필 + 건강 로그 인사이트 요약 + 최근 검색 이력"""
    all_logs = request.user.symptom_logs.all()
    total = all_logs.count()

    # 인사이트: 가장 많이 추천받은 진료과, 이번 달 검색 수
    top = (
        all_logs.exclude(recommended_dept="(매칭 없음)")
        .values("recommended_dept")
        .annotate(c=Count("id"))
        .order_by("-c")
        .first()
    )
    month_start = timezone.localtime().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    this_month = all_logs.filter(searched_at__gte=month_start).count()

    logs = all_logs[:30]
    return Response({
        "email": request.user.username,
        "nickname": request.user.first_name,
        "joined_at": request.user.date_joined.strftime("%Y-%m-%d"),
        "stats": {
            "total": total,
            "this_month": this_month,
            "top_dept": top["recommended_dept"] if top else None,
            "top_dept_count": top["c"] if top else 0,
        },
        "logs": [
            {
                "id": log.id,
                "symptom_text": log.symptom_text,
                "recommended_dept": log.recommended_dept,
                "score": log.score,
                "feedback": log.feedback,
                "searched_at": log.searched_at.strftime("%Y-%m-%d %H:%M"),
            }
            for log in logs
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def log_feedback(request, pk):
    """POST /api/auth/logs/<id>/feedback/  {value: 1|-1|0}

    추천 결과 평가(👍=1 / 👎=-1 / 0=평가 취소). 직전 평가와의 차이만큼 키워드 피드백 보정값에
    반영하므로 같은 로그를 여러 번 눌러도 중복 가산되지 않는다.
    """
    try:
        value = int(request.data.get("value"))
    except (TypeError, ValueError):
        return Response({"detail": "value는 1, -1, 0 중 하나여야 합니다."},
                        status=status.HTTP_400_BAD_REQUEST)
    if value not in (1, -1, 0):
        return Response({"detail": "value는 1, -1, 0 중 하나여야 합니다."},
                        status=status.HTTP_400_BAD_REQUEST)

    log = SymptomLog.objects.filter(pk=pk, user=request.user).first()
    if log is None:
        return Response({"detail": "이력을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)

    old = log.feedback or 0
    delta = value - old  # 이전 평가 대비 순변화만 보정값에 반영
    apply_recommendation_feedback(log.symptom_text, log.recommended_dept, delta)

    log.feedback = value or None
    log.save(update_fields=["feedback"])
    return Response({"id": log.id, "feedback": log.feedback})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_log(request, pk):
    """DELETE /api/auth/logs/<id>/ → 내 검색 이력 삭제"""
    deleted, _ = SymptomLog.objects.filter(pk=pk, user=request.user).delete()
    if not deleted:
        return Response({"detail": "이력을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
