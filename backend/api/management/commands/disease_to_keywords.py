"""LLM 전처리: 질병정보(질병명+KCD코드) → 환자 구어체 증상표현 + 진료과 매핑 후보

import_disease로 받은 질병 목록(data/disease_codes.csv)을 입력으로, 각 질병에서
환자가 실제로 검색할 법한 구어체 증상 표현을 LLM으로 만들고 우리 16개 진료과 중
하나로 매핑한다. 출력은 generate_keywords와 동일한 검수용 CSV(keyword_candidates.csv)
포맷이라, 이후 흐름(사람 검수 → keywords_approved.csv → seed_data)을 그대로 재사용한다.

설계 의도
  - 실제 공공 질병 데이터를 원천으로 쓰되, LLM 생성물은 '그럴듯해도 틀릴 수 있어'
    자동 적재하지 않고 반드시 사람 검수를 거친다 (HITL).
  - 진료과는 반드시 DB의 16개 중 하나로 강제(목록 밖이면 폐기) → 추천 엔진과 정합.
  - 응급(생명위협) 증상은 제외 — 응급은 EmergencyKeyword 규칙이 별도로 먼저 처리.

사용법:
  python manage.py disease_to_keywords                       # disease_codes.csv 전체
  python manage.py disease_to_keywords --csv data/sample.csv # 다른 입력
  python manage.py disease_to_keywords --limit 20 --model claude-haiku-4-5
"""
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.models import Department, EmergencyKeyword, SymptomKeyword

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_IN = DATA_DIR / "disease_codes.csv"
DEFAULT_OUT = DATA_DIR / "keyword_candidates.csv"
DEFAULT_MODEL = "claude-haiku-4-5"  # 양 많은 전처리라 빠르고 싼 모델 기본
BATCH = 12  # 한 번에 보낼 질병 수 (응답 크기·정확도 균형)

SYSTEM = (
    "너는 한국 1차 의료 분류를 돕는 도우미다. 질병명(상병명)과 허용된 진료과 목록이 주어지면, "
    "그 질병을 가진 환자가 병원을 찾을 때 실제로 입력할 법한 한국어 구어체 증상 표현을 만든다. "
    "각 항목: (keyword: 매칭용 짧은 어간/구어체 표현, label: 화면용 표준 증상명, "
    "department: 반드시 아래 목록 중 하나, weight: 1~3, disease: 출처 질병명). "
    "weight 3=그 과 대표 증상, 2=일반, 1=약한 신호. "
    "규칙: ① department는 반드시 주어진 목록의 이름을 그대로 쓴다(새 이름 금지). "
    "② 생명을 위협하는 응급 증상(의식소실·심한 호흡곤란·가슴을 쥐어짜는 통증·대량출혈 등)은 만들지 마라. "
    "③ 질병명 자체가 아니라 '환자가 느끼는 증상' 위주로(예: 위염→'속쓰림','명치아파'). "
    "④ 너무 일반적이라 변별력 없는 표현은 피한다."
)


class Command(BaseCommand):
    help = "질병정보(질병명/코드)를 LLM으로 구어체 증상표현+진료과 후보로 전처리 (검수용 CSV)"

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(DEFAULT_IN), help="입력 질병 CSV (sick_nm 컬럼 필요)")
        parser.add_argument("--out", default=str(DEFAULT_OUT), help="출력 후보 CSV")
        parser.add_argument("--limit", type=int, default=0, help="처리할 질병 수 상한 (0=전체)")
        parser.add_argument("--per-disease", type=int, default=3, help="질병당 생성 목표 표현 수")
        parser.add_argument("--model", default=DEFAULT_MODEL, help=f"사용 모델 (기본 {DEFAULT_MODEL})")

    def handle(self, *args, **opts):
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise CommandError("ANTHROPIC_API_KEY가 없습니다. backend/.env에 키를 넣어 주세요.")
        try:
            import anthropic
            from pydantic import BaseModel
        except ImportError as e:
            raise CommandError(f"의존성 누락: {e}. 'pip install anthropic pydantic' 후 재실행.")

        in_path = Path(opts["csv"])
        if not in_path.exists():
            raise CommandError(
                f"입력 CSV가 없습니다: {in_path}\n먼저 'python manage.py import_disease'로 질병을 받아오세요."
            )

        diseases = []
        with in_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                nm = (row.get("sick_nm") or "").strip()
                cd = (row.get("sick_cd") or "").strip()
                if nm:
                    diseases.append((cd, nm))
        if not diseases:
            raise CommandError("입력에 질병명(sick_nm)이 없습니다.")
        if opts["limit"]:
            diseases = diseases[: opts["limit"]]

        dept_names = list(Department.objects.values_list("name", flat=True))
        dept_descs = {d.name: d.description for d in Department.objects.all()}
        dept_block = "\n".join(f"- {n}: {dept_descs.get(n) or ''}" for n in dept_names)
        valid_depts = set(dept_names)

        existing = set(SymptomKeyword.objects.values_list("keyword", flat=True))
        emergency = set(EmergencyKeyword.objects.values_list("keyword", flat=True))

        class KeywordItem(BaseModel):
            keyword: str
            label: str
            department: str
            weight: int
            disease: str

        class KeywordList(BaseModel):
            items: list[KeywordItem]

        client = anthropic.Anthropic(api_key=api_key, timeout=60.0)
        out_path = Path(opts["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        gen_raw = skip_dup = skip_dept = skip_emergency = total = 0
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["keyword", "department", "weight", "label", "approved"])

            for start in range(0, len(diseases), BATCH):
                chunk = diseases[start:start + BATCH]
                disease_lines = "\n".join(f"- {nm} (코드 {cd})" for cd, nm in chunk)
                prompt = (
                    f"허용 진료과 목록:\n{dept_block}\n\n"
                    f"다음 질병들 각각에 대해, 환자가 검색할 법한 구어체 증상 표현을 "
                    f"질병당 약 {opts['per_disease']}개씩 만들어라.\n질병:\n{disease_lines}"
                )
                self.stdout.write(f"[{start + 1}~{start + len(chunk)}/{len(diseases)}] 생성 중...")
                try:
                    resp = client.messages.parse(
                        model=opts["model"],
                        max_tokens=8000,
                        system=SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                        output_format=KeywordList,
                    )
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f"  배치 실패(건너뜀): {e}"))
                    continue

                for item in resp.parsed_output.items:
                    gen_raw += 1
                    kw = item.keyword.strip()
                    dept = item.department.strip()
                    if not kw or kw in existing:
                        skip_dup += 1
                        continue
                    if kw in emergency:
                        skip_emergency += 1
                        continue
                    if dept not in valid_depts:
                        skip_dept += 1
                        continue
                    existing.add(kw)
                    weight = max(1, min(3, item.weight))
                    writer.writerow([kw, dept, weight, item.label.strip(), ""])
                    total += 1

        kept = (total / gen_raw * 100) if gen_raw else 0.0
        self.stdout.write(self.style.SUCCESS(
            f"\n=== 전처리 퍼널 (질병 {len(diseases)}건 입력) ===\n"
            f"  LLM 생성(raw): {gen_raw}개\n"
            f"  자동 필터 탈락: 중복 {skip_dup} + 진료과오류 {skip_dept} + 응급겹침 {skip_emergency}\n"
            f"  검수 후보 기록: {total}개 (자동필터 통과율 {kept:.1f}%)\n"
            f"→ {out_path}\n"
            f"이제 사람이 검수해 좋은 행을 data/keywords_approved.csv 로 옮기고 'manage.py seed_data' 실행."
        ))
