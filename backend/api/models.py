from django.conf import settings
from django.db import models


class Department(models.Model):
    """표준 진료과. code는 심평원(HIRA) 진료과목코드(dgsbjtCd)와 1:1 매칭."""

    name = models.CharField("진료과명", max_length=50, unique=True)
    code = models.CharField(
        "HIRA 진료과목코드", max_length=2, unique=True, null=True, blank=True,
        help_text="건강보험심사평가원 진료과목코드(dgsbjtCd). 예: 01=내과, 13=이비인후과",
    )
    description = models.TextField("설명", blank=True)

    class Meta:
        verbose_name = "진료과"
        verbose_name_plural = "진료과"

    def __str__(self):
        return self.name


class Hospital(models.Model):
    """병원 정보. 위·경도로 거리 계산 및 지도 마커 표시."""

    ykiho = models.CharField(
        "암호화 요양기호", max_length=200, unique=True, null=True, blank=True,
        help_text="심평원 API 연동용 식별자. 상세정보(진료시간 등) 조회에 사용",
    )
    name = models.CharField("병원명", max_length=100)
    address = models.CharField("주소", max_length=200)
    latitude = models.FloatField("위도")
    longitude = models.FloatField("경도")
    phone = models.CharField("전화번호", max_length=20, blank=True)
    open_time = models.TimeField("평일 진료 시작")
    close_time = models.TimeField("평일 진료 종료")
    # 주말 진료시간 (심평원 상세정보 trmtSat*/trmtSun* — 없으면 해당 요일 휴진으로 간주)
    sat_open_time = models.TimeField("토요일 시작", null=True, blank=True)
    sat_close_time = models.TimeField("토요일 종료", null=True, blank=True)
    sun_open_time = models.TimeField("일요일 시작", null=True, blank=True)
    sun_close_time = models.TimeField("일요일 종료", null=True, blank=True)
    departments = models.ManyToManyField(
        Department, related_name="hospitals", verbose_name="진료과목"
    )

    class Meta:
        verbose_name = "병원"
        verbose_name_plural = "병원"

    def __str__(self):
        return self.name


class EmergencyCenter(models.Model):
    """응급의료기관 (국립중앙의료원 E-Gen). 응급 분기 시 거리순 안내에 사용.

    심평원 Hospital과 식별자 체계가 달라 매칭하지 않고 독립 저장한다.
    """

    hpid = models.CharField("기관코드", max_length=20, unique=True)
    name = models.CharField("기관명", max_length=100)
    address = models.CharField("주소", max_length=200, blank=True)
    latitude = models.FloatField("위도")
    longitude = models.FloatField("경도")
    phone = models.CharField("대표전화", max_length=20, blank=True)
    er_phone = models.CharField("응급실 전화", max_length=20, blank=True)
    # 권역응급의료센터 / 지역응급의료센터 / 지역응급의료기관 등 (dutyEmclsName)
    emcls_name = models.CharField("응급의료기관 분류", max_length=40, blank=True)

    class Meta:
        verbose_name = "응급의료기관"
        verbose_name_plural = "응급의료기관"

    def __str__(self):
        return self.name


class SymptomKeyword(models.Model):
    """증상 키워드 ↔ 진료과 매핑 사전. 추천 점수화의 핵심 데이터."""

    keyword = models.CharField("증상 키워드", max_length=50)
    # 화면(추천 근거)에 보여줄 표준 증상명. 비우면 keyword를 그대로 표시.
    # "배가아"·"허리가아" 같은 구어체·활용형 매칭 토큰을 깔끔한 이름("복통"·"허리통증")으로 노출.
    label = models.CharField("표시용 증상명", max_length=50, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="symptom_keywords",
        verbose_name="진료과",
    )
    weight = models.PositiveSmallIntegerField("가중치", default=1)

    @property
    def display_name(self) -> str:
        """추천 근거에 노출할 이름 — label이 있으면 label, 없으면 keyword."""
        return self.label or self.keyword

    class Meta:
        verbose_name = "증상 키워드"
        verbose_name_plural = "증상 키워드"
        unique_together = [("keyword", "department")]

    def __str__(self):
        return f"{self.keyword} → {self.department.name} (w={self.weight})"


class EmergencyKeyword(models.Model):
    """응급 강제 분기용 고위험 증상어 목록."""

    keyword = models.CharField("응급 키워드", max_length=50, unique=True)
    category = models.CharField("분류", max_length=30, blank=True)

    class Meta:
        verbose_name = "응급 키워드"
        verbose_name_plural = "응급 키워드"

    def __str__(self):
        return f"[{self.category}] {self.keyword}"


class HospitalReview(models.Model):
    """회원이 남기는 병원 후기·평점. 추천 정렬의 품질 가중치로 활용.

    별점은 거리 우선 정렬을 깨지 않는 '보정 계수'로만 반영한다(services.find_hospitals).
    표본 편향 방지를 위해 단순 평균이 아닌 베이즈 평균으로 집계한다.
    1인 1병원 1후기 — 재방문 시 기존 후기를 수정(upsert)한다.
    """

    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="병원",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hospital_reviews",
        verbose_name="회원",
    )
    # 어떤 진료과로 방문했는지 — 일반 만족도와 '이 과 진료가 좋았다'를 구분 수집
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        verbose_name="방문 진료과",
    )
    rating = models.PositiveSmallIntegerField("별점", default=5)  # 1~5
    content = models.TextField("후기", blank=True)
    helpful_count = models.PositiveIntegerField("도움돼요", default=0)
    created_at = models.DateTimeField("작성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "병원 후기"
        verbose_name_plural = "병원 후기"
        ordering = ["-created_at"]
        unique_together = [("hospital", "user")]  # 1인 1병원 1후기

    def __str__(self):
        return f"{self.hospital.name} ★{self.rating} - {self.user}"


class SymptomLog(models.Model):
    """회원의 증상 검색 이력 (로그인 구현 시 사용)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="symptom_logs",
        verbose_name="회원",
    )
    symptom_text = models.CharField("증상 입력", max_length=300)
    recommended_dept = models.CharField("추천 진료과", max_length=50)
    score = models.PositiveIntegerField("점수", default=0)
    # 추천 결과 평가: 1=도움됨(👍), -1=아님(👎), null=미평가. KeywordFeedback 학습의 입력원.
    feedback = models.SmallIntegerField("추천 평가", null=True, blank=True)
    searched_at = models.DateTimeField("검색 일시", auto_now_add=True)

    class Meta:
        verbose_name = "증상 검색 이력"
        verbose_name_plural = "증상 검색 이력"
        ordering = ["-searched_at"]

    def __str__(self):
        return f"{self.user} - {self.symptom_text[:20]}"


class KeywordFeedback(models.Model):
    """사용자 추천 평가(👍/👎)로 학습되는 (키워드→진료과) 보정 점수.

    운영자가 관리하는 SymptomKeyword.weight는 그대로 두고, 이 레이어를 추천 점수에
    덧씌운다(services.recommend_departments). score는 누적 순투표(👍 +1 / 👎 -1)이며,
    추천 시 진료과별 합산 후 ±FEEDBACK_CAP로 클램프되어 소수 표가 결과를 뒤집지 못한다.
    """

    keyword = models.CharField("정규화 키워드", max_length=50)
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="keyword_feedbacks",
        verbose_name="진료과",
    )
    score = models.IntegerField("누적 피드백 점수", default=0)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "추천 피드백 학습값"
        verbose_name_plural = "추천 피드백 학습값"
        unique_together = [("keyword", "department")]

    def __str__(self):
        return f"{self.keyword} → {self.department.name} ({self.score:+d})"
