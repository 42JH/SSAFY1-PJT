from django.contrib import admin

from .models import Department, EmergencyKeyword, Hospital, SymptomKeyword, SymptomLog

# 관리 페이지 타이틀
admin.site.site_header = "잇닥 (ITdoc) 관리"
admin.site.site_title = "잇닥 관리"
admin.site.index_title = "데이터 관리 — 키워드 사전·응급 키워드·병원"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "keyword_count", "hospital_count", "description")
    ordering = ("code",)
    search_fields = ("name",)

    @admin.display(description="키워드 수")
    def keyword_count(self, obj):
        return obj.symptom_keywords.count()

    @admin.display(description="병원 수")
    def hospital_count(self, obj):
        return obj.hospitals.count()


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "address", "phone", "weekday_hours", "sat_hours", "sun_hours")
    search_fields = ("name", "address")
    list_filter = ("departments",)
    filter_horizontal = ("departments",)
    list_per_page = 50

    @admin.display(description="평일")
    def weekday_hours(self, obj):
        return f"{obj.open_time:%H:%M}~{obj.close_time:%H:%M}"

    @admin.display(description="토요일")
    def sat_hours(self, obj):
        if obj.sat_open_time and obj.sat_close_time:
            return f"{obj.sat_open_time:%H:%M}~{obj.sat_close_time:%H:%M}"
        return "휴진"

    @admin.display(description="일요일")
    def sun_hours(self, obj):
        if obj.sun_open_time and obj.sun_close_time:
            return f"{obj.sun_open_time:%H:%M}~{obj.sun_close_time:%H:%M}"
        return "휴진"


@admin.register(SymptomKeyword)
class SymptomKeywordAdmin(admin.ModelAdmin):
    """추천 품질 운영의 핵심 — 가중치를 목록에서 바로 수정 가능"""

    list_display = ("id", "keyword", "department", "weight")
    list_editable = ("weight",)
    list_filter = ("department", "weight")
    search_fields = ("keyword",)
    list_per_page = 100
    ordering = ("department__code", "-weight")


@admin.register(EmergencyKeyword)
class EmergencyKeywordAdmin(admin.ModelAdmin):
    list_display = ("id", "keyword", "category")
    list_filter = ("category",)
    search_fields = ("keyword",)


@admin.register(SymptomLog)
class SymptomLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "symptom_text", "recommended_dept", "score", "searched_at")
    list_filter = ("recommended_dept",)
    date_hierarchy = "searched_at"
    readonly_fields = ("user", "symptom_text", "recommended_dept", "score", "searched_at")
