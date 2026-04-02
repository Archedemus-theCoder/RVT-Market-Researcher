# Rovothome 한국 시장규모 추정 시스템

데이터가 주기적으로 갱신되고, 근거가 추적 가능한 살아있는 시장규모 추정 모델입니다.

## 프로젝트 구조

```
rovothome-market/
├── app.py                  # Streamlit 대시보드
├── agents/
│   ├── researcher.py       # 리서처 에이전트 (데이터 수집)
│   └── critic.py           # 크리틱 에이전트 (데이터 검증)
├── data/
│   ├── sources.json        # 리서처가 수집한 원본 수치 + 출처
│   ├── validated.json      # 크리틱이 승인한 수치 (대시보드 입력)
│   └── history/            # 수치 변경 이력 (날짜별 스냅샷)
├── requirements.txt
└── README.md
```

## 설치

```bash
pip install -r requirements.txt
```

## 환경변수

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## 실행 순서

### 1단계: 데이터 수집 (리서처 에이전트)

```bash
python agents/researcher.py
```

- Claude API (`claude-sonnet-4-20250514`) + `web_search` 툴로 공공통계 수집
- 정부기관(통계청, 국토교통부, 한국부동산원 등) 데이터 우선
- 결과: `data/sources.json`에 저장
- 기존 데이터가 있으면 변경 이력 자동 저장

### 2단계: 데이터 검증 (크리틱 에이전트)

```bash
python agents/critic.py
```

- `sources.json` 검토 후 `validated.json` 생성
- 검증 기준:
  - 출처 신뢰도 (정부기관=high, 언론=medium, 블로그=low)
  - 최신성 (기준연도 2년 이상 경과 시 경고)
  - 논리 일관성 (비중 합계=100%, 이사건수 > 신축세대수 등)

### 3단계: 대시보드 실행

```bash
streamlit run app.py
```

## 세그먼트 구성

| 세그먼트 | 대상 | 모수 |
|----------|------|------|
| 1. 신축 주거 | 신규 분양 아파트/오피스텔 | 전국 준공 세대수 × 지역비중 |
| 2. 호텔 | 신규 개관 호텔 객실 | 신규 호텔수 × 평균 객실수 |
| 3. 이사 수요 | 구축→구축 이사 | 총 이사건수 - 신축세대수 |
| 4. 리모델링 | 노후 주택 리모델링 | 연 3,000세대 (고정) |

## 대시보드에서 직접 실행

사이드바 하단의 "리서처 실행" / "크리틱 검토" 버튼으로 대시보드 내에서 데이터 갱신이 가능합니다.
