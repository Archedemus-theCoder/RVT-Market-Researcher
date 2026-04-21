"""한국 시장규모 계산 엔진.

두 가지 계산 모드:
- compute_detailed_sam(): app.py 대시보드용 (9칸 매트릭스 × 개별 Ceily/Wally 도입률)
- compute_scenario_sam(): ir.py IR 카드용 (세그먼트당 단일 침투율 × 시나리오 배수)

두 모드는 모집단(신축 세대수, 이사건수 등)을 공유하지만 도입률 모델링이 다르다.
Stage 2에서 통합 예정.
"""
from __future__ import annotations

from dataclasses import dataclass, field


SCENARIO_MULT = {"보수": 0.5, "중립": 1.0, "공격": 1.5}

# Stage 2a: 이사자 중 "신축 입주이사" 비율 기본값.
# 한국 통계청 인구이동통계 + 국토부 주거실태조사 기준 약 5~8%.
# 이 비율만큼 이사수요 모수에서 제외 (S1과 진짜 중복되는 부분).
# 기존 공식(이사건수 − 신축준공세대수)은 "신축 준공 = 신축 입주이사"라는
# 잘못된 가정이었음 — 신축 공급됐다고 그해 모두 이사하는 것이 아님.
NEW_MOVE_IN_RATIO_DEFAULT = 0.06


def get_val(data: dict, key: str, default=0):
    item = data.get(key, {})
    return item.get("value", default) if isinstance(item, dict) else default


# ─────────────────────────────────────────────────────────
# 1) Detailed mode (app.py용)
# ─────────────────────────────────────────────────────────

@dataclass
class DetailedKrSam:
    """app.py 대시보드 출력. 단위: 만원 (SAM), 세대/실/건 (모집단)."""
    # 세그먼트별 SAM
    sam1: float
    sam2: float
    sam3: float
    ceily_sam1: float
    wally_sam1: float
    ceily_sam2: float
    wally_sam2: float
    ceily_sam3: float
    wally_sam3: float
    # 모집단
    seg1_base: float
    seg2_base: float
    pure_moving: float
    # 파생
    avg_adoption_rate: float
    units_matrix: list = field(default_factory=list)  # 3×3
    region_ratio: float = 1.0

    @property
    def total_sam(self) -> float:
        return self.sam1 + self.sam2 + self.sam3

    @property
    def total_ceily_sam(self) -> float:
        return self.ceily_sam1 + self.ceily_sam2 + self.ceily_sam3

    @property
    def total_wally_sam(self) -> float:
        return self.wally_sam1 + self.wally_sam2 + self.wally_sam3


def compute_detailed_sam(
    data: dict,
    region: str,
    matrix_pct: list[list[float]],
    ceily_matrix: list[list[float]],
    wally_matrix: list[list[float]],
    hotel_ceily: tuple[float, float, float],
    hotel_wally: tuple[float, float, float],
    moving_ratio: float,
    remodel_units: float,
    ceily_price: float,
    wally_price: float,
    product_combo: str,
    new_move_in_ratio: float = NEW_MOVE_IN_RATIO_DEFAULT,
) -> DetailedKrSam:
    """한국 대시보드용 SAM 계산 (app.py 로직 이식)."""

    # 지역 비중
    if region == "수도권":
        region_ratio = get_val(data, "수도권_비중", 50) / 100
    elif region == "서울":
        region_ratio = get_val(data, "서울_비중", 15) / 100
    else:
        region_ratio = 1.0

    # ── S1 신축 주거 (9칸 매트릭스) ──
    new_build_total = get_val(data, "전국_신축_준공_세대수", 300000)
    seg1_base = new_build_total * region_ratio + remodel_units
    matrix_total = sum(v for row in matrix_pct for v in row)

    units_matrix = []
    for i in range(3):
        row = []
        for j in range(3):
            units = seg1_base * (matrix_pct[i][j] / 100) if matrix_total > 0 else 0
            row.append(units)
        units_matrix.append(row)

    ceily_sam1 = wally_sam1 = 0.0
    weighted_ceily = weighted_wally = 0.0
    for i in range(3):
        for j in range(3):
            units = units_matrix[i][j]
            c_prob = ceily_matrix[i][j] / 100
            w_prob = wally_matrix[i][j] / 100
            if product_combo != "Wally만":
                ceily_sam1 += units * c_prob * ceily_price
                weighted_ceily += units * c_prob
            if product_combo != "Ceily만":
                wally_sam1 += units * w_prob * wally_price
                weighted_wally += units * w_prob
    sam1 = ceily_sam1 + wally_sam1
    avg_adoption = (weighted_ceily + weighted_wally) / (2 * seg1_base) if seg1_base > 0 else 0

    # ── S2 호텔 ──
    hotel_new = get_val(data, "신규_호텔_개관수", 30)
    hotel_rooms = get_val(data, "호텔_평균_객실수", 150)
    seg2_base = hotel_new * hotel_rooms

    h5_r = get_val(data, "호텔_5성급_비중", 15) / 100
    h4_r = get_val(data, "호텔_4성급_비중", 30) / 100
    h3_r = get_val(data, "호텔_3성급이하_비중", 55) / 100

    ceily_sam2 = wally_sam2 = 0.0
    for grade_r, cp, wp in [
        (h5_r, hotel_ceily[0] / 100, hotel_wally[0] / 100),
        (h4_r, hotel_ceily[1] / 100, hotel_wally[1] / 100),
        (h3_r, hotel_ceily[2] / 100, hotel_wally[2] / 100),
    ]:
        rooms = seg2_base * grade_r
        if product_combo != "Wally만":
            ceily_sam2 += rooms * cp * ceily_price
        if product_combo != "Ceily만":
            wally_sam2 += rooms * wp * wally_price
    sam2 = ceily_sam2 + wally_sam2

    # ── S3 이사 수요 ──
    # Stage 2a: 중첩 제거를 "이사자 중 신축입주자 비율"로 재정의
    # (기존: pure_moving = 이사건수 − 신축준공 → 부정확한 가정)
    moving_total = get_val(data, "전국_연간_이사건수", 5_000_000)
    moving_regional = moving_total * region_ratio
    pure_moving = max(moving_regional * (1 - new_move_in_ratio), 0)
    moving_adoption = avg_adoption * (moving_ratio / 100)

    ceily_sam3 = wally_sam3 = 0.0
    if product_combo != "Wally만":
        ceily_sam3 = pure_moving * moving_adoption * ceily_price
    if product_combo != "Ceily만":
        wally_sam3 = pure_moving * moving_adoption * wally_price
    sam3 = ceily_sam3 + wally_sam3

    return DetailedKrSam(
        sam1=sam1, sam2=sam2, sam3=sam3,
        ceily_sam1=ceily_sam1, wally_sam1=wally_sam1,
        ceily_sam2=ceily_sam2, wally_sam2=wally_sam2,
        ceily_sam3=ceily_sam3, wally_sam3=wally_sam3,
        seg1_base=seg1_base, seg2_base=seg2_base, pure_moving=pure_moving,
        avg_adoption_rate=avg_adoption,
        units_matrix=units_matrix, region_ratio=region_ratio,
    )


