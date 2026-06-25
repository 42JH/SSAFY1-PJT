"""검수 보조: keyword_candidates.csv에서 사람이 채택한 행을 keywords_approved.csv로 추출.

검수 흐름
  ① disease_to_keywords → data/keyword_candidates.csv (후보, approved 칸 비어있음)
  ② (사람 검수) 엑셀/시트로 열어 좋은 행의 'approved' 칸에 표시(y/1/o/yes/✓ 등)
  ③ 이 커맨드 → 표시된 행을 data/keywords_approved.csv 로 병합(기존+신규, 중복 제거)
  ④ manage.py seed_data → 사전에 적재

비용·시간이 빠듯할 때를 위한 일괄 채택 옵션도 제공한다(엑셀 표시 없이도 가능):
  --min-weight N   가중치 N 이상 행 자동 채택(예: 3=각 과 대표 증상만 빠르게)
  --dept 내과      특정 진료과만

사용법:
  python manage.py approve_keywords                 # approved 칸 표시분만 추출
  python manage.py approve_keywords --min-weight 3  # +가중치3 행 일괄 채택
  python manage.py approve_keywords --min-weight 3 --dept 안과
  python manage.py approve_keywords --dry-run       # 파일 안 쓰고 건수만 확인
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CAND_CSV = DATA_DIR / "keyword_candidates.csv"
APPROVED_CSV = DATA_DIR / "keywords_approved.csv"

# approved 칸에 이 중 하나가 있으면 '채택'으로 본다(엑셀 자동완성·체크 다양성 대응).
TRUTHY = {"y", "yes", "o", "ok", "1", "true", "t", "✓", "v", "채택", "승인"}

FIELDS = ["keyword", "department", "weight", "label"]


class Command(BaseCommand):
    help = "keyword_candidates.csv의 채택 행을 keywords_approved.csv로 병합(중복 제거)"

    def add_arguments(self, parser):
        parser.add_argument("--candidates", default=str(CAND_CSV), help="입력 후보 CSV")
        parser.add_argument("--out", default=str(APPROVED_CSV), help="출력 승인 CSV")
        parser.add_argument("--min-weight", type=int, default=0,
                            help="가중치 N 이상 행을 approved 표시 없이도 일괄 채택(0=미사용)")
        parser.add_argument("--dept", default="", help="특정 진료과만 채택")
        parser.add_argument("--dry-run", action="store_true", help="파일 안 쓰고 건수만 출력")

    def handle(self, *args, **opts):
        cand_path = Path(opts["candidates"])
        out_path = Path(opts["out"])
        if not cand_path.exists():
            raise CommandError(
                f"후보 CSV가 없습니다: {cand_path}\n먼저 'manage.py disease_to_keywords'를 실행하세요."
            )

        min_w = opts["min_weight"]
        dept_filter = opts["dept"].strip()

        # 기존 승인본 로드 → (keyword, department) 중복 키 집합
        existing = []
        seen = set()
        if out_path.exists():
            with out_path.open(encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    kw = (r.get("keyword") or "").strip()
                    dept = (r.get("department") or "").strip()
                    if not kw or not dept:
                        continue
                    key = (kw, dept)
                    if key in seen:
                        continue
                    seen.add(key)
                    existing.append({k: (r.get(k) or "").strip() for k in FIELDS})

        # 후보에서 채택 행 선별
        picked_marked = picked_bulk = skipped_dup = 0
        new_rows = []
        with cand_path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                kw = (r.get("keyword") or "").strip()
                dept = (r.get("department") or "").strip()
                if not kw or not dept:
                    continue
                if dept_filter and dept != dept_filter:
                    continue

                try:
                    w = max(1, min(3, int(r.get("weight") or 2)))
                except ValueError:
                    w = 2

                marked = (r.get("approved") or "").strip().lower() in TRUTHY
                bulk = min_w and w >= min_w
                if not (marked or bulk):
                    continue

                key = (kw, dept)
                if key in seen:
                    skipped_dup += 1
                    continue
                seen.add(key)
                new_rows.append({"keyword": kw, "department": dept, "weight": w,
                                 "label": (r.get("label") or "").strip()})
                if marked:
                    picked_marked += 1
                else:
                    picked_bulk += 1

        total = len(existing) + len(new_rows)
        self.stdout.write(
            f"기존 승인본: {len(existing)}건\n"
            f"신규 채택: {len(new_rows)}건 (approved표시 {picked_marked} + 일괄 {picked_bulk}), "
            f"중복 제외 {skipped_dup}\n"
            f"→ 병합 후 총 {total}건"
        )

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("dry-run — 파일을 쓰지 않았습니다."))
            return

        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(existing + new_rows)

        self.stdout.write(self.style.SUCCESS(
            f"{out_path} 저장({total}건). 이제 'manage.py seed_data'로 적재하세요."
        ))
