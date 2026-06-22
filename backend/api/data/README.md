# 증상 키워드 확장 데이터

LLM로 키워드 후보를 만들고, 사람이 검수한 것만 추려 사전에 반영하는 워크플로의 데이터 폴더.

## 흐름

1. **생성** — `python manage.py generate_keywords`
   - 진료과별로 증상 표현 후보를 LLM(기본 `claude-opus-4-8`)으로 생성
   - 결과: `keyword_candidates.csv` (컬럼: `keyword, department, weight, label, approved`)
   - `ANTHROPIC_API_KEY`(backend/.env) 필요. 비용 절감은 `--model claude-sonnet-4-6`

2. **검수(사람)** — `keyword_candidates.csv`를 열어
   - 진료과 매핑이 맞는지, 가중치가 적절한지, 응급 증상이 섞이지 않았는지 확인
   - 좋은 행만 골라 `keywords_approved.csv`로 옮긴다 (틀린 매핑·label·weight는 수정)

3. **반영** — `python manage.py seed_data`
   - `keywords_approved.csv`가 있으면 기존 사전(`keyword_dictionary.py`)과 함께 적재된다

## 컬럼

| 컬럼 | 의미 |
|---|---|
| `keyword` | 매칭용 토큰(짧은 어간/구어체). 예: `배가아`, `허리가아` |
| `department` | 진료과명 (seed_data의 DEPARTMENTS 이름과 일치해야 함) |
| `weight` | 1~3 (3=대표 증상, 2=일반, 1=약한 신호) |
| `label` | 화면(추천 근거)에 보일 표준 증상명. 예: `복통` |

> ⚠️ LLM 생성물은 그럴듯해도 틀릴 수 있다. **반드시 사람 검수 후** `keywords_approved.csv`로 반영할 것.
> `keyword_candidates.csv`는 매번 덮어쓰이는 임시 산출물이다.
