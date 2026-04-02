"""
Rovothome 시장 데이터 리서처 에이전트 (멀티소스 교차검증 버전)
- Claude API (claude-sonnet-4-20250514) + web_search 툴로 공공통계 수집
- 항목당 최대 3회 검색 → 복수 출처 수집 → sources.json에 배열로 저장
"""

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOURCES_PATH = DATA_DIR / "sources.json"
HISTORY_DIR = DATA_DIR / "history"

# 수집 대상 항목 정의 (검색 전략 포함)
ITEMS = [
    {
        "key": "전국_신축_준공_세대수",
        "description": "전국 신축 아파트/주거시설 연간 준공(사용승인) 세대수",
        "unit": "세대",
        "search_queries": [
            {"query": "한국 전국 연간 주택 준공 세대수 통계청", "prefer": "통계청"},
            {"query": "국토교통부 주택건설 인허가 준공 실적 연간", "prefer": "국토교통부"},
            {"query": "한국 신축 아파트 사용승인 실적 연간 총세대수", "prefer": "부동산R114"},
        ],
    },
    {
        "key": "수도권_비중",
        "description": "전국 신축 준공 세대 중 수도권(서울+경기+인천) 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "수도권 주택 준공 비중 전국 대비 국토교통부", "prefer": "국토교통부"},
            {"query": "수도권 신축 아파트 비중 서울 경기 인천 통계", "prefer": "부동산R114"},
            {"query": "수도권 주택 공급 비중 전국 대비 퍼센트", "prefer": "한국부동산원"},
        ],
    },
    {
        "key": "서울_비중",
        "description": "전국 신축 준공 세대 중 서울 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "서울 주택 준공 세대수 전국 대비 비중", "prefer": "국토교통부"},
            {"query": "서울 신축 아파트 입주 물량 전국 비중", "prefer": "부동산R114"},
            {"query": "서울 연간 주택 공급 비중 통계", "prefer": "서울연구원"},
        ],
    },
    {
        "key": "아파트_대형_비중",
        "description": "신축 아파트 중 대형(전용 85㎡ 초과) 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "신축 아파트 전용 85제곱미터 초과 대형 비중 통계", "prefer": "국토교통부"},
            {"query": "아파트 면적별 분양 비중 대형 85㎡ 초과", "prefer": "부동산R114"},
            {"query": "한국 아파트 대형 중소형 비율 연간 추이", "prefer": "한국부동산원"},
        ],
    },
    {
        "key": "아파트_중소형_비중",
        "description": "신축 아파트 중 중소형(전용 85㎡ 이하) 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "신축 아파트 전용 85제곱미터 이하 중소형 비중", "prefer": "국토교통부"},
            {"query": "아파트 면적별 분양 비중 중소형 85㎡ 이하", "prefer": "부동산R114"},
            {"query": "한국 중소형 아파트 비중 추이", "prefer": "한국부동산원"},
        ],
    },
    {
        "key": "오피스텔_비중",
        "description": "전체 신축 주거시설 중 오피스텔 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "오피스텔 준공 물량 전체 주택 대비 비중 국토교통부", "prefer": "국토교통부"},
            {"query": "오피스텔 공급 비중 전체 주거시설 대비", "prefer": "부동산R114"},
            {"query": "오피스텔 입주 물량 연간 추이 전국", "prefer": "한국경제"},
        ],
    },
    {
        "key": "분양가_10억이상_비중",
        "description": "신축 분양가 10억원 이상 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "신축 아파트 분양가 10억원 이상 비중 한국부동산원", "prefer": "한국부동산원"},
            {"query": "아파트 분양가 가격대별 비중 10억 이상", "prefer": "HUG"},
            {"query": "분양가 고가 아파트 비중 전국 통계", "prefer": "부동산R114"},
        ],
    },
    {
        "key": "분양가_5to10억_비중",
        "description": "신축 분양가 5억~10억원 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "신축 아파트 분양가 5억 10억 사이 비중 통계", "prefer": "한국부동산원"},
            {"query": "아파트 분양가 가격대별 분포 5억에서 10억", "prefer": "HUG"},
            {"query": "전국 아파트 분양가 중간 가격대 비중", "prefer": "부동산R114"},
        ],
    },
    {
        "key": "분양가_5억미만_비중",
        "description": "신축 분양가 5억원 미만 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "신축 아파트 분양가 5억원 미만 비중 통계", "prefer": "한국부동산원"},
            {"query": "아파트 분양가 가격대별 분포 5억 미만", "prefer": "HUG"},
            {"query": "지방 아파트 분양가 5억 미만 비중", "prefer": "부동산R114"},
        ],
    },
    {
        "key": "전국_연간_이사건수",
        "description": "전국 연간 이사(주거이동) 건수",
        "unit": "건",
        "search_queries": [
            {"query": "통계청 국내인구이동통계 연간 이동 건수", "prefer": "통계청"},
            {"query": "한국 연간 이사 건수 주거이동 통계", "prefer": "e-나라지표"},
            {"query": "전국 인구이동 연간 현황 총이동자수", "prefer": "행정안전부"},
        ],
    },
    {
        "key": "신규_호텔_개관수",
        "description": "연간 신규 개관(등록) 호텔 수",
        "unit": "개",
        "search_queries": [
            {"query": "한국 연간 신규 호텔 개관 등록 수 문화체육관광부", "prefer": "문화체육관광부"},
            {"query": "관광숙박업 신규 등록 호텔 연간 현황", "prefer": "한국호텔업협회"},
            {"query": "한국 호텔 신규 개관 연간 추이", "prefer": "한국관광공사"},
        ],
    },
    {
        "key": "호텔_평균_객실수",
        "description": "호텔 1개당 평균 객실 수",
        "unit": "개",
        "search_queries": [
            {"query": "한국 관광호텔 평균 객실수 문화체육관광부", "prefer": "문화체육관광부"},
            {"query": "호텔 1개당 평균 객실 수 한국 통계", "prefer": "한국호텔업협회"},
            {"query": "한국 호텔 평균 객실 규모 관광숙박", "prefer": "한국관광공사"},
        ],
    },
    {
        "key": "호텔_5성급_비중",
        "description": "신규 호텔 중 5성급 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "한국 호텔 등급별 비중 5성급 비율 문화체육관광부", "prefer": "문화체육관광부"},
            {"query": "호텔 5성급 비중 한국관광협회중앙회 등급 결정", "prefer": "한국관광협회중앙회"},
            {"query": "한국 5성급 호텔 수 전체 호텔 대비", "prefer": "호텔등급결정사업"},
        ],
    },
    {
        "key": "호텔_4성급_비중",
        "description": "신규 호텔 중 4성급 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "한국 호텔 등급별 비중 4성급 비율 문화체육관광부", "prefer": "문화체육관광부"},
            {"query": "호텔 4성급 비중 한국관광협회중앙회 등급 결정", "prefer": "한국관광협회중앙회"},
            {"query": "한국 4성급 호텔 수 전체 호텔 대비", "prefer": "호텔등급결정사업"},
        ],
    },
    {
        "key": "호텔_3성급이하_비중",
        "description": "신규 호텔 중 3성급 이하 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "한국 호텔 등급별 비중 3성급 이하 비율", "prefer": "문화체육관광부"},
            {"query": "호텔 3성급 2성급 1성급 비중 한국관광협회중앙회", "prefer": "한국관광협회중앙회"},
            {"query": "한국 3성급 이하 호텔 수 비중", "prefer": "호텔등급결정사업"},
        ],
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


