# 응급 키워드에 표시용 증상명(label) 추가 + 기존 행 백필.
# 매칭은 어간(keyword)으로 하되 화면 노출은 label로 — SymptomKeyword.label과 동일한 의도.

from django.db import migrations, models

# 어간 → 표시용 증상명. seed_data.EMERGENCY_KEYWORDS와 동일하게 유지.
LABELS = {
    "가슴통증": "가슴 통증", "가슴이아": "가슴 통증", "가슴답답": "가슴 답답함",
    "심장두근": "심장 두근거림", "왼쪽팔저림": "왼쪽 팔 저림", "가슴을쥐어짜": "가슴을 쥐어짜는 통증",
    "호흡곤란": "호흡곤란", "숨못쉬": "호흡곤란", "숨을못쉬": "호흡곤란",
    "숨이막혀": "숨막힘", "숨쉬기힘들": "호흡곤란", "숨이안쉬어": "호흡곤란",
    "의식잃": "의식 소실", "의식을잃": "의식 소실", "의식이없": "의식 없음",
    "정신을잃": "의식 소실", "쓰러지": "쓰러짐", "쓰러졌": "쓰러짐", "쓰러져": "쓰러짐",
    "말이안나와": "언어 장애", "말이어눌": "발음 어눌함", "한쪽마비": "편마비",
    "한쪽팔다리": "한쪽 팔다리 마비", "벼락두통": "벼락두통", "갑자기심한두통": "갑작스런 심한 두통",
    "발작": "발작", "경련": "경련",
    "심한출혈": "심한 출혈", "피가멈추지": "지혈 안 됨", "출혈이심": "심한 출혈",
    "골절": "골절", "뼈가부러": "골절", "고열에경련": "고열 동반 경련",
    "39도": "고열(39도 이상)", "40도": "고열(40도)", "피를토": "토혈(피를 토함)",
    "하혈": "하혈", "음독": "음독(중독)", "삼켰어요": "이물질 삼킴",
    "실신": "실신", "기절": "실신",
}


def backfill_labels(apps, schema_editor):
    EmergencyKeyword = apps.get_model("api", "EmergencyKeyword")
    for ek in EmergencyKeyword.objects.all():
        label = LABELS.get(ek.keyword)
        if label and not ek.label:
            ek.label = label
            ek.save(update_fields=["label"])


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_alter_keywordfeedback_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='emergencykeyword',
            name='label',
            field=models.CharField(blank=True, max_length=50, verbose_name='표시용 증상명'),
        ),
        migrations.RunPython(backfill_labels, migrations.RunPython.noop),
    ]
