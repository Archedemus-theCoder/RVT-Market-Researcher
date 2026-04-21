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

from core.jp_model import JpSamParams, compute_jp_sam

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

        # ── S1: 신축 주거 (분양+임대) ──
        st.subheader("S1: 신축 주거")
        st.markdown("**분양 맨션**")
        s1_bun_tokyo = st.number_input("도쿄권 분양 (호)", 0, 200000, int(_v(data, "도쿄권_신축_맨션_분양호수", 23000)), 500, key="jp_tokyo")
        s1_bun_osaka = st.number_input("오사카권 분양 (호)", 0, 200000, int(_v(data, "오사카권_신축_맨션_분양호수", 15000)), 500, key="jp_osaka")
        s1_bun_nagoya = st.number_input("나고야권 분양 (호)", 0, 200000, int(_v(data, "나고야권_신축_맨션_분양호수", 6000)), 500, key="jp_nagoya")
        st.markdown("**임대 맨션 (貸家)**")
        s1_rent_tokyo = st.number_input("도쿄권 임대 (호)", 0, 500000, int(_v(data, "도쿄권_임대맨션_착공호수", 119000)), 5000, key="jp_rent_tokyo")
        s1_rent_osaka = st.number_input("오사카권 임대 (호)", 0, 500000, int(_v(data, "오사카권_임대맨션_착공호수", 40500)), 5000, key="jp_rent_osaka")
        s1_rent_nagoya = st.number_input("나고야권 임대 (호)", 0, 500000, int(_v(data, "나고야권_임대맨션_착공호수", 28600)), 5000, key="jp_rent_nagoya")

        # 합산
        s1_tokyo_raw = s1_bun_tokyo + s1_rent_tokyo
        s1_osaka_raw = s1_bun_osaka + s1_rent_osaka
        s1_nagoya_raw = s1_bun_nagoya + s1_rent_nagoya
        st.caption(f"합산: 도쿄 {s1_tokyo_raw:,} | 오사카 {s1_osaka_raw:,} | 나고야 {s1_nagoya_raw:,} | 총 {s1_tokyo_raw+s1_osaka_raw+s1_nagoya_raw:,}호")

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

        bun_total = s1_bun_tokyo + s1_bun_osaka + s1_bun_nagoya
        rent_total = s1_rent_tokyo + s1_rent_osaka + s1_rent_nagoya
        st.caption(f"📍 **{region_label}** | 분양 {bun_total:,} + 임대 {rent_total:,} = {s1_tokyo_raw+s1_osaka_raw+s1_nagoya_raw:,}호")
        st.caption(f"출처: 분양=不動産経済研究所 | 임대=国土交通省 建築着工統計(貸家×共同住宅90%推定)")

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

        # ── 참고: 리노베이션 (S1에 포함) ──
        st.subheader("참고: 리노베이션")
        s2_total = st.number_input("전국 리노베이션 건수", 0, 1000000, int(_v(data, "전국_리노베이션_맨션_건수", 52800)), 10000, key="jp_s2t")
        s2_city = st.slider("3대 도시권 집중도(%)", 0, 100, 60, key="jp_s2c")
        st.caption("※ 리노베이션은 신축 맨션 모수에 포함하여 계산")

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
        bundle_discount_jp_pct = st.slider(
            "번들 할인 (세트 구매 시, %)", 0, 30, 0, 1, key="jp_bundle_discount",
            help="Ceily+Wally 세트 구매자에게 적용할 가격 할인율. 0%면 기존 공식과 동일.",
        )
        jp_tam = st.number_input("TAM (조엔)", 1.0, 50.0, 6.0, 0.5, key="jp_tam",
                                  help="일본 전체 인테리어/가구 시장규모")
        growth = st.slider("연간 성장률(%)", -5.0, 15.0, 4.0, 0.5, key="jp_gr")
        jp_som_y1 = st.slider("SOM 1년차 점유율(%)", 0.5, 30.0, 2.0, 0.5, key="jp_som_y1")
        jp_som_y5 = st.slider("SOM 5년차 점유율(%)", 1.0, 50.0, 15.0, 1.0, key="jp_som_y5")

        st.divider()
        st.subheader("🤖 데이터 관리")
        jp_admin_pw = st.text_input("관리자 비밀번호", type="password", key="jp_admin_pw")

        def _check_pw_jp(pw):
            try:
                return pw == st.secrets["ADMIN_PASSWORD"]
            except (KeyError, FileNotFoundError):
                return pw == "rovothome2026"

        if jp_admin_pw:
            if _check_pw_jp(jp_admin_pw):
                st.success("🔓 인증 완료")
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
            else:
                st.error("🔒 비밀번호가 올바르지 않습니다")
        else:
            st.caption("🔒 데이터 갱신은 관리자 비밀번호가 필요합니다")
        st.caption(f"마지막 갱신: {meta.get('validated_at', 'N/A')}")

    # 비활성 탭이면 사이드바 위젯만 생성하고 종료 (state 유지)
    if not visible:
        return

    st.title("🇯🇵 Rovothome 일본 시장규모 추정 시스템")

    if not data or len(data) <= 1:
        st.warning("⚠️ 일본 검증 데이터가 없습니다. 사이드바에서 리서처→크리틱을 실행하세요.")

    # ════════════════ CALCULATIONS ════════════════
    # 단일 엔진(core.jp_model)에 위임
    _params = JpSamParams(
        s1_bun_tokyo=s1_bun_tokyo, s1_bun_osaka=s1_bun_osaka, s1_bun_nagoya=s1_bun_nagoya,
        s1_rent_tokyo=s1_rent_tokyo, s1_rent_osaka=s1_rent_osaka, s1_rent_nagoya=s1_rent_nagoya,
        region_mode=region_mode,
        sz_s=sz_s, sz_m=sz_m, sz_l=sz_l,
        pr_h=pr_h, pr_m=pr_m, pr_l=pr_l,
        c1h=c1h, c1m=c1m, c1l=c1l, w1h=w1h, w1m=w1m, w1l=w1l,
        small_boost=small_boost,
        s2_total=s2_total, s2_city=s2_city,
        s3_hotel=s3_hotel, s3_rooms=s3_rooms,
        h5=h5, h4=h4, h3=h3,
        c3_5=c3_5, w3_5=w3_5, c3_4=c3_4, w3_4=w3_4, c3_3=c3_3, w3_3=w3_3,
        ryokan_on=ryokan_on, s3_ryokan=s3_ryokan, s3_ry_rooms=s3_ry_rooms,
        c3_ry=c3_ry, w3_ry=w3_ry,
        s4_moving=s4_moving, s4_ratio=s4_ratio, s4_single=s4_single,
        s5_corp=s5_corp, s5_units=s5_units, s5_rate=s5_rate, c5=c5, w5=w5,
        s6_fac=s6_fac, s6_units=s6_units, s6_city=s6_city,
        s6_ind=s6_ind, s6_care=s6_care, s6_mix=s6_mix,
        c6_i=c6_i, c6_c=c6_c, c6_m=c6_m, w6_i=w6_i, w6_c=w6_c, w6_m=w6_m,
        kaigo_ins=kaigo_ins,
        ceily_p=ceily_p, wally_p=wally_p, combo=combo,
        bundle_discount=bundle_discount_jp_pct / 100,
    )
    _r = compute_jp_sam(data, _params)

    # 하위 시각화 코드가 쓰던 지역 변수명 유지
    sam1, sam3, sam4, sam5, sam6 = _r.sam1, _r.sam3, _r.sam4, _r.sam5, _r.sam6
    sam2 = 0  # S2(리노베이션)는 S1에 통합, 별도 SAM 없음
    ceily_s1, wally_s1 = _r.ceily_s1, _r.wally_s1
    ceily_s2 = wally_s2 = 0
    ceily_s3, wally_s3 = _r.ceily_s3, _r.wally_s3
    ceily_s4, wally_s4 = _r.ceily_s4, _r.wally_s4
    ceily_s5, wally_s5 = _r.ceily_s5, _r.wally_s5
    ceily_s6, wally_s6 = _r.ceily_s6, _r.wally_s6
    s1_base = _r.s1_base
    reno_regional = _r.reno_regional
    reno_base = reno_regional
    pure_moving = _r.pure_moving
    avg_adopt = _r.avg_adopt
    s5_contracted = _r.s5_contracted
    s6_base = _r.s6_base
    # region_label / rgn_ratio는 사이드바 블록에서 이미 계산됨 (동일 값)
    # 이사 도입확률 (시각화 caption용)
    moving_adopt = avg_adopt * (s4_ratio / 100)
    s4_regional = s4_moving * rgn_ratio
    overlap = s1_base + s5_contracted + s6_base

    if _r.moving_overlap_warning:
        st.warning(
            f"⚠️ 이사수요 모수 음수: {s4_regional:,.0f} - {overlap:,.0f} < 0. "
            "파라미터를 확인하세요. (Stage 2a에서 로직 교체 예정)"
        )

    with st.sidebar:
        # Stage 2b: S1 고객 4분할 (투자자 설명용)
        st.markdown("**👥 S1 신축+리노베 고객 구성**")
        jp_total_buyers = _r.s1_set_customers + _r.s1_c_only_customers + _r.s1_w_only_customers
        jp_none_buyers = max(_r.s1_base - jp_total_buyers, 0)
        st.caption(f"🎁 세트 (C+W): {_r.s1_set_customers:,.0f}호")
        st.caption(f"🟦 Ceily 단독: {_r.s1_c_only_customers:,.0f}호")
        st.caption(f"🟥 Wally 단독: {_r.s1_w_only_customers:,.0f}호")
        st.caption(f"⬜ 미도입:     {jp_none_buyers:,.0f}호")
        if _r.s1_base > 0:
            st.caption(f"→ 타겟 비율: {jp_total_buyers/_r.s1_base*100:.1f}%")
        st.divider()
        st.caption(f"이사 모수({region_label}): {s4_regional:,.0f} × 95% = {pure_moving:,.0f}건")
        st.caption(f"이사 도입확률: {moving_adopt * 100:.2f}%")

    total_sam = _r.total_sam / 10000  # 만엔 → 억엔
    ceily_total = _r.total_ceily_sam / 10000
    wally_total = _r.total_wally_sam / 10000
    krw_total = total_sam * (fx / 100)  # 1억엔 × (원/100엔 ÷ 100) = 억원

    # 한일 비교 탭에서 사용할 계산값을 session_state에 저장
    st.session_state["_jp_computed"] = {
        "tam": jp_tam * 10000,  # 억엔
        "sam": total_sam,
        "ceily_sam": ceily_total,
        "wally_sam": wally_total,
        "som_pct": jp_som_y1,
        "som": total_sam * jp_som_y1 / 100,
        "fx": fx,
        "region_label": region_label,
        "sam_segments": {
            "신축+리노베": sam1 / 10000,
            "호텔/료칸": sam3 / 10000,
            "이사수요": sam4 / 10000,
            "기업사택": sam5 / 10000,
            "고령자주거": sam6 / 10000,
        },
    }

    # ════════════════ VISUALIZATION ════════════════
    jp_tam_value = jp_tam * 10000  # 조엔 → 억엔
    jp_som_current = total_sam * (jp_som_y1 / 100)
    st.markdown(f"**TAM** {jp_tam_value:,.0f}억엔 → **SAM** {total_sam:,.0f}억엔 ({total_sam/jp_tam_value*100:.1f}%) → **SOM** {jp_som_current:,.0f}억엔 ({jp_som_y1:.0f}%) | ≈ {krw_total:,.0f}억원")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("TAM", f"{jp_tam:,.0f} 조엔")
    c2.metric(f"SAM ({region_label})", f"{total_sam:,.0f} 억엔")
    c3.metric("Ceily SAM", f"{ceily_total:,.0f} 억엔")
    c4.metric("Wally SAM", f"{wally_total:,.0f} 억엔")
    c5.metric(f"SOM ({jp_som_y1:.0f}%)", f"{jp_som_current:,.0f} 억엔")

    # ─────────── TAM → SAM → SOM 인포그래픽 ───────────
    with st.expander("🎯 TAM → SAM → SOM 관계 시각화", expanded=True):
        info_col1, info_col2 = st.columns([3, 2])

        with info_col1:
            st.markdown("##### 📊 Sankey: 시장 규모 흐름")
            non_sam = jp_tam_value * 10000 - total_sam * 10000
            non_som = total_sam * 10000 - jp_som_current * 10000

            nodes = [
                "TAM",                         # 0
                "SAM (대상 세그먼트)",            # 1
                "비대상 시장",                   # 2
                "신축+리노베",                   # 3
                "호텔/료칸",                    # 4
                "이사수요",                      # 5
                "기업사택",                     # 6
                "고령자주거",                   # 7
                "Ceily",                       # 8
                "Wally",                       # 9
                f"SOM ({jp_som_y1:.0f}%)",      # 10
                "미점유 SAM",                   # 11
            ]
            node_colors = [
                "#2E86AB", "#A23B72", "#D1D5DB",
                "#3498DB", "#9B59B6", "#F39C12", "#1ABC9C", "#E67E22",
                "#636EFA", "#EF553B",
                "#E74C3C", "#BDC3C7"
            ]

            source = [0, 0,   1, 1, 1, 1, 1, 1, 1,    3, 3, 4, 4, 5, 5, 6, 6, 7, 7]
            target = [1, 2,   3, 4, 5, 6, 7, 10, 11,  8, 9, 8, 9, 8, 9, 8, 9, 8, 9]
            value = [
                total_sam * 10000, non_sam,
                sam1, sam3, sam4, sam5, sam6,
                jp_som_current * 10000, non_som,
                ceily_s1, wally_s1,
                ceily_s3, wally_s3,
                ceily_s4, wally_s4,
                ceily_s5, wally_s5,
                ceily_s6, wally_s6,
            ]
            link_colors = [
                "rgba(162,59,114,0.3)", "rgba(209,213,219,0.3)",
                "rgba(52,152,219,0.3)", "rgba(155,89,182,0.3)",
                "rgba(243,156,18,0.3)", "rgba(26,188,156,0.3)",
                "rgba(230,126,34,0.3)",
                "rgba(231,76,60,0.5)", "rgba(189,195,199,0.3)",
                "rgba(99,110,250,0.3)", "rgba(239,85,59,0.3)",
                "rgba(99,110,250,0.3)", "rgba(239,85,59,0.3)",
                "rgba(99,110,250,0.3)", "rgba(239,85,59,0.3)",
                "rgba(99,110,250,0.3)", "rgba(239,85,59,0.3)",
                "rgba(99,110,250,0.3)", "rgba(239,85,59,0.3)",
            ]

            fig_sankey = go.Figure(go.Sankey(
                node=dict(
                    pad=15, thickness=20,
                    line=dict(color="black", width=0.3),
                    label=nodes, color=node_colors,
                ),
                link=dict(source=source, target=target, value=value, color=link_colors),
            ))
            fig_sankey.update_layout(height=480, margin=dict(t=10, b=10, l=10, r=10),
                                     font=dict(size=11))
            st.plotly_chart(fig_sankey, use_container_width=True)

        with info_col2:
            st.markdown("##### 📐 규모 비율")
            sam_pct = total_sam / jp_tam_value * 100
            som_pct_of_tam = jp_som_current / jp_tam_value * 100
            som_pct_of_sam = jp_som_y1

            st.markdown(f"""
<div style="padding:10px; border:2px solid #2E86AB; background:rgba(46,134,171,0.1); position:relative;">
  <div style="color:#2E86AB; font-weight:bold; font-size:14px;">TAM — 100% ({jp_tam_value:,.0f}억엔)</div>
  <div style="font-size:11px; color:#888;">일본 전체 인테리어/가구 시장</div>
  <div style="margin-top:15px; padding:10px; border:2px solid #A23B72; background:rgba(162,59,114,0.15);">
    <div style="color:#A23B72; font-weight:bold; font-size:13px;">SAM — {sam_pct:.1f}% ({total_sam:,.0f}억엔)</div>
    <div style="font-size:11px; color:#888;">Rovothome 대상 5개 세그먼트</div>
    <div style="margin-top:12px; padding:8px; border:2px solid #E74C3C; background:rgba(231,76,60,0.2);">
      <div style="color:#E74C3C; font-weight:bold; font-size:12px;">SOM — {som_pct_of_tam:.2f}% of TAM ({jp_som_current:,.0f}억엔)</div>
      <div style="font-size:10px; color:#888;">SAM의 {som_pct_of_sam:.0f}% (시장 점유율)</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

            st.markdown(f"""
**단계별 필터 설명:**

| 단계 | 값 | 비율 |
|------|-----|------|
| TAM | {jp_tam_value:,.0f}억 | 100% |
| SAM | {total_sam:,.0f}억 | {sam_pct:.1f}% |
| SOM | {jp_som_current:,.0f}억 | {som_pct_of_tam:.2f}% |

**TAM → SAM ({sam_pct:.1f}%)**
- 5개 세그먼트 한정
- 신축+리노베/호텔/이사/B2B

**SAM → SOM ({som_pct_of_sam:.0f}%)**
- 초기 점유율
- 리로 재팬 등 채널 의존
            """)

    # ─────────── SAM 세분화 → SOM 통합 Sankey (IR용) ───────────
    with st.expander("🔍 SAM 세분화 → SOM 흐름 (IR용)", expanded=True):
        s1_total_units = max(bun_total + rent_total + reno_regional, 1)
        s1_new_sam = sam1 * (bun_total + rent_total) / s1_total_units
        s1_reno_sam = sam1 * reno_regional / s1_total_units
        som_rate = jp_som_y1 / 100
        fx_r = fx / 100  # 원/엔

        # 기타 = 호텔+기업사택+고령자
        etc_sam = sam3 + sam5 + sam6

        # 억원 환산 함수
        def yen2won(v):
            return v / 10000 * fx_r

        sam_won = total_sam * fx_r
        som_won = jp_som_current * fx_r

        nodes = [
            f"<b>SAM {yen2won(total_sam*10000):,.0f}억원</b><br>({total_sam:,.0f}억엔)",   # 0
            f"<b>신축+리노베</b><br>{yen2won(sam1):,.0f}억원 ({s1_base:,}호)",              # 1
            f"<b>이사수요</b><br>{yen2won(sam4):,.0f}억원 ({int(pure_moving):,}건)",        # 2
            f"<b>기타</b><br>{yen2won(etc_sam):,.0f}억원",                                 # 3
            f"<b>신축 (분양+임대)</b><br>{yen2won(s1_new_sam):,.0f}억원 ({bun_total+rent_total:,}호)",  # 4
            f"<b>리노베이션</b><br>{yen2won(s1_reno_sam):,.0f}억원 ({reno_regional:,}건)",  # 5
            f"<b>🎯 SOM {som_won:,.0f}억원</b><br>({jp_som_current:,.0f}억엔)",            # 6
        ]
        node_colors = [
            "#A23B72",
            "#3498DB", "#F39C12", "#9B9B9B",
            "#5DADE2", "#EC7063",
            "#C0392B",
        ]

        source = []; target = []; value = []; link_colors = []; link_labels = []

        # Level 1: SAM → 신축+리노베 / 이사 / 기타
        for tgt, val, col in [
            (1, sam1, "rgba(52,152,219,0.4)"),
            (2, sam4, "rgba(243,156,18,0.4)"),
            (3, etc_sam, "rgba(155,155,155,0.3)"),
        ]:
            source.append(0); target.append(tgt); value.append(val)
            link_colors.append(col); link_labels.append("")

        # Level 2: 신축+리노베 → 신축/리노베
        for tgt, val, col in [
            (4, s1_new_sam, "rgba(93,173,226,0.45)"),
            (5, s1_reno_sam, "rgba(236,112,99,0.45)"),
        ]:
            source.append(1); target.append(tgt); value.append(val)
            link_colors.append(col); link_labels.append("")

        # Level 3: 신축/리노베 → SOM (비율 표시)
        for sub_idx, sub_val, sub_name in [
            (4, s1_new_sam, "신축"),
            (5, s1_reno_sam, "리노베"),
        ]:
            som_val = sub_val * som_rate
            pct = yen2won(som_val) / som_won * 100 if som_won > 0 else 0
            source.append(sub_idx); target.append(6)
            value.append(max(som_val, 0.01))
            link_colors.append("rgba(192,57,43,0.6)")
            link_labels.append(f"{yen2won(som_val):,.0f}억원 ({pct:.0f}%)")

        # 이사 → SOM 직행
        som_mv = sam4 * som_rate
        pct_mv = yen2won(som_mv) / som_won * 100 if som_won > 0 else 0
        source.append(2); target.append(6)
        value.append(max(som_mv, 0.01))
        link_colors.append("rgba(243,156,18,0.6)")
        link_labels.append(f"{yen2won(som_mv):,.0f}억원 ({pct_mv:.0f}%)")

        # 기타 → SOM 직행
        som_etc = etc_sam * som_rate
        pct_etc = yen2won(som_etc) / som_won * 100 if som_won > 0 else 0
        source.append(3); target.append(6)
        value.append(max(som_etc, 0.01))
        link_colors.append("rgba(155,155,155,0.4)")
        link_labels.append(f"{yen2won(som_etc):,.0f}억원 ({pct_etc:.0f}%)")

        fig_combined = go.Figure(go.Sankey(
            arrangement="snap",
            node=dict(
                pad=30, thickness=28,
                line=dict(color="rgba(0,0,0,0.15)", width=0.5),
                label=nodes, color=node_colors,
            ),
            link=dict(source=source, target=target, value=value,
                      color=link_colors, label=link_labels),
        ))
        fig_combined.update_layout(
            height=550,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=14, family="Arial Black, sans-serif", color="#333"),
        )
        st.plotly_chart(fig_combined, use_container_width=True,
                        config={"toImageButtonOptions": {
                            "format": "png", "width": 1600, "height": 700,
                            "filename": "rovothome_jp_sam_sankey",
                            "scale": 2,
                        }})

        st.caption(f"💡 SAM {yen2won(total_sam*10000):,.0f}억원 중 신축+리노베+이사가 "
                   f"{yen2won(sam1+sam4):,.0f}억원 ({(sam1+sam4)/(total_sam*10000)*100:.0f}%) → "
                   f"SOM {som_won:,.0f}억원 ({jp_som_y1:.0f}%)")

    seg_labels = ["신축+리노베 (주거)", "호텔/료칸", "이사수요", "기업사택", "고령자주거"]
    seg_vals = [sam1/10000, sam3/10000, sam4/10000, sam5/10000, sam6/10000]
    ceily_vals = [ceily_s1/10000, ceily_s3/10000, ceily_s4/10000, ceily_s5/10000, ceily_s6/10000]
    wally_vals = [wally_s1/10000, wally_s3/10000, wally_s4/10000, wally_s5/10000, wally_s6/10000]

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
        st.subheader("📈 2026~2030 TAM / SAM / SOM 추이")
        years = list(range(2026, 2031))
        gf = [(1 + growth / 100) ** (y - 2026) for y in years]
        tam_trend = [jp_tam_value * g for g in gf]
        total_trend = [total_sam * g for g in gf]

        jp_som_rates = [jp_som_y1 + (jp_som_y5 - jp_som_y1) * i / 4 for i in range(5)]
        jp_som_trend = [total_trend[i] * jp_som_rates[i] / 100 for i in range(5)]

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=years, y=tam_trend, name="TAM",
                                  mode="lines", line=dict(width=1, color="#999", dash="dash")))
        fig3.add_trace(go.Scatter(x=years, y=total_trend, name="SAM",
                                  mode="lines+markers", line=dict(width=2, color="#636EFA")))
        fig3.add_trace(go.Scatter(x=years, y=jp_som_trend, name="SOM",
                                  mode="lines+markers+text", line=dict(width=3, color="#EF553B"),
                                  text=[f"{v:,.0f}" for v in jp_som_trend],
                                  textposition="top center", textfont=dict(size=10)))
        fig3.update_layout(yaxis_title="억엔", legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig3, use_container_width=True)

        som_df = pd.DataFrame({
            "연도": years,
            "TAM (억엔)": [f"{v:,.0f}" for v in tam_trend],
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
        st.write(f"- ※ 리노베이션({reno_regional:,}건)은 S1에 이미 포함")
        st.write(f"- (-) S5 기업사택: {s5_contracted:,.0f}")
        st.write(f"- (-) S6 고령자주거: {s6_base:,.0f}")
        st.write(f"- **= 순수 이사수요: {pure_moving:,.0f}**")

    # 세부 계산
    with st.expander("📋 세부 계산 내역"):
        st.markdown("#### S1: 신축 주거 + 리노베이션")
        st.write(f"**분양 맨션** (不動産経済研究所): {s1_bun_tokyo:,} + {s1_bun_osaka:,} + {s1_bun_nagoya:,} = {bun_total:,}호")
        st.write(f"**임대 맨션** (国土交通省 着工統計 貸家×90%): {s1_rent_tokyo:,} + {s1_rent_osaka:,} + {s1_rent_nagoya:,} = {rent_total:,}호")
        st.write(f"**리노베이션**: {s2_total:,} × {s2_city}% × {rgn_ratio:.0%} = {reno_regional:,}건")
        st.write(f"합산 모수: **{s1_base:,}호** (분양 {bun_total:,} + 임대 {rent_total:,} + 리노베 {reno_regional:,})")
        st.caption("⚠️ 임대 맨션은 貸家 착공수 × 공동주택비율 90% 추정치입니다")
        st.write(f"Ceily: **{ceily_s1/10000:,.0f}억엔** | Wally: **{wally_s1/10000:,.0f}억엔**")
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
