"""회원가입·로그인(JWT)·마이페이지 API

기존 Django User 모델 활용 (username=email, first_name=nickname).
핵심 흐름은 비로그인(게스트)으로 동작하고, 로그인 시 검색 이력이 저장된다.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SymptomLog


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
    """GET /api/auth/me/ → 프로필 + 최근 검색 이력 (건강 로그)"""
    logs = request.user.symptom_logs.all()[:30]
    return Response({
        "email": request.user.username,
        "nickname": request.user.first_name,
        "joined_at": request.user.date_joined.strftime("%Y-%m-%d"),
        "logs": [
            {
                "id": log.id,
                "symptom_text": log.symptom_text,
                "recommended_dept": log.recommended_dept,
                "score": log.score,
                "searched_at": log.searched_at.strftime("%Y-%m-%d %H:%M"),
            }
            for log in logs
        ],
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_log(request, pk):
    """DELETE /api/auth/logs/<id>/ → 내 검색 이력 삭제"""
    deleted, _ = SymptomLog.objects.filter(pk=pk, user=request.user).delete()
    if not deleted:
        return Response({"detail": "이력을 찾을 수 없습니다."}, status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)
