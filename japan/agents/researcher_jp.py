"""
Rovothome 일본 시장 데이터 리서처 에이전트 (멀티소스 교차검증)
- Claude API + web_search 툴로 일본 부동산/호텔/고령자주거 통계 수집
- 항목당 최대 3회 검색 → 복수 출처 수집
"""

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "jp"
SOURCES_PATH = DATA_DIR / "sources.json"
HISTORY_DIR = DATA_DIR / "history"

ITEMS = [
    {
        "key": "도쿄권_신축_맨션_분양호수",
        "description": "도쿄권(1都3県) 연간 신축 맨션 분양 호수",
        "unit": "호",
        "search_queries": [
            {"query": "東京圏 新築マンション 供給戸数 年間 不動産経済研究所", "prefer": "不動産経済研究所"},
            {"query": "首都圏 新築分譲マンション 発売戸数 統計", "prefer": "国土交通省"},
            {"query": "tokyo metropolitan area new condominium supply annual", "prefer": "REINS"},
        ],
    },
    {
        "key": "오사카권_신축_맨션_분양호수",
        "description": "오사카권(近畿圏) 연간 신축 맨션 분양 호수",
        "unit": "호",
        "search_queries": [
            {"query": "近畿圏 新築マンション 供給戸数 年間 不動産経済研究所", "prefer": "不動産経済研究所"},
            {"query": "大阪圏 新築分譲マンション 発売戸数", "prefer": "国土交通省"},
            {"query": "osaka kansai new condominium supply annual statistics", "prefer": "REINS"},
        ],
    },
    {
        "key": "나고야권_신축_맨션_분양호수",
        "description": "나고야권(中部圏/東海) 연간 신축 맨션 분양 호수",
        "unit": "호",
        "search_queries": [
            {"query": "東海圏 中部圏 新築マンション 供給戸数 不動産経済研究所", "prefer": "不動産経済研究所"},
            {"query": "名古屋圏 新築分譲マンション 発売戸数 統計", "prefer": "国土交通省"},
        ],
    },
    {
        "key": "전국_리노베이션_맨션_건수",
        "description": "일본 전국 연간 리노베이션 맨션 건수",
        "unit": "건",
        "search_queries": [
            {"query": "日本 マンション リノベーション 年間件数 国土交通省", "prefer": "国土交通省"},
            {"query": "既存住宅 リフォーム リノベーション 市場規模 件数", "prefer": "矢野経済研究所"},
            {"query": "中古マンション リノベーション 年間 施工件数 統計", "prefer": "リフォーム産業新聞"},
        ],
    },
    {
        "key": "풀리노베이션_비중",
        "description": "전체 리노베이션 중 풀리노베이션(스켈톤) 비중 (%)",
        "unit": "%",
        "search_queries": [
            {"query": "フルリノベーション スケルトン 割合 比率 統計", "prefer": "国土交通省"},
            {"query": "マンション フルリノベ 部分リノベ 比率", "prefer": "矢野経済研究所"},
        ],
    },
    {
        "key": "3대도시권_이사건수",
        "description": "3대 도시권(도쿄+오사카+나고야) 연간 이사 건수",
        "unit": "건",
        "search_queries": [
            {"query": "日本 三大都市圏 引越し件数 年間 総務省", "prefer": "総務省"},
            {"query": "日本 住民移動 転入転出 件数 年間 統計", "prefer": "総務省統計局"},
            {"query": "全国 引越し件数 年間 推計 3大都市圏", "prefer": "全日本トラック協会"},
        ],
    },
    {
        "key": "신규_호텔_개관수",
        "description": "일본 연간 신규 호텔 개관 수",
        "unit": "개",
        "search_queries": [
            {"query": "日本 新規ホテル 開業数 年間 観光庁", "prefer": "観光庁"},
            {"query": "日本 ホテル 新規開業 年間 件数 統計", "prefer": "日本ホテル協会"},
            {"query": "japan new hotel openings annual statistics", "prefer": "STR"},
        ],
    },
    {
        "key": "호텔_평균_객실수",
        "description": "일본 호텔 1개당 평균 객실 수",
        "unit": "실",
        "search_queries": [
            {"query": "日本 ホテル 平均客室数 1施設あたり 観光庁", "prefer": "観光庁"},
            {"query": "ホテル 平均 客室数 統計 日本", "prefer": "厚生労働省"},
        ],
    },
    {
        "key": "료칸_리노베이션_건수",
        "description": "연간 료칸 리노베이션 건수",
        "unit": "건",
        "search_queries": [
            {"query": "旅館 リノベーション 年間件数 改装 統計", "prefer": "観光庁"},
            {"query": "旅館 改修 リニューアル 年間 件数 日本", "prefer": "国土交通省"},
        ],
    },
    {
        "key": "연간_기업사택_신규리노베이션_기업수",
        "description": "연간 기업 사택/사원 기숙사 신규 또는 리노베이션 대상 기업 수",
        "unit": "개사",
        "search_queries": [
            {"query": "社宅 社員寮 新規 リノベーション 企業数 年間", "prefer": "経済産業省"},
            {"query": "企業 社宅 整備 年間 件数 統計 日本", "prefer": "日本経済新聞"},
        ],
    },
    {
        "key": "신규_고령자주거_시설수",
        "description": "연간 신규 개설 고령자 주거 시설 수 (서비스드 레지던스 등)",
        "unit": "개소",
        "search_queries": [
            {"query": "サービス付き高齢者向け住宅 新規登録 年間 件数", "prefer": "厚生労働省"},
            {"query": "サ高住 新規開設 年間 統計 国土交通省", "prefer": "国土交通省"},
            {"query": "高齢者住宅 新設 年間 施設数 統計", "prefer": "高齢者住宅協会"},
        ],
    },
    {
        "key": "고령자주거_평균세대수",
        "description": "고령자 주거 시설당 평균 세대(호실) 수",
        "unit": "세대",
        "search_queries": [
            {"query": "サ高住 平均戸数 1施設あたり 統計", "prefer": "国土交通省"},
            {"query": "サービス付き高齢者向け住宅 平均 住戸数", "prefer": "高齢者住宅協会"},
        ],
    },
]


