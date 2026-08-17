from datetime import datetime

from backend.app.modules.analytics.service import recent_months


def test_recent_months_crosses_year_boundary():
    assert recent_months(datetime(2026, 2, 1), count=4) == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]

