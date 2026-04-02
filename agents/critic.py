"""
Rovothome 시장 데이터 크리틱 에이전트
- sources.json 검토 → validated.json 생성
- 출처 신뢰도, 최신성, 논리 일관성, 교차검증
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOURCES_PATH = DATA_DIR / "sources.json"
VALIDATED_PATH = DATA_DIR / "validated.json"
HISTORY_DIR = DATA_DIR / "history"

# 정부/공공기관 키워드
GOV_KEYWORDS = [
    "통계청", "국토교통부", "한국부동산원", "문화체육관광부",
    "한국호텔업협회", "kosis", "molit", "kostat", "reb.or.kr",
    "mcst.go.kr", "국토부", "행정안전부", "서울시",
]
MEDIA_KEYWORDS = ["뉴스", "신문", "일보", "경제", "매일", "헤럴드", "연합"]


def load_sources() -> dict:
    """sources.json 로드"""
    if not SOURCES_PATH.exists():
        print("❌ sources.json이 없습니다. researcher.py를 먼저 실행해주세요.")
        return {}
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def assess_source_reliability(item: dict) -> str:
    """출처 신뢰도 평가"""
    source_name = (item.get("source_name") or "").lower()
    source_url = (item.get("source_url") or "").lower()
    combined = source_name + " " + source_url

    for kw in GOV_KEYWORDS:
        if kw.lower() in combined:
            return "high"
    for kw in MEDIA_KEYWORDS:
        if kw.lower() in combined:
            return "medium"
    return "low"


def check_freshness(item: dict) -> tuple[bool, str]:
    """최신성 검사: 기준연도가 2년 이상 오래되면 경고"""
    ref_year = item.get("reference_year", "")
    try:
        year = int(ref_year)
        current_year = datetime.now().year
        if current_year - year >= 2:
            return False, f"기준연도 {year}년은 {current_year - year}년 경과 (2년 이상 경과 ⚠️)"
        return True, f"기준연도 {year}년 (최신)"
    except (ValueError, TypeError):
        return False, "기준연도 파싱 불가"


def validate_logical_consistency(sources: dict) -> list[dict]:
    """논리 일관성 검증"""
    issues = []

    # 1. 수도권비중 + 비수도권 = 100% (서울은 수도권의 부분집합)
    sudogwon = sources.get("수도권_비중", {}).get("value")
    seoul = sources.get("서울_비중", {}).get("value")
    if sudogwon is not None and seoul is not None:
        if seoul > sudogwon:
            issues.append({
                "type": "error",
                "message": f"서울 비중({seoul}%)이 수도권 비중({sudogwon}%)보다 큼 - 논리 오류",
                "items": ["서울_비중", "수도권_비중"],
            })

    # 2. 아파트 대형 + 중소형 비중 합계 검증
    large = sources.get("아파트_대형_비중", {}).get("value")
    small_mid = sources.get("아파트_중소형_비중", {}).get("value")
    if large is not None and small_mid is not None:
        total = large + small_mid
        if abs(total - 100) > 5:
            issues.append({
                "type": "warning",
                "message": f"아파트 대형({large}%) + 중소형({small_mid}%) = {total}% (100%와 차이 > 5%p)",
                "items": ["아파트_대형_비중", "아파트_중소형_비중"],
            })

    # 3. 분양가 구간 비중 합계 = 100%
    p_high = sources.get("분양가_10억이상_비중", {}).get("value")
    p_mid = sources.get("분양가_5to10억_비중", {}).get("value")
    p_low = sources.get("분양가_5억미만_비중", {}).get("value")
    if all(v is not None for v in [p_high, p_mid, p_low]):
        total = p_high + p_mid + p_low
        if abs(total - 100) > 5:
            issues.append({
                "type": "warning",
                "message": f"분양가 구간 합계: {p_high}+{p_mid}+{p_low}={total}% (100%와 차이 > 5%p)",
                "items": ["분양가_10억이상_비중", "분양가_5to10억_비중", "분양가_5억미만_비중"],
            })

    # 4. 호텔 등급 비중 합계 = 100%
    h5 = sources.get("호텔_5성급_비중", {}).get("value")
    h4 = sources.get("호텔_4성급_비중", {}).get("value")
    h3 = sources.get("호텔_3성급이하_비중", {}).get("value")
    if all(v is not None for v in [h5, h4, h3]):
        total = h5 + h4 + h3
        if abs(total - 100) > 5:
            issues.append({
                "type": "warning",
                "message": f"호텔 등급 합계: {h5}+{h4}+{h3}={total}% (100%와 차이 > 5%p)",
                "items": ["호텔_5성급_비중", "호텔_4성급_비중", "호텔_3성급이하_비중"],
            })

    # 5. 이사건수 > 신축준공세대수
    moving = sources.get("전국_연간_이사건수", {}).get("value")
    new_build = sources.get("전국_신축_준공_세대수", {}).get("value")
    if moving is not None and new_build is not None:
        if moving <= new_build:
            issues.append({
                "type": "error",
                "message": f"이사건수({moving:,}) ≤ 신축준공세대수({new_build:,}) - 중첩제거 불가",
                "items": ["전국_연간_이사건수", "전국_신축_준공_세대수"],
            })

    return issues


def run():
    """크리틱 에이전트 메인 실행"""
    print("=" * 60)
    print("🔎 Rovothome 시장 데이터 크리틱 검토 시작")
    print("=" * 60)

    sources = load_sources()
    if not sources:
        return

    # 논리 일관성 검증
    consistency_issues = validate_logical_consistency(sources)
    # 이슈가 있는 항목 집합
    issue_items = set()
    for issue in consistency_issues:
        for item_key in issue.get("items", []):
            issue_items.add(item_key)

    validated = {}
    approved_count = 0
    warning_count = 0
    rejected_count = 0

    for key, item in sources.items():
        print(f"\n검토: {key}")

        # 출처 신뢰도
        reliability = assess_source_reliability(item)
        fresh, fresh_note = check_freshness(item)

        notes = []
        status = "approved"

        # 신뢰도 체크
        if reliability == "low":
            status = "warning"
            notes.append(f"출처 신뢰도 낮음 (비공식 출처: {item.get('source_name')})")
        elif reliability == "medium":
            notes.append(f"출처: 언론/간접출처 ({item.get('source_name')})")

        # 최신성 체크
        if not fresh:
            if status == "approved":
                status = "warning"
            notes.append(fresh_note)
        else:
            notes.append(fresh_note)

        # 논리 일관성 이슈
        if key in issue_items:
            related = [i for i in consistency_issues if key in i.get("items", [])]
            for issue in related:
                if issue["type"] == "error":
                    status = "rejected"
                    notes.append(f"논리 오류: {issue['message']}")
                else:
                    if status == "approved":
                        status = "warning"
                    notes.append(f"경고: {issue['message']}")

        # confidence 반영
        if item.get("confidence") == "low":
            if status == "approved":
                status = "warning"
            notes.append("원본 데이터 confidence가 low")

        # 카운트
        if status == "approved":
            approved_count += 1
            print(f"  ✅ 승인 | {item.get('value')} {item.get('unit')}")
        elif status == "warning":
            warning_count += 1
            print(f"  ⚠️ 경고 | {item.get('value')} {item.get('unit')}")
        else:
            rejected_count += 1
            print(f"  ❌ 거부 | {item.get('value')} {item.get('unit')}")

        for note in notes:
            print(f"     - {note}")

        validated[key] = {
            "value": item.get("value"),
            "status": status,
            "critic_note": " | ".join(notes),
            "source": item,
        }

    # 메타데이터 추가
    validated["_meta"] = {
        "validated_at": datetime.now().strftime("%Y-%m-%d"),
        "approved": approved_count,
        "warnings": warning_count,
        "rejected": rejected_count,
    }

    # validated.json 저장
    with open(VALIDATED_PATH, "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)

    # 이력 저장
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    history_path = HISTORY_DIR / f"validated_{timestamp}.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)

    # 논리 일관성 결과 출력
    if consistency_issues:
        print("\n" + "-" * 40)
        print("📋 논리 일관성 검증 결과:")
        for issue in consistency_issues:
            icon = "❌" if issue["type"] == "error" else "⚠️"
            print(f"  {icon} {issue['message']}")

    # 요약
    print("\n" + "=" * 60)
    print(f"✅ 승인: {approved_count} | ⚠️ 경고: {warning_count} | ❌ 거부: {rejected_count}")
    print(f"📁 저장: {VALIDATED_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run()
