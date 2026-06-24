"""증상 키워드 사전 구성 분석 — AI 데이터 전처리 증거를 정량화.

사용법:
  python manage.py keyword_stats              # 콘솔 출력
  python manage.py keyword_stats --md         # 마크다운 (발표 자료용)

보여주는 것
  - 사전 규모와 출처 구성: 기본 사전(keyword_dictionary.py) vs LLM 생성→검수 채택분
  - 진료과별 / 가중치별 분포
  - 전처리 파이프라인 단계 (생성 → 자동 필터 → 사람 검수 → 적재)

출처 판별: keywords_approved.csv(LLM 생성 후 사람이 검수·채택한 키워드)에 있는
keyword는 'LLM 채택', 나머지는 '기본 사전'으로 집계한다.
"""
import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from api.models import SymptomKeyword

APPROVED_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "keywords_approved.csv"


class Command(BaseCommand):
    help = "증상 키워드 사전의 구성·출처를 분석해 전처리 증거로 출력"

    def add_arguments(self, parser):
        parser.add_argument("--md", action="store_true", help="마크다운 형식으로 출력")

    def handle(self, *args, **opts):
        md = opts["md"]
        out = self.stdout.write
        H = (lambda t: f"\n## {t}\n") if md else (lambda t: f"\n=== {t} ===")

        # LLM 생성 후 검수 채택된 키워드 집합 로드
        approved = set()
        if APPROVED_CSV.exists():
            with APPROVED_CSV.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    kw = (row.get("keyword") or "").strip()
                    if kw:
                        approved.add(kw)

        all_kw = list(SymptomKeyword.objects.select_related("department"))
        total = len(all_kw)
        llm_kw = [k for k in all_kw if k.keyword in approved]
        base_kw = [k for k in all_kw if k.keyword not in approved]
        llm_n, base_n = len(llm_kw), len(base_kw)
        llm_pct = (llm_n / total * 100) if total else 0.0

        out(f"# 증상 키워드 사전 구성 분석\n" if md
            else "\n########## 증상 키워드 사전 구성 분석 ##########")

        out(H("규모·출처 구성"))
        lines = [
            f"전체 키워드: {total}개",
            f"기본 사전(수기 구축): {base_n}개",
            f"LLM 생성 → 사람 검수 채택: {llm_n}개 ({llm_pct:.1f}%)",
        ]
        for ln in lines:
            out(f"- {ln}" if md else f"  {ln}")

        out(H("전처리 파이프라인 (생성 → 자동 필터 → 검수 → 적재)"))
        steps = [
            "① 생성: Claude로 진료과별 증상 표현 후보 생성 (generate_keywords)",
            "② 자동 필터: 기존 사전 중복 제거 · 응급 키워드 겹침 제외 · 가중치 1~3 클램프",
            "③ 사람 검수(HITL): 진료과 매핑·가중치·응급 혼입 확인 후 채택분만 keywords_approved.csv 로",
            "④ 적재: seed_data가 기본 사전과 채택분을 함께 DB에 반영",
        ]
        for s in steps:
            out(f"- {s}" if md else f"  {s}")

        # 진료과별 분포 (LLM 기여 강조)
        out(H("진료과별 분포 (전체 / LLM 채택분)"))
        by_dept = Counter(k.department.name for k in all_kw)
        llm_by_dept = Counter(k.department.name for k in llm_kw)
        rows = sorted(by_dept.items(), key=lambda kv: -kv[1])
        if md:
            out("| 진료과 | 전체 | LLM 채택 |")
            out("|---|---|---|")
            for name, n in rows:
                out(f"| {name} | {n} | {llm_by_dept.get(name, 0)} |")
        else:
            for name, n in rows:
                out(f"  {name}: {n} (LLM {llm_by_dept.get(name, 0)})")

        # 가중치 분포
        out(H("가중치 분포 (3=대표증상 / 2=일반 / 1=약한신호)"))
        by_w = Counter(k.weight for k in all_kw)
        for w in (3, 2, 1):
            n = by_w.get(w, 0)
            p = (n / total * 100) if total else 0.0
            out(f"- weight {w}: {n}개 ({p:.1f}%)" if md else f"  weight {w}: {n}개 ({p:.1f}%)")

        out("" if md else "\n########## 끝 ##########")