def research_single_query(client: anthropic.Anthropic, item: dict, query_info: dict) -> dict | None:
    """Claude API + web_search로 단일 쿼리 리서치"""
    prompt = f"""한국 부동산/주거 시장 데이터를 수집하는 리서처입니다.

다음 항목의 최신 데이터를 찾아주세요:

항목: {item['key']}
설명: {item['description']}
단위: {item['unit']}
검색 키워드: {query_info['query']}
우선 출처: {query_info['prefer']}

검색 지침:
1. "{query_info['prefer']}" 출처를 최우선으로 찾을 것
2. 가능한 최신 연도 데이터를 찾을 것
3. 출처 URL을 반드시 포함할 것
4. 정확한 수치를 찾지 못하면 가장 신뢰할 수 있는 추정치를 사용하되 confidence를 "low"로 표시
5. 검색 결과에서 실제 수치가 나온 원본 출처를 명시할 것

반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "value": 숫자,
  "unit": "{item['unit']}",
  "source_name": "출처 기관명",
  "source_url": "URL",
  "collected_at": "{datetime.now().strftime('%Y-%m-%d')}",
  "reference_year": "YYYY",
  "confidence": "high/medium/low",
  "note": "보충 설명 (수치 산출 근거 포함)"
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

        result_text = ""
        for block in response.content:
            if block.type == "text":
                result_text += block.text

        result_text = result_text.strip()
        if "```" in result_text:
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            result_text = result_text[start:end]

        data = json.loads(result_text)
        data["search_query"] = query_info["query"]
        data["preferred_source"] = query_info["prefer"]
        return data

    except json.JSONDecodeError:
        return None
    except anthropic.APIError as e:
        print(f"    ❌ API 오류: {e}")
        return None


def research_item_multi(client: anthropic.Anthropic, item: dict) -> list[dict]:
    """항목당 최대 3회 검색으로 복수 출처 수집"""
    results = []

    for i, query_info in enumerate(item["search_queries"], 1):
        print(f"    검색 {i}/3: {query_info['prefer']} ...", end=" ")
        data = research_single_query(client, item, query_info)

        if data:
            # 중복 값 체크 (같은 값+같은 출처면 스킵)
            is_duplicate = any(
                r.get("value") == data.get("value") and r.get("source_name") == data.get("source_name")
                for r in results
            )
            if not is_duplicate:
                results.append(data)
                print(f"✅ {data.get('value')} {data.get('unit')} ({data.get('source_name')})")
            else:
                print(f"⏭️ 중복 (동일 값+출처)")
        else:
            print("❌ 실패")

    return results


def run():
    """리서처 에이전트 메인 실행"""
    print("=" * 60)
    print("🔍 Rovothome 시장 데이터 리서처 (멀티소스 교차검증)")
    print("=" * 60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수를 설정해주세요.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    existing = load_existing_sources()

    if existing:
        save_history(existing)
        print(f"📦 기존 데이터 이력 저장 완료")

    results = {}
    total_sources = 0
    multi_source_items = 0
    single_source_items = 0
    failed_items = 0

    for i, item in enumerate(ITEMS, 1):
        key = item["key"]
        print(f"\n[{i}/{len(ITEMS)}] 수집 중: {key}")

        sources_list = research_item_multi(client, item)

        if sources_list:
            results[key] = sources_list
            total_sources += len(sources_list)
            if len(sources_list) >= 2:
                multi_source_items += 1
            else:
                single_source_items += 1
            print(f"  📊 {len(sources_list)}개 출처 수집 완료")
        else:
            failed_items += 1
            # 기존 값이 있으면 유지
            if key in existing:
                results[key] = existing[key]
                prev = existing[key]
                count = len(prev) if isinstance(prev, list) else 1
                print(f"  ↩️ 기존 값 유지 ({count}개 출처)")
            else:
                print(f"  ❌ 수집 실패, 기존 값 없음")

    # sources.json 저장
    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 요약 리포트
    print("\n" + "=" * 60)
    print(f"✅ 수집완료: {multi_source_items + single_source_items}/{len(ITEMS)}항목")
    print(f"  📊 복수출처(2+): {multi_source_items}항목 | 단일출처: {single_source_items}항목")
    print(f"  🔢 총 출처 수: {total_sources}개 | ❌ 미수집: {failed_items}항목")
    print(f"📁 저장: {SOURCES_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run()
