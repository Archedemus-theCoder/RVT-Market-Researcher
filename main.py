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

BASE_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ─────────── 탭 구성 ───────────
tab_kr, tab_jp, tab_compare = st.tabs(["🇰🇷 한국 시장", "🇯🇵 일본 시장", "🌏 한일 비교"])

with tab_kr:
    # 한국 대시보드 — 기존 app.py의 main() 호출
    import app as kr_app
    kr_app.main()

with tab_jp:
    # 일본 대시보드
    from japan.app_japan import render_japan
    render_japan()

with tab_compare:
    st.header("🌏 한일 시장 비교")
    st.caption("양국 대시보드에서 설정한 파라미터 기준으로 비교합니다.")

    # 한국 데이터 로드
    kr_data = load_json(BASE_DIR / "data" / "validated.json")
    jp_data = load_json(BASE_DIR / "data" / "jp" / "validated.json")

    # 환율 입력
    exchange_rate = st.slider("환율 (원/100엔)", 700, 1200, 900, 10, key="compare_fx")

    if not kr_data or len(kr_data) <= 1:
        st.warning("한국 데이터가 없습니다.")
    if not jp_data or len(jp_data) <= 1:
        st.warning("일본 데이터가 없습니다.")

    st.info("💡 각 탭에서 파라미터를 조정한 후, 이 탭에서 비교 결과를 확인하세요. "
            "정확한 비교를 위해서는 양국 탭을 먼저 로드해야 합니다.")

    # 기본 데이터 비교 (validated.json 기반 원본 수치)
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

    # 신축 공급량 비교
    if kr_data and jp_data and len(kr_data) > 1 and len(jp_data) > 1:
        st.subheader("📊 신축 공급량 비교")

        def _v(data, key, default=0):
            item = data.get(key, {})
            return item.get("value", default) if isinstance(item, dict) else default

        kr_new = _v(kr_data, "전국_신축_준공_세대수", 0)
        jp_tokyo = _v(jp_data, "도쿄권_신축_맨션_분양호수", 50000)
        jp_osaka = _v(jp_data, "오사카권_신축_맨션_분양호수", 20000)
        jp_nagoya = _v(jp_data, "나고야권_신축_맨션_분양호수", 5000)
        jp_total = jp_tokyo + jp_osaka + jp_nagoya

        fig_compare = go.Figure()
        fig_compare.add_trace(go.Bar(
            x=["🇰🇷 한국 (전국)", "🇯🇵 일본 (3대 도시권)"],
            y=[kr_new, jp_total],
            text=[f"{kr_new:,.0f}", f"{jp_total:,.0f}"],
            textposition="outside",
            marker_color=["#636EFA", "#EF553B"],
        ))
        fig_compare.update_layout(yaxis_title="세대/호", title="연간 신축 주거 공급량")
        st.plotly_chart(fig_compare, use_container_width=True)
