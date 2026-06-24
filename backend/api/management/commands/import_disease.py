"""심평원(HIRA) 질병정보서비스 API → 질병명·KCD코드 적재 (전처리 원천 데이터)

이 API는 '증상'이 아니라 '질병명 + 상병코드(KCD)'를 제공한다. 받아온 질병 목록은
그 자체로는 증상 추천에 못 쓰므로, 다음 단계(disease_to_keywords)에서 LLM으로
'질병 → 환자 구어체 증상표현 + 진료과'로 전처리한 뒤 사람 검수를 거쳐 사전에 반영한다.

  ① import_disease         # 질병명/코드 수집 → data/disease_codes.csv (이 커맨드)
  ② disease_to_keywords    # LLM 전처리: 질병 → 증상표현+진료과 후보 (검수용 CSV)
  ③ (사람 검수) → keywords_approved.csv
  ④ seed_data              # 사전에 적재

사용법:
  python manage.py import_disease                 # 전체 수집 (.env의 HIRA_DISEASE_SERVICE_KEY)
  python manage.py import_disease --key <인증키>
  python manage.py import_disease --max-rows 500  # 상한 지정

참고: data.go.kr 게이트웨이는 기본 Python UA를 차단 → 브라우저 UA 필수.
      서버 장애 시 resultCode=99(커넥션 풀 오류)를 반환 → 지수 백오프 재시도.
"""
import csv
import json
import time as time_mod
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BASE_URL = "https://apis.data.go.kr/B551182/diseaseInfoService1/getDissNameCodeList1"
NUM_OF_ROWS = 100
TIMEOUT = 40
MAX_RETRY = 5
OUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "disease_codes.csv"

# 응답 필드명을 모르는 채로 적재해도 깨지지 않도록, 코드/이름 컬럼을 휴리스틱으로 탐지한다.
CODE_HINTS = ("sickcd", "code", "cd")
NAME_HINTS = ("sicknm", "name", "nm")


class Command(BaseCommand):
    help = "HIRA 질병정보서비스에서 질병명·KCD코드를 받아 data/disease_codes.csv로 저장"

    def add_arguments(self, parser):
        parser.add_argument("--key", help="공공데이터포털 일반 인증키 (또는 .env의 HIRA_DISEASE_SERVICE_KEY)")
        parser.add_argument("--max-rows", type=int, default=0, help="수집 상한 (0=전체)")
        parser.add_argument("--out", default=str(OUT_PATH), help="출력 CSV 경로")

    def fetch(self, key, page, rows):
        """한 페이지를 JSON으로 받는다. resultCode 99(서버 장애)는 재시도 대상."""
        qs = urllib.parse.urlencode({
            "serviceKey": key, "pageNo": page, "numOfRows": rows, "_type": "json",
        })
        req = urllib.request.Request(f"{BASE_URL}?{qs}", headers={"User-Agent": "Mozilla/5.0"})
        last = None
        for attempt in range(1, MAX_RETRY + 1):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    raw = resp.read().decode("utf-8")
                if raw.lstrip().startswith("<"):  # 인증 실패 등은 평문/XML로 옴
                    raise CommandError(f"JSON이 아닌 응답: {raw[:200]}")
                data = json.loads(raw)
                header = data.get("response", {}).get("header", {})
                code = str(header.get("resultCode"))
                if code == "99":  # 서버 커넥션 풀 장애 → 재시도
                    last = header.get("resultMsg")
                    raise RuntimeError(f"resultCode 99: {last}")
                if code not in ("0", "00"):
                    raise CommandError(f"API 오류 resultCode={code}: {header.get('resultMsg')}")
                return data.get("response", {}).get("body", {}) or {}
            except CommandError:
                raise
            except Exception as e:
                last = e
                if attempt == MAX_RETRY:
                    raise CommandError(
                        f"API 호출 {MAX_RETRY}회 실패: {e}\n"
                        f"resultCode 99면 HIRA 질병정보 서버 장애이니 잠시 후 다시 실행하세요."
                    )
                wait = 2 ** attempt
                self.stdout.write(f"    재시도 {attempt}/{MAX_RETRY} ({e}) — {wait}s 대기")
                time_mod.sleep(wait)

    @staticmethod
    def _items(body):
        """body.items.item을 항상 리스트로 반환 (0건/1건/N건 모두 대응)."""
        items = (body.get("items") or {})
        if isinstance(items, str):  # 빈 응답이 ""로 오는 경우
            return []
        item = items.get("item") if isinstance(items, dict) else items
        if item is None:
            return []
        return item if isinstance(item, list) else [item]

    @staticmethod
    def _detect(field_keys, hints):
        for k in field_keys:
            kl = k.lower()
            if any(h in kl for h in hints):
                return k
        return None

    def handle(self, *args, **opts):
        key = opts["key"] or settings.HIRA_DISEASE_SERVICE_KEY
        if not key:
            raise CommandError("인증키가 없습니다. --key 또는 .env의 HIRA_DISEASE_SERVICE_KEY를 지정하세요.")

        max_rows = opts["max_rows"]
        out_path = Path(opts["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 1페이지로 총건수·필드 구조 파악
        first = self.fetch(key, 1, NUM_OF_ROWS)
        total = int(first.get("totalCount") or 0)
        items = self._items(first)
        if not items:
            raise CommandError("질병 데이터가 비어 있습니다 (서버 장애 또는 권한 문제).")

        keys = list(items[0].keys())
        code_key = self._detect(keys, CODE_HINTS)
        name_key = self._detect(keys, NAME_HINTS)
        self.stdout.write(f"응답 필드: {keys}")
        self.stdout.write(f"감지된 코드 컬럼: {code_key} / 이름 컬럼: {name_key}")
        if not name_key:
            self.stderr.write(self.style.WARNING(
                "질병명 컬럼을 자동 감지하지 못했습니다. 원시 필드를 그대로 저장합니다."
            ))

        target = total if max_rows == 0 else min(total, max_rows)
        collected = list(items)
        page = 1
        while len(collected) < target:
            page += 1
            body = self.fetch(key, page, NUM_OF_ROWS)
            batch = self._items(body)
            if not batch:
                break
            collected.extend(batch)
            self.stdout.write(f"  {len(collected)}/{target} 수집...")
        collected = collected[:target] if max_rows else collected

        # 정규화 컬럼(sick_cd/sick_nm) + 원시 필드 함께 저장 → 다음 단계가 안전하게 읽음
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sick_cd", "sick_nm"] + keys)
            for it in collected:
                cd = it.get(code_key, "") if code_key else ""
                nm = it.get(name_key, "") if name_key else ""
                writer.writerow([cd, nm] + [it.get(k, "") for k in keys])

        self.stdout.write(self.style.SUCCESS(
            f"질병 {len(collected)}건 저장 → {out_path}\n"
            f"다음: python manage.py disease_to_keywords"
        ))
