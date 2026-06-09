"""심평원(HIRA) 병원정보서비스 API → 구미권 병·의원 + 진료과목 적재

전략: 진료과목코드(dgsbjtCd)로 역방향 조회.
  Department.code(=dgsbjtCd)마다 "경북 + 해당 과목" 병원 목록을 받아
  시군구명으로 구미권만 필터 → 병원↔진료과 M:N을 상세 API 없이 구축.

사용법:
  python manage.py import_hira --key <일반인증키>
  python manage.py import_hira --key <키> --regions 구미시,김천시,칠곡군
  python manage.py import_hira --key <키> --probe-sido   # 시도코드 탐색
  (키는 backend/.env의 HIRA_SERVICE_KEY로도 지정 가능)

참고: 진료시간은 별도 상세 API가 필요해 기본값(09:00~18:00)으로 적재.
"""
import time as time_mod
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.models import Department, Hospital

BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
NUM_OF_ROWS = 200  # 페이지가 크면 응답이 느려 타임아웃 발생 → 적당히 분할
TIMEOUT = 40
MAX_RETRY = 4
DEFAULT_SIDO_CD = "370000"  # 경상북도 (--probe-sido로 검증 가능)
DEFAULT_REGIONS = "구미시,김천시,칠곡군"
DEFAULT_OPEN, DEFAULT_CLOSE = time(9, 0), time(18, 0)

# 치과의원은 일반 치과(49) 대신 세부과목 코드(50~61)로 신고하는 경우가 대부분
# → 치과는 세부코드 전체를 함께 조회해 같은 진료과로 귀속
EXTRA_DGSBJT_CODES = {
    "치과": [str(c) for c in range(50, 62)],
}


