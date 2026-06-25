"""추천 정확도 평가: 라벨링된 증상셋으로 규칙 엔진(+AI 폴백)의 Top-1/Top-3 적중률 측정.

사용법:
  python manage.py eval_recommend                 # 규칙 엔진만 평가 (무료·결정적)
  python manage.py eval_recommend --with-ai       # 규칙 0건 케이스를 AI 폴백으로 추가 평가
  python manage.py eval_recommend --md            # 마크다운 출력 (발표 자료용)
  python manage.py eval_recommend --csv other.csv # 다른 평가셋 사용

평가셋: api/data/eval_symptoms.csv (컬럼: symptom_text, expected_department)
  - 흔한 표현(규칙이 잡아야 함) + 까다로운 중첩 케이스를 섞어 현실적 적중률을 측정한다.

지표
  - 규칙 Top-1/Top-3: 규칙 엔진이 정답 진료과를 1순위/3순위 안에 넣었는지
  - 규칙 커버리지: 규칙이 후보를 1개라도 낸 비율(폴백이 아닌 비율)
  - (--with-ai) AI 구제 적중: 규칙 0건 케이스에서 AI 폴백이 정답을 맞춘 비율
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.services import recommend_departments, recommend_with_ai

DEFAULT_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "eval_symptoms.csv"


class Command(BaseCommand):
    help = "라벨링된 증상셋으로 추천 Top-1/Top-3 적중률을 측정"

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(DEFAULT_CSV), help="평가셋 CSV 경로")
        parser.add_argument("--with-ai", action="store_true", help="규칙 0건 케이스를 AI 폴백으로 추가 평가")
        parser.add_argument("--md", action="store_true", help="마크다운 형식으로 출력")
        parser.add_argument("--show-miss", action="store_true", help="틀린 케이스 상세 출력")

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv"])
        if not csv_path.exists():
            raise CommandError(f"평가셋을 찾을 수 없습니다: {csv_path}")

        cases = []
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                text = (row.get("symptom_text") or "").strip()
                expected = (row.get("expected_department") or "").strip()
                if text and expected:
                    cases.append((text, expected))
        if not cases:
            raise CommandError("평가셋이 비어 있습니다.")

        total = len(cases)
        top1 = top3 = covered = 0
        rule_handled = ai_handled = 0
        misses = []  # (text, expected, got_top3, via)

        for text, expected in cases:
            # --with-ai: 배포 하이브리드(recommend_with_ai) = 규칙 우선 + 약하면 AI 위임(top-3)
            # 미지정: 규칙 엔진만(recommend_departments)
            if opts["with_ai"]:
                results, source = recommend_with_ai(text)
                if source == "rule":
                    rule_handled += 1
                else:
                    ai_handled += 1  # ai / ai_emergency / fallback
            else:
                results = recommend_departments(text)
                source = "규칙" if results else "규칙0건"
                if results:
                    covered += 1

            names = [r["department"] for r in results]
            if names and names[0] == expected:
                top1 += 1
            if expected in names[:3]:
                top3 += 1
            else:
                via = ("AI" if source not in ("rule", "규칙") else "규칙")
                misses.append((text, expected, names[:3] or ["(폴백)"], via))

        pct = lambda n: f"{n / total * 100:.1f}%"
        md = opts["md"]
        out = self.stdout.write
        H = (lambda t: f"\n## {t}\n") if md else (lambda t: f"\n=== {t} ===")

        out(f"# 추천 정확도 평가 ({total}케이스)\n" if md
            else f"\n########## 추천 정확도 평가 ({total}케이스) ##########")
        out(H("종합 적중률 (규칙 + AI 하이브리드)" if opts["with_ai"] else "규칙 엔진 적중률"))
        rows = [
            ("Top-1 적중", f"{top1}/{total}", pct(top1)),
            ("Top-3 적중(1~3순위)", f"{top3}/{total}", pct(top3)),
        ]
        if opts["with_ai"]:
            rows.append(("처리 분담(규칙/AI)", f"{rule_handled} / {ai_handled}", f"AI {ai_handled / total * 100:.1f}%"))
        else:
            rows.append(("규칙 커버리지(폴백 아님)", f"{covered}/{total}", pct(covered)))
        if md:
            out("| 지표 | 건수 | 비율 |")
            out("|---|---|---|")
            for name, cnt, p in rows:
                out(f"| {name} | {cnt} | {p} |")
        else:
            for name, cnt, p in rows:
                out(f"  {name}: {cnt}  {p}")

        if opts["show_miss"] and misses:
            out(H(f"오답 {len(misses)}건"))
            for text, expected, got, via in misses:
                line = f"[{via}] '{text}' → 정답 {expected}, 결과 {got}"
                out(f"- {line}" if md else f"  {line}")

        out("" if md else "\n########## 끝 ##########")
