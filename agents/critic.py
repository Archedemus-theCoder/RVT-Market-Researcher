"""
Rovothome 시장 데이터 크리틱 에이전트 (멀티소스 교차검증 버전)
- sources.json (배열 형식) 검토 → validated.json 생성
- 출처 신뢰도, 최신성, 논리 일관성, 교차검증(편차 분석)
"""

import json
import statistics
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
    "mcst.go.kr", "국토부", "행정안전부", "서울시", "서울연구원",
    "한국관광협회", "한국관광공사", "e-나라지표", "index.go.kr",
    "HUG", "주택도시보증공사", "khug", "hotelrating",
]
MEDIA_KEYWORDS = ["뉴스", "신문", "일보", "경제", "매일", "헤럴드", "연합", "한경", "R114", "부동산114", "부동산R114", "로빈"]

# 신뢰도 점수 (교차검증 가중치에 사용)
CONFIDENCE_SCORE = {"high": 3, "medium": 2, "low": 1}


def load_sources() -> dict:
    """sources.json 로드 (배열 형식 또는 기존 단일 형식 모두 지원)"""
    if not SOURCES_PATH.exists():
        print("❌ sources.json이 없습니다. researcher.py를 먼저 실행해주세요.")
        return {}
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 기존 단일 형식을 배열로 변환 (하위 호환)
    normalized = {}
    for key, val in data.items():
        if isinstance(val, list):
            normalized[key] = val
        elif isinstance(val, dict):
            normalized[key] = [val]
        else:
            continue
    return normalized


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
    """최신성 검사: 기준연도가 2년 초과 오래되면 경고"""
    ref_year = item.get("reference_year", "")
    try:
        year = int(ref_year)
        current_year = datetime.now().year
        if current_year - year > 2:
            return False, f"기준연도 {year}년은 {current_year - year}년 경과 (2년 이상 경과 ⚠️)"
        return True, f"기준연도 {year}년 (최신)"
    except (ValueError, TypeError):
        return False, "기준연도 파싱 불가"


def cross_validate(sources: list[dict]) -> dict:
    """
    복수 출처 교차검증
    Returns: {
        "selected_value": 채택 값,
        "selected_source": 채택 출처 인덱스,
        "method": "단일출처/중앙값/최고신뢰도",
        "all_values": [모든 값],
        "deviation_pct": 편차율(%),
        "cross_note": 교차검증 설명
    }
    """
    values = []
    for s in sources:
        v = s.get("value")
        if v is not None and isinstance(v, (int, float)):
            values.append(v)

    if len(values) == 0:
        return {
            "selected_value": None,
            "selected_source": 0,
            "method": "값없음",
            "all_values": [],
            "deviation_pct": None,
            "cross_note": "수집된 값이 없습니다",
        }

    if len(values) == 1:
        return {
            "selected_value": values[0],
            "selected_source": 0,
            "method": "단일출처",
            "all_values": values,
            "deviation_pct": None,
            "cross_note": f"단일 출처 ({sources[0].get('source_name')}). 교차검증 불가",
        }

    # 편차 계산
    median_val = statistics.median(values)
    mean_val = statistics.mean(values)

    if median_val > 0:
        max_dev = max(abs(v - median_val) / median_val * 100 for v in values)
    else:
        max_dev = 0

    # 신뢰도 가중 점수 계산
    scored = []
    for i, s in enumerate(sources):
        v = s.get("value")
        if v is None or not isinstance(v, (int, float)):
            continue
        reliability = assess_source_reliability(s)
        conf = s.get("confidence", "low")
        # 종합 점수: 출처신뢰도 + 자체confidence
        score = CONFIDENCE_SCORE.get(reliability, 0) + CONFIDENCE_SCORE.get(conf, 0)
        scored.append((i, v, score, reliability, conf, s.get("source_name")))

    scored.sort(key=lambda x: x[2], reverse=True)

    if max_dev <= 10:
        # 편차 10% 이내: 중앙값 채택
        selected_val = median_val
        # 중앙값에 가장 가까운 출처 선택
        closest_idx = min(range(len(scored)), key=lambda i: abs(scored[i][1] - median_val))
        selected_source = scored[closest_idx][0]
        method = "중앙값"
        note = (
            f"교차검증 통과 ✅ | 출처 {len(values)}개 | "
            f"값: {values} | 중앙값: {median_val} | 최대편차: {max_dev:.1f}%"
        )
    elif max_dev <= 30:
        # 편차 10~30%: 최고 신뢰도 출처 채택 + 경고
        selected_val = scored[0][1]
        selected_source = scored[0][0]
        method = "최고신뢰도"
        note = (
            f"교차검증 주의 ⚠️ | 출처 {len(values)}개 | "
            f"값: {values} | 편차: {max_dev:.1f}% | "
            f"최고신뢰 출처 채택: {scored[0][5]} ({scored[0][1]})"
        )
    else:
        # 편차 30% 초과: 최고 신뢰도 출처 채택 + 강한 경고
        selected_val = scored[0][1]
        selected_source = scored[0][0]
        method = "최고신뢰도(고편차)"
        note = (
            f"교차검증 경고 ❌ | 출처 {len(values)}개 | "
            f"값: {values} | 편차: {max_dev:.1f}% (30% 초과!) | "
            f"최고신뢰 출처 채택: {scored[0][5]} ({scored[0][1]})"
        )

    return {
        "selected_value": selected_val,
        "selected_source": selected_source,
        "method": method,
        "all_values": values,
        "deviation_pct": round(max_dev, 1),
        "cross_note": note,
    }


