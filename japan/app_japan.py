"""
Rovothome 일본 시장규모 추정 대시보드 (6 세그먼트)
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
JP_DATA = BASE_DIR / "data" / "jp" / "validated.json"


def _load():
    if JP_DATA.exists():
        with open(JP_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _v(data, key, default=0):
    item = data.get(key, {})
    return item.get("value", default) if isinstance(item, dict) else default


def _status(data, key):
    item = data.get(key, {})
    return item.get("status", "unknown") if isinstance(item, dict) else "unknown"


def _dots(data, keys):
    statuses = [_status(data, k) for k in keys]
    w = sum(1.0 if s == "approved" else 0.5 if s == "warning" else 0 for s in statuses)
    t = len(statuses)
    if t == 0:
        return "○○○○○"
    sc = round(w / t * 5)
    return "●" * sc + "○" * (5 - sc)


def _warn(data, keys):
    return any(_status(data, k) in ("warning", "rejected") for k in keys)


def render_japan(visible=True):
    data = _load()
    meta = data.get("_meta", {})

    # ════════════════ SIDEBAR ════════════════
    with st.sidebar:
        st.header("🇯🇵 일본 파라미터")

        # ── 지역 범위 ──
        st.subheader("📍 지역 범위")
        region_mode = st.radio("범위 선택", ["3대 도시권 합산", "도쿄권만", "오사카권만", "나고야권만", "개별 지정"], key="jp_rgn")

        # ── S1: 신축 맨션 ──
        st.subheader("S1: 신축 맨션")
        s1_tokyo_raw = st.number_input("도쿄권 (호)", 0, 200000, int(_v(data, "도쿄권_신축_맨션_분양호수", 23000)), 500, key="jp_tokyo")
        s1_osaka_raw = st.number_input("오사카권 (호)", 0, 200000, int(_v(data, "오사카권_신축_맨션_분양호수", 15000)), 500, key="jp_osaka")
        s1_nagoya_raw = st.number_input("나고야권 (호)", 0, 200000, int(_v(data, "나고야권_신축_맨션_분양호수", 6000)), 500, key="jp_nagoya")

        # 지역 범위에 따라 적용
        if region_mode == "도쿄권만":
            s1_tokyo, s1_osaka, s1_nagoya = s1_tokyo_raw, 0, 0
            region_label = "도쿄권"
            # 도시권별 비중: 이사/리노베이션 등에 적용할 비중
            rgn_ratio = s1_tokyo_raw / max(s1_tokyo_raw + s1_osaka_raw + s1_nagoya_raw, 1)
        elif region_mode == "오사카권만":
            s1_tokyo, s1_osaka, s1_nagoya = 0, s1_osaka_raw, 0
            region_label = "오사카권"
            rgn_ratio = s1_osaka_raw / max(s1_tokyo_raw + s1_osaka_raw + s1_nagoya_raw, 1)
        elif region_mode == "나고야권만":
            s1_tokyo, s1_osaka, s1_nagoya = 0, 0, s1_nagoya_raw
            region_label = "나고야권"
            rgn_ratio = s1_nagoya_raw / max(s1_tokyo_raw + s1_osaka_raw + s1_nagoya_raw, 1)
        elif region_mode == "개별 지정":
            s1_tokyo, s1_osaka, s1_nagoya = s1_tokyo_raw, s1_osaka_raw, s1_nagoya_raw
            region_label = "개별 지정"
            rgn_ratio = 1.0
        else:  # 3대 도시권 합산
            s1_tokyo, s1_osaka, s1_nagoya = s1_tokyo_raw, s1_osaka_raw, s1_nagoya_raw
            region_label = "3대 도시권"
            rgn_ratio = 1.0

        st.caption(f"📍 현재: **{region_label}** | S1 모수: {s1_tokyo+s1_osaka+s1_nagoya:,}호")

        st.markdown("**면적 비중 (%)**")
        sz_s = st.slider("40㎡이하(소형)", 0, 100, 15, key="jp_sz_s")
        sz_m = st.slider("40~70㎡(표준)", 0, 100, 55, key="jp_sz_m")
        sz_l = st.slider("70㎡이상(대형)", 0, 100, 30, key="jp_sz_l")

        st.markdown("**가격 비중 (%)**")
        pr_h = st.slider("고가(100만엔/㎡+)", 0, 100, 25, key="jp_pr_h")
        pr_m = st.slider("중가(60~100만엔)", 0, 100, 50, key="jp_pr_m")
        pr_l = st.slider("보급(60만엔미만)", 0, 100, 25, key="jp_pr_l")

        st.markdown("**Ceily 도입확률(%)**")
        c1h = st.number_input("고가 Ceily", 0.0, 100.0, 20.0, 0.5, key="jp_c1h")
        c1m = st.number_input("중가 Ceily", 0.0, 100.0, 10.0, 0.5, key="jp_c1m")
        c1l = st.number_input("보급 Ceily", 0.0, 100.0, 3.0, 0.5, key="jp_c1l")

        st.markdown("**Wally 도입확률(%)**")
        w1h = st.number_input("고가 Wally", 0.0, 100.0, 25.0, 0.5, key="jp_w1h")
        w1m = st.number_input("중가 Wally", 0.0, 100.0, 13.0, 0.5, key="jp_w1m")
        w1l = st.number_input("보급 Wally", 0.0, 100.0, 4.0, 0.5, key="jp_w1l")

        small_boost = st.number_input("소형(40㎡↓) 보정계수", 1.0, 2.0, 1.3, 0.1, key="jp_sb")

        st.divider()

        # ── S2: 리모델링/리노베이션 ──
        st.subheader("S2: 리모델링/리노베이션 ★")
        s2_total = st.number_input("전국 리노베이션 건수", 0, 1000000, int(_v(data, "전국_리노베이션_맨션_건수", 230000)), 10000, key="jp_s2t")
        s2_city = st.slider("3대 도시권 집중도(%)", 0, 100, 60, key="jp_s2c")
        s2_full_pct = st.slider("풀리노베이션 비중(%)", 0, 100, int(_v(data, "풀리노베이션_비중", 20)), key="jp_s2f")
        c2f = st.number_input("풀리노 Ceily(%)", 0.0, 100.0, 18.0, 0.5, key="jp_c2f")
        w2f = st.number_input("풀리노 Wally(%)", 0.0, 100.0, 22.0, 0.5, key="jp_w2f")
        c2p = st.number_input("부분리노 Ceily(%)", 0.0, 100.0, 3.0, 0.5, key="jp_c2p")
        w2p = st.number_input("부분리노 Wally(%)", 0.0, 100.0, 4.0, 0.5, key="jp_w2p")
        subsidy = st.toggle("정부 보조금 적용 (+20%)", False, key="jp_sub")

        st.divider()

        # ── S3: 호텔/료칸 ──
        st.subheader("S3: 호텔/료칸")
        s3_hotel = st.number_input("신규 호텔 개관(개)", 0, 5000, 250, 10, key="jp_s3h")
        s3_rooms = st.number_input("호텔 평균 객실(실)", 0, 500, 120, 10, key="jp_s3r")
        h5 = st.slider("5성급 비중(%)", 0, 100, 8, key="jp_h5")
        h4 = st.slider("4성급 비중(%)", 0, 100, 25, key="jp_h4")
        h3 = st.slider("3성급↓ 비중(%)", 0, 100, 67, key="jp_h3")
        c3_5 = st.number_input("5성 Ceily(%)", 0.0, 100.0, 28.0, 1.0, key="jp_c35")
        w3_5 = st.number_input("5성 Wally(%)", 0.0, 100.0, 32.0, 1.0, key="jp_w35")
        c3_4 = st.number_input("4성 Ceily(%)", 0.0, 100.0, 12.0, 1.0, key="jp_c34")
        w3_4 = st.number_input("4성 Wally(%)", 0.0, 100.0, 16.0, 1.0, key="jp_w34")
        c3_3 = st.number_input("3성↓ Ceily(%)", 0.0, 100.0, 3.0, 1.0, key="jp_c33")
        w3_3 = st.number_input("3성↓ Wally(%)", 0.0, 100.0, 4.0, 1.0, key="jp_w33")
        ryokan_on = st.toggle("료칸 포함", True, key="jp_ry")
        s3_ryokan = st.number_input("료칸 리노베이션(건)", 0, 5000, 600, 50, key="jp_s3ry")
        s3_ry_rooms = st.number_input("료칸 평균 객실(실)", 0, 200, 20, 5, key="jp_s3ryr")
        c3_ry = st.number_input("료칸 Ceily(%)", 0.0, 100.0, 10.0, 1.0, key="jp_c3ry")
        w3_ry = st.number_input("료칸 Wally(%)", 0.0, 100.0, 30.0, 1.0, key="jp_w3ry")

        st.divider()

        # ── S4: 이사수요 ──
        st.subheader("S4: 이사수요")
        s4_moving = st.number_input("3대도시권 이사건수", 0, 10000000, int(_v(data, "3대도시권_이사건수", 2250000)), 50000, key="jp_s4m")
        s4_ratio = st.slider("신축대비 도입비율(%)", 10, 60, 25, key="jp_s4r")
        s4_single = st.toggle("1인가구 보정", False, key="jp_s4s")

        st.divider()

        # ── S5: 기업사택 ──
        st.subheader("S5: 기업사택")
        s5_corp = st.number_input("대상 기업수", 0, 5000, 200, 10, key="jp_s5c")
        s5_units = st.number_input("기업당 세대수", 0, 500, 80, 10, key="jp_s5u")
        s5_rate = st.slider("계약 성공률(%)", 1, 20, 5, key="jp_s5r")
        c5 = st.number_input("계약시 Ceily(%)", 0.0, 100.0, 60.0, 5.0, key="jp_c5")
        w5 = st.number_input("계약시 Wally(%)", 0.0, 100.0, 70.0, 5.0, key="jp_w5")

        st.divider()

        # ── S6: 고령자주거 ──
        st.subheader("S6: 고령자주거")
        s6_fac = st.number_input("신규 시설수", 0, 5000, int(_v(data, "신규_고령자주거_시설수", 600)), 50, key="jp_s6f")
        s6_units = st.number_input("평균 세대수", 0, 300, int(_v(data, "고령자주거_평균세대수", 70)), 10, key="jp_s6u")
        s6_city = st.slider("도시권 집중도(%)", 0, 100, 55, key="jp_s6c")
        s6_ind = st.slider("자립형 비중(%)", 0, 100, 40, key="jp_s6i")
        s6_care = st.slider("개호형 비중(%)", 0, 100, 35, key="jp_s6ca")
        s6_mix = st.slider("혼합형 비중(%)", 0, 100, 25, key="jp_s6mx")
        c6_i = st.number_input("자립 Ceily(%)", 0.0, 100.0, 25.0, 1.0, key="jp_c6i")
        c6_c = st.number_input("개호 Ceily(%)", 0.0, 100.0, 40.0, 1.0, key="jp_c6c")
        c6_m = st.number_input("혼합 Ceily(%)", 0.0, 100.0, 32.0, 1.0, key="jp_c6m")
        w6_i = st.number_input("자립 Wally(%)", 0.0, 100.0, 12.0, 1.0, key="jp_w6i")
        w6_c = st.number_input("개호 Wally(%)", 0.0, 100.0, 8.0, 1.0, key="jp_w6c")
        w6_m = st.number_input("혼합 Wally(%)", 0.0, 100.0, 10.0, 1.0, key="jp_w6m")
        kaigo_ins = st.toggle("개호보험 연계 (Ceily+15%)", False, key="jp_kai")

        st.divider()

        # ── 제품 단가 / 환율 ──
        st.subheader("💰 제품 단가")
        ceily_p = st.slider("Ceily 단가(만엔)", 30, 200, 80, 5, key="jp_cp")
        wally_p = st.slider("Wally 단가(만엔)", 30, 200, 50, 5, key="jp_wp")
        fx = st.slider("환율(원/100엔)", 700, 1200, 900, 10, key="jp_fx")
        combo = st.radio("제품 조합", ["Ceily + Wally", "Ceily만", "Wally만"], key="jp_combo")
        growth = st.slider("연간 성장률(%)", -5.0, 15.0, 4.0, 0.5, key="jp_gr")
        jp_som_y1 = st.slider("SOM 1년차 점유율(%)", 0.5, 30.0, 2.0, 0.5, key="jp_som_y1")
        jp_som_y5 = st.slider("SOM 5년차 점유율(%)", 1.0, 50.0, 15.0, 1.0, key="jp_som_y5")

        st.divider()
        st.subheader("🤖 데이터 관리")
        ca, cb = st.columns(2)
        with ca:
            if st.button("🔍 리서처", key="jp_res", use_container_width=True):
                with st.spinner("수집 중..."):
                    r = subprocess.run([sys.executable, str(BASE_DIR / "japan" / "agents" / "researcher_jp.py")],
                                       capture_output=True, text=True, cwd=str(BASE_DIR))
                    st.text(r.stdout[-500:] if len(r.stdout) > 500 else r.stdout)
        with cb:
            if st.button("🔎 크리틱", key="jp_crt", use_container_width=True):
                with st.spinner("검증 중..."):
                    r = subprocess.run([sys.executable, str(BASE_DIR / "japan" / "agents" / "critic_jp.py")],
                                       capture_output=True, text=True, cwd=str(BASE_DIR))
                    st.text(r.stdout[-500:] if len(r.stdout) > 500 else r.stdout)
        st.caption(f"마지막 갱신: {meta.get('validated_at', 'N/A')}")

    # 비활성 탭이면 사이드바 위젯만 생성하고 종료 (state 유지)
    if not visible:
        return

    st.title("🇯🇵 Rovothome 일본 시장규모 추정 시스템")

    if not data or len(data) <= 1:
        st.warning("⚠️ 일본 검증 데이터가 없습니다. 사이드바에서 리서처→크리틱을 실행하세요.")

    # ════════════════ CALCULATIONS ════════════════
    use_c = combo != "Wally만"
    use_w = combo != "Ceily만"

    # --- S1 ---
    s1_base = s1_tokyo + s1_osaka + s1_nagoya
    sz_total = max(sz_s + sz_m + sz_l, 1)
    pr_total = max(pr_h + pr_m + pr_l, 1)
    ceily_s1 = wally_s1 = 0
    s1_weighted_c = s1_weighted_w = 0
    for p_pct, cp, wp in [(pr_h, c1h, w1h), (pr_m, c1m, w1m), (pr_l, c1l, w1l)]:
        for s_pct, is_small in [(sz_s, True), (sz_m, False), (sz_l, False)]:
            units = s1_base * (p_pct / pr_total) * (s_pct / sz_total)
            boost = small_boost if is_small else 1.0
            if use_c:
                ceily_s1 += units * (cp / 100) * boost * ceily_p
                s1_weighted_c += units * (cp / 100) * boost
            if use_w:
                wally_s1 += units * (wp / 100) * boost * wally_p
                s1_weighted_w += units * (wp / 100) * boost
    sam1 = ceily_s1 + wally_s1
    avg_adopt = (s1_weighted_c + s1_weighted_w) / (2 * s1_base) if s1_base > 0 else 0

    # --- S2 --- (지역 비중 적용)
    reno_base = s2_total * (s2_city / 100) * rgn_ratio
    full_reno = reno_base * (s2_full_pct / 100)
    partial_reno = reno_base * (1 - s2_full_pct / 100)
    sub_mult = 1.2 if subsidy else 1.0
    ceily_s2 = wally_s2 = 0
    if use_c:
        ceily_s2 = full_reno * (c2f / 100) * sub_mult * ceily_p + partial_reno * (c2p / 100) * sub_mult * ceily_p
    if use_w:
        wally_s2 = full_reno * (w2f / 100) * sub_mult * wally_p + partial_reno * (w2p / 100) * sub_mult * wally_p
    sam2 = ceily_s2 + wally_s2

    # --- S3 --- (지역 비중 적용)
    hotel_rooms = s3_hotel * s3_rooms * rgn_ratio
    ht = max(h5 + h4 + h3, 1)
    ceily_s3 = wally_s3 = 0
    for g_pct, cp, wp in [(h5, c3_5, w3_5), (h4, c3_4, w3_4), (h3, c3_3, w3_3)]:
        rooms = hotel_rooms * (g_pct / ht)
        if use_c:
            ceily_s3 += rooms * (cp / 100) * ceily_p
        if use_w:
            wally_s3 += rooms * (wp / 100) * wally_p
    if ryokan_on:
        ry_rooms = s3_ryokan * s3_ry_rooms * rgn_ratio
        if use_c:
            ceily_s3 += ry_rooms * (c3_ry / 100) * ceily_p
        if use_w:
            wally_s3 += ry_rooms * (w3_ry / 100) * wally_p
    sam3 = ceily_s3 + wally_s3

    # --- S5 (before S4 for overlap) --- (지역 비중 적용)
    s5_contracted = s5_corp * s5_units * (s5_rate / 100) * rgn_ratio
    ceily_s5 = s5_contracted * (c5 / 100) * ceily_p if use_c else 0
    wally_s5 = s5_contracted * (w5 / 100) * wally_p if use_w else 0
    sam5 = ceily_s5 + wally_s5

    # --- S6 (before S4 for overlap) --- (지역 비중 적용)
    s6_base = s6_fac * s6_units * (s6_city / 100) * rgn_ratio
    s6t = max(s6_ind + s6_care + s6_mix, 1)
    ceily_s6 = wally_s6 = 0
    kai_mult = 1.15 if kaigo_ins else 1.0
    for t_pct, cp, wp in [(s6_ind, c6_i, w6_i), (s6_care, c6_c, w6_c), (s6_mix, c6_m, w6_m)]:
        units = s6_base * (t_pct / s6t)
        if use_c:
            ceily_s6 += units * (cp / 100) * kai_mult * ceily_p
        if use_w:
            wally_s6 += units * (wp / 100) * wally_p
    sam6 = ceily_s6 + wally_s6

    # --- S4: 이사수요 (중첩 제거, 지역 비중 적용) ---
    s4_regional = s4_moving * rgn_ratio
    overlap = s1_base + full_reno + s5_contracted + s6_base
    pure_moving = s4_regional - overlap
    if pure_moving < 0:
        st.warning(f"⚠️ 이사수요 모수 음수: {s4_regional:,.0f} - {overlap:,.0f} = {pure_moving:,.0f}. 파라미터를 확인하세요.")
        pure_moving = 0
    moving_adopt = avg_adopt * (s4_ratio / 100)
    single_c = 0.95 if s4_single else 1.0
    single_w = 1.15 if s4_single else 1.0
    ceily_s4 = pure_moving * moving_adopt * single_c * ceily_p if use_c else 0
    wally_s4 = pure_moving * moving_adopt * single_w * wally_p if use_w else 0
    sam4 = ceily_s4 + wally_s4

    with st.sidebar:
        st.caption(f"이사 모수({region_label}): {s4_regional:,.0f} - {overlap:,.0f} = {pure_moving:,.0f}")
        st.caption(f"이사 도입확률: {moving_adopt * 100:.2f}%")

    # --- 총합 ---
    total_sam = (sam1 + sam2 + sam3 + sam4 + sam5 + sam6) / 10000  # 억엔
    ceily_total = (ceily_s1 + ceily_s2 + ceily_s3 + ceily_s4 + ceily_s5 + ceily_s6) / 10000
    wally_total = (wally_s1 + wally_s2 + wally_s3 + wally_s4 + wally_s5 + wally_s6) / 10000
    krw_total = total_sam * (fx / 100)  # 억엔 → 억원: 1억엔 × (원/100엔 ÷ 100) = 억원

    # ════════════════ VISUALIZATION ════════════════
    jp_som_current = total_sam * (jp_som_y1 / 100)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"총 SAM ({region_label})", f"{total_sam:,.0f} 억엔", f"≈ {krw_total:,.0f} 억원")
    c2.metric("Ceily SAM", f"{ceily_total:,.0f} 억엔")
    c3.metric("Wally SAM", f"{wally_total:,.0f} 억엔")
    c4.metric(f"SOM ({jp_som_y1:.0f}%)", f"{jp_som_current:,.0f} 억엔")

    seg_labels = ["신축 맨션", "리모델링", "호텔/료칸", "이사수요", "기업사택", "고령자주거"]
    seg_vals = [sam1/10000, sam2/10000, sam3/10000, sam4/10000, sam5/10000, sam6/10000]
    ceily_vals = [ceily_s1/10000, ceily_s2/10000, ceily_s3/10000, ceily_s4/10000, ceily_s5/10000, ceily_s6/10000]
    wally_vals = [wally_s1/10000, wally_s2/10000, wally_s3/10000, wally_s4/10000, wally_s5/10000, wally_s6/10000]

    ch1, ch2 = st.columns(2)
    with ch1:
        st.subheader("세그먼트별 SAM 구성")
        fig = px.pie(names=seg_labels, values=seg_vals, color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition="inside", textinfo="label+percent+value",
                          texttemplate="%{label}<br>%{value:,.0f}억엔<br>(%{percent})")
        st.plotly_chart(fig, use_container_width=True)

        # 신뢰도 카드
        seg_keys = [
            ("신축 맨션", ["도쿄권_신축_맨션_분양호수", "오사카권_신축_맨션_분양호수", "나고야권_신축_맨션_분양호수"]),
            ("리모델링", ["전국_리노베이션_맨션_건수", "풀리노베이션_비중"]),
            ("호텔/료칸", ["신규_호텔_개관수", "호텔_평균_객실수", "료칸_리노베이션_건수"]),
            ("이사수요", ["3대도시권_이사건수"]),
            ("기업사택", ["연간_기업사택_신규리노베이션_기업수"]),
            ("고령자주거", ["신규_고령자주거_시설수", "고령자주거_평균세대수"]),
        ]
        for label, keys in seg_keys:
            w = _warn(data, keys)
            icon = " ⚠️" if w else " ✅"
            msg = f"**{label}{icon}** — 신뢰도: {_dots(data, keys)}"
            if w:
                st.warning(msg)
            else:
                st.success(msg)

    with ch2:
        st.subheader("Ceily vs Wally 세그먼트별 SAM")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="Ceily", x=seg_labels, y=ceily_vals, marker_color="#636EFA",
                              text=[f"{v:,.0f}" for v in ceily_vals], textposition="inside"))
        fig2.add_trace(go.Bar(name="Wally", x=seg_labels, y=wally_vals, marker_color="#EF553B",
                              text=[f"{v:,.0f}" for v in wally_vals], textposition="inside"))
        fig2.update_layout(barmode="stack", yaxis_title="억엔",
                           legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig2, use_container_width=True)

    # 하단 차트
    bt1, bt2 = st.columns(2)
    with bt1:
        st.subheader("📈 2025~2030 SAM / SOM 추이")
        years = list(range(2025, 2031))
        gf = [(1 + growth / 100) ** (y - 2025) for y in years]
        total_trend = [total_sam * g for g in gf]

        jp_som_rates = [jp_som_y1 + (jp_som_y5 - jp_som_y1) * i / 5 for i in range(6)]
        jp_som_trend = [total_trend[i] * jp_som_rates[i] / 100 for i in range(6)]

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=years, y=total_trend, name="SAM",
                                  mode="lines+markers", line=dict(width=2, color="#636EFA")))
        fig3.add_trace(go.Scatter(x=years, y=[ceily_total * g for g in gf], name="Ceily SAM",
                                  mode="lines", line=dict(dash="dash", width=1, color="#636EFA")))
        fig3.add_trace(go.Scatter(x=years, y=[wally_total * g for g in gf], name="Wally SAM",
                                  mode="lines", line=dict(dash="dot", width=1, color="#636EFA")))
        fig3.add_trace(go.Scatter(x=years, y=jp_som_trend, name="SOM",
                                  mode="lines+markers+text", line=dict(width=3, color="#EF553B"),
                                  text=[f"{v:,.0f}" for v in jp_som_trend],
                                  textposition="top center", textfont=dict(size=10)))
        fig3.update_layout(yaxis_title="억엔", legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig3, use_container_width=True)

        som_df = pd.DataFrame({
            "연도": years,
            "SAM (억엔)": [f"{v:,.0f}" for v in total_trend],
            "점유율": [f"{r:.1f}%" for r in jp_som_rates],
            "SOM (억엔)": [f"{v:,.0f}" for v in jp_som_trend],
        })
        st.dataframe(som_df, use_container_width=True, hide_index=True)

    with bt2:
        st.subheader("📊 도입확률 민감도 (±50%)")
        sens = []
        for f, lb in [(0.5, "-50%"), (0.75, "-25%"), (1.0, "기준"), (1.25, "+25%"), (1.5, "+50%")]:
            sens.append({"변화율": lb, "총SAM(억엔)": total_sam * f})
        df_s = pd.DataFrame(sens)
        fig4 = px.bar(df_s, x="변화율", y="총SAM(억엔)", color="변화율",
                      color_discrete_sequence=["#ff6b6b", "#ffa07a", "#4ecdc4", "#45b7d1", "#2196f3"])
        fig4.update_layout(showlegend=False)
        st.plotly_chart(fig4, use_container_width=True)
        st.info(f"SAM 범위: **{total_sam*0.5:,.0f}** ~ **{total_sam*1.5:,.0f}** 억엔")

    # 중첩 제거 내역
    with st.expander("🔗 S4 중첩 제거 내역"):
        st.write(f"- 이사건수({region_label}): {s4_moving:,.0f} × {rgn_ratio:.0%} = **{s4_regional:,.0f}**")
        st.write(f"- (-) S1 신축 입주: {s1_base:,.0f}")
        st.write(f"- (-) S2 풀리노 입주: {full_reno:,.0f}")
        st.write(f"- (-) S5 기업사택: {s5_contracted:,.0f}")
        st.write(f"- (-) S6 고령자주거: {s6_base:,.0f}")
        st.write(f"- **= 순수 이사수요: {pure_moving:,.0f}**")

    # 세부 계산
    with st.expander("📋 세부 계산 내역"):
        st.markdown("#### S1: 신축 맨션")
        st.write(f"모수: {s1_tokyo:,}+{s1_osaka:,}+{s1_nagoya:,} = **{s1_base:,}호**")
        st.write(f"Ceily: **{ceily_s1/10000:,.0f}억엔** | Wally: **{wally_s1/10000:,.0f}억엔**")
        st.markdown("#### S2: 리모델링")
        st.write(f"모수: {s2_total:,} × {s2_city}% = {reno_base:,.0f} (풀: {full_reno:,.0f} / 부분: {partial_reno:,.0f})")
        st.write(f"Ceily: **{ceily_s2/10000:,.0f}억엔** | Wally: **{wally_s2/10000:,.0f}억엔**")
        st.markdown("#### S3: 호텔/료칸")
        st.write(f"호텔: {s3_hotel}개 × {s3_rooms}실 = {hotel_rooms:,}실")
        if ryokan_on:
            st.write(f"료칸: {s3_ryokan}건 × {s3_ry_rooms}실 = {s3_ryokan*s3_ry_rooms:,}실")
        st.write(f"Ceily: **{ceily_s3/10000:,.0f}억엔** | Wally: **{wally_s3/10000:,.0f}억엔**")
        st.markdown("#### S5: 기업사택")
        st.write(f"계약: {s5_corp}사 × {s5_units}세대 × {s5_rate}% = **{s5_contracted:,.0f}세대**")
        st.write(f"Ceily: **{ceily_s5/10000:,.0f}억엔** | Wally: **{wally_s5/10000:,.0f}억엔**")
        st.markdown("#### S6: 고령자주거")
        st.write(f"모수: {s6_fac}시설 × {s6_units}세대 × {s6_city}% = **{s6_base:,.0f}세대**")
        st.write(f"Ceily: **{ceily_s6/10000:,.0f}억엔** | Wally: **{wally_s6/10000:,.0f}억엔**")

    # 원본 데이터
    with st.expander("🔍 검증된 데이터 원본"):
        for key, item in data.items():
            if key == "_meta" or not isinstance(item, dict):
                continue
            status = item.get("status", "")
            icon = {"approved": "✅", "warning": "⚠️", "rejected": "❌"}.get(status, "❓")
            src = item.get("source", {})
            cross = item.get("cross_validation", {})
            st.markdown(f"**{icon} {key}**: {item.get('value')} {src.get('unit', '')} — {src.get('source_name', '')} [{cross.get('method', '')}]")
            if item.get("critic_note"):
                st.caption(f"   {item['critic_note']}")

    # 리포트 다운로드
    with st.sidebar:
        st.divider()
        lines = [
            "# Rovothome 일본 시장규모 추정 리포트",
            f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"\n## 요약",
            f"- 총 SAM: {total_sam:,.0f} 억엔 (≈{krw_total:,.0f} 억원)",
            f"- Ceily: {ceily_total:,.0f} 억엔 | Wally: {wally_total:,.0f} 억엔",
            f"\n## 세그먼트별",
        ]
        for lb, sv, cv, wv in zip(seg_labels, seg_vals, ceily_vals, wally_vals):
            lines.append(f"- {lb}: {sv:,.0f}억엔 (C:{cv:,.0f} W:{wv:,.0f})")
        st.download_button("📥 리포트 (MD)", "\n".join(lines),
                           f"rovothome_japan_{datetime.now().strftime('%Y%m%d')}.md",
                           "text/markdown", use_container_width=True, key="jp_dl")
