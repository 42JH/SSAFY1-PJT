"""E-Gen 응급의료기관 정보 API → 구미권 응급실 기관 적재

getEgytListInfoInqire로 시도(경북)·시군구별 목록을 받아 EmergencyCenter에 저장.
좌표가 없으면 getEgytBassInfoInqire로 보강.

  python manage.py import_emergency --key <인증키>
  python manage.py import_emergency --key <키> --regions 구미시,김천시,칠곡군
  (키는 backend/.env의 EGEN_SERVICE_KEY로도 지정 가능)
"""
import time as time_mod
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api.models import EmergencyCenter

BASE_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService"
LIST_OP = "getEgytListInfoInqire"
BASIS_OP = "getEgytBassInfoInqire"
DEFAULT_SIDO = "경상북도"
DEFAULT_REGIONS = "구미시,김천시,칠곡군"
NUM_OF_ROWS = 100
TIMEOUT = 40
MAX_RETRY = 4


class Command(BaseCommand):
    help = "E-Gen 응급의료기관 정보에서 구미권 응급실 기관을 받아 DB에 적재"

    def add_arguments(self, parser):
        parser.add_argument("--key", help="공공데이터포털 인증키 (또는 backend/.env의 EGEN_SERVICE_KEY)")
        parser.add_argument("--sido", default=DEFAULT_SIDO)
        parser.add_argument("--regions", default=DEFAULT_REGIONS, help="쉼표 구분 시군구명")
        parser.add_argument("--probe", action="store_true", help="첫 item 원본 XML만 출력")
        parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 요약만 출력")

    def fetch(self, key, op, params):
        qs = urllib.parse.urlencode({"serviceKey": key, **params})
        url = f"{BASE_URL}/{op}?{qs}"
        # data.go.kr은 기본 Python UA를 차단하므로 브라우저 UA 사용
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(1, MAX_RETRY + 1):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    root = ET.fromstring(resp.read())
                break
            except Exception as e:
                if attempt == MAX_RETRY:
                    raise CommandError(f"API 호출 {MAX_RETRY}회 실패: {e}")
                wait = 2 ** attempt
                self.stdout.write(f"    재시도 {attempt}/{MAX_RETRY} ({e}) - {wait}s 대기")
                time_mod.sleep(wait)

        if root.tag == "OpenAPI_ServiceResponse":
            msg = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or "unknown"
            code = root.findtext(".//returnReasonCode") or "?"
            raise CommandError(f"API 오류 [{code}] {msg}")

        result_code = root.findtext(".//resultCode")
        if result_code not in ("00", "0", None):
            raise CommandError(f"resultCode={result_code}: {root.findtext('.//resultMsg')}")

        total = int(root.findtext(".//totalCount") or 0)
        return total, root.findall(".//item")

    def fetch_all(self, key, op, params):
        items, page = [], 1
        while True:
            total, page_items = self.fetch(key, op, {**params, "pageNo": page, "numOfRows": NUM_OF_ROWS})
            items.extend(page_items)
            if page * NUM_OF_ROWS >= total or not page_items:
                return total, items
            page += 1
            time_mod.sleep(0.2)

    def basis_coords(self, key, hpid):
        """목록에 좌표가 없을 때 기본정보에서 좌표·대표전화 보강."""
        try:
            _, items = self.fetch(key, BASIS_OP, {"HPID": hpid})
        except CommandError:
            return None
        if not items:
            return None
        it = items[0]
        lat = it.findtext("wgs84Lat") or it.findtext("latitude")
        lng = it.findtext("wgs84Lon") or it.findtext("longitude")
        if lat and lng:
            return float(lat), float(lng), (it.findtext("dutyTel1") or "").strip()
        return None

    def handle(self, *args, **options):
        key = options["key"] or settings.EGEN_SERVICE_KEY
        if not key:
            raise CommandError("인증키가 없습니다. backend/.env의 EGEN_SERVICE_KEY 또는 --key로 지정하세요.")

        sido = options["sido"]
        regions = [r.strip() for r in options["regions"].split(",") if r.strip()]

        if options["probe"]:
            _, items = self.fetch(key, LIST_OP, {"Q0": sido, "Q1": regions[0], "pageNo": 1, "numOfRows": 1})
            self.stdout.write(ET.tostring(items[0], encoding="unicode") if items else "(no item)")
            return

        centers = {}
        no_coord = 0
        for region in regions:
            total, items = self.fetch_all(key, LIST_OP, {"Q0": sido, "Q1": region})
            added = 0
            for it in items:
                hpid = it.findtext("hpid")
                if not hpid:
                    continue
                lat = it.findtext("wgs84Lat") or it.findtext("latitude")
                lng = it.findtext("wgs84Lon") or it.findtext("longitude")
                tel1 = (it.findtext("dutyTel1") or "").strip()
                if not lat or not lng:
                    coords = self.basis_coords(key, hpid)
                    if not coords:
                        no_coord += 1
                        continue
                    lat, lng, tel1 = coords[0], coords[1], tel1 or coords[2]
                centers[hpid] = {
                    "name": (it.findtext("dutyName") or "").strip(),
                    "address": (it.findtext("dutyAddr") or "").strip(),
                    "latitude": float(lat),
                    "longitude": float(lng),
                    "phone": tel1,
                    "er_phone": (it.findtext("dutyTel3") or "").strip(),
                    "emcls_name": (it.findtext("dutyEmclsName") or "").strip(),
                }
                added += 1
            self.stdout.write(f"  {region}: {added}곳 (지역 전체 {total}건)")

        self.stdout.write(self.style.SUCCESS(
            f"\n응급의료기관 {len(centers)}곳 수집 (좌표 없음 제외 {no_coord}곳)"
        ))

        if options["dry_run"]:
            for c in list(centers.values())[:20]:
                tel = c["er_phone"] or c["phone"] or "-"
                self.stdout.write(f"  - [{c['emcls_name'] or '응급기관'}] {c['name']} / {c['address']} / Tel {tel}")
            self.stdout.write("(dry-run: DB 미반영)")
            return

        EmergencyCenter.objects.all().delete()
        for hpid, c in centers.items():
            EmergencyCenter.objects.create(hpid=hpid, **c)
        self.stdout.write(self.style.SUCCESS(f"응급의료기관 {len(centers)}곳 DB 적재 완료!"))
