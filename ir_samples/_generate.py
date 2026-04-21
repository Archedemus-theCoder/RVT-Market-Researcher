"""IR 페이지 샘플 이미지 4종 생성 (개선판).
1) 1_hero.png         — 헤드라인 요약 (결론 먼저)
2) 2_stacked_bar.png  — 세그먼트 기여도: SAM / SOM 스택바 + TAM 퍼센티지 표시
3) 3_waterfall.png    — 세그먼트별 수평 퍼널 (모수 → 필터 → SAM)
4) 4_formula_card.png — 수식 카드 1장 (신축 주거 예시)
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, Rectangle

# ── 한글 폰트 ──
font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
bold_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
fm.fontManager.addfont(font_path)
fm.fontManager.addfont(bold_path)
plt.rcParams["font.family"] = "Noto Sans CJK JP"
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).parent

# ── 수치 (validated.json 스냅샷 기반) ──
SEG = {
    "신축 주거":   {"sam": 1751, "color": "#2E5EAA"},
    "호텔":        {"sam":  122, "color": "#6F9CEB"},
    "이사 수요":   {"sam":  839, "color": "#F4A259"},
    "리모델링":    {"sam":   36, "color": "#C44536"},
}
TOTAL_SAM = sum(v["sam"] for v in SEG.values())   # 2,748
TAM       = 150_000                                # 억원 (15조)
SOM_PCT   = 2.0
TOTAL_SOM = round(TOTAL_SAM * SOM_PCT / 100, 1)    # 55.0

BG = "#0E1117"; FG = "#FAFAFA"; MUTED = "#9BA3AF"; ACCENT = "#F59E0B"


def _style(ax, darkbg=True):
    bg, fg = (BG, FG) if darkbg else ("#FFFFFF", "#111111")
    ax.set_facecolor(bg)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=fg)
    for axis in (ax.yaxis, ax.xaxis):
        axis.label.set_color(fg)
    ax.title.set_color(fg)
    return bg, fg


# ─────────────────────────────────────────
# 1) HERO
# ─────────────────────────────────────────
def make_hero():
    fig, ax = plt.subplots(figsize=(14, 6.5), dpi=140)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    ax.text(3, 92, "Rovothome 시장 규모", fontsize=14, color=MUTED, weight="light")
    ax.text(3, 82, "Bottom-up으로 산출한 한국 시장 SOM",
            fontsize=28, color=FG, weight="bold")

    cards = [
        ("TAM", "15.0",          "조원",                         "한국 인테리어·가구 전체 시장", "#334155"),
        ("SAM", f"{TOTAL_SAM:,}", "억원",                         "4개 세그먼트 합산",             "#2E5EAA"),
        ("SOM", f"{TOTAL_SOM:,.0f}", "억원 (1년차 · 점유율 2%)",  "실현 가능 시장",                "#F59E0B"),
    ]
    x0, w, gap = 3, 30, 2
    for i, (label, num, unit, sub, col) in enumerate(cards):
        x = x0 + i * (w + gap)
        box = FancyBboxPatch((x, 18), w, 48,
                             boxstyle="round,pad=0.02,rounding_size=2",
                             linewidth=0, facecolor=col, alpha=0.18)
        ax.add_patch(box)
        ax.text(x + 2, 58, label, fontsize=13, color=col, weight="bold")
        ax.text(x + 2, 38, num, fontsize=54, color=FG, weight="bold")
        ax.text(x + 2, 30, unit, fontsize=12, color=MUTED)
        ax.text(x + 2, 23, sub, fontsize=11, color=FG, alpha=0.8)

    ax.text(3, 10, "산출 방식: 세그먼트별 모수 × 지역필터 × 침투율 × 객단가",
            fontsize=11, color=MUTED)
    ax.text(3, 5,  "데이터 출처: 국토교통부 · 통계청 · 문화체육관광부 · HUG (2024–2025)",
            fontsize=10, color=MUTED, style="italic")

    plt.savefig(OUT / "1_hero.png", facecolor=BG, bbox_inches="tight", pad_inches=0.3)
    plt.close()
    print("✓ 1_hero.png")


# ─────────────────────────────────────────
# 2) STACKED BAR — SAM/SOM 세그먼트 스택 + TAM은 옆에 비율 카드
# ─────────────────────────────────────────
def make_stacked_bar():
    fig, (ax_card, ax) = plt.subplots(1, 2, figsize=(14, 7), dpi=140,
                                       gridspec_kw={"width_ratios": [1, 3]})
    fig.patch.set_facecolor(BG)
    ax_card.set_facecolor(BG); _style(ax)
    ax_card.axis("off")

    # TAM 카드 (왼쪽)
    card = FancyBboxPatch((0.05, 0.15), 0.9, 0.75, transform=ax_card.transAxes,
                          boxstyle="round,pad=0.01,rounding_size=0.02",
                          linewidth=0, facecolor="#334155", alpha=0.25)
    ax_card.add_patch(card)
    ax_card.text(0.5, 0.82, "TAM", transform=ax_card.transAxes,
                 ha="center", fontsize=16, color=FG, weight="bold")
    ax_card.text(0.5, 0.65, "150,000", transform=ax_card.transAxes,
                 ha="center", fontsize=38, color=FG, weight="bold")
    ax_card.text(0.5, 0.55, "억원", transform=ax_card.transAxes,
                 ha="center", fontsize=13, color=MUTED)
    ax_card.text(0.5, 0.42, "한국 인테리어·가구", transform=ax_card.transAxes,
                 ha="center", fontsize=11, color=FG, alpha=0.8)
    ax_card.text(0.5, 0.30, "전체 시장 (15조원)", transform=ax_card.transAxes,
                 ha="center", fontsize=11, color=FG, alpha=0.8)
    ax_card.text(0.5, 0.18, f"→ SAM은 TAM 대비  {TOTAL_SAM/TAM*100:.1f}%",
                 transform=ax_card.transAxes,
                 ha="center", fontsize=10, color=ACCENT, weight="bold")

    # 오른쪽: SAM / SOM 스택바 (선형 스케일)
    seg_names  = list(SEG.keys())
    seg_colors = [SEG[n]["color"] for n in seg_names]
    sam_vals   = [SEG[n]["sam"] for n in seg_names]
    som_vals   = [round(s * SOM_PCT / 100, 1) for s in sam_vals]

    # SAM 바
    bottom = 0
    for name, col, v in zip(seg_names, seg_colors, sam_vals):
        ax.bar(0, v, bottom=bottom, color=col, width=0.5)
        if v > 80:
            ax.text(0, bottom + v / 2, f"{name}\n{v:,}억 ({v/TOTAL_SAM*100:.0f}%)",
                    ha="center", va="center", fontsize=11, color="white", weight="bold")
        else:
            # 작은 세그먼트는 오른쪽 외부 주석
            ax.annotate(f"{name}  {v:,}억",
                        xy=(0.25, bottom + v / 2), xytext=(0.6, bottom + v / 2),
                        fontsize=10, color=col, weight="bold", va="center",
                        arrowprops=dict(arrowstyle="-", color=col, lw=0.8))
        bottom += v

    # SOM 바
    bottom = 0
    for name, col, v in zip(seg_names, seg_colors, som_vals):
        ax.bar(1, v, bottom=bottom, color=col, width=0.5)
        bottom += v

    # 합계 라벨
    ax.text(0, TOTAL_SAM * 1.03, f"SAM  {TOTAL_SAM:,}억원",
            ha="center", color=FG, fontsize=14, weight="bold")
    ax.text(1, TOTAL_SAM * 1.03, f"SOM  {TOTAL_SOM:,.0f}억원",
            ha="center", color=ACCENT, fontsize=14, weight="bold")
    ax.text(1, TOTAL_SOM + 30, f"(SAM의 {SOM_PCT:.1f}%)",
            ha="center", color=MUTED, fontsize=10)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["SAM\n(도달 가능 시장)", "SOM\n(1년차 점유)"],
                       fontsize=12, color=FG)
    ax.set_ylabel("억원", color=FG)
    ax.set_ylim(0, TOTAL_SAM * 1.18)
    ax.set_xlim(-0.8, 1.8)
    ax.grid(axis="y", alpha=0.12)

    # 범례
    handles = [mpatches.Patch(color=SEG[n]["color"],
                              label=f"{n}  {SEG[n]['sam']:,}억 ({SEG[n]['sam']/TOTAL_SAM*100:.0f}%)")
               for n in seg_names]
    ax.legend(handles=handles, loc="upper right", frameon=False,
              labelcolor=FG, fontsize=11, title="세그먼트 기여도",
              title_fontsize=11)

    fig.suptitle("TAM → SAM → SOM  (세그먼트별 기여도)",
                 color=FG, fontsize=18, weight="bold", x=0.05, ha="left", y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(OUT / "2_stacked_bar.png", facecolor=BG, bbox_inches="tight", pad_inches=0.3)
    plt.close()
    print("✓ 2_stacked_bar.png")


# ─────────────────────────────────────────
# 3) 수평 퍼널 — 세그먼트별 4연작
# ─────────────────────────────────────────
def _funnel(ax, steps, title, color, sam_krw):
    """steps: [(라벨, 설명, 잔존값, 단위)] — 수량 단계만. 마지막에 SAM(원)은 별도 블록으로 표시.
       sam_krw: 최종 SAM (원 단위). 별도 highlight 블록으로 그림."""
    _style(ax)
    n = len(steps)
    # 수량 단계 최대값으로 폭 정규화
    qty_vals = [v for (_, _, v, _) in steps if v > 0]
    mx = max(qty_vals) if qty_vals else 1

    for i, (lab, desc, val, unit) in enumerate(steps):
        y = n - i  # 위→아래 (맨 위 = 첫 단계)
        if val <= 0:  # 빈 행 (정렬 padding)
            continue
        ratio = val / mx
        width = ratio * 0.82 + 0.03
        alpha_val = max(0.25, min(1.0, 0.35 + 0.6 * ratio))
        ax.barh(y, width, left=0.03, height=0.62, color=color,
                alpha=alpha_val, edgecolor="none")
        # 좌측 단계 번호
        ax.text(0.0, y, f"{i + 1}", ha="right", va="center",
                color=MUTED, fontsize=10, weight="bold")
        # 바 내부 라벨
        ax.text(0.05, y, lab, ha="left", va="center",
                color="white", fontsize=11, weight="bold")
        # 오른쪽: 수치 + 설명
        num = f"{val:,}" + f" {unit}" if unit else f"{val:,}"
        ax.text(0.93, y + 0.15, num, ha="left", va="center",
                color=FG, fontsize=12, weight="bold")
        if desc:
            ax.text(0.93, y - 0.19, desc, ha="left", va="center",
                    color=MUTED, fontsize=9)

    # SAM 결과 블록 (맨 아래)
    y_sam = 0
    sam_bar = Rectangle((0.03, y_sam - 0.31), 0.85, 0.62,
                        color=ACCENT, alpha=0.95)
    ax.add_patch(sam_bar)
    ax.text(0.0, y_sam, f"{n + 1}", ha="right", va="center",
            color=ACCENT, fontsize=10, weight="bold")
    ax.text(0.05, y_sam, "SAM  (× 객단가)", ha="left", va="center",
            color="#1F2937", fontsize=11, weight="bold")
    ax.text(0.93, y_sam, f"{sam_krw:,}억원", ha="left", va="center",
            color=ACCENT, fontsize=15, weight="bold")

    ax.set_xlim(-0.04, 1.35)
    ax.set_ylim(-0.7, n + 0.7)
    ax.set_yticks([]); ax.set_xticks([])
    ax.set_title(title, color=FG, fontsize=14, weight="bold", loc="left", pad=10)


def make_waterfall():
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), dpi=140)
    fig.patch.set_facecolor(BG)
    fig.suptitle("세그먼트별 Bottom-up 산출 경로   (모수 → 필터 → SAM)",
                 color=FG, fontsize=19, weight="bold", x=0.02, ha="left", y=0.985)

    # S1 신축 주거: 449,835 → ×48% → +3K → ×10% → ×800만원 = 1,751억
    _funnel(axes[0, 0], [
        ("전국 신축 준공",  "국토교통부 2024",       449_835, "세대"),
        ("수도권",          "× 48%",                 int(449_835 * 0.48), "세대"),
        ("+ 리모델링",      "+ 3,000세대",           int(449_835 * 0.48) + 3_000, "세대"),
        ("침투율 적용",     "× 10% (Ceily+Wally)",   int((449_835 * 0.48 + 3_000) * 0.10), "세대"),
    ], "S1 · 신축 주거", SEG["신축 주거"]["color"], sam_krw=1_751)

    # S2 호텔
    _funnel(axes[0, 1], [
        ("신규 개관 호텔",  "문체부 2024",           135, "개"),
        ("총 객실",         "× 151실/개",            int(135 * 151), "실"),
        ("침투율 적용",     "× 12% (등급 가중)",     int(135 * 151 * 0.12), "실"),
        ("",                "",                      -1, ""),
    ], "S2 · 호텔", SEG["호텔"]["color"], sam_krw=122)

    # S3 이사
    _funnel(axes[1, 0], [
        ("연간 이사건수",   "통계청 2024",           6_283_000, "건"),
        ("수도권",          "× 48%",                 int(6_283_000 * 0.48), "건"),
        ("신축 중첩 제외",  "− 신축 218,921",        int(6_283_000 * 0.48) - 218_921, "건"),
        ("침투율 적용",     "× 1%",                  int((6_283_000 * 0.48 - 218_921) * 0.01), "건"),
    ], "S3 · 이사 수요", SEG["이사 수요"]["color"], sam_krw=839)

    # S4 리모델링
    _funnel(axes[1, 1], [
        ("노후주택 리모델링", "사내 추정 (고정)",     3_000, "세대"),
        ("타겟 필터",        "× 100%",                3_000, "세대"),
        ("침투율 적용",      "× 15%",                 int(3_000 * 0.15), "세대"),
        ("",                 "",                      -1, ""),
    ], "S4 · 리모델링", SEG["리모델링"]["color"], sam_krw=36)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(OUT / "3_waterfall.png", facecolor=BG, bbox_inches="tight", pad_inches=0.3)
    plt.close()
    print("✓ 3_waterfall.png")


# ─────────────────────────────────────────
# 4) FORMULA CARD — 신축 주거 수식 카드
# ─────────────────────────────────────────
def make_formula_card():
    fig, ax = plt.subplots(figsize=(11, 9), dpi=140)
    fig.patch.set_facecolor("#FFFFFF"); ax.set_facecolor("#FFFFFF")
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    card = FancyBboxPatch((3, 4), 94, 92,
                          boxstyle="round,pad=0.02,rounding_size=2",
                          linewidth=1.2, edgecolor="#E5E7EB", facecolor="#FFFFFF")
    ax.add_patch(card)

    # 세그먼트 컬러 헤더
    cbar = Rectangle((3, 89), 94, 7, color=SEG["신축 주거"]["color"], alpha=1)
    ax.add_patch(cbar)
    ax.text(6, 92.5, "SEG 1 · 신축 주거", color="white",
            fontsize=15, weight="bold", va="center")
    ax.text(94, 92.5, "SAM 1,751억원", color="white",
            fontsize=15, weight="bold", va="center", ha="right")

    rows = [
        ("전국 신축 준공 세대수",       "449,835",     "세대",   "fact",  "국토교통부 주택건설 실적 ('24)"),
        ("×  수도권 비중",               "48.0",       "%",      "fact",  "국토교통부 월간 주택통계 ('25)"),
        ("+  리모델링 세대수",           "3,000",      "세대",   "assump","사내 추정 (고정)"),
        ("×  침투율 (Ceily+Wally 가중)", "10.0",       "%",      "assump","보수 가정 (시나리오: 중립)"),
        ("×  객단가 (세트)",             "8,000,000",  "원",     "fact",  "사내 pricing"),
    ]

    ax.text(6, 82, "계산 경로", fontsize=11, color="#6B7280", weight="bold")
    ax.plot([6, 94], [80, 80], color="#E5E7EB", lw=1)

    y0 = 76
    for i, (lab, val, unit, kind, src) in enumerate(rows):
        y = y0 - i * 9
        ax.text(6, y, lab, fontsize=13, color="#111827",
                weight="bold" if i == 0 else "normal")
        # 숫자는 모노스페이스 대신 Noto Sans CJK로 (한글 tofu 방지)
        ax.text(58, y, val, fontsize=15, color="#111827", ha="right", weight="bold")
        ax.text(60, y, unit, fontsize=11, color="#6B7280", ha="left")
        badge_color = "#10B981" if kind == "fact" else "#F59E0B"
        badge_text  = "FACT"   if kind == "fact" else "추정"
        badge = FancyBboxPatch((70, y - 1.8), 8, 4,
                               boxstyle="round,pad=0.02,rounding_size=1",
                               linewidth=0, facecolor=badge_color, alpha=0.15)
        ax.add_patch(badge)
        ax.text(74, y, badge_text, fontsize=9, color=badge_color,
                ha="center", va="center", weight="bold")
        ax.text(79, y, src, fontsize=9, color="#6B7280")

    result = FancyBboxPatch((6, 14), 88, 12,
                            boxstyle="round,pad=0.02,rounding_size=2",
                            linewidth=0, facecolor=SEG["신축 주거"]["color"], alpha=0.1)
    ax.add_patch(result)
    ax.text(9, 20, "= SAM", fontsize=15, color=SEG["신축 주거"]["color"], weight="bold")
    ax.text(92, 20, "1,751억원", fontsize=30, color=SEG["신축 주거"]["color"],
            weight="bold", ha="right")
    ax.text(92, 15.5, "(SOM 1년차, 점유율 2% → 35.0억원)", fontsize=10,
            color="#6B7280", ha="right")

    ax.text(6, 8, "● FACT = 출처 있는 공식 통계     ● 추정 = 사내 가정치 (시나리오 조정 가능)",
            fontsize=9, color="#6B7280")

    plt.savefig(OUT / "4_formula_card.png", facecolor="#FFFFFF",
                bbox_inches="tight", pad_inches=0.3)
    plt.close()
    print("✓ 4_formula_card.png")


if __name__ == "__main__":
    make_hero()
    make_stacked_bar()
    make_waterfall()
    make_formula_card()
    print("\n생성 완료:", OUT)
