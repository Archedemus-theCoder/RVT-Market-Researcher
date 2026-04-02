"""
Rovothome 일본 시장 데이터 크리틱 에이전트 (멀티소스 교차검증)
- sources.json (배열) 검토 → validated.json 생성
- 출처 신뢰도, 최신성, 논리 일관성, 교차검증
"""

import json
import statistics
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "jp"
SOURCES_PATH = DATA_DIR / "sources.json"
VALIDATED_PATH = DATA_DIR / "validated.json"
HISTORY_DIR = DATA_DIR / "history"

GOV_KEYWORDS = [
    "国土交通省", "総務省", "厚生労働省", "経済産業省", "観光庁",
    "不動産経済研究所", "mlit.go.jp", "stat.go.jp", "mhlw.go.jp",
    "e-stat", "高齢者住宅協会", "日本ホテル協会",
]
MEDIA_KEYWORDS = [
    "日経", "nikkei", "朝日", "読売", "矢野経済", "STR",
    "リフォーム産業", "REINS", "全日本トラック",
]

CONFIDENCE_SCORE = {"high": 3, "medium": 2, "low": 1}


def load_sources() -> dict:
    if not SOURCES_PATH.exists():
        print("❌ sources.json이 없습니다.")
        return {}
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    normalized = {}
    for key, val in data.items():
        if isinstance(val, list):
            normalized[key] = val
        elif isinstance(val, dict):
            normalized[key] = [val]
    return normalized


def assess_source_reliability(item: dict) -> str:
    combined = ((item.get("source_name") or "") + " " + (item.get("source_url") or "")).lower()
    for kw in GOV_KEYWORDS:
        if kw.lower() in combined:
            return "high"
    for kw in MEDIA_KEYWORDS:
        if kw.lower() in combined:
            return "medium"
    return "low"


def check_freshness(item: dict) -> tuple[bool, str]:
    ref_year = item.get("reference_year", "")
    try:
        year = int(ref_year)
        current_year = datetime.now().year
        if current_year - year > 2:
            return False, f"기준연도 {year}년 ({current_year - year}년 경과 ⚠️)"
        return True, f"기준연도 {year}년 (최신)"
    except (ValueError, TypeError):
        return False, "기준연도 파싱 불가"


def cross_validate(sources: list[dict]) -> dict:
    values = [s.get("value") for s in sources if isinstance(s.get("value"), (int, float))]

    if not values:
        return {"selected_value": None, "selected_source": 0, "method": "값없음",
                "all_values": [], "deviation_pct": None, "cross_note": "수집된 값 없음"}

    if len(values) == 1:
        return {"selected_value": values[0], "selected_source": 0, "method": "단일출처",
                "all_values": values, "deviation_pct": None,
                "cross_note": f"단일 출처 ({sources[0].get('source_name')}). 교차검증 불가"}

    median_val = statistics.median(values)
    max_dev = max(abs(v - median_val) / median_val * 100 for v in values) if median_val > 0 else 0

    scored = []
    for i, s in enumerate(sources):
        v = s.get("value")
        if not isinstance(v, (int, float)):
            continue
        rel = assess_source_reliability(s)
        conf = s.get("confidence", "low")
        score = CONFIDENCE_SCORE.get(rel, 0) + CONFIDENCE_SCORE.get(conf, 0)
        scored.append((i, v, score, s.get("source_name")))
    scored.sort(key=lambda x: x[2], reverse=True)

    if max_dev <= 10:
        closest_idx = min(range(len(scored)), key=lambda i: abs(scored[i][1] - median_val))
        return {"selected_value": median_val, "selected_source": scored[closest_idx][0],
                "method": "중앙값", "all_values": values, "deviation_pct": round(max_dev, 1),
                "cross_note": f"교차검증 통과 ✅ | {len(values)}개 출처 | 편차 {max_dev:.1f}%"}
    elif max_dev <= 30:
        return {"selected_value": scored[0][1], "selected_source": scored[0][0],
                "method": "최고신뢰도", "all_values": values, "deviation_pct": round(max_dev, 1),
                "cross_note": f"교차검증 주의 ⚠️ | {len(values)}개 출처 | 편차 {max_dev:.1f}%"}
    else:
        return {"selected_value": scored[0][1], "selected_source": scored[0][0],
                "method": "최고신뢰도(고편차)", "all_values": values, "deviation_pct": round(max_dev, 1),
                "cross_note": f"교차검증 경고 ❌ | {len(values)}개 출처 | 편차 {max_dev:.1f}%"}


