"""
Rovothome 시장규모 추정 시스템 — 한일 통합 대시보드
사이드바: 선택된 시장의 파라미터만 표시
메인: 한국/일본/비교 탭
"""

import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Rovothome 시장규모 추정",
    page_icon="🏠",
    layout="wide",
)

# ── 사이드바 폰트 축소 + 반응형 레이아웃 CSS ──
st.markdown("""
<style>
/* 반응형: 사이드바 접힐 때 메인 영역 100% */
[data-testid="stAppViewContainer"] {
    transition: margin-left 0.3s ease;
}
[data-testid="stSidebar"][aria-expanded="false"] ~ [data-testid="stAppViewContainer"] {
    margin-left: 0 !important;
}
/* 메인 컨텐츠 최대 너비 해제 */
.main .block-container {
    max-width: 100% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
[data-testid="stSidebar"] {
    min-width: 280px;
    max-width: 340px;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] span {
    font-size: 0.82rem !important;
    line-height: 1.3 !important;
}
[data-testid="stSidebar"] h2 {
    font-size: 0.95rem !important;
    margin-bottom: 0.2rem !important;
}
[data-testid="stSidebar"] h3 {
    font-size: 0.88rem !important;
    margin-bottom: 0.1rem !important;
    margin-top: 0.3rem !important;
}
[data-testid="stSidebar"] .stSlider {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
}
[data-testid="stSidebar"] .stNumberInput {
    margin-bottom: -0.5rem !important;
}
[data-testid="stSidebar"] hr {
    margin: 0.3rem 0 !important;
}
</style>
""", unsafe_allow_html=True)

BASE_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── 사이드바 상단: 시장 선택 ──
with st.sidebar:
    market = st.radio("📍 시장 선택", ["🇰🇷 한국", "🇯🇵 일본", "🌏 한일 비교"],
                      key="market_select", horizontal=True)

# ── 선택된 시장에 따라 사이드바 + 메인 컨텐츠 표시 ──
if market == "🇰🇷 한국":
    import app as kr_app
    kr_app.main()

elif market == "🇯🇵 일본":
    from japan.app_japan import render_japan
    render_japan()