# ─────────────────────────────────────────────────────────
# 2) Scenario mode (ir.py용)
# ─────────────────────────────────────────────────────────

# IR 카드 기본 가정 — Stage 2에서 재검증 예정
PEN_HOUSING_BASE = 0.10
PEN_HOTEL_BASE = 0.12
PEN_MOVING_BASE = 0.01
PEN_REMODEL_BASE = 0.15
REMODEL_UNITS_FIXED = 3_000
PRICE_HOUSING = 8_000_000
PRICE_HOTEL = 5_000_000
PRICE_MOVING = 3_000_000
PRICE_REMODEL = 8_000_000


def compute_scenario_sam(
    data: dict,
    scenario: str,
    new_move_in_ratio: float = NEW_MOVE_IN_RATIO_DEFAULT,
) -> dict:
    """IR 카드용 시나리오 기반 SAM 계산 (ir.py 로직 이식).

    반환: 각 세그먼트의 모집단·침투율·단가·SAM을 딕셔너리로 반환.
    ir.py가 카드 렌더링에 직접 사용하는 형태를 유지.
    """
    mult = SCENARIO_MULT[scenario]

    new_units = get_val(data, "전국_신축_준공_세대수", 449_835)
    sudo_pct = get_val(data, "수도권_비중", 48)
    moving = get_val(data, "전국_연간_이사건수", 6_283_000)
    hotel_new = get_val(data, "신규_호텔_개관수", 135)
    hotel_avg = get_val(data, "호텔_평균_객실수", 151)

    pen_housing = PEN_HOUSING_BASE * mult
    pen_hotel = PEN_HOTEL_BASE * mult
    pen_moving = PEN_MOVING_BASE * mult
    pen_remodel = PEN_REMODEL_BASE * mult

    s1_target = int(new_units * sudo_pct / 100) + REMODEL_UNITS_FIXED
    s1_reach = int(s1_target * pen_housing)
    s1_sam = s1_reach * PRICE_HOUSING

    s2_rooms = hotel_new * hotel_avg
    s2_reach = int(s2_rooms * pen_hotel)
    s2_sam = s2_reach * PRICE_HOTEL

    # Stage 2a: 이사 중첩 제거 공식 교체 (신축준공 차감 → 신축입주 비율)
    s3_regional = int(moving * sudo_pct / 100)
    s3_pure = max(int(s3_regional * (1 - new_move_in_ratio)), 0)
    s3_reach = int(s3_pure * pen_moving)
    s3_sam = s3_reach * PRICE_MOVING

    s4_reach = int(REMODEL_UNITS_FIXED * pen_remodel)
    s4_sam = s4_reach * PRICE_REMODEL

    return {
        "inputs": {
            "new_units": new_units, "sudo_pct": sudo_pct, "moving": moving,
            "hotel_new": hotel_new, "hotel_avg": hotel_avg,
            "new_move_in_ratio": new_move_in_ratio,
        },
        "rates": {
            "PEN_HOUSING": pen_housing, "PEN_HOTEL": pen_hotel,
            "PEN_MOVING": pen_moving, "PEN_REMODEL": pen_remodel,
        },
        "constants": {
            "REMODEL_UNITS": REMODEL_UNITS_FIXED,
            "PRICE_HOUSING": PRICE_HOUSING, "PRICE_HOTEL": PRICE_HOTEL,
            "PRICE_MOVING": PRICE_MOVING, "PRICE_REMODEL": PRICE_REMODEL,
        },
        "segments": {
            "신축 주거": {"target": s1_target, "reach": s1_reach, "sam": s1_sam},
            "호텔":     {"target": s2_rooms, "reach": s2_reach, "sam": s2_sam},
            "이사 수요": {"target": s3_pure, "reach": s3_reach, "sam": s3_sam},
            "리모델링":  {"target": REMODEL_UNITS_FIXED, "reach": s4_reach, "sam": s4_sam},
        },
    }