def validate_logical_consistency(validated: dict) -> list[dict]:
    issues = []

    def _v(key):
        item = validated.get(key, {})
        return item.get("value") if isinstance(item, dict) else None

    # 3대 도시권 합산이 전국 이사건수 초과하지 않는지
    tokyo = _v("도쿄권_신축_맨션_분양호수") or 0
    osaka = _v("오사카권_신축_맨션_분양호수") or 0
    nagoya = _v("나고야권_신축_맨션_분양호수") or 0
    total_new = tokyo + osaka + nagoya

    moving = _v("3대도시권_이사건수")
    if moving is not None and moving <= total_new:
        issues.append({
            "type": "error",
            "message": f"이사건수({moving:,}) ≤ 3대도시권 신축({total_new:,})",
            "items": ["3대도시권_이사건수"],
        })

    # 풀리노베이션 비중 0~100%
    full_reno = _v("풀리노베이션_비중")
    if full_reno is not None and (full_reno < 0 or full_reno > 100):
        issues.append({
            "type": "error",
            "message": f"풀리노베이션 비중 {full_reno}% 범위 초과",
            "items": ["풀리노베이션_비중"],
        })

    return issues


def run():
    print("=" * 60)
    print("🔎 Rovothome 일본 시장 데이터 크리틱 (교차검증)")
    print("=" * 60)

    sources = load_sources()
    if not sources:
        return

    validated = {}
    approved = warning = rejected = 0

    for key, sources_list in sources.items():
        print(f"\n{'─'*40}")
        print(f"검토: {key} ({len(sources_list)}개 출처)")

        cross = cross_validate(sources_list)
        print(f"  {cross['cross_note']}")

        sel_idx = cross["selected_source"]
        sel_src = sources_list[sel_idx] if sel_idx < len(sources_list) else sources_list[0]
        sel_val = cross["selected_value"]

        reliabilities = [assess_source_reliability(s) for s in sources_list]
        best_rel = max(reliabilities, key=lambda r: CONFIDENCE_SCORE.get(r, 0))
        fresh, fresh_note = check_freshness(sel_src)

        notes = []
        status = "approved"

        if cross["method"] == "단일출처":
            notes.append("단일출처 — 교차검증 불가")
            if best_rel == "low":
                status = "warning"
        elif cross["deviation_pct"] is not None:
            if cross["deviation_pct"] > 30:
                status = "rejected"
                notes.append(f"교차검증 실패: 편차 {cross['deviation_pct']}%")
            elif cross["deviation_pct"] > 10:
                status = "warning"
                notes.append(f"교차검증 주의: 편차 {cross['deviation_pct']}%")
            else:
                notes.append(f"교차검증 통과: 편차 {cross['deviation_pct']}%")

        if not fresh:
            if status == "approved":
                status = "warning"
            notes.append(fresh_note)
        else:
            notes.append(fresh_note)

        if sel_src.get("confidence") == "low" and cross["method"] == "단일출처":
            if status == "approved":
                status = "warning"
            notes.append("원본 confidence low")

        if status == "approved":
            approved += 1
            print(f"  ✅ 승인 | {sel_val} [{cross['method']}]")
        elif status == "warning":
            warning += 1
            print(f"  ⚠️ 경고 | {sel_val} [{cross['method']}]")
        else:
            rejected += 1
            print(f"  ❌ 거부 | {sel_val} [{cross['method']}]")

        validated[key] = {
            "value": sel_val, "status": status,
            "critic_note": " | ".join(notes), "source": sel_src,
            "cross_validation": {
                "method": cross["method"], "all_values": cross["all_values"],
                "deviation_pct": cross["deviation_pct"], "num_sources": len(sources_list),
                "note": cross["cross_note"],
            },
            "all_sources": sources_list,
        }

    consistency_issues = validate_logical_consistency(validated)
    if consistency_issues:
        print(f"\n{'─'*40}\n📋 논리 일관성:")
        for issue in consistency_issues:
            print(f"  {'❌' if issue['type']=='error' else '⚠️'} {issue['message']}")

    validated["_meta"] = {
        "validated_at": datetime.now().strftime("%Y-%m-%d"),
        "approved": approved, "warnings": warning, "rejected": rejected,
        "total_sources_collected": sum(
            len(v.get("all_sources", [])) for k, v in validated.items()
            if k != "_meta" and isinstance(v, dict)
        ),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(VALIDATED_PATH, "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)

    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    with open(HISTORY_DIR / f"validated_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(validated, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 승인: {approved} | ⚠️ 경고: {warning} | ❌ 거부: {rejected}")
    print(f"📁 저장: {VALIDATED_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run()