def load_existing_sources() -> dict:
    if SOURCES_PATH.exists():
        with open(SOURCES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data:
                return data
    return {}


def save_history(sources: dict):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    with open(HISTORY_DIR / f"sources_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(sources, f, ensure_ascii=False, indent=2)


def research_single_query(client, item, query_info):
    prompt = f"""일본 부동산/주거/호텔 시장 데이터를 수집하는 리서처입니다.

다음 항목의 최신 데이터를 찾아주세요:

항목: {item['key']}
설명: {item['description']}
단위: {item['unit']}
검색 키워드: {query_info['query']}
우선 출처: {query_info['prefer']}

검색 지침:
1. "{query_info['prefer']}" 출처를 최우선으로 찾을 것
2. 일본어/영어로 검색하되 최신 연도 데이터 우선
3. 출처 URL을 반드시 포함할 것
4. 정확한 수치를 찾지 못하면 가장 신뢰할 수 있는 추정치 사용, confidence를 "low"로

반드시 아래 JSON 형식으로만 응답:
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
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
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
    except (json.JSONDecodeError, anthropic.APIError) as e:
        print(f"    ❌ 오류: {e}")
        return None


def research_item_multi(client, item):
    results = []
    for i, query_info in enumerate(item["search_queries"], 1):
        print(f"    검색 {i}/{len(item['search_queries'])}: {query_info['prefer']} ...", end=" ")
        data = research_single_query(client, item, query_info)
        if data:
            is_dup = any(
                r.get("value") == data.get("value") and r.get("source_name") == data.get("source_name")
                for r in results
            )
            if not is_dup:
                results.append(data)
                print(f"✅ {data.get('value')} {data.get('unit')}")
            else:
                print("⏭️ 중복")
        else:
            print("❌ 실패")
    return results


def run():
    print("=" * 60)
    print("🔍 Rovothome 일본 시장 데이터 리서처 (멀티소스)")
    print("=" * 60)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수를 설정해주세요.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    existing = load_existing_sources()
    if existing:
        save_history(existing)

    results = {}
    collected = 0
    failed = 0

    for i, item in enumerate(ITEMS, 1):
        key = item["key"]
        print(f"\n[{i}/{len(ITEMS)}] 수집 중: {key}")
        sources_list = research_item_multi(client, item)
        if sources_list:
            results[key] = sources_list
            collected += 1
        else:
            failed += 1
            if key in existing:
                results[key] = existing[key]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 수집완료: {collected}/{len(ITEMS)}항목 | ❌ 미수집: {failed}항목")
    print(f"📁 저장: {SOURCES_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run()
