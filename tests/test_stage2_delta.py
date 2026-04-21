"""Stage 2 논리 수정 전후 비교.

Stage 2a(이사 overlap)와 Stage 2b(Ceily/Wally 배타적 믹스)가
SAM에 미치는 영향을 측정한다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.kr_model import (
    compute_detailed_sam,
    compute_scenario_sam,
    NEW_MOVE_IN_RATIO_DEFAULT,
    BUNDLE_DISCOUNT_DEFAULT,
)
from core.jp_model import JpSamParams, compute_jp_sam


def load_kr():
    with open(ROOT / "data" / "validated.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_jp():
    path = ROOT / "data" / "jp" / "validated.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


KR_MATRIX = [[4,11,7],[12,27,9],[11,14,5]]
KR_CEILY  = [[20,15,12],[10,8,5],[3,2,1]]
KR_WALLY  = [[25,20,15],[15,12,8],[5,4,2]]


def _kr_compute(data, region, new_move_in_ratio):
    return compute_detailed_sam(
        data=data, region=region,
        matrix_pct=KR_MATRIX, ceily_matrix=KR_CEILY, wally_matrix=KR_WALLY,
        hotel_ceily=(30, 15, 5), hotel_wally=(40, 20, 8),
        moving_ratio=20, remodel_units=3000,
        ceily_price=500, wally_price=300, product_combo="Ceily + Wally",
        new_move_in_ratio=new_move_in_ratio,
    )


def report_kr_stage2a():
    """한국 Stage 2a 이사수요 모수 변화."""
    data = load_kr()
    print("\n== 한국 Stage 2a 효과 (이사 중첩 제거 로직 교체) ==")
    print("수도권 기준 (region_ratio≒0.48, 신축준공 449,835, 이사 6,283,000):")
    new_res = _kr_compute(data, "수도권", NEW_MOVE_IN_RATIO_DEFAULT)

    # 기존 로직 이사 모수 수치 재현 (비교용 — 실제 코드는 이미 신규)
    moving_regional = 6_283_000 * 0.48
    seg1_base = 449_835 * 0.48 + 3_000
    old_pure = max(moving_regional - seg1_base, 0)
    new_pure = new_res.pure_moving
    print(f"  이사 모수(기존): {old_pure:,.0f}건 (=이사-신축준공-리모델링)")
    print(f"  이사 모수(신규): {new_pure:,.0f}건 (=이사×{(1-NEW_MOVE_IN_RATIO_DEFAULT)*100:.0f}%)")
    print(f"  Δ: {(new_pure-old_pure)/old_pure*100:+.1f}%")
    print(f"  신규 SAM(총): {new_res.total_sam/10000:,.0f}억원 (S3={new_res.sam3/10000:,.0f}억)")


def report_kr_scenario_stage2a():
    """한국 ir.py scenario 모드에서 Stage 2a 효과."""
    data = load_kr()
    print("\n== 한국 IR 카드(scenario) Stage 2a 효과 ==")
    for sc in ["보수", "중립", "공격"]:
        r = compute_scenario_sam(data, sc)
        s3_sam = r["segments"]["이사 수요"]["sam"] / 1e8
        s3_target = r["segments"]["이사 수요"]["target"]
        print(f"  {sc}: S3 target={s3_target:,}, SAM={s3_sam:,.0f}억원")


def _default_jp_params():
    return JpSamParams(
        s1_bun_tokyo=23000, s1_bun_osaka=15000, s1_bun_nagoya=6000,
        s1_rent_tokyo=119000, s1_rent_osaka=40500, s1_rent_nagoya=28600,
        region_mode="3대 도시권 합산",
        sz_s=15, sz_m=55, sz_l=30,
        pr_h=25, pr_m=50, pr_l=25,
        c1h=20, c1m=10, c1l=3,
        w1h=25, w1m=13, w1l=4,
        small_boost=1.3,
        s2_total=52800, s2_city=60,
        s3_hotel=250, s3_rooms=120,
        h5=8, h4=25, h3=67,
        c3_5=28, w3_5=32, c3_4=12, w3_4=16, c3_3=3, w3_3=4,
        ryokan_on=True, s3_ryokan=600, s3_ry_rooms=20, c3_ry=10, w3_ry=30,
        s4_moving=2_250_000, s4_ratio=25, s4_single=False,
        s5_corp=200, s5_units=80, s5_rate=5, c5=60, w5=70,
        s6_fac=600, s6_units=70, s6_city=55,
        s6_ind=40, s6_care=35, s6_mix=25,
        c6_i=25, c6_c=40, c6_m=32, w6_i=12, w6_c=8, w6_m=10,
        kaigo_ins=False,
        ceily_p=80, wally_p=50, combo="Ceily + Wally",
    )


def report_jp_stage2a():
    data = load_jp()
    p = _default_jp_params()
    r = compute_jp_sam(data, p)
    print("\n== 일본 Stage 2a 효과 ==")
    print(f"  이사 모수(신규): {r.pure_moving:,.0f}건 = 2,250,000 × 95%")
    print(f"  S4 SAM: {r.sam4/10000:,.0f}억엔")
    print(f"  총 SAM: {r.total_sam/10000:,.0f}억엔")
    print(f"  음수 경고 여부: {r.moving_overlap_warning}")


def report_kr_stage2b_mix():
    """한국 Stage 2b: 4분할 고객 분포 노출 + 번들 할인 민감도."""
    data = load_kr()
    print("\n== 한국 Stage 2b: 4분할 고객 분포 (수도권) ==")
    r0 = _kr_compute(data, "수도권", NEW_MOVE_IN_RATIO_DEFAULT)
    print(f"  세트 구매자:    {r0.s1_set_customers:,.0f}세대")
    print(f"  Ceily 단독:     {r0.s1_c_only_customers:,.0f}세대")
    print(f"  Wally 단독:     {r0.s1_w_only_customers:,.0f}세대")
    print(f"  미도입:         {r0.seg1_base - r0.s1_set_customers - r0.s1_c_only_customers - r0.s1_w_only_customers:,.0f}세대")
    print(f"  S1 모수:        {r0.seg1_base:,.0f}세대 (합계 확인)")

    print("\n  번들 할인 민감도 (세트 가격 할인):")
    for disc in [0.0, 0.05, 0.10, 0.15, 0.20]:
        res = compute_detailed_sam(
            data=data, region="수도권",
            matrix_pct=KR_MATRIX, ceily_matrix=KR_CEILY, wally_matrix=KR_WALLY,
            hotel_ceily=(30, 15, 5), hotel_wally=(40, 20, 8),
            moving_ratio=20, remodel_units=3000,
            ceily_price=500, wally_price=300, product_combo="Ceily + Wally",
            new_move_in_ratio=NEW_MOVE_IN_RATIO_DEFAULT,
            bundle_discount=disc,
        )
        print(f"    할인 {disc*100:.0f}%: 총 SAM = {res.total_sam/10000:,.0f}억원 "
              f"(Δ {(res.total_sam-r0.total_sam)/r0.total_sam*100:+.2f}%)")


def report_jp_stage2b_mix():
    data = load_jp()
    p = _default_jp_params()
    r0 = compute_jp_sam(data, p)
    print("\n== 일본 Stage 2b: 4분할 고객 분포 ==")
    print(f"  세트 구매자 (S1): {r0.s1_set_customers:,.0f}호")
    print(f"  Ceily 단독 (S1):  {r0.s1_c_only_customers:,.0f}호")
    print(f"  Wally 단독 (S1):  {r0.s1_w_only_customers:,.0f}호")

    print("\n  번들 할인 민감도:")
    for disc in [0.0, 0.05, 0.10, 0.15, 0.20]:
        p2 = _default_jp_params()
        p2.bundle_discount = disc
        r = compute_jp_sam(data, p2)
        print(f"    할인 {disc*100:.0f}%: 총 SAM = {r.total_sam/10000:,.0f}억엔 "
              f"(Δ {(r.total_sam-r0.total_sam)/r0.total_sam*100:+.2f}%)")


if __name__ == "__main__":
    report_kr_stage2a()
    report_kr_scenario_stage2a()
    report_jp_stage2a()
    report_kr_stage2b_mix()
    report_jp_stage2b_mix()