def validate_logical_consistency(validated: dict) -> list[dict]:
    """논리 일관성 검증 (validated 값 기준)"""
    issues = []

    def _v(key):
        item = validated.get(key, {})
        return item.get("value") if isinstance(item, dict) else None

    # 서울 ≤ 수도권
    sudogwon = _v("수도권_비중")
    seoul = _v("서울_비중")
    if sudogwon is not None and seoul is not None and seoul > sudogwon:
        issues.append({
            "type": "error",
            "message": f"서울 비중({seoul}%)이 수도권 비중({sudogwon}%)보다 큼",
            "items": ["서울_비중", "수도권_비중"],
        })

    # 아파트 대형 + 중소형 ≈ 100%
    large = _v("아파트_대형_비중")
    small_mid = _v("아파트_중소형_비중")
    if large is not None and small_mid is not None:
        total = large + small_mid
        if abs(total - 100) > 5:
            issues.append({
                "type": "warning",
                "message": f"아파트 대형({large}%) + 중소형({small_mid}%) = {total}%",
                "items": ["아파트_대형_비중", "아파트_중소형_비중"],
            })

    # 분양가 구간 합계 ≈ 100%
    p_high = _v("분양가_10억이상_비중")
    p_mid = _v("분양가_5to10억_비중")
    p_low = _v("분양가_5억미만_비중")
    if all(v is not None for v in [p_high, p_mid, p_low]):
        total = p_high + p_mid + p_low
        if abs(total - 100) > 5:
            issues.append({
                "type": "warning",
                "message": f"분양가 구간 합계: {p_high}+{p_mid}+{p_low}={total}%",
                "items": ["분양가_10억이상_비중", "분양가_5to10억_비중", "분양가_5억미만_비중"],
            })

    # 호텔 등급 합계 ≈ 100%
    h5 = _v("호텔_5성급_비중")
    h4 = _v("호텔_4성급_비중")
    h3 = _v("호텔_3성급이하_비중")
    if all(v is not None for v in [h5, h4, h3]):
        total = h5 + h4 + h3
        if abs(total - 100) > 5:
            issues.append({
                "type": "warning",
                "message": f"호텔 등급 합계: {h5}+{h4}+{h3}={total}%",
                "items": ["호텔_5성급_비중", "호텔_4성급_비중", "호텔_3성급이하_비중"],
            })

    # 이사건수 > 신축준공세대수
    moving = _v("전국_연간_이사건수")
    new_build = _v("전국_신축_준공_세대수")
    if moving is not None and new_build is not None and moving <= new_build:
        issues.append({
            "type": "error",
            "message": f"이사건수({moving:,}) ≤ 신축준공세대수({new_build:,})",
            "items": ["전국_연간_이사건수", "전국_신축_준공_세대수"],
        })

    return issues