else:  # 한일 비교
    st.header("🌏 한일 시장 비교")

    kr_data = load_json(BASE_DIR / "data" / "validated.json")
    jp_data = load_json(BASE_DIR / "data" / "jp" / "validated.json")

    with st.sidebar:
        exchange_rate = st.slider("환율 (원/100엔)", 700, 1200, 900, 10, key="compare_fx")

    if not kr_data or len(kr_data) <= 1:
        st.warning("한국 데이터가 없습니다.")
    if not jp_data or len(jp_data) <= 1:
        st.warning("일본 데이터가 없습니다.")

    def _v(data, key, default=0):
        item = data.get(key, {})
        return item.get("value", default) if isinstance(item, dict) else default

    # ── 데이터 추출 ──
    kr_new = _v(kr_data, "전국_신축_준공_세대수", 449835)
    kr_moving = _v(kr_data, "전국_연간_이사건수", 6283000)

    jp_tokyo = _v(jp_data, "도쿄권_신축_맨션_분양호수", 23000)
    jp_osaka = _v(jp_data, "오사카권_신축_맨션_분양호수", 15000)
    jp_nagoya = _v(jp_data, "나고야권_신축_맨션_분양호수", 6000)
    jp_new = jp_tokyo + jp_osaka + jp_nagoya
    jp_reno = _v(jp_data, "전국_리노베이션_맨션_건수", 52800)
    jp_moving = _v(jp_data, "3대도시권_이사건수", 2300000)
    jp_hotel_new = _v(jp_data, "신규_호텔_개관수", 198)
    jp_hotel_rooms = _v(jp_data, "호텔_평균_객실수", 94)
    jp_elderly_fac = _v(jp_data, "신규_고령자주거_시설수", 300)
    jp_elderly_units = _v(jp_data, "고령자주거_평균세대수", 35)

    kr_hotel_new = _v(kr_data, "신규_호텔_개관수", 80)
    kr_hotel_rooms = _v(kr_data, "호텔_평균_객실수", 150)

    # ── 1행: 신축 공급 비교 + 이사건수 비교 ──
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        st.subheader("🏗️ 신축 주거 공급량")
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(
            x=["🇰🇷 한국 (전국)", "🇯🇵 일본 (3대 도시권)"],
            y=[kr_new, jp_new],
            text=[f"{kr_new:,.0f}", f"{jp_new:,.0f}"],
            textposition="outside",
            marker_color=["#636EFA", "#EF553B"],
        ))
        fig1.update_layout(yaxis_title="세대/호", height=350, margin=dict(t=30, b=30))
        st.plotly_chart(fig1, use_container_width=True)

    with r1c2:
        st.subheader("🚚 연간 이사건수")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=["🇰🇷 한국 (전국)", "🇯🇵 일본 (3대 도시권)"],
            y=[kr_moving, jp_moving],
            text=[f"{kr_moving/10000:,.0f}만", f"{jp_moving/10000:,.0f}만"],
            textposition="outside",
            marker_color=["#636EFA", "#EF553B"],
        ))
        fig2.update_layout(yaxis_title="건", height=350, margin=dict(t=30, b=30))
        st.plotly_chart(fig2, use_container_width=True)

    # ── 2행: 호텔 비교 + 일본 도시권별 ──
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        st.subheader("🏨 호텔 신규 공급 (객실 수)")
        kr_hotel_total = kr_hotel_new * kr_hotel_rooms
        jp_hotel_total = jp_hotel_new * jp_hotel_rooms
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=["🇰🇷 한국", "🇯🇵 일본"],
            y=[kr_hotel_total, jp_hotel_total],
            text=[f"{kr_hotel_total:,.0f}실<br>({kr_hotel_new}개×{kr_hotel_rooms}실)",
                  f"{jp_hotel_total:,.0f}실<br>({jp_hotel_new}개×{jp_hotel_rooms}실)"],
            textposition="outside",
            marker_color=["#636EFA", "#EF553B"],
        ))
        fig3.update_layout(yaxis_title="객실 수", height=350, margin=dict(t=30, b=30))
        st.plotly_chart(fig3, use_container_width=True)

    with r2c2:
        st.subheader("🇯🇵 일본 도시권별 신축 맨션")
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            y=["나고야권", "오사카권", "도쿄권"],
            x=[jp_nagoya, jp_osaka, jp_tokyo],
            text=[f"{jp_nagoya:,.0f}", f"{jp_osaka:,.0f}", f"{jp_tokyo:,.0f}"],
            textposition="outside",
            orientation="h",
            marker_color=["#00CC96", "#FFA15A", "#EF553B"],
        ))
        fig4.update_layout(xaxis_title="호", height=350, margin=dict(t=30, b=30))
        st.plotly_chart(fig4, use_container_width=True)

    # ── 3행: 일본 고유 세그먼트 비교 ──
    r3c1, r3c2 = st.columns(2)

    with r3c1:
        st.subheader("🇯🇵 일본 고유 세그먼트")
        jp_segments = {
            "리노베이션": jp_reno,
            "고령자주거": jp_elderly_fac * jp_elderly_units,
        }
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(
            x=list(jp_segments.keys()),
            y=list(jp_segments.values()),
            text=[f"{v:,.0f}" for v in jp_segments.values()],
            textposition="outside",
            marker_color=["#AB63FA", "#19D3F3"],
        ))
        fig5.update_layout(yaxis_title="건/세대", height=350, margin=dict(t=30, b=30))
        st.plotly_chart(fig5, use_container_width=True)

    with r3c2:
        st.subheader("📊 데이터 신뢰도 비교")
        def count_status(data):
            a = w = r = 0
            for k, v in data.items():
                if k == "_meta" or not isinstance(v, dict):
                    continue
                s = v.get("status", "")
                if s == "approved": a += 1
                elif s == "warning": w += 1
                elif s == "rejected": r += 1
            return a, w, r

        kr_a, kr_w, kr_r = count_status(kr_data) if kr_data else (0, 0, 0)
        jp_a, jp_w, jp_r = count_status(jp_data) if jp_data else (0, 0, 0)

        fig6 = go.Figure()
        fig6.add_trace(go.Bar(name="승인", x=["🇰🇷 한국", "🇯🇵 일본"], y=[kr_a, jp_a], marker_color="#00CC96"))
        fig6.add_trace(go.Bar(name="경고", x=["🇰🇷 한국", "🇯🇵 일본"], y=[kr_w, jp_w], marker_color="#FFA15A"))
        fig6.add_trace(go.Bar(name="거부", x=["🇰🇷 한국", "🇯🇵 일본"], y=[kr_r, jp_r], marker_color="#EF553B"))
        fig6.update_layout(barmode="stack", yaxis_title="항목 수", height=350, margin=dict(t=30, b=30),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig6, use_container_width=True)

    # ── 원본 데이터 (접기) ──
    with st.expander("🇰🇷 한국 원본 데이터"):
        if kr_data:
            for key, item in kr_data.items():
                if key == "_meta" or not isinstance(item, dict):
                    continue
                src = item.get("source", {})
                st.caption(f"**{key}**: {item.get('value')} {src.get('unit', '')}")

    with st.expander("🇯🇵 일본 원본 데이터"):
        if jp_data:
            for key, item in jp_data.items():
                if key == "_meta" or not isinstance(item, dict):
                    continue
                src = item.get("source", {})
                st.caption(f"**{key}**: {item.get('value')} {src.get('unit', '')}")
