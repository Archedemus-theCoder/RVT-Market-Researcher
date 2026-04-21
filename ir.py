"""IR 용 포뮬러 카드 페이지.
validated.json의 FACT 수치 + 시나리오 가정을 조합해 세그먼트별 SAM 도출 경로를 카드로 표시.
"""
import json
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
VALIDATED_PATH = BASE_DIR / "data" / "validated.json"

SEG_COLORS = {
    "신축 주거":  "#2E5EAA",
    "호텔":       "#6F9CEB",
    "이사 수요":  "#F4A259",
    "리모델링":   "#C44536",
}

SCENARIO_MULT = {"보수": 0.5, "중립": 1.0, "공격": 1.5}


# ───────── 데이터 로드 ─────────
def _load_data() -> dict:
    if VALIDATED_PATH.exists():
        with open(VALIDATED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get(data: dict, key: str, default=0):
    item = data.get(key, {})
    return item.get("value", default) if isinstance(item, dict) else default


def _src(data: dict, key: str) -> tuple[str, str]:
    """(source_name, reference_year) 튜플 반환"""
    item = data.get(key, {})
    if not isinstance(item, dict):
        return ("사내 추정", "")
    src = item.get("source", {})
    name = src.get("source_name", "출처 미상")
    year = src.get("reference_year", "")
    return (name, year)


def _src_label(data: dict, key: str) -> str:
    name, year = _src(data, key)
    return f"{name}{' ('+year+')' if year else ''}"


# ───────── 세그먼트별 계산 ─────────
def _compute(data: dict, scenario: str) -> dict:
    mult = SCENARIO_MULT[scenario]

    new_units = _get(data, "전국_신축_준공_세대수", 449_835)
    sudo_pct  = _get(data, "수도권_비중", 48)
    moving    = _get(data, "전국_연간_이사건수", 6_283_000)
    hotel_new = _get(data, "신규_호텔_개관수", 135)
    hotel_avg = _get(data, "호텔_평균_객실수", 151)

    # 기본(중립) 가정치 — scenario로 침투율만 스케일
    PEN_HOUSING  = 0.10 * mult   # 신축 주거 침투율
    PEN_HOTEL    = 0.12 * mult   # 호텔 가중 침투율
    PEN_MOVING   = 0.01 * mult   # 이사 침투율
    PEN_REMODEL  = 0.15 * mult   # 리모델링 침투율
    REMODEL_UNITS = 3_000
    PRICE_HOUSING = 8_000_000    # 세트 (Ceily+Wally)
    PRICE_HOTEL   = 5_000_000
    PRICE_MOVING  = 3_000_000
    PRICE_REMODEL = 8_000_000

    # S1 신축 주거
    s1_target = int(new_units * sudo_pct / 100) + REMODEL_UNITS
    s1_reach  = int(s1_target * PEN_HOUSING)
    s1_sam    = s1_reach * PRICE_HOUSING

    # S2 호텔
    s2_rooms  = hotel_new * hotel_avg
    s2_reach  = int(s2_rooms * PEN_HOTEL)
    s2_sam    = s2_reach * PRICE_HOTEL

    # S3 이사
    s3_regional = int(moving * sudo_pct / 100)
    s3_pure     = max(s3_regional - s1_target, 0)
    s3_reach    = int(s3_pure * PEN_MOVING)
    s3_sam      = s3_reach * PRICE_MOVING

    # S4 리모델링 (S1과 별개 카드로 시각화)
    s4_reach = int(REMODEL_UNITS * PEN_REMODEL)
    s4_sam   = s4_reach * PRICE_REMODEL

    return {
        "신축 주거": {
            "sam": s1_sam,
            "rows": [
                ("전국 신축 준공 세대수",       f"{new_units:,}",        "세대", "fact",   _src_label(data, "전국_신축_준공_세대수")),
                ("×  수도권 비중",              f"{sudo_pct:.1f}",       "%",    "fact",   _src_label(data, "수도권_비중")),
                ("+  리모델링 세대수",          f"{REMODEL_UNITS:,}",    "세대", "assump", "사내 추정 (고정)"),
                ("×  침투율 (Ceily+Wally 세트)", f"{PEN_HOUSING*100:.1f}", "%",   "assump", f"시나리오: {scenario}"),
                ("×  객단가",                    f"{PRICE_HOUSING:,}",   "원",   "fact",   "사내 pricing"),
            ],
        },
        "호텔": {
            "sam": s2_sam,
            "rows": [
                ("신규 호텔 개관수",             f"{hotel_new:,}",       "개",   "fact",   _src_label(data, "신규_호텔_개관수")),
                ("×  평균 객실수",                f"{hotel_avg:,}",       "실/개", "fact", _src_label(data, "호텔_평균_객실수")),
                ("×  가중 침투율 (등급별)",       f"{PEN_HOTEL*100:.1f}",  "%",   "assump", f"시나리오: {scenario}"),
                ("×  객단가",                     f"{PRICE_HOTEL:,}",    "원",   "fact",   "사내 pricing"),
            ],
        },
        "이사 수요": {
            "sam": s3_sam,
            "rows": [
                ("연간 이사 건수",                f"{moving:,}",          "건",   "fact",   _src_label(data, "전국_연간_이사건수")),
                ("×  수도권 비중",                f"{sudo_pct:.1f}",     "%",    "fact",   _src_label(data, "수도권_비중")),
                ("−  신축 중첩 제외",             f"{s1_target:,}",      "세대", "calc",   "S1과 중복 제거"),
                ("×  침투율",                     f"{PEN_MOVING*100:.2f}", "%",  "assump", f"시나리오: {scenario}"),
                ("×  객단가",                     f"{PRICE_MOVING:,}",   "원",   "fact",   "사내 pricing"),
            ],
        },
        "리모델링": {
            "sam": s4_sam,
            "rows": [
                ("연간 리모델링 세대수",          f"{REMODEL_UNITS:,}",   "세대", "assump", "사내 추정 (고정)"),
                ("×  침투율",                     f"{PEN_REMODEL*100:.1f}", "%", "assump", f"시나리오: {scenario}"),
                ("×  객단가",                     f"{PRICE_REMODEL:,}",  "원",   "fact",   "사내 pricing"),
            ],
        },
    }


# ───────── 카드 렌더링 (HTML) ─────────
def _card_html(name: str, seg: dict, som_pct: float) -> str:
    color = SEG_COLORS[name]
    sam_eok = seg["sam"] / 1e8
    som_eok = sam_eok * som_pct / 100

    rows_html = ""
    for (lab, val, unit, kind, src) in seg["rows"]:
        if kind == "fact":
            badge_bg, badge_fg, badge_txt = "#D1FAE5", "#059669", "FACT"
        elif kind == "assump":
            badge_bg, badge_fg, badge_txt = "#FEF3C7", "#B45309", "추정"
        else:
            badge_bg, badge_fg, badge_txt = "#E5E7EB", "#374151", "계산"

        rows_html += (
            '<div class="ir-row">'
            f'<div class="ir-label">{lab}</div>'
            f'<div class="ir-value">{val}</div>'
            f'<div class="ir-unit">{unit}</div>'
            f'<div class="ir-badge" style="background:{badge_bg};color:{badge_fg}">{badge_txt}</div>'
            f'<div class="ir-source">{src}</div>'
            '</div>'
        )

    return (
        '<div class="ir-card">'
          f'<div class="ir-card-header" style="background:{color}">'
            f'<span class="ir-seg-name">{name}</span>'
            f'<span class="ir-seg-sam">SAM {sam_eok:,.0f}억원</span>'
          '</div>'
          '<div class="ir-card-body">'
            '<div class="ir-section-title">계산 경로</div>'
            f'{rows_html}'
          '</div>'
          f'<div class="ir-result" style="background:{color}1A;border-color:{color}33">'
            f'<span class="ir-result-label" style="color:{color}">= SAM</span>'
            f'<span class="ir-result-value" style="color:{color}">{sam_eok:,.0f}억원</span>'
            f'<div class="ir-result-sub">SOM 1년차 (점유율 {som_pct:.1f}%) → {som_eok:,.1f}억원</div>'
          '</div>'
        '</div>'
    )


_CARD_CSS = """
<style>
/* main.py 전역 CSS(.stApp div { color }) 를 이기기 위해 !important 사용 */
.ir-card {
    background:#FFFFFF !important;
    border:1px solid #E5E7EB;
    border-radius:12px;
    overflow:hidden;
    margin-bottom:24px;
    box-shadow:0 1px 3px rgba(0,0,0,0.08);
}
.ir-card * { color:#111827; }
.ir-card-header {
    padding:14px 24px;
    display:flex;
    justify-content:space-between;
    align-items:center;
    font-weight:700;
}
.ir-card-header * { color:#FFFFFF !important; }
.ir-seg-name { font-size:17px !important; }
.ir-seg-sam  { font-size:17px !important; }
.ir-card-body { padding:20px 24px 8px 24px; background:#FFFFFF !important; }
.ir-section-title {
    color:#6B7280 !important; font-size:12px !important; font-weight:700;
    letter-spacing:0.5px; text-transform:uppercase;
    padding-bottom:10px; border-bottom:1px solid #E5E7EB; margin-bottom:14px;
}
.ir-row {
    display:grid;
    grid-template-columns: 2fr 1.2fr 0.6fr 0.7fr 2.2fr;
    align-items:center;
    gap:12px;
    padding:11px 0;
    border-bottom:1px dashed #F3F4F6;
}
.ir-row:last-child { border-bottom:none; }
.ir-label { color:#111827 !important; font-size:14px !important; font-weight:500; }
.ir-value {
    color:#111827 !important; font-size:16px !important; font-weight:700; text-align:right;
    font-variant-numeric: tabular-nums;
}
.ir-unit   { color:#6B7280 !important; font-size:12px !important; }
.ir-badge  { font-size:10px !important; font-weight:700; padding:3px 8px; border-radius:10px; text-align:center; letter-spacing:0.5px; }
.ir-source { color:#6B7280 !important; font-size:11px !important; }

.ir-result {
    margin:12px 24px 20px 24px;
    padding:18px 20px;
    border:1px solid;
    border-radius:10px;
    display:grid;
    grid-template-columns: 1fr auto;
    align-items:center;
    row-gap:4px;
}
.ir-result-label { font-size:15px !important; font-weight:700; }
.ir-result-value {
    font-size:28px !important; font-weight:800; text-align:right;
    font-variant-numeric: tabular-nums;
}
.ir-result-sub {
    grid-column: 1 / -1; color:#6B7280 !important; font-size:11px !important;
    text-align:right;
}

/* 헤로 카드 */
.ir-hero {
    display:grid; grid-template-columns: repeat(3, 1fr); gap:16px;
    margin-bottom:28px;
}
.ir-hero-card {
    background:#FFFFFF !important; border:1px solid #E5E7EB; border-radius:12px;
    padding:22px 24px; box-shadow:0 1px 3px rgba(0,0,0,0.08);
}
.ir-hero-card * { color:#111827; }
.ir-hero-label { font-size:13px !important; font-weight:700; letter-spacing:0.8px; }
.ir-hero-value {
    font-size:40px !important; font-weight:800; color:#111827 !important; line-height:1.1;
    margin-top:6px; font-variant-numeric: tabular-nums;
}
.ir-hero-unit { font-size:13px !important; color:#6B7280 !important; margin-top:4px; }
.ir-hero-sub  { font-size:12px !important; color:#4B5563 !important; margin-top:10px; }
</style>
"""


def _hero_html(tam_eok: float, sam_eok: float, som_eok: float, som_pct: float) -> str:
    return (
        _CARD_CSS
        + '<div class="ir-hero">'
          '<div class="ir-hero-card" style="border-top:4px solid #64748B">'
            '<div class="ir-hero-label" style="color:#64748B">TAM</div>'
            f'<div class="ir-hero-value">{tam_eok/10000:.1f}</div>'
            '<div class="ir-hero-unit">조원</div>'
            '<div class="ir-hero-sub">한국 인테리어·가구 전체 시장</div>'
          '</div>'
          '<div class="ir-hero-card" style="border-top:4px solid #2E5EAA">'
            '<div class="ir-hero-label" style="color:#2E5EAA">SAM</div>'
            f'<div class="ir-hero-value">{sam_eok:,.0f}</div>'
            '<div class="ir-hero-unit">억원 · 4개 세그먼트 합산</div>'
            f'<div class="ir-hero-sub">TAM 대비 {sam_eok/tam_eok*100:.1f}%</div>'
          '</div>'
          '<div class="ir-hero-card" style="border-top:4px solid #F59E0B">'
            '<div class="ir-hero-label" style="color:#F59E0B">SOM</div>'
            f'<div class="ir-hero-value">{som_eok:,.1f}</div>'
            f'<div class="ir-hero-unit">억원 · 1년차 · 점유율 {som_pct:.1f}%</div>'
            '<div class="ir-hero-sub">실현 가능 시장</div>'
          '</div>'
        '</div>'
    )


# ───────── 메인 엔트리 ─────────
def render_ir():
    """메인 IR 페이지 렌더링."""
    data = _load_data()

    st.title("📑 IR 포뮬러 카드")
    st.caption("세그먼트별 SAM 도출 경로 — 각 숫자는 출처(FACT) 또는 사내 가정(추정)으로 명시됩니다.")

    if not data or len(data) <= 1:
        st.warning("validated.json이 비어있습니다. 먼저 데이터를 수집/검증해주세요.")
        return

    # 사이드바 컨트롤
    with st.sidebar:
        st.subheader("IR 시안 설정")
        scenario = st.radio("시나리오", ["보수", "중립", "공격"], index=1,
                            horizontal=True, key="ir_scenario",
                            help="침투율 가정에 0.5× / 1.0× / 1.5×를 적용")
        tam_tril = st.number_input("TAM (조원)", 1.0, 100.0, 15.0, 1.0, key="ir_tam",
                                    help="한국 인테리어·가구 전체 시장")
        som_pct = st.slider("SOM 점유율 (1년차, %)", 0.5, 20.0, 2.0, 0.5, key="ir_som")
        st.divider()
        st.caption(
            "**FACT** = 출처 있는 공식 통계\n\n"
            "**추정** = 사내 가정치 (시나리오로 조정)\n\n"
            "**계산** = 다른 값에서 유도"
        )

    segs = _compute(data, scenario)
    tam_eok = tam_tril * 10_000
    sam_eok = sum(s["sam"] for s in segs.values()) / 1e8
    som_eok = sam_eok * som_pct / 100

    # 헤로
    st.markdown(_hero_html(tam_eok, sam_eok, som_eok, som_pct),
                unsafe_allow_html=True)

    # 세그먼트 카드 4장
    st.markdown(f"### 세그먼트별 산출 경로 ({scenario} 시나리오)")
    for name, seg in segs.items():
        st.markdown(_card_html(name, seg, som_pct), unsafe_allow_html=True)

    # 시나리오 요약 표
    st.markdown("### 시나리오 비교")
    scenario_summary = []
    for sc in ["보수", "중립", "공격"]:
        s = _compute(data, sc)
        total_sam = sum(v["sam"] for v in s.values()) / 1e8
        scenario_summary.append({
            "시나리오": sc,
            "침투율 배수": f"× {SCENARIO_MULT[sc]:.1f}",
            "SAM (억원)": f"{total_sam:,.0f}",
            "SOM (억원)": f"{total_sam * som_pct / 100:,.1f}",
            "SAM/TAM": f"{total_sam/tam_eok*100:.2f}%",
        })
    st.dataframe(scenario_summary, hide_index=True, use_container_width=True)

    st.caption("※ 모든 숫자의 원본 출처는 '한국' 탭 하단의 validated.json 뷰어에서 확인하세요.")
