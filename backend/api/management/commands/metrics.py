"""피드백 수집 기간(노트북+터널 배포) 동안 쌓인 데이터를 발표용 지표로 집계.

사용법:
  python manage.py metrics
  python manage.py metrics --since 2026-06-23   # 특정일 이후만 집계
  python manage.py metrics --md > ../METRICS_RESULT.md   # 마크다운으로 저장

집계 항목:
  - 가입자 수 (수집 기간 신규 가입 포함)
  - 증상 검색 건수 / 추천 평가(👍/👎) 수와 만족도 비율
  - 병원 후기 수 / 평균 별점
  - 최다 추천 진료과 Top N
  - 피드백 보정값(KeywordFeedback) 변동 상위 (👍👎 누적 — 규칙 기반 보정, ML 학습 아님)
"""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.utils import timezone

from api.models import HospitalReview, KeywordFeedback, SymptomLog

User = get_user_model()


class Command(BaseCommand):
    help = "수집 기간 동안 쌓인 사용자 데이터를 발표용 지표로 집계"

    def add_arguments(self, parser):
        parser.add_argument("--since", help="이 날짜(YYYY-MM-DD) 이후 데이터만 집계")
        parser.add_argument("--top", type=int, default=5, help="Top N 개수 (기본 5)")
        parser.add_argument("--md", action="store_true", help="마크다운 형식으로 출력")

    def handle(self, *args, **opts):
        since = None
        if opts["since"]:
            naive = datetime.strptime(opts["since"], "%Y-%m-%d")
            since = timezone.make_aware(naive)

        top = opts["top"]

        # --- 사용자 ---
        users = User.objects.all()
        user_total = users.count()
        user_new = users.filter(date_joined__gte=since).count() if since else None

        # --- 증상 검색 / 추천 평가 ---
        logs = SymptomLog.objects.all()
        if since:
            logs = logs.filter(searched_at__gte=since)
        search_total = logs.count()
        # 추천 출처: 규칙 사전 매칭 vs 규칙 0건 시 AI 진료과 추론 폴백이 구제한 검색
        ai_rescued = logs.filter(source="ai").count()
        ai_rescue_rate = (ai_rescued / search_total * 100) if search_total else 0.0
        rated = logs.exclude(feedback__isnull=True)
        rated_total = rated.count()
        up = rated.filter(feedback=1).count()
        down = rated.filter(feedback=-1).count()
        satisfaction = (up / rated_total * 100) if rated_total else 0.0

        # 최다 추천 진료과 Top N
        top_depts = (
            logs.values("recommended_dept")
            .annotate(n=Count("id"))
            .order_by("-n")[:top]
        )

        # --- 후기 / 평점 ---
        reviews = HospitalReview.objects.all()
        if since:
            reviews = reviews.filter(created_at__gte=since)
        review_total = reviews.count()
        avg_rating = reviews.aggregate(a=Avg("rating"))["a"] or 0.0
        top_reviewed = (
            reviews.values("hospital__name")
            .annotate(n=Count("id"), avg=Avg("rating"))
            .order_by("-n")[:top]
        )

        # --- 피드백 보정값 (전 기간 누적 — 기간 필터 무의미) ---
        learned = (
            KeywordFeedback.objects.exclude(score=0)
            .order_by("-score")[:top]
        )

        # ---------- 출력 ----------
        md = opts["md"]
        H = (lambda t: f"\n## {t}\n") if md else (lambda t: f"\n=== {t} ===")
        out = self.stdout.write

        title = "발표용 지표 집계"
        if since:
            title += f" (기준: {opts['since']} 이후)"
        out(f"# {title}\n" if md else f"\n########## {title} ##########")

        out(H("사용자"))
        out(f"- 총 가입자: **{user_total}명**" if md else f"총 가입자: {user_total}명")
        if user_new is not None:
            out(f"- 수집 기간 신규 가입: **{user_new}명**" if md else f"수집 기간 신규 가입: {user_new}명")

        out(H("증상 검색 / 추천 평가"))
        out(f"- 증상 검색 건수: **{search_total}건**" if md else f"증상 검색 건수: {search_total}건")
        out(f"- AI가 구제한 검색(규칙 0건→AI 추론): **{ai_rescued}건** ({ai_rescue_rate:.1f}%)" if md
            else f"AI가 구제한 검색(규칙 0건→AI 추론): {ai_rescued}건 ({ai_rescue_rate:.1f}%)")
        out(f"- 추천 평가 수: **{rated_total}건** (👍 {up} / 👎 {down})" if md
            else f"추천 평가 수: {rated_total}건 (👍 {up} / 👎 {down})")
        out(f"- 추천 만족도(👍 비율): **{satisfaction:.1f}%**" if md
            else f"추천 만족도(👍 비율): {satisfaction:.1f}%")

        out(H(f"최다 추천 진료과 Top {top}"))
        if top_depts:
            for i, d in enumerate(top_depts, 1):
                line = f"{i}. {d['recommended_dept']} — {d['n']}건"
                out(f"- {line}" if md else f"  {line}")
        else:
            out("- (데이터 없음)" if md else "  (데이터 없음)")

        out(H("병원 후기 / 평점"))
        out(f"- 후기 수: **{review_total}건**" if md else f"후기 수: {review_total}건")
        out(f"- 평균 별점: **{avg_rating:.2f} / 5**" if md else f"평균 별점: {avg_rating:.2f} / 5")
        if top_reviewed:
            out(f"\n후기 많은 병원 Top {top}:" if not md else f"\n후기 많은 병원 Top {top}:")
            for i, r in enumerate(top_reviewed, 1):
                line = f"{i}. {r['hospital__name']} — {r['n']}건 (평균 ★{r['avg']:.1f})"
                out(f"- {line}" if md else f"  {line}")

        out(H(f"추천 피드백 보정값 변동 Top {top} (👍👎 누적 반영)"))
        if learned:
            for i, k in enumerate(learned, 1):
                line = f"{k.keyword} → {k.department.name} ({k.score:+d})"
                out(f"- {line}" if md else f"  {line}")
        else:
            out("- (아직 피드백 보정값 없음)" if md else "  (아직 피드백 보정값 없음)")

        out("" if md else "\n########## 끝 ##########")
