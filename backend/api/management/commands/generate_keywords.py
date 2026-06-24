"""증상 키워드 후보 LLM 생성 (검수용 CSV 출력)

워크플로
  1) python manage.py generate_keywords           # 진료과별 후보 생성 → data/keyword_candidates.csv
  2) 사람이 CSV를 열어 검수 → 좋은 행만 data/keywords_approved.csv 로 옮김 (틀린 매핑·가중치 수정)
  3) python manage.py seed_data                    # 승인 CSV가 사전에 함께 적재됨

설계 의도
  - LLM이 만든 증상→진료과 매핑은 "그럴듯하지만 틀릴 수 있다". 그래서 자동 적재가 아니라
    반드시 사람 검수를 거치는 후보 생성기로만 동작한다 (생성 → 검수 → seed).
  - 응급 증상(EmergencyKeyword)·기존 키워드는 프롬프트에서 제외해 중복/충돌을 줄인다.
  - 모델 기본값은 claude-opus-4-8. 비용을 줄이려면 --model claude-sonnet-4-6 등으로 바꾼다.
"""
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.models import Department, EmergencyKeyword, SymptomKeyword

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_OUT = OUT_DIR / "keyword_candidates.csv"
DEFAULT_MODEL = "claude-opus-4-8"

SYSTEM = (
    "너는 한국 1차 의료 분류를 돕는 도우미다. 주어진 진료과로 환자가 직접 내원하게 만드는 "
    "증상 표현을, 한국어 구어체·오타·활용형까지 포함해 만들어낸다. "
    "각 항목은 (keyword: 매칭용 짧은 어간/표현, label: 화면에 보일 표준 증상명, weight: 1~3) 형식. "
    "weight는 3=그 과의 대표 증상, 2=일반 증상, 1=여러 과에 걸치는 약한 신호. "
    "생명을 위협하는 응급 증상(가슴통증·호흡곤란·의식소실·심한 출혈 등)은 절대 포함하지 마라. "
    "다른 진료과가 명백히 더 적절한 증상도 넣지 마라."
)


class Command(BaseCommand):
    help = "진료과별 증상 키워드 후보를 LLM으로 생성해 검수용 CSV로 출력"

    def add_arguments(self, parser):
        parser.add_argument("--department", help="특정 진료과명만 생성 (기본: 전체)")
        parser.add_argument("--count", type=int, default=25, help="진료과당 생성 개수 목표 (기본 25)")
        parser.add_argument("--model", default=DEFAULT_MODEL, help=f"사용 모델 (기본 {DEFAULT_MODEL})")
        parser.add_argument("--out", default=str(DEFAULT_OUT), help="출력 CSV 경로")

    def handle(self, *args, **options):
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise CommandError("ANTHROPIC_API_KEY가 없습니다. backend/.env에 키를 넣어 주세요.")
        try:
            import anthropic
            from pydantic import BaseModel
        except ImportError as e:
            raise CommandError(f"의존성 누락: {e}. 'pip install anthropic' 후 다시 실행하세요.")

        class KeywordItem(BaseModel):
            keyword: str
            label: str
            weight: int

        class KeywordList(BaseModel):
            items: list[KeywordItem]

        client = anthropic.Anthropic(api_key=api_key)

        depts = Department.objects.all()
        if options["department"]:
            depts = depts.filter(name=options["department"])
            if not depts.exists():
                raise CommandError(f"진료과 '{options['department']}'를 찾을 수 없습니다.")

        # 중복 회피용: 이미 있는 키워드 + 응급 키워드
        existing = set(SymptomKeyword.objects.values_list("keyword", flat=True))
        emergency = set(EmergencyKeyword.objects.values_list("keyword", flat=True))

        out_path = Path(options["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 전처리 퍼널 집계: LLM 생성 → 자동 필터(중복·응급 제외) → 기록.
        # 사람 검수(생성 → 검수 → seed) 앞단의 '자동 정제' 단계를 정량화한다.
        gen_raw = 0       # LLM이 생성한 원시 항목 수
        skip_dup = 0      # 기존 사전/같은 실행 중복으로 탈락
        skip_emergency = 0  # 응급 키워드와 겹쳐 탈락
        total = 0         # 검수 후보로 기록된 수
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["keyword", "department", "weight", "label", "approved"])

            for dept in depts:
                self.stdout.write(f"[{dept.name}] 생성 중...")
                dept_existing = sorted(
                    SymptomKeyword.objects.filter(department=dept)
                    .values_list("keyword", flat=True)
                )
                prompt = (
                    f"진료과: {dept.name}\n"
                    f"설명: {dept.description or '(없음)'}\n"
                    f"이미 사전에 있는 키워드(중복 금지): {', '.join(dept_existing) or '(없음)'}\n\n"
                    f"위 진료과로 내원하게 만드는 새로운 증상 표현 {options['count']}개를 만들어라. "
                    f"기존 키워드와 겹치지 않게."
                )
                try:
                    resp = client.messages.parse(
                        model=options["model"],
                        max_tokens=8000,
                        system=SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                        output_format=KeywordList,
                    )
                except Exception as e:  # 한 과 실패해도 나머지는 계속
                    self.stderr.write(self.style.WARNING(f"  실패: {e}"))
                    continue

                for item in resp.parsed_output.items:
                    kw = item.keyword.strip()
                    gen_raw += 1
                    if not kw or kw in existing:
                        skip_dup += 1
                        continue
                    if kw in emergency:
                        skip_emergency += 1
                        continue
                    existing.add(kw)  # 같은 실행 내 중복도 방지
                    weight = max(1, min(3, item.weight))
                    writer.writerow([kw, dept.name, weight, item.label.strip(), ""])
                    total += 1

        # 전처리 퍼널 요약 (생성 → 자동 필터 → 검수 후보)
        kept_rate = (total / gen_raw * 100) if gen_raw else 0.0
        self.stdout.write(self.style.SUCCESS(
            f"\n=== 전처리 퍼널 ===\n"
            f"  LLM 생성(raw): {gen_raw}개\n"
            f"  자동 필터 탈락: 중복 {skip_dup} + 응급겹침 {skip_emergency} = {skip_dup + skip_emergency}개\n"
            f"  검수 후보 기록: {total}개 (자동필터 통과율 {kept_rate:.1f}%)\n"
            f"→ {out_path}\n"
            f"이제 사람이 검수해 좋은 행을 data/keywords_approved.csv 로 옮기고 'manage.py seed_data' 실행."
        ))
