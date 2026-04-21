"""시장규모 계산 엔진 (Single Source of Truth).

app.py / ir.py / app_japan.py는 모두 이 모듈을 호출하여 SAM을 계산한다.
리팩토링 이력:
- Stage 1 (현재): 기존 로직 그대로 추출 — 수치 불변
- Stage 2a: 이사수요 중첩제거 로직 교체 (신축준공 차감 → 신축입주이사 비율)
- Stage 2b: Ceily/Wally 덧셈 → 배타적 4분할 제품 믹스
"""
