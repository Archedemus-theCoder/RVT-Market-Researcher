"""
Rovothome 시장 데이터 리서처 에이전트
- Claude API (claude-sonnet-4-20250514) + web_search 툴로 공공통계 수집
- sources.json에 결과 저장, 변경 이력 추적
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOURCES_PATH = DATA_DIR / "sources.json"
HISTORY_DIR = DATA_DIR / "history"

# 수집 대상 항목 정의
ITEMS = [
    {
        "key": "전국_신축_준공_세대수",
        "description": "전국 신축 아파트/주거시설 연간 준공(사용승인) 세대수",
        "preferred_source": "통계청 또는 국토교통부 주택통계",
        "unit": "세대",
    },
    {
        "key": "수도권_비중",
        "description": "전국 신축 준공 세대 중 수도권(서울+경기+인천) 비중 (%)",
        "preferred_source": "국토교통부",
        "unit": "%",
    },
    {
        "key": "서울_비중",
        "description": "전국 신축 준공 세대 중 서울 비중 (%)",
        "preferred_source": "국토교통부",
        "unit": "%",
    },
    {
        "key": "아파트_대형_비중",
        "description": "신축 아파트 중 대형(전용 85㎡ 초과) 비중 (%)",
        "preferred_source": "국토교통부 분양가 통계",
        "unit": "%",
    },
    {
        "key": "아파트_중소형_비중",
        "description": "신축 아파트 중 중소형(전용 85㎡ 이하) 비중 (%)",
        "preferred_source": "국토교통부 분양가 통계",
        "unit": "%",
    },
    {
        "key": "오피스텔_비중",
        "description": "전체 신축 주거시설 중 오피스텔 비중 (%)",
        "preferred_source": "국토교통부",
        "unit": "%",
    },
    {
        "key": "분양가_10억이상_비중",
        "description": "신축 분양가 10억원 이상 비중 (%)",
        "preferred_source": "한국부동산원",
        "unit": "%",
    },
    {
        "key": "분양가_5to10억_비중",
        "description": "신축 분양가 5억~10억원 비중 (%)",
        "preferred_source": "한국부동산원",
        "unit": "%",
    },
    {
        "key": "분양가_5억미만_비중",
        "description": "신축 분양가 5억원 미만 비중 (%)",
        "preferred_source": "한국부동산원",
        "unit": "%",
    },
    {
        "key": "전국_연간_이사건수",
        "description": "전국 연간 이사(주거이동) 건수",
        "preferred_source": "통계청 인구이동통계",
        "unit": "건",
    },
    {
        "key": "신규_호텔_개관수",
        "description": "연간 신규 개관(등록) 호텔 수",
        "preferred_source": "한국호텔업협회 또는 문화체육관광부",
        "unit": "개",
    },
    {
        "key": "호텔_평균_객실수",
        "description": "호텔 1개당 평균 객실 수",
        "preferred_source": "문화체육관광부",
        "unit": "개",
    },
    {
        "key": "호텔_5성급_비중",
        "description": "신규 호텔 중 5성급 비중 (%)",
        "preferred_source": "문화체육관광부 관광숙박업 통계",
        "unit": "%",
    },
    {
        "key": "호텔_4성급_비중",
        "description": "신규 호텔 중 4성급 비중 (%)",
        "preferred_source": "문화체육관광부 관광숙박업 통계",
        "unit": "%",
    },
    {
        "key": "호텔_3성급이하_비중",
        "description": "신규 호텔 중 3성급 이하 비중 (%)",
        "preferred_source": "문화체육관광부 관광숙박업 통계",
        "unit": "%",
    },
]


def load_existing_sources() -> dict:
    """기존 sources.json 로드"""
    if SOURCES_PATH.exists():
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data:
                return data
    return {}


def save_history(sources: dict):
    """변경 이력을 날짜별로 저장"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    history_path = HISTORY_DIR / f"sources_{timestamp}.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def research_item(client: anthropic.Anthropic, item: dict, existing_value: dict | None) -> dict:
    """Claude API + web_search로 단일 항목 리서치"""
    context = ""
    if existing_value:
        context = (
            f"\n\n기존 데이터 참고:\n"
            f"- 기존 값: {existing_value.get('value')} {existing_value.get('unit')}\n"
            f"- 기존 출처: {existing_value.get('source_name')}\n"
            f"- 기존 기준연도: {existing_value.get('reference_year')}\n"
            f"새로운 데이터가 있으면 업데이트하고, 없으면 기존 값을 유지하되 재확인해주세요."
        )

    prompt = f"""한국 부동산/주거 시장 데이터를 수집하는 리서처입니다.

다음 항목의 최신 데이터를 찾아주세요:

항목: {item['key']}
설명: {item['description']}
우선 출처: {item['preferred_source']}
단위: {item['unit']}
{context}

검색 지침:
1. 정부 공공기관 통계를 최우선으로 찾을 것 (통계청, 국토교통부, 한국부동산원 등)
2. 가능한 최신 연도 데이터를 찾을 것
3. 출처 URL을 반드시 포함할 것
4. 정확한 수치를 찾지 못하면 가장 신뢰할 수 있는 추정치를 사용하되 confidence를 "low"로 표시

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "value": 숫자,
  "unit": "{item['unit']}",
  "source_name": "출처 기관명",
  "source_url": "URL",
  "collected_at": "{datetime.now().strftime('%Y-%m-%d')}",
  "reference_year": "YYYY",
  "confidence": "high/medium/low",
  "note": "보충 설명"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        # 응답에서 텍스트 블록 추출
        result_text = ""
        for block in response.content:
            if block.type == "text":
                result_text += block.text

        # JSON 파싱
        result_text = result_text.strip()
        # JSON 블록이 ```로 감싸진 경우 처리
        if "```" in result_text:
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            result_text = result_text[start:end]

        data = json.loads(result_text)
        return data

    except json.JSONDecodeError:
        print(f"  ⚠️ JSON 파싱 실패: {item['key']}")
        print(f"  응답: {result_text[:200]}")
        return None
    except anthropic.APIError as e:
        print(f"  ❌ API 오류 ({item['key']}): {e}")
        return None


def run():
    """리서처 에이전트 메인 실행"""
    print("=" * 60)
    print("🔍 Rovothome 시장 데이터 리서처 시작")
    print("=" * 60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수를 설정해주세요.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    existing = load_existing_sources()

    # 기존 데이터가 있으면 히스토리 저장
    if existing:
        save_history(existing)
        print(f"📦 기존 데이터 이력 저장 완료")

    results = {}
    collected = 0
    changed = 0
    failed = 0

    for i, item in enumerate(ITEMS, 1):
        key = item["key"]
        print(f"\n[{i}/{len(ITEMS)}] 수집 중: {key}")

        existing_val = existing.get(key)
        data = research_item(client, item, existing_val)

        if data:
            results[key] = data
            collected += 1

            # 변경 감지
            if existing_val and existing_val.get("value") != data.get("value"):
                changed += 1
                print(f"  ⚠️ 값 변경: {existing_val.get('value')} → {data.get('value')}")
            else:
                print(f"  ✅ 수집 완료: {data.get('value')} {data.get('unit')}")
                print(f"     출처: {data.get('source_name')} ({data.get('reference_year')})")
        else:
            failed += 1
            # 기존 값이 있으면 유지
            if existing_val:
                results[key] = existing_val
                print(f"  ↩️ 기존 값 유지: {existing_val.get('value')}")

    # sources.json 저장
    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 요약 리포트
    print("\n" + "=" * 60)
    print(f"✅ 수집완료: {collected}/{len(ITEMS)}항목 | "
          f"⚠️ 변경감지: {changed}항목 | "
          f"❌ 미수집: {failed}항목")
    print(f"📁 저장: {SOURCES_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run()
