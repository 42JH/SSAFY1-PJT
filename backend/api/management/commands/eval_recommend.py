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

from api.services import classify_symptom_with_ai, recommend_departments

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
        ai_eligible = ai_hit = 0
        misses = []  # (text, expected, got_top3, via)

        for text, expected in cases:
            results = recommend_departments(text)
            if results:
                covered += 1
                names = [r["department"] for r in results]
                is_top1 = names[0] == expected
                is_top3 = expected in names[:3]
                if is_top1:
                    top1 += 1
                if is_top3:
                    top3 += 1
                else:
                    misses.append((text, expected, names[:3], "규칙"))
            else:
                # 규칙 0건 → 폴백. --with-ai면 AI 추론으로 구제 가능한지 평가
                if opts["with_ai"]:
                    ai_eligible += 1
                    ai = classify_symptom_with_ai(text)
                    got = (ai or {}).get("department")
                    if ai and got == expected:
                        ai_hit += 1
                        top1 += 1
                        top3 += 1
                    else:
                        label = "AI:응급분기" if (ai or {}).get("is_emergency") else f"AI:{got or '실패'}"
                        misses.append((text, expected, [label], "AI"))
                else:
                    misses.append((text, expected, ["(폴백)"], "규칙0건"))

        pct = lambda n: f"{n / total * 100:.1f}%"
        md = opts["md"]
        out = self.stdout.write
        H = (lambda t: f"\n## {t}\n") if md else (lambda t: f"\n=== {t} ===")

        out(f"# 추천 정확도 평가 ({total}케이스)\n" if md
            else f"\n########## 추천 정확도 평가 ({total}케이스) ##########")
        out(H("종합 적중률 (규칙 + AI 폴백)" if opts["with_ai"] else "규칙 엔진 적중률"))
        rows = [
            ("Top-1 적중", f"{top1}/{total}", pct(top1)),
            ("Top-3 적중", f"{top3}/{total}", pct(top3)),
            ("규칙 커버리지(폴백 아님)", f"{covered}/{total}", pct(covered)),
        ]
        if opts["with_ai"]:
            ai_rate = f"{ai_hit}/{ai_eligible} ({ai_hit / ai_eligible * 100:.1f}%)" if ai_eligible else "—"
            rows.append(("AI 구제 적중(규칙 0건 중)", ai_rate, ""))
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