def run():
    """크리틱 에이전트 메인 실행"""
    print("=" * 60)
    print("🔎 Rovothome 시장 데이터 크리틱 (교차검증 포함)")
    print("=" * 60)

    sources = load_sources()
    if not sources:
        return

    validated = {}
    approved_count = 0
    warning_count = 0
    rejected_count = 0

    for key, sources_list in sources.items():
        print(f"\n{'─'*40}")
        print(f"검토: {key} ({len(sources_list)}개 출처)")

        # 1. 교차검증
        cross = cross_validate(sources_list)
        print(f"  {cross['cross_note']}")

        selected_idx = cross["selected_source"]
        selected_source = sources_list[selected_idx] if selected_idx < len(sources_list) else sources_list[0]
        selected_value = cross["selected_value"]

        # 2. 개별 출처 신뢰도 평가
        reliabilities = [assess_source_reliability(s) for s in sources_list]
        best_reliability = max(reliabilities, key=lambda r: CONFIDENCE_SCORE.get(r, 0))

        # 3. 최신성 검사 (선택된 출처 기준)
        fresh, fresh_note = check_freshness(selected_source)

        # 4. 상태 결정
        notes = []
        status = "approved"

        # 교차검증 결과 반영
        if cross["method"] == "단일출처":
            notes.append("단일출처 — 교차검증 불가")
            if best_reliability == "low":
                status = "warning"
        elif cross["deviation_pct"] is not None:
            if cross["deviation_pct"] > 30:
                status = "rejected"
                notes.append(f"교차검증 실패: 편차 {cross['deviation_pct']}% (30% 초과)")
            elif cross["deviation_pct"] > 10:
                status = "warning"
                notes.append(f"교차검증 주의: 편차 {cross['deviation_pct']}%")
            else:
                notes.append(f"교차검증 통과: 편차 {cross['deviation_pct']}%")

        # 출처 신뢰도
        if best_reliability == "low":
            if status == "approved":
                status = "warning"
            notes.append(f"출처 신뢰도 낮음")
        elif best_reliability == "medium":
            notes.append(f"출처: 간접출처")

        # 최신성
        if not fresh:
            if status == "approved":
                status = "warning"
            notes.append(fresh_note)
        else:
            notes.append(fresh_note)

        # confidence
        if selected_source.get("confidence") == "low" and cross["method"] == "단일출처":
            if status == "approved":
                status = "warning"
            notes.append("원본 confidence low")

        # 카운트
        if status == "approved":
            approved_count += 1
            print(f"  ✅ 승인 | {selected_value} {selected_source.get('unit')} [{cross['method']}]")
        elif status == "warning":
            warning_count += 1
            print(f"  ⚠️ 경고 | {selected_value} {selected_source.get('unit')} [{cross['method']}]")
        else:
            rejected_count += 1
            print(f"  ❌ 거부 | {selected_value} {selected_source.get('unit')} [{cross['method']}]")

        for note in notes:
            print(f"     - {note}")

        # validated 항목 저장
        validated[key] = {
            "value": selected_value,
            "status": status,
            "critic_note": " | ".join(notes),
            "source": selected_source,
            "cross_validation": {
                "method": cross["method"],
                "all_values": cross["all_values"],
                "deviation_pct": cross["deviation_pct"],
                "num_sources": len(sources_list),
                "note": cross["cross_note"],
            },
            "all_sources": sources_list,
        }

    # 논리 일관성 검증
    consistency_issues = validate_logical_consistency(validated)
    if consistency_issues:
        print(f"\n{'─'*40}")
        print("📋 논리 일관성 검증:")
        issue_items = set()
        for issue in consistency_issues:
            for item_key in issue.get("items", []):
                issue_items.add(item_key)
            icon = "❌" if issue["type"] == "error" else "⚠️"
            print(f"  {icon} {issue['message']}")

        # 상태 업데이트
        for key in issue_items:
            if key in validated:
                related = [i for i in consistency_issues if key in i.get("items", [])]
                for issue in related:
                    if issue["type"] == "error":
                        validated[key]["status"] = "rejected"
                        rejected_count += 1
                        # approved나 warning이었으면 카운트 조정
                    else:
                        if validated[key]["status"] == "approved":
                            validated[key]["status"] = "warning"
                    validated[key]["critic_note"] += f" | 논리검증: {issue['message']}"

    # 메타데이터
    validated["_meta"] = {
        "validated_at": datetime.now().strftime("%Y-%m-%d"),
        "approved": approved_count,
        "warnings": warning_count,
        "rejected": rejected_count,
        "total_sources_collected": sum(
            len(v.get("all_sources", [])) for k, v in validated.items()
            if k != "_meta" and isinstance(v, dict)
        ),
    }

    # 저장
    with open(VALIDATED_PATH, "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    with open(HISTORY_DIR / f"validated_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)

    # 요약
    print("\n" + "=" * 60)
    print(f"✅ 승인: {approved_count} | ⚠️ 경고: {warning_count} | ❌ 거부: {rejected_count}")
    total_src = validated["_meta"]["total_sources_collected"]
    print(f"📊 총 수집 출처: {total_src}개")
    print(f"📁 저장: {VALIDATED_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run()
