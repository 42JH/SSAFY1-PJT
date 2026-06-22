from rest_framework import serializers

from .models import Department, Hospital, HospitalReview


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "description"]


class HospitalSerializer(serializers.ModelSerializer):
    departments = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="name"
    )
    open_time = serializers.TimeField(format="%H:%M")
    close_time = serializers.TimeField(format="%H:%M")
    sat_open_time = serializers.TimeField(format="%H:%M", allow_null=True)
    sat_close_time = serializers.TimeField(format="%H:%M", allow_null=True)
    sun_open_time = serializers.TimeField(format="%H:%M", allow_null=True)
    sun_close_time = serializers.TimeField(format="%H:%M", allow_null=True)

    class Meta:
        model = Hospital
        fields = [
            "id", "name", "address", "latitude", "longitude",
            "phone", "open_time", "close_time",
            "sat_open_time", "sat_close_time", "sun_open_time", "sun_close_time",
            "departments",
        ]


class RecommendRequestSerializer(serializers.Serializer):
    """증상 입력 검증 (최대 300자)"""

    symptom_text = serializers.CharField(max_length=300, trim_whitespace=True)


class HospitalReviewSerializer(serializers.ModelSerializer):
    """후기 조회용. nickname/department_name은 읽기 전용 파생 필드."""

    nickname = serializers.CharField(source="user.first_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = HospitalReview
        fields = [
            "id", "rating", "content", "helpful_count",
            "nickname", "department_name", "is_mine",
            "created_at", "updated_at",
        ]

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.user_id == request.user.id)


class HospitalReviewWriteSerializer(serializers.Serializer):
    """후기 작성/수정 입력 검증."""

    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(max_length=1000, allow_blank=True, required=False, default="")
    department_id = serializers.IntegerField(required=False, allow_null=True)
