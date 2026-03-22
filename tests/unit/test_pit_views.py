"""Unit tests for PIT view logic."""
import pytest
from datetime import datetime, UTC


@pytest.mark.unit
class TestPITFiltering:
    def test_pit_safe_filter(self):
        """Only data reported before asof should be visible."""
        data = [
            {"metric": "revenue", "reported_at": datetime(2024, 2, 15, tzinfo=UTC), "value": 100},
            {"metric": "revenue", "reported_at": datetime(2024, 5, 15, tzinfo=UTC), "value": 200},
            {"metric": "revenue", "reported_at": datetime(2024, 8, 15, tzinfo=UTC), "value": 300},
        ]
        asof = datetime(2024, 6, 1, tzinfo=UTC)
        visible = [d for d in data if d["reported_at"] <= asof]
        assert len(visible) == 2
        assert visible[-1]["value"] == 200

    def test_pit_latest_only(self):
        """Should return the most recent reported value."""
        data = [
            {"metric": "revenue", "period_end": "2023-12-31", "reported_at": datetime(2024, 2, 15, tzinfo=UTC), "value": 100},
            {"metric": "revenue", "period_end": "2024-03-31", "reported_at": datetime(2024, 5, 15, tzinfo=UTC), "value": 200},
        ]
        asof = datetime(2024, 6, 1, tzinfo=UTC)
        visible = [d for d in data if d["reported_at"] <= asof]
        latest = max(visible, key=lambda x: x["period_end"])
        assert latest["value"] == 200
