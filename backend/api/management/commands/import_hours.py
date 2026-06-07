"""심평원 의료기관별상세정보서비스 → 병원 진료시간 적재

Hospital.ykiho를 키로 상세정보(getDtlInfo)를 조회해
요일별 진료시간 중 월요일(trmtMonStart/End)을 대표 시간으로 저장한다.
(모델이 단일 open/close라 평일 대표값 사용 — 응답에 월요일이 없으면 기존값 유지)

사용법:
  python manage.py import_hours --key <일반인증키>
  python manage.py import_hours --key <키> --base-url https://apis.data.go.kr/B551182/MadmDtlInfoService2.7 --op getDtlInfo2.7
  python manage.py import_hours --key <키> --limit 20   # 일부만 테스트
"""
import time as time_mod
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import time

from django.core.management.base import BaseCommand, CommandError

from api.models import Hospital

DEFAULT_BASE = "https://apis.data.go.kr/B551182/MadmDtlInfoService2.8"
DEFAULT_OP = "getDtlInfo2.8"
TIMEOUT = 30
MAX_RETRY = 3


def parse_hhmm(value):
    """'0900' / '900' / '09:00' → time(9, 0). 실패 시 None."""
    if not value:
        return None
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) == 3:
        digits = "0" + digits
    if len(digits) != 4:
        return None
    hh, mm = int(digits[:2]), int(digits[2:])
    if hh == 24:  # 일부 기관이 24:00로 신고 → 23:59로 보정
        hh, mm = 23, 59
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return time(hh, mm)


class Command(BaseCommand):
    help = "심평원 상세정보 API에서 병원 진료시간(월요일 기준)을 받아 적재"

    def add_arguments(self, parser):
        parser.add_argument("--key", required=True, help="공공데이터포털 일반 인증키")
        parser.add_argument("--base-url", default=DEFAULT_BASE)
        parser.add_argument("--op", default=DEFAULT_OP)
        parser.add_argument("--limit", type=int, default=None, help="처리할 병원 수 제한 (테스트용)")

    def fetch_detail(self, key, base_url, op, ykiho):
        qs = urllib.parse.urlencode({"serviceKey": key, "ykiho": ykiho})
        req = urllib.request.Request(
            f"{base_url}/{op}?{qs}", headers={"User-Agent": "Mozilla/5.0"}
        )
        for attempt in range(1, MAX_RETRY + 1):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return ET.fromstring(resp.read())
            except Exception as e:
                if attempt == MAX_RETRY:
                    raise e
                time_mod.sleep(2 ** attempt)

    def handle(self, *args, **options):
        key = options["key"]
        base_url, op = options["base_url"], options["op"]

        hospitals = Hospital.objects.exclude(ykiho=None).order_by("id")
        if options["limit"]:
            hospitals = hospitals[: options["limit"]]
        total = len(hospitals)
        if total == 0:
            raise CommandError("ykiho가 있는 병원이 없습니다. import_hira를 먼저 실행하세요.")

        updated, no_data, failed = 0, 0, 0
        for i, h in enumerate(hospitals, 1):
            try:
                root = self.fetch_detail(key, base_url, op, h.ykiho)
            except Exception as e:
                failed += 1
                self.stdout.write(f"  [{i}/{total}] {h.name}: 호출 실패 ({e})")
                continue

            def day_hours(prefix):
                """요일별 시작·종료 파싱 + 오신고 보정.

                - 한쪽만 있거나 00:00~00:00이면 휴진(None) 처리
                - 종료가 시작보다 빠르고 정오 이전이면 PM 오신고 (08:00 → 20:00)
                """
                o = parse_hhmm(root.findtext(f".//trmt{prefix}Start"))
                c = parse_hhmm(root.findtext(f".//trmt{prefix}End"))
                if not o or not c or (o == c == time(0, 0)):
                    return None, None
                if c < o and c.hour < 12:
                    c = time(c.hour + 12, c.minute)
                return o, c

            open_t, close_t = day_hours("Mon")
            sat_o, sat_c = day_hours("Sat")
            sun_o, sun_c = day_hours("Sun")

            if open_t and close_t:
                h.open_time, h.close_time = open_t, close_t
                h.sat_open_time, h.sat_close_time = sat_o, sat_c
                h.sun_open_time, h.sun_close_time = sun_o, sun_c
                h.save(update_fields=[
                    "open_time", "close_time",
                    "sat_open_time", "sat_close_time",
                    "sun_open_time", "sun_close_time",
                ])
                updated += 1
            else:
                no_data += 1

            if i % 50 == 0:
                self.stdout.write(f"  진행 {i}/{total} (갱신 {updated}, 정보없음 {no_data}, 실패 {failed})")
            time_mod.sleep(0.1)

        self.stdout.write(self.style.SUCCESS(
            f"완료: 총 {total}곳 — 진료시간 갱신 {updated}, 정보없음 {no_data}, 실패 {failed}"
        ))
