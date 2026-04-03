"""
Rovothome 시장규모 추정 시스템 — 한일 통합 대시보드
탭1: 🇰🇷 한국 시장
탭2: 🇯🇵 일본 시장
탭3: 🌏 한일 비교
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

# ── 사이드바 폰트 축소 CSS ──
st.markdown("""
<style>
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


# ── 탭 선택을 session_state로 관리 ──
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0

tab_kr, tab_jp, tab_compare = st.tabs(["🇰🇷 한국 시장", "🇯🇵 일본 시장", "🌏 한일 비교"])

with tab_kr:
    # 한국 탭이 활성화되면 한국 사이드바 표시
    import app as kr_app
    kr_app.main()

with tab_jp:
    from japan.app_japan import render_japan
    render_japan()

with tab_compare:
    st.header("🌏 한일 시장 비교")
    st.caption("양국 대시보드에서 설정한 파라미터 기준으로 비교합니다.")

    kr_data = load_json(BASE_DIR / "data" / "validated.json")
    jp_data = load_json(BASE_DIR / "data" / "jp" / "validated.json")

    exchange_rate = st.sidebar.slider("환율 (원/100엔)", 700, 1200, 900, 10, key="compare_fx")

    if not kr_data or len(kr_data) <= 1:
        st.warning("한국 데이터가 없습니다.")
    if not jp_data or len(jp_data) <= 1:
        st.warning("일본 데이터가 없습니다.")

    st.info("💡 각 탭에서 파라미터를 조정한 후, 이 탭에서 비교 결과를 확인하세요.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🇰🇷 한국 주요 지표")
        if kr_data and len(kr_data) > 1:
            for key, item in kr_data.items():
                if key == "_meta" or not isinstance(item, dict):
                    continue
                src = item.get("source", {})
                st.caption(f"**{key}**: {item.get('value')} {src.get('unit', '')}")

    with col2:
        st.subheader("🇯🇵 일본 주요 지표")
        if jp_data and len(jp_data) > 1:
            for key, item in jp_data.items():
                if key == "_meta" or not isinstance(item, dict):
                    continue
                src = item.get("source", {})
                st.caption(f"**{key}**: {item.get('value')} {src.get('unit', '')}")

    if kr_data and jp_data and len(kr_data) > 1 and len(jp_data) > 1:
        st.subheader("📊 신축 공급량 비교")

        def _v(data, key, default=0):
            item = data.get(key, {})
            return item.get("value", default) if isinstance(item, dict) else default

        kr_new = _v(kr_data, "전국_신축_준공_세대수", 0)
        jp_tokyo = _v(jp_data, "도쿄권_신축_맨션_분양호수", 23000)
        jp_osaka = _v(jp_data, "오사카권_신축_맨션_분양호수", 15000)
        jp_nagoya = _v(jp_data, "나고야권_신축_맨션_분양호수", 6000)
        jp_total = jp_tokyo + jp_osaka + jp_nagoya

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["🇰🇷 한국 (전국)", "🇯🇵 일본 (3대 도시권)"],
            y=[kr_new, jp_total],
            text=[f"{kr_new:,.0f}", f"{jp_total:,.0f}"],
            textposition="outside",
            marker_color=["#636EFA", "#EF553B"],
        ))
        fig.update_layout(yaxis_title="세대/호", title="연간 신축 주거 공급량")
        st.plotly_chart(fig, use_container_width=True)
