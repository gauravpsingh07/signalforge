from app.services.metrics_service import build_slo_summary

TARGET = 0.995
FAST_BURN = 14.4


def test_healthy_when_error_rate_is_inside_budget() -> None:
    summary = build_slo_summary(1000, 2, 0, TARGET, FAST_BURN)

    assert summary["status"] == "healthy"
    assert summary["errorBudget"] == 0.005
    assert summary["burnRate"] == 0.4
    assert summary["budgetRemaining"] == 0.6


def test_at_risk_when_budget_is_burning_faster_than_pace() -> None:
    summary = build_slo_summary(1000, 10, 0, TARGET, FAST_BURN)

    assert summary["status"] == "at_risk"
    assert summary["burnRate"] == 2.0
    assert summary["budgetRemaining"] == 0.0


def test_burning_at_or_above_fast_burn_threshold() -> None:
    summary = build_slo_summary(100, 8, 0, TARGET, FAST_BURN)

    assert summary["status"] == "burning"
    assert summary["burnRate"] == 16.0


def test_no_data_without_events() -> None:
    summary = build_slo_summary(0, 0, 0, TARGET, FAST_BURN)

    assert summary["status"] == "no_data"
    assert summary["burnRate"] is None
    assert summary["budgetRemaining"] is None


def test_misconfigured_when_target_leaves_no_budget() -> None:
    summary = build_slo_summary(100, 1, 0, 1.0, FAST_BURN)

    assert summary["status"] == "misconfigured"
    assert summary["burnRate"] is None
