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
    kr_sudogwon_pct = _v(kr_data, "수도권_비중", 48) / 100
    kr_seoul_pct = _v(kr_data, "서울_비중", 12) / 100
    kr_seoul = kr_new * kr_seoul_pct
    kr_sudogwon_rest = kr_new * kr_sudogwon_pct - kr_seoul  # 수도권(서울 제외)
    kr_local = kr_new * (1 - kr_sudogwon_pct)  # 지방

    kr_moving = _v(kr_data, "전국_연간_이사건수", 6283000)
    kr_moving_seoul = kr_moving * kr_seoul_pct
    kr_moving_sudo = kr_moving * kr_sudogwon_pct - kr_moving_seoul
    kr_moving_local = kr_moving * (1 - kr_sudogwon_pct)

    jp_tokyo = _v(jp_data, "도쿄권_신축_맨션_분양호수", 23000)
    jp_osaka = _v(jp_data, "오사카권_신축_맨션_분양호수", 15000)
    jp_nagoya = _v(jp_data, "나고야권_신축_맨션_분양호수", 6000)
    jp_new = jp_tokyo + jp_osaka + jp_nagoya
    jp_reno = _v(jp_data, "전국_리노베이션_맨션_건수", 52800)
    jp_moving = _v(jp_data, "3대도시권_이사건수", 2300000)
    # 이사건수 도시권 배분 (신축 비중 기반)
    jp_mv_tokyo = jp_moving * (jp_tokyo / jp_new) if jp_new > 0 else 0
    jp_mv_osaka = jp_moving * (jp_osaka / jp_new) if jp_new > 0 else 0
    jp_mv_nagoya = jp_moving * (jp_nagoya / jp_new) if jp_new > 0 else 0

    jp_hotel_new = _v(jp_data, "신규_호텔_개관수", 198)
    jp_hotel_rooms = _v(jp_data, "호텔_평균_객실수", 94)
    jp_elderly_fac = _v(jp_data, "신규_고령자주거_시설수", 300)
    jp_elderly_units = _v(jp_data, "고령자주거_평균세대수", 35)

    kr_hotel_new = _v(kr_data, "신규_호텔_개관수", 80)
    kr_hotel_rooms = _v(kr_data, "호텔_평균_객실수", 150)
    # 호텔 등급별
    kr_h5 = _v(kr_data, "호텔_5성급_비중", 10) / 100
    kr_h4 = _v(kr_data, "호텔_4성급_비중", 15) / 100
    kr_h3 = 1 - kr_h5 - kr_h4
    jp_h5_pct = 0.08
    jp_h4_pct = 0.25
    jp_h3_pct = 0.67

    # ── 1행: 신축 공급 비교 (세부 스택) + 이사건수 비교 ──
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        st.subheader("🏗️ 신축 주거 공급량")
        fig1 = go.Figure()
        # 한국: 서울 / 수도권(서울제외) / 지방
        fig1.add_trace(go.Bar(name="서울/도쿄권", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_seoul, jp_tokyo],
                              text=[f"{kr_seoul:,.0f}", f"{jp_tokyo:,.0f}"],
                              textposition="inside", marker_color="#EF553B"))
        fig1.add_trace(go.Bar(name="수도권外/오사카권", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_sudogwon_rest, jp_osaka],
                              text=[f"{kr_sudogwon_rest:,.0f}", f"{jp_osaka:,.0f}"],
                              textposition="inside", marker_color="#FFA15A"))
        fig1.add_trace(go.Bar(name="지방/나고야권", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_local, jp_nagoya],
                              text=[f"{kr_local:,.0f}", f"{jp_nagoya:,.0f}"],
                              textposition="inside", marker_color="#00CC96"))
        fig1.update_layout(barmode="stack", yaxis_title="세대/호", height=400,
                           margin=dict(t=30, b=30),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig1, use_container_width=True)

    with r1c2:
        st.subheader("🚚 연간 이사건수")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="서울/도쿄권", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_moving_seoul, jp_mv_tokyo],
                              text=[f"{kr_moving_seoul/10000:,.0f}만", f"{jp_mv_tokyo/10000:,.0f}만"],
                              textposition="inside", marker_color="#EF553B"))
        fig2.add_trace(go.Bar(name="수도권外/오사카권", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_moving_sudo, jp_mv_osaka],
                              text=[f"{kr_moving_sudo/10000:,.0f}만", f"{jp_mv_osaka/10000:,.0f}만"],
                              textposition="inside", marker_color="#FFA15A"))
        fig2.add_trace(go.Bar(name="지방/나고야권", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_moving_local, jp_mv_nagoya],
                              text=[f"{kr_moving_local/10000:,.0f}만", f"{jp_mv_nagoya/10000:,.0f}만"],
                              textposition="inside", marker_color="#00CC96"))
        fig2.update_layout(barmode="stack", yaxis_title="건", height=400,
                           margin=dict(t=30, b=30),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig2, use_container_width=True)

    # ── 2행: 호텔 비교 + 일본 도시권별 ──
    r2c1, r2c2 = st.columns(2)

    with r2c1:
        st.subheader("🏨 호텔 신규 객실 (등급별)")
        kr_total_rooms = kr_hotel_new * kr_hotel_rooms
        jp_total_rooms = jp_hotel_new * jp_hotel_rooms
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(name="5성급", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_total_rooms * kr_h5, jp_total_rooms * jp_h5_pct],
                              text=[f"{kr_total_rooms*kr_h5:,.0f}", f"{jp_total_rooms*jp_h5_pct:,.0f}"],
                              textposition="inside", marker_color="#AB63FA"))
        fig3.add_trace(go.Bar(name="4성급", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_total_rooms * kr_h4, jp_total_rooms * jp_h4_pct],
                              text=[f"{kr_total_rooms*kr_h4:,.0f}", f"{jp_total_rooms*jp_h4_pct:,.0f}"],
                              textposition="inside", marker_color="#19D3F3"))
        fig3.add_trace(go.Bar(name="3성급↓", x=["🇰🇷 한국", "🇯🇵 일본"],
                              y=[kr_total_rooms * kr_h3, jp_total_rooms * jp_h3_pct],
                              text=[f"{kr_total_rooms*kr_h3:,.0f}", f"{jp_total_rooms*jp_h3_pct:,.0f}"],
                              textposition="inside", marker_color="#636EFA"))
        fig3.update_layout(barmode="stack", yaxis_title="객실 수", height=400,
                           margin=dict(t=30, b=30),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.caption(f"한국: {kr_hotel_new}개×{kr_hotel_rooms}실={kr_total_rooms:,} | "
                   f"일본: {jp_hotel_new}개×{jp_hotel_rooms}실={jp_total_rooms:,}")
        st.plotly_chart(fig3, use_container_width=True)

    with r2c2:
        st.subheader("📊 세그먼트 구성 비교")
        # 한국 4세그먼트 vs 일본 6세그먼트 — 공통 카테고리로 매핑
        categories = ["신축", "리모델링", "호텔", "이사수요", "기업사택", "고령자"]
        kr_seg = [kr_new, 0, kr_total_rooms, kr_moving, 0, 0]  # 한국은 리모델링/기업/고령자 없음
        jp_seg = [jp_new, jp_reno, jp_total_rooms, jp_moving,
                  200 * 80, jp_elderly_fac * jp_elderly_units]  # 일본 6개

        fig4 = go.Figure()
        fig4.add_trace(go.Bar(name="🇰🇷 한국", x=categories, y=kr_seg,
                              marker_color="#636EFA", text=[f"{v:,.0f}" if v > 0 else "" for v in kr_seg],
                              textposition="outside"))
        fig4.add_trace(go.Bar(name="🇯🇵 일본", x=categories, y=jp_seg,
                              marker_color="#EF553B", text=[f"{v:,.0f}" if v > 0 else "" for v in jp_seg],
                              textposition="outside"))
        fig4.update_layout(barmode="group", yaxis_title="모수 (건/세대/실)", height=400,
                           margin=dict(t=30, b=30),
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
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
