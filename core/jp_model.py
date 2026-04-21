"""일본 시장규모 계산 엔진.

app_japan.py의 6세그먼트 계산 로직을 이식한다.
Stage 1: 기존 로직 그대로 (수치 불변).
Stage 2a: 이사수요(S4) overlap 로직 교체.
Stage 2b: Ceily/Wally 덧셈 → 배타적 믹스.
"""
from __future__ import annotations

from dataclasses import dataclass


def get_val(data: dict, key: str, default=0):
    item = data.get(key, {})
    return item.get("value", default) if isinstance(item, dict) else default


@dataclass
class JpSamParams:
    """app_japan.py UI 입력. 기본값은 UI 기본값과 동일."""
    # S1 신축 (분양+임대)
    s1_bun_tokyo: int
    s1_bun_osaka: int
    s1_bun_nagoya: int
    s1_rent_tokyo: int
    s1_rent_osaka: int
    s1_rent_nagoya: int
    region_mode: str  # "3대 도시권 합산" / "도쿄권만" / ...
    # S1 면적×가격 분포
    sz_s: float; sz_m: float; sz_l: float
    pr_h: float; pr_m: float; pr_l: float
    # S1 도입확률 (고가/중가/보급)
    c1h: float; c1m: float; c1l: float
    w1h: float; w1m: float; w1l: float
    small_boost: float
    # 리노베이션
    s2_total: int
    s2_city: float
    # S3 호텔/료칸
    s3_hotel: int
    s3_rooms: int
    h5: float; h4: float; h3: float
    c3_5: float; w3_5: float
    c3_4: float; w3_4: float
    c3_3: float; w3_3: float
    ryokan_on: bool
    s3_ryokan: int
    s3_ry_rooms: int
    c3_ry: float; w3_ry: float
    # S4 이사
    s4_moving: int
    s4_ratio: float
    s4_single: bool
    # S5 기업사택
    s5_corp: int
    s5_units: int
    s5_rate: float
    c5: float; w5: float
    # S6 고령자주거
    s6_fac: int
    s6_units: int
    s6_city: float
    s6_ind: float; s6_care: float; s6_mix: float
    c6_i: float; c6_c: float; c6_m: float
    w6_i: float; w6_c: float; w6_m: float
    kaigo_ins: bool
    # 제품 단가
    ceily_p: float
    wally_p: float
    combo: str


@dataclass
class JpSamResult:
    """일본 SAM 계산 결과. 단위: 만엔."""
    # 세그먼트별 SAM
    sam1: float; sam3: float; sam4: float; sam5: float; sam6: float
    ceily_s1: float; wally_s1: float
    ceily_s3: float; wally_s3: float
    ceily_s4: float; wally_s4: float
    ceily_s5: float; wally_s5: float
    ceily_s6: float; wally_s6: float
    # 파생
    s1_base: float
    reno_regional: int
    pure_moving: float
    avg_adopt: float
    region_label: str
    rgn_ratio: float
    bun_total: int
    rent_total: int
    s5_contracted: float
    s6_base: float
    # 경고
    moving_overlap_warning: bool = False

    @property
    def total_sam(self) -> float:
        return self.sam1 + self.sam3 + self.sam4 + self.sam5 + self.sam6

    @property
    def total_ceily_sam(self) -> float:
        return self.ceily_s1 + self.ceily_s3 + self.ceily_s4 + self.ceily_s5 + self.ceily_s6

    @property
    def total_wally_sam(self) -> float:
        return self.wally_s1 + self.wally_s3 + self.wally_s4 + self.wally_s5 + self.wally_s6