class Command(BaseCommand):
    help = "심평원 병원정보서비스 API에서 구미권 병·의원과 진료과목을 받아 DB에 적재"

    def add_arguments(self, parser):
        parser.add_argument("--key", help="공공데이터포털 일반 인증키 (또는 backend/.env의 HIRA_SERVICE_KEY)")
        parser.add_argument("--sido-cd", default=DEFAULT_SIDO_CD, help="시도코드 (기본: 370000 경북)")
        parser.add_argument("--regions", default=DEFAULT_REGIONS, help="쉼표 구분 시군구명 필터")
        parser.add_argument("--probe-sido", action="store_true", help="시도코드 후보를 탐색해 출력만 한다")
        parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 결과 요약만 출력")

    # ── API 호출 ───────────────────────────────────────────────

    def fetch(self, key, params):
        qs = urllib.parse.urlencode({"serviceKey": key, **params})
        url = f"{BASE_URL}?{qs}"
        # 타임아웃·일시적 403(게이트웨이 동기화)·5xx에 대해 지수 백오프 재시도
        last_err = None
        # data.go.kr 게이트웨이가 기본 Python-urllib UA를 차단하므로 브라우저 UA 필수
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(1, MAX_RETRY + 1):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    root = ET.fromstring(resp.read())
                break
            except Exception as e:
                last_err = e
                if attempt == MAX_RETRY:
                    raise CommandError(f"API 호출 {MAX_RETRY}회 실패: {e}")
                wait = 2 ** attempt
                self.stdout.write(f"    재시도 {attempt}/{MAX_RETRY} ({e}) — {wait}s 대기")
                time_mod.sleep(wait)

        # 표준 오류 응답(OpenAPI_ServiceResponse)과 정상 응답 모두 처리
        if root.tag == "OpenAPI_ServiceResponse":
            msg = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or "unknown"
            code = root.findtext(".//returnReasonCode") or "?"
            raise CommandError(f"API 오류 [{code}] {msg} — 병원정보서비스 활용신청 여부와 키를 확인하세요.")

        result_code = root.findtext(".//resultCode")
        if result_code not in ("00", "0"):
            raise CommandError(f"API resultCode={result_code}: {root.findtext('.//resultMsg')}")

        total = int(root.findtext(".//totalCount") or 0)
        items = root.findall(".//item")
        return total, items

    def fetch_all_pages(self, key, params):
        """totalCount 기반 페이지네이션으로 모든 item을 수집."""
        items, page = [], 1
        while True:
            total, page_items = self.fetch(key, {**params, "pageNo": page, "numOfRows": NUM_OF_ROWS})
            items.extend(page_items)
            if page * NUM_OF_ROWS >= total or not page_items:
                return total, items
            page += 1
            time_mod.sleep(0.2)  # 호출 간격 (트래픽 예의)

    # ── 시도코드 탐색 ──────────────────────────────────────────

    def probe_sido(self, key):
        self.stdout.write("시도코드 탐색 중...")
        for cd in range(110000, 510000, 10000):
            try:
                total, items = self.fetch(key, {"sidoCd": cd, "pageNo": 1, "numOfRows": 1})
            except CommandError as e:
                raise e
            except Exception:
                continue
            if items:
                name = items[0].findtext("sidoCdNm") or "?"
                self.stdout.write(f"  sidoCd={cd}: {name} (기관 {total}개)")

    # ── 메인 ──────────────────────────────────────────────────

    def handle(self, *args, **options):
        key = options["key"] or settings.HIRA_SERVICE_KEY
        if not key:
            raise CommandError("인증키가 없습니다. backend/.env의 HIRA_SERVICE_KEY 또는 --key로 지정하세요.")

        if options["probe_sido"]:
            self.probe_sido(key)
            return

        sido_cd = options["sido_cd"]
        regions = [r.strip() for r in options["regions"].split(",") if r.strip()]
        departments = list(Department.objects.exclude(code=None).order_by("code"))
        if not departments:
            raise CommandError("code가 지정된 진료과가 없습니다. 먼저 seed_data를 실행하세요.")

        # 진료과목코드별 역방향 조회 → 병원 dict 누적 (ykiho 키)
        hospitals = {}
        skipped_no_coord = 0
        for dept in departments:
            codes = [dept.code] + EXTRA_DGSBJT_CODES.get(dept.name, [])
            total, items = 0, []
            for code in codes:
                t, i = self.fetch_all_pages(key, {"sidoCd": sido_cd, "dgsbjtCd": code})
                total += t
                items.extend(i)
            matched = 0
            for it in items:
                sggu = it.findtext("sgguCdNm") or ""
                if not any(r in sggu for r in regions):
                    continue
                ykiho = it.findtext("ykiho")
                lat, lng = it.findtext("YPos"), it.findtext("XPos")
                if not ykiho:
                    continue
                if not lat or not lng:
                    skipped_no_coord += 1
                    continue
                h = hospitals.setdefault(ykiho, {
                    "name": (it.findtext("yadmNm") or "").strip(),
                    "address": (it.findtext("addr") or "").strip(),
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "phone": (it.findtext("telno") or "").strip(),
                    "depts": set(),
                })
                h["depts"].add(dept.name)
                matched += 1
            self.stdout.write(f"  [{dept.code}] {dept.name}: 경북 {total}곳 중 구미권 {matched}곳")

        self.stdout.write(self.style.SUCCESS(
            f"\n구미권 병·의원 {len(hospitals)}곳 수집 (좌표 없음 제외 {skipped_no_coord}곳)"
        ))

        if options["dry_run"]:
            for h in list(hospitals.values())[:10]:
                self.stdout.write(f"  - {h['name']} / {h['address']} / {sorted(h['depts'])}")
            self.stdout.write("(dry-run: DB 미반영)")
            return

        # 기존 병원 삭제 후 적재
        dept_by_name = {d.name: d for d in departments}
        Hospital.objects.all().delete()
        for ykiho, h in hospitals.items():
            obj = Hospital.objects.create(
                ykiho=ykiho, name=h["name"], address=h["address"],
                latitude=h["latitude"], longitude=h["longitude"],
                phone=h["phone"], open_time=DEFAULT_OPEN, close_time=DEFAULT_CLOSE,
            )
            obj.departments.set([dept_by_name[n] for n in h["depts"]])

        self.stdout.write(self.style.SUCCESS(f"병원 {len(hospitals)}곳 DB 적재 완료!"))
