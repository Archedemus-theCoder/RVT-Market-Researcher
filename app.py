"""
Rovothome 한국 시장규모 추정 대시보드
- validated.json 기반 세그먼트별 SAM 계산
- Streamlit + Plotly 시각화
"""

import json
import subprocess
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VALIDATED_PATH = DATA_DIR / "validated.json"

# set_page_config는 main.py에서 호출 (단독 실행 시에만 여기서)
if __name__ == "__main__":
    st.set_page_config(page_title="Rovothome 시장규모 추정", page_icon="🏠", layout="wide")


# ─────────── 데이터 로드 ───────────
def load_validated() -> dict:
    if VALIDATED_PATH.exists():
        with open(VALIDATED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_val(data: dict, key: str, default=0):
    """validated.json에서 값 추출"""
    item = data.get(key, {})
    return item.get("value", default) if isinstance(item, dict) else default


def get_status(data: dict, key: str) -> str:
    item = data.get(key, {})
    return item.get("status", "unknown") if isinstance(item, dict) else "unknown"


def confidence_dots(data: dict, keys: list[str]) -> str:
    """신뢰도 점수를 ●○ 형태로 표시 (approved=1.0, warning=0.5, rejected=0)"""
    statuses = [get_status(data, k) for k in keys]
    weight = sum(1.0 if s == "approved" else 0.5 if s == "warning" else 0 for s in statuses)
    total = len(statuses)
    if total == 0:
        return "○○○○○"
    score = round(weight / total * 5)
    return "●" * score + "○" * (5 - score)


def has_warnings(data: dict, keys: list[str]) -> bool:
    return any(get_status(data, k) == "warning" for k in keys)


def ref_year(data: dict, keys: list[str]) -> str:
    """대표 기준연도 반환"""
    years = set()
    for k in keys:
        item = data.get(k, {})
        if isinstance(item, dict):
            src = item.get("source", {})
            y = src.get("reference_year", "")
            if y:
                years.add(y)
    return ", ".join(sorted(years)) if years else "N/A"


# ─────────── 메인 ───────────
def main(visible=True):
    data = load_validated()
    meta = data.get("_meta", {})

    # ─────────── 사이드바 ───────────
    with st.sidebar:
        st.header("⚙️ 파라미터 설정")

        # 세그먼트 1: 신축 주거
        st.subheader("세그먼트 1: 신축 주거")
        region = st.radio("지역 범위", ["전국", "수도권", "서울"], index=0, key="region")

        # 3×3 면적×가격 매트릭스 (추정 비중, %)
        # 기본값: HUG+R114+국토부 데이터 조합 추정
        # 행=가격대, 열=면적
        st.markdown("**면적×가격 분포 비중 (%)**")
        st.caption("행: 가격대 / 열: 면적 (합계 100%)")

        SIZE_LABELS = ["59㎡이하", "60~84㎡", "85㎡초과"]
        PRICE_LABELS = ["10억 이상", "5~10억", "5억 미만"]
        # 기본값 매트릭스 [가격][면적] — 리서치 기반 추정
        DEFAULT_MATRIX = [
            [4.0, 11.0, 7.0],   # 10억 이상
            [12.0, 27.0, 9.0],  # 5~10억
            [11.0, 14.0, 5.0],  # 5억 미만
        ]

        # 헤더
        hcols = st.columns([1.2, 1, 1, 1])
        hcols[0].markdown("**가격＼면적**")
        for j, sl in enumerate(SIZE_LABELS):
            hcols[j + 1].markdown(f"**{sl}**")

        matrix_pct = []  # 3×3 비중
        for i, pl in enumerate(PRICE_LABELS):
            row_cols = st.columns([1.2, 1, 1, 1])
            row_cols[0].markdown(f"**{pl}**")
            row = []
            for j, sl in enumerate(SIZE_LABELS):
                val = row_cols[j + 1].number_input(
                    f"{pl}_{sl}", min_value=0.0, max_value=50.0,
                    value=DEFAULT_MATRIX[i][j], step=0.5,
                    key=f"mx_{i}_{j}", label_visibility="collapsed",
                )
                row.append(val)
            matrix_pct.append(row)

        matrix_total = sum(v for row in matrix_pct for v in row)
        if abs(matrix_total - 100) > 1:
            st.warning(f"합계: {matrix_total:.1f}% (100%와 차이)")
        else:
            st.caption(f"합계: {matrix_total:.1f}%")

        st.divider()

        # Ceily 도입확률 3×3
        st.markdown("**Ceily 도입확률 (%) — 9칸 개별**")
        DEFAULT_CEILY = [
            [20.0, 15.0, 12.0],  # 10억 이상
            [10.0, 8.0, 5.0],    # 5~10억
            [3.0, 2.0, 1.0],     # 5억 미만
        ]
        hcols2 = st.columns([1.2, 1, 1, 1])
        hcols2[0].markdown("**가격＼면적**")
        for j, sl in enumerate(SIZE_LABELS):
            hcols2[j + 1].markdown(f"**{sl}**")

        ceily_matrix = []
        for i, pl in enumerate(PRICE_LABELS):
            row_cols = st.columns([1.2, 1, 1, 1])
            row_cols[0].markdown(f"**{pl}**")
            row = []
            for j, sl in enumerate(SIZE_LABELS):
                val = row_cols[j + 1].number_input(
                    f"C_{pl}_{sl}", min_value=0.0, max_value=100.0,
                    value=DEFAULT_CEILY[i][j], step=0.5,
                    key=f"cp_{i}_{j}", label_visibility="collapsed",
                )
                row.append(val)
            ceily_matrix.append(row)

        st.divider()

        # Wally 도입확률 3×3
        st.markdown("**Wally 도입확률 (%) — 9칸 개별**")
        DEFAULT_WALLY = [
            [25.0, 20.0, 15.0],  # 10억 이상
            [15.0, 12.0, 8.0],   # 5~10억
            [5.0, 4.0, 2.0],     # 5억 미만
        ]
        hcols3 = st.columns([1.2, 1, 1, 1])
        hcols3[0].markdown("**가격＼면적**")
        for j, sl in enumerate(SIZE_LABELS):
            hcols3[j + 1].markdown(f"**{sl}**")

        wally_matrix = []
        for i, pl in enumerate(PRICE_LABELS):
            row_cols = st.columns([1.2, 1, 1, 1])
            row_cols[0].markdown(f"**{pl}**")
            row = []
            for j, sl in enumerate(SIZE_LABELS):
                val = row_cols[j + 1].number_input(
                    f"W_{pl}_{sl}", min_value=0.0, max_value=100.0,
                    value=DEFAULT_WALLY[i][j], step=0.5,
                    key=f"wp_{i}_{j}", label_visibility="collapsed",
                )
                row.append(val)
            wally_matrix.append(row)

        st.divider()

        # 세그먼트 2: 호텔
        st.subheader("세그먼트 2: 호텔")
        st.markdown("**Ceily 도입확률 (%)**")
        ceily_hotel_5 = st.slider("5성급", 0.0, 100.0, 30.0, 1.0, key="ch5")
        ceily_hotel_4 = st.slider("4성급", 0.0, 100.0, 15.0, 1.0, key="ch4")
        ceily_hotel_3 = st.slider("3성급 이하", 0.0, 100.0, 5.0, 1.0, key="ch3")

        st.markdown("**Wally 도입확률 (%)**")
        wally_hotel_5 = st.slider("5성급", 0.0, 100.0, 40.0, 1.0, key="wh5")
        wally_hotel_4 = st.slider("4성급", 0.0, 100.0, 20.0, 1.0, key="wh4")
        wally_hotel_3 = st.slider("3성급 이하", 0.0, 100.0, 8.0, 1.0, key="wh3")

        st.divider()

        # 세그먼트 3: 이사수요
        st.subheader("세그먼트 3: 이사수요")
        moving_ratio = st.slider("신축 대비 도입률 비율 (%)", 5.0, 50.0, 20.0, 1.0, key="mv_ratio")

        st.divider()

        # 리모델링 (S1에 포함, 참고 표시)
        st.subheader("참고: 리모델링")
        remodel_units = st.number_input("연간 리모델링 세대수", 0, 100000, 3000, 500, key="remodel_units",
                                         help="S1 모수에 합산됨")
        st.caption("※ 리모델링은 신축 주거 모수에 포함하여 계산")

        st.divider()

        # 제품 단가
        st.subheader("💰 제품 단가")
        ceily_price = st.slider("Ceily 단가 (만원)", 100, 2000, 500, 50, key="ceily_price")
        wally_price = st.slider("Wally 단가 (만원)", 100, 2000, 300, 50, key="wally_price")
        product_combo = st.radio("제품 조합", ["Ceily + Wally", "Ceily만", "Wally만"], key="combo")

        st.divider()

        # TAM / 성장률 / SOM
        st.subheader("📈 TAM / 성장 / SOM")
        tam_billion = st.number_input("TAM (조원)", 1.0, 100.0, 15.0, 1.0, key="tam_kr",
                                       help="한국 전체 인테리어/가구 시장규모")
        growth_rate = st.slider("연간 시장 성장률 (%)", -5.0, 15.0, 3.0, 0.5, key="growth")
        som_y1 = st.slider("SOM 1년차 점유율 (%)", 0.5, 30.0, 2.0, 0.5, key="som_y1")
        som_y5 = st.slider("SOM 5년차 점유율 (%)", 1.0, 50.0, 15.0, 1.0, key="som_y5")

        st.divider()

        # 에이전트 실행 (비밀번호 보호)
        st.subheader("🤖 데이터 관리")
        admin_pw = st.text_input("관리자 비밀번호", type="password", key="kr_admin_pw")

        def _check_pw(pw):
            try:
                return pw == st.secrets["ADMIN_PASSWORD"]
            except (KeyError, FileNotFoundError):
                return pw == "rovothome2026"  # fallback (로컬 개발용)

        if admin_pw:
            if _check_pw(admin_pw):
                st.success("🔓 인증 완료")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔍 리서처 실행", use_container_width=True):
                        with st.spinner("데이터 수집 중..."):
                            result = subprocess.run(
                                [sys.executable, str(BASE_DIR / "agents" / "researcher.py")],
                                capture_output=True, text=True, cwd=str(BASE_DIR),
                            )
                            st.text(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                            if result.returncode != 0:
                                st.error(result.stderr[-300:])
                with col_b:
                    if st.button("🔎 크리틱 검토", use_container_width=True):
                        with st.spinner("검증 중..."):
                            result = subprocess.run(
                                [sys.executable, str(BASE_DIR / "agents" / "critic.py")],
                                capture_output=True, text=True, cwd=str(BASE_DIR),
                            )
                            st.text(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                            if result.returncode != 0:
                                st.error(result.stderr[-300:])
            else:
                st.error("🔒 비밀번호가 올바르지 않습니다")
        else:
            st.caption("🔒 데이터 갱신은 관리자 비밀번호가 필요합니다")

        # 마지막 갱신
        validated_at = meta.get("validated_at", "N/A")
        st.caption(f"마지막 데이터 갱신: {validated_at}")

    # 비활성 탭이면 사이드바 위젯만 생성하고 종료 (state 유지)
    if not visible:
        return

    st.title("🏠 Rovothome 한국 시장규모 추정 시스템")

    if not data or len(data) <= 1:
        st.warning("⚠️ 검증된 데이터가 없습니다. 사이드바에서 '리서처 실행' → '크리틱 검토'를 순서대로 실행해주세요.")

    # ─────────── 계산 로직 ───────────
    # 지역 비중
    if region == "수도권":
        region_ratio = get_val(data, "수도권_비중", 50) / 100
    elif region == "서울":
        region_ratio = get_val(data, "서울_비중", 15) / 100
    else:
        region_ratio = 1.0

    # 세그먼트 1: 신축 주거 (3×3 매트릭스 기반)
    new_build_total = get_val(data, "전국_신축_준공_세대수", 300000)
    seg1_base = new_build_total * region_ratio + remodel_units

    # 3×3 세대수 매트릭스 계산
    units_matrix = []  # [가격][면적] = 세대수
    for i in range(3):
        row = []
        for j in range(3):
            units = seg1_base * (matrix_pct[i][j] / 100) if matrix_total > 0 else 0
            row.append(units)
        units_matrix.append(row)

    # 세대수 표시 (사이드바)
    with st.sidebar:
        st.markdown("**📊 셀별 추정 세대수**")
        ucols = st.columns([1.2, 1, 1, 1])
        ucols[0].markdown("**가격＼면적**")
        for j, sl in enumerate(SIZE_LABELS):
            ucols[j + 1].markdown(f"**{sl}**")
        for i, pl in enumerate(PRICE_LABELS):
            rcols = st.columns([1.2, 1, 1, 1])
            rcols[0].markdown(f"**{pl}**")
            for j in range(3):
                rcols[j + 1].caption(f"{units_matrix[i][j]:,.0f}")
        st.caption(f"총 모수: **{seg1_base:,.0f}세대** ({region})")
        st.divider()

    # SAM 계산 (9칸 개별)
    ceily_sam1 = 0
    wally_sam1 = 0
    total_weighted_ceily = 0
    total_weighted_wally = 0

    for i in range(3):
        for j in range(3):
            units = units_matrix[i][j]
            c_prob = ceily_matrix[i][j] / 100
            w_prob = wally_matrix[i][j] / 100
            if product_combo != "Wally만":
                ceily_sam1 += units * c_prob * ceily_price
                total_weighted_ceily += units * c_prob
            if product_combo != "Ceily만":
                wally_sam1 += units * w_prob * wally_price
                total_weighted_wally += units * w_prob

    sam1 = ceily_sam1 + wally_sam1  # 만원

    # 가중평균 도입확률 (세그먼트3 계산에 사용)
    avg_adoption_rate = (total_weighted_ceily + total_weighted_wally) / (2 * seg1_base) if seg1_base > 0 else 0

    # 세그먼트 2: 호텔
    hotel_new = get_val(data, "신규_호텔_개관수", 30)
    hotel_rooms = get_val(data, "호텔_평균_객실수", 150)
    seg2_base = hotel_new * hotel_rooms

    h5_r = get_val(data, "호텔_5성급_비중", 15) / 100
    h4_r = get_val(data, "호텔_4성급_비중", 30) / 100
    h3_r = get_val(data, "호텔_3성급이하_비중", 55) / 100

    ceily_sam2 = 0
    wally_sam2 = 0
    for grade_r, c_prob, w_prob in [
        (h5_r, ceily_hotel_5 / 100, wally_hotel_5 / 100),
        (h4_r, ceily_hotel_4 / 100, wally_hotel_4 / 100),
        (h3_r, ceily_hotel_3 / 100, wally_hotel_3 / 100),
    ]:
        rooms = seg2_base * grade_r
        if product_combo != "Wally만":
            ceily_sam2 += rooms * c_prob * ceily_price
        if product_combo != "Ceily만":
            wally_sam2 += rooms * w_prob * wally_price

    sam2 = ceily_sam2 + wally_sam2

    # 세그먼트 3: 이사 수요
    moving_total = get_val(data, "전국_연간_이사건수", 5000000)
    moving_regional = moving_total * region_ratio  # 지역 비중 적용
    pure_moving = max(moving_regional - seg1_base, 0)
    moving_adoption = avg_adoption_rate * (moving_ratio / 100)

    # 현재 적용 확률 표시
    with st.sidebar:
        st.caption(f"이사 모수: {moving_regional:,.0f} - {seg1_base:,.0f} = {pure_moving:,.0f}건 ({region})")
        st.caption(f"현재 이사 도입확률: {moving_adoption * 100:.2f}%")

    ceily_sam3 = 0
    wally_sam3 = 0
    if product_combo != "Wally만":
        ceily_sam3 = pure_moving * moving_adoption * ceily_price
    if product_combo != "Ceily만":
        wally_sam3 = pure_moving * moving_adoption * wally_price
    sam3 = ceily_sam3 + wally_sam3

    # 총합 (만원 → 억원) — 리모델링은 S1에 통합됨
    total_sam = (sam1 + sam2 + sam3) / 10000
    ceily_total = (ceily_sam1 + ceily_sam2 + ceily_sam3) / 10000
    wally_total = (wally_sam1 + wally_sam2 + wally_sam3) / 10000

    # ─────────── 상단: TAM → SAM → SOM ───────────
    tam_value = tam_billion * 10000  # 조원 → 억원
    som_current = total_sam * (som_y1 / 100)
    st.markdown(f"**TAM** {tam_value:,.0f}억원 → **SAM** {total_sam:,.0f}억원 ({total_sam/tam_value*100:.1f}%) → **SOM** {som_current:,.0f}억원 ({som_y1:.0f}%)")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("TAM", f"{tam_billion:,.0f} 조원")
    with col2:
        st.metric("총 SAM", f"{total_sam:,.0f} 억원")
    with col3:
        st.metric("Ceily SAM", f"{ceily_total:,.0f} 억원")
    with col4:
        st.metric("Wally SAM", f"{wally_total:,.0f} 억원")
    with col5:
        st.metric(f"SOM ({som_y1:.0f}%)", f"{som_current:,.0f} 억원")

    # ─────────── 중단: 차트 ───────────
    seg_labels = ["신축 주거 (리모델링 포함)", "호텔", "이사 수요"]
    seg_values = [sam1 / 10000, sam2 / 10000, sam3 / 10000]
    seg1_keys = ["전국_신축_준공_세대수", "수도권_비중", "서울_비중", "아파트_대형_비중",
                 "아파트_중소형_비중", "오피스텔_비중", "분양가_10억이상_비중",
                 "분양가_5to10억_비중", "분양가_5억미만_비중"]
    seg2_keys = ["신규_호텔_개관수", "호텔_평균_객실수", "호텔_5성급_비중",
                 "호텔_4성급_비중", "호텔_3성급이하_비중"]
    seg3_keys = ["전국_연간_이사건수"]

    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("세그먼트별 SAM 구성")
        fig_pie = px.pie(
            names=seg_labels,
            values=seg_values,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_pie.update_traces(textposition="inside", textinfo="label+percent+value",
                              texttemplate="%{label}<br>%{value:,.0f}억원<br>(%{percent})")
        st.plotly_chart(fig_pie, use_container_width=True)

        # 데이터 신뢰도 카드
        for label, keys, sam_val in [
            ("신축 주거", seg1_keys, seg_values[0]),
            ("호텔", seg2_keys, seg_values[1]),
            ("이사 수요", seg3_keys, seg_values[2]),
        ]:
            warn = has_warnings(data, keys)
            warn_icon = " ⚠️" if warn else " ✅"
            msg = f"**{label}{warn_icon}** — 데이터 기준: {ref_year(data, keys)}년 | 신뢰도: {confidence_dots(data, keys)}"
            if warn:
                st.warning(msg)
            else:
                st.success(msg)

    with chart_col2:
        st.subheader("Ceily vs Wally 세그먼트별 SAM")
        ceily_vals = [ceily_sam1 / 10000, ceily_sam2 / 10000, ceily_sam3 / 10000]
        wally_vals = [wally_sam1 / 10000, wally_sam2 / 10000, wally_sam3 / 10000]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(name="Ceily", x=seg_labels, y=ceily_vals,
                                 marker_color="#636EFA", text=[f"{v:,.0f}" for v in ceily_vals],
                                 textposition="inside"))
        fig_bar.add_trace(go.Bar(name="Wally", x=seg_labels, y=wally_vals,
                                 marker_color="#EF553B", text=[f"{v:,.0f}" for v in wally_vals],
                                 textposition="inside"))
        fig_bar.update_layout(barmode="stack", yaxis_title="억원",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig_bar, use_container_width=True)

    # ─────────── 하단: 성장 추이 & 민감도 ───────────
    bottom_col1, bottom_col2 = st.columns(2)

    with bottom_col1:
        st.subheader("📈 2026~2030 TAM / SAM / SOM 추이")
        years = list(range(2026, 2031))
        growth_factor = [(1 + growth_rate / 100) ** (y - 2026) for y in years]
        tam_trend = [tam_value * g for g in growth_factor]
        total_trend = [total_sam * g for g in growth_factor]

        # SOM: 1년차(2026)→5년차(2030) 선형 보간
        som_rates = [som_y1 + (som_y5 - som_y1) * i / 4 for i in range(5)]
        som_trend = [total_trend[i] * som_rates[i] / 100 for i in range(5)]

        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=years, y=tam_trend, name="TAM",
                                      mode="lines", line=dict(width=1, color="#999", dash="dash")))
        fig_line.add_trace(go.Scatter(x=years, y=total_trend, name="SAM",
                                      mode="lines+markers", line=dict(width=2, color="#636EFA")))
        fig_line.add_trace(go.Scatter(x=years, y=som_trend, name="SOM",
                                      mode="lines+markers+text", line=dict(width=3, color="#EF553B"),
                                      text=[f"{v:,.0f}" for v in som_trend],
                                      textposition="top center", textfont=dict(size=10)))
        fig_line.update_layout(yaxis_title="억원", xaxis_title="연도",
                               legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig_line, use_container_width=True)

        som_df = pd.DataFrame({
            "연도": years,
            "TAM (억원)": [f"{v:,.0f}" for v in tam_trend],
            "SAM (억원)": [f"{v:,.0f}" for v in total_trend],
            "점유율": [f"{r:.1f}%" for r in som_rates],
            "SOM (억원)": [f"{v:,.0f}" for v in som_trend],
        })
        st.dataframe(som_df, use_container_width=True, hide_index=True)

    with bottom_col2:
        st.subheader("📊 도입확률 민감도 분석")
        st.caption("도입확률 ±50% 변화 시 SAM 범위")

        sensitivity_data = []
        for factor, label in [(0.5, "-50%"), (0.75, "-25%"), (1.0, "기준"), (1.25, "+25%"), (1.5, "+50%")]:
            # 세그먼트1 재계산 (간이)
            adj_ceily1 = ceily_sam1 * factor
            adj_wally1 = wally_sam1 * factor
            adj_ceily2 = ceily_sam2 * factor
            adj_wally2 = wally_sam2 * factor
            adj_ceily3 = ceily_sam3 * factor
            adj_wally3 = wally_sam3 * factor
            adj_total = (adj_ceily1 + adj_wally1 + adj_ceily2 + adj_wally2 +
                         adj_ceily3 + adj_wally3) / 10000
            sensitivity_data.append({"변화율": label, "총 SAM (억원)": adj_total})

        df_sens = pd.DataFrame(sensitivity_data)
        fig_sens = px.bar(df_sens, x="변화율", y="총 SAM (억원)",
                          color="변화율",
                          color_discrete_sequence=["#ff6b6b", "#ffa07a", "#4ecdc4", "#45b7d1", "#2196f3"])
        fig_sens.update_layout(showlegend=False)
        st.plotly_chart(fig_sens, use_container_width=True)

        # 범위 표시
        min_sam = sensitivity_data[0]["총 SAM (억원)"]
        max_sam = sensitivity_data[-1]["총 SAM (억원)"]
        st.info(f"SAM 범위: **{min_sam:,.0f}** ~ **{max_sam:,.0f}** 억원")

    # ─────────── 세부 데이터 테이블 ───────────
    with st.expander("📋 세부 계산 내역"):
        st.markdown("#### 세그먼트 1: 신축 주거 (3×3 매트릭스)")
        st.write(f"- 모수: {new_build_total:,.0f} × {region_ratio:.0%} = **{seg1_base:,.0f}세대** ({region})")

        # 세대수 테이블
        df_units = pd.DataFrame(
            [[f"{units_matrix[i][j]:,.0f}" for j in range(3)] for i in range(3)],
            columns=SIZE_LABELS, index=PRICE_LABELS,
        )
        st.markdown("**셀별 세대수:**")
        st.dataframe(df_units, use_container_width=True)

        # Ceily SAM 기여 테이블
        df_ceily = pd.DataFrame(
            [[f"{units_matrix[i][j] * ceily_matrix[i][j] / 100 * ceily_price / 10000:,.1f}" for j in range(3)] for i in range(3)],
            columns=SIZE_LABELS, index=PRICE_LABELS,
        )
        st.markdown("**Ceily 셀별 SAM (억원):**")
        st.dataframe(df_ceily, use_container_width=True)

        st.write(f"- Ceily SAM1: **{ceily_sam1/10000:,.0f}억원** | Wally SAM1: **{wally_sam1/10000:,.0f}억원**")
        st.caption(f"※ 리모델링 {remodel_units:,}세대가 모수에 포함되어 있음")

        st.markdown("#### 세그먼트 2: 호텔")
        st.write(f"- 모수: {hotel_new}개 × {hotel_rooms}실 = **{seg2_base:,}실**")
        st.write(f"- Ceily SAM2: **{ceily_sam2/10000:,.0f}억원** | Wally SAM2: **{wally_sam2/10000:,.0f}억원**")

        st.markdown("#### 세그먼트 3: 이사 수요")
        st.write(f"- 이사건수({region}): {moving_total:,.0f} × {region_ratio:.0%} = {moving_regional:,.0f}건")
        st.write(f"- 순수이사수요: {moving_regional:,.0f} - {seg1_base:,.0f} = **{pure_moving:,.0f}건**")
        st.write(f"- 도입확률: {avg_adoption_rate:.4f} × {moving_ratio:.0f}% = **{moving_adoption*100:.2f}%**")
        st.write(f"- Ceily SAM3: **{ceily_sam3/10000:,.0f}억원** | Wally SAM3: **{wally_sam3/10000:,.0f}억원**")

    # ─────────── 원본 데이터 확인 ───────────
    with st.expander("🔍 검증된 데이터 원본 (validated.json)"):
        for key, item in data.items():
            if key == "_meta":
                continue
            if not isinstance(item, dict):
                continue
            status = item.get("status", "")
            icon = {"approved": "✅", "warning": "⚠️", "rejected": "❌"}.get(status, "❓")
            source = item.get("source", {})
            cross = item.get("cross_validation", {})
            num_src = cross.get("num_sources", 1)
            method = cross.get("method", "")
            dev = cross.get("deviation_pct")

            # 메인 라인
            dev_str = f" | 편차: {dev}%" if dev is not None else ""
            st.markdown(
                f"**{icon} {key}**: {item.get('value')} {source.get('unit', '')} "
                f"— {source.get('source_name', 'N/A')} ({source.get('reference_year', 'N/A')}년) "
                f"[{method}, {num_src}개 출처{dev_str}]"
            )

            # 크리틱 노트
            if item.get("critic_note"):
                st.caption(f"   크리틱: {item['critic_note']}")

            # 교차검증: 모든 출처 표시
            all_sources = item.get("all_sources", [])
            if len(all_sources) > 1:
                for j, src in enumerate(all_sources):
                    marker = "→" if j == cross.get("selected_source", 0) else "  "
                    st.caption(
                        f"   {marker} 출처{j+1}: {src.get('value')} {src.get('unit', '')} "
                        f"({src.get('source_name', '')}, {src.get('reference_year', '')}년, "
                        f"신뢰도: {src.get('confidence', '')})"
                    )

    # ─────────── 리포트 다운로드 ───────────
    with st.sidebar:
        st.divider()
        report = generate_report(
            total_sam, ceily_total, wally_total,
            seg_labels, seg_values, ceily_vals, wally_vals,
            data, meta, region, growth_rate,
        )
        st.download_button(
            "📥 리포트 다운로드 (MD)",
            data=report,
            file_name=f"rovothome_market_report_{datetime.now().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            use_container_width=True,
        )


def generate_report(
    total_sam, ceily_total, wally_total,
    seg_labels, seg_values, ceily_vals, wally_vals,
    data, meta, region, growth_rate,
) -> str:
    """마크다운 리포트 생성"""
    lines = [
        "# Rovothome 한국 시장규모 추정 리포트",
        f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"데이터 검증일: {meta.get('validated_at', 'N/A')}",
        "",
        "## 요약",
        f"- **총 SAM**: {total_sam:,.0f} 억원",
        f"- **Ceily SAM**: {ceily_total:,.0f} 억원",
        f"- **Wally SAM**: {wally_total:,.0f} 억원",
        f"- **지역 범위**: {region}",
        f"- **성장률**: {growth_rate}%/년",
        "",
        "## 세그먼트별 SAM",
    ]
    for label, total, ceily, wally in zip(seg_labels, seg_values, ceily_vals, wally_vals):
        lines.append(f"### {label}")
        lines.append(f"- 합계: {total:,.0f} 억원 (Ceily: {ceily:,.0f}, Wally: {wally:,.0f})")

    lines.append("")
    lines.append("## 데이터 출처")
    for key, item in data.items():
        if key == "_meta" or not isinstance(item, dict):
            continue
        source = item.get("source", {})
        status = item.get("status", "")
        lines.append(
            f"- **{key}**: {item.get('value')} {source.get('unit', '')} "
            f"[{status}] (출처: {source.get('source_name', 'N/A')}, "
            f"{source.get('reference_year', 'N/A')}년)"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    main()