def compute_jp_sam(data: dict, p: JpSamParams) -> JpSamResult:
    """일본 6세그먼트 SAM 계산 (app_japan.py 로직 이식)."""
    use_c = p.combo != "Wally만"
    use_w = p.combo != "Ceily만"

    # ── 지역 필터 ──
    s1_tokyo_raw = p.s1_bun_tokyo + p.s1_rent_tokyo
    s1_osaka_raw = p.s1_bun_osaka + p.s1_rent_osaka
    s1_nagoya_raw = p.s1_bun_nagoya + p.s1_rent_nagoya
    total_raw = max(s1_tokyo_raw + s1_osaka_raw + s1_nagoya_raw, 1)

    if p.region_mode == "도쿄권만":
        s1_tokyo, s1_osaka, s1_nagoya = s1_tokyo_raw, 0, 0
        region_label = "도쿄권"
        rgn_ratio = s1_tokyo_raw / total_raw
    elif p.region_mode == "오사카권만":
        s1_tokyo, s1_osaka, s1_nagoya = 0, s1_osaka_raw, 0
        region_label = "오사카권"
        rgn_ratio = s1_osaka_raw / total_raw
    elif p.region_mode == "나고야권만":
        s1_tokyo, s1_osaka, s1_nagoya = 0, 0, s1_nagoya_raw
        region_label = "나고야권"
        rgn_ratio = s1_nagoya_raw / total_raw
    elif p.region_mode == "개별 지정":
        s1_tokyo, s1_osaka, s1_nagoya = s1_tokyo_raw, s1_osaka_raw, s1_nagoya_raw
        region_label = "개별 지정"
        rgn_ratio = 1.0
    else:
        s1_tokyo, s1_osaka, s1_nagoya = s1_tokyo_raw, s1_osaka_raw, s1_nagoya_raw
        region_label = "3대 도시권"
        rgn_ratio = 1.0

    bun_total = p.s1_bun_tokyo + p.s1_bun_osaka + p.s1_bun_nagoya
    rent_total = p.s1_rent_tokyo + p.s1_rent_osaka + p.s1_rent_nagoya

    # ── S1 신축+리노베이션 ──
    reno_regional = int(p.s2_total * (p.s2_city / 100) * rgn_ratio)
    s1_base = s1_tokyo + s1_osaka + s1_nagoya + reno_regional

    sz_total = max(p.sz_s + p.sz_m + p.sz_l, 1)
    pr_total = max(p.pr_h + p.pr_m + p.pr_l, 1)

    ceily_s1 = wally_s1 = 0.0
    s1_weighted_c = s1_weighted_w = 0.0
    for p_pct, cp, wp in [(p.pr_h, p.c1h, p.w1h), (p.pr_m, p.c1m, p.w1m), (p.pr_l, p.c1l, p.w1l)]:
        for s_pct, is_small in [(p.sz_s, True), (p.sz_m, False), (p.sz_l, False)]:
            units = s1_base * (p_pct / pr_total) * (s_pct / sz_total)
            boost = p.small_boost if is_small else 1.0
            if use_c:
                ceily_s1 += units * (cp / 100) * boost * p.ceily_p
                s1_weighted_c += units * (cp / 100) * boost
            if use_w:
                wally_s1 += units * (wp / 100) * boost * p.wally_p
                s1_weighted_w += units * (wp / 100) * boost
    sam1 = ceily_s1 + wally_s1
    avg_adopt = (s1_weighted_c + s1_weighted_w) / (2 * s1_base) if s1_base > 0 else 0

    # ── S3 호텔+료칸 ──
    hotel_rooms = p.s3_hotel * p.s3_rooms * rgn_ratio
    ht = max(p.h5 + p.h4 + p.h3, 1)
    ceily_s3 = wally_s3 = 0.0
    for g_pct, cp, wp in [
        (p.h5, p.c3_5, p.w3_5), (p.h4, p.c3_4, p.w3_4), (p.h3, p.c3_3, p.w3_3),
    ]:
        rooms = hotel_rooms * (g_pct / ht)
        if use_c:
            ceily_s3 += rooms * (cp / 100) * p.ceily_p
        if use_w:
            wally_s3 += rooms * (wp / 100) * p.wally_p
    if p.ryokan_on:
        ry_rooms = p.s3_ryokan * p.s3_ry_rooms * rgn_ratio
        if use_c:
            ceily_s3 += ry_rooms * (p.c3_ry / 100) * p.ceily_p
        if use_w:
            wally_s3 += ry_rooms * (p.w3_ry / 100) * p.wally_p
    sam3 = ceily_s3 + wally_s3

    # ── S5 기업사택 ──
    s5_contracted = p.s5_corp * p.s5_units * (p.s5_rate / 100) * rgn_ratio
    ceily_s5 = s5_contracted * (p.c5 / 100) * p.ceily_p if use_c else 0
    wally_s5 = s5_contracted * (p.w5 / 100) * p.wally_p if use_w else 0
    sam5 = ceily_s5 + wally_s5

    # ── S6 고령자주거 ──
    s6_base = p.s6_fac * p.s6_units * (p.s6_city / 100) * rgn_ratio
    s6t = max(p.s6_ind + p.s6_care + p.s6_mix, 1)
    kai_mult = 1.15 if p.kaigo_ins else 1.0
    ceily_s6 = wally_s6 = 0.0
    for t_pct, cp, wp in [
        (p.s6_ind, p.c6_i, p.w6_i), (p.s6_care, p.c6_c, p.w6_c), (p.s6_mix, p.c6_m, p.w6_m),
    ]:
        units = s6_base * (t_pct / s6t)
        if use_c:
            ceily_s6 += units * (cp / 100) * kai_mult * p.ceily_p
        if use_w:
            wally_s6 += units * (wp / 100) * p.wally_p
    sam6 = ceily_s6 + wally_s6

    # ── S4 이사수요 (중첩제거) ──
    s4_regional = p.s4_moving * rgn_ratio
    overlap = s1_base + s5_contracted + s6_base
    pure_moving = s4_regional - overlap
    warning = False
    if pure_moving < 0:
        warning = True
        pure_moving = 0
    moving_adopt = avg_adopt * (p.s4_ratio / 100)
    single_c = 0.95 if p.s4_single else 1.0
    single_w = 1.15 if p.s4_single else 1.0
    ceily_s4 = pure_moving * moving_adopt * single_c * p.ceily_p if use_c else 0
    wally_s4 = pure_moving * moving_adopt * single_w * p.wally_p if use_w else 0
    sam4 = ceily_s4 + wally_s4

    return JpSamResult(
        sam1=sam1, sam3=sam3, sam4=sam4, sam5=sam5, sam6=sam6,
        ceily_s1=ceily_s1, wally_s1=wally_s1,
        ceily_s3=ceily_s3, wally_s3=wally_s3,
        ceily_s4=ceily_s4, wally_s4=wally_s4,
        ceily_s5=ceily_s5, wally_s5=wally_s5,
        ceily_s6=ceily_s6, wally_s6=wally_s6,
        s1_base=s1_base,
        reno_regional=reno_regional,
        pure_moving=pure_moving,
        avg_adopt=avg_adopt,
        region_label=region_label,
        rgn_ratio=rgn_ratio,
        bun_total=bun_total, rent_total=rent_total,
        s5_contracted=s5_contracted, s6_base=s6_base,
        moving_overlap_warning=warning,
    )
