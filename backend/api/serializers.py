from rest_framework import serializers

from .models import Department, Hospital


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
