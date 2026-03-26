"""Phase 6 — Daily Research Platform integration tests."""
import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


class TestDailyBrief:
    """Test /daily endpoints."""

    def test_daily_brief_returns_200(self):
        r = client.get("/daily/brief")
        assert r.status_code == 200
        data = r.json()
        assert "data_status" in data
        assert "dq_status" in data
        assert "upcoming_earnings" in data
        assert "execution_status" in data
        assert "generated_at" in data

    def test_daily_brief_data_status_fields(self):
        r = client.get("/daily/brief")
        ds = r.json()["data_status"]
        assert "total_instruments" in ds
        assert "total_price_bars" in ds
        assert "latest_bar_date" in ds
        assert "data_freshness" in ds

    def test_recent_activity_returns_200(self):
        r = client.get("/daily/recent-activity")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_recent_activity_limit(self):
        r = client.get("/daily/recent-activity?limit=3")
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 3


class TestWatchlistAPI:
    """Test /watchlist endpoints."""

    def test_list_groups_empty(self):
        r = client.get("/watchlist/groups")
        assert r.status_code == 200
        assert "groups" in r.json()

    def test_create_and_list_group(self):
        r = client.post("/watchlist/groups", json={"name": "Test Group", "is_default": False})
        assert r.status_code == 200
        gid = r.json()["group_id"]
        assert gid

        r2 = client.get("/watchlist/groups")
        groups = r2.json()["groups"]
        names = [g["name"] for g in groups]
        assert "Test Group" in names

    def test_add_and_list_items(self):
        # Create a group
        r = client.post("/watchlist/groups", json={"name": "Item Test", "is_default": False})
        gid = r.json()["group_id"]

        # Get an instrument
        r_inst = client.get("/instruments?limit=1")
        items = r_inst.json().get("items", [])
        if not items:
            pytest.skip("No instruments in DB")

        inst_id = items[0]["instrument_id"]

        # Add item
        r_add = client.post(f"/watchlist/groups/{gid}/items", json={"instrument_id": inst_id, "notes": "testing"})
        assert r_add.status_code == 200

        # List items
        r_list = client.get(f"/watchlist/groups/{gid}/items")
        assert r_list.status_code == 200
        assert r_list.json()["total"] >= 1

    def test_delete_group(self):
        r = client.post("/watchlist/groups", json={"name": "ToDelete"})
        gid = r.json()["group_id"]
        r_del = client.delete(f"/watchlist/groups/{gid}")
        assert r_del.status_code == 200
        assert r_del.json()["deleted"] is True


class TestPresetsAPI:
    """Test /presets endpoints."""

    def test_list_presets_empty(self):
        r = client.get("/presets")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_create_preset(self):
        r = client.post("/presets", json={
            "name": "My Screen",
            "preset_type": "screener",
            "config": {"min_volume": 1000000},
            "description": "High volume filter"
        })
        assert r.status_code == 200
        assert r.json()["name"] == "My Screen"

    def test_use_preset(self):
        r = client.post("/presets", json={
            "name": "Use Test",
            "preset_type": "screener",
            "config": {"x": 1}
        })
        pid = r.json()["preset_id"]
        r_use = client.post(f"/presets/{pid}/use")
        assert r_use.status_code == 200
        assert r_use.json()["use_count"] == 1

    def test_update_preset(self):
        r = client.post("/presets", json={
            "name": "Update Me",
            "preset_type": "backtest",
            "config": {"a": 1}
        })
        pid = r.json()["preset_id"]
        r_up = client.put(f"/presets/{pid}", json={"name": "Updated"})
        assert r_up.status_code == 200

    def test_delete_preset(self):
        r = client.post("/presets", json={
            "name": "Delete Me",
            "preset_type": "research",
            "config": {}
        })
        pid = r.json()["preset_id"]
        r_del = client.delete(f"/presets/{pid}")
        assert r_del.status_code == 200

    def test_filter_by_type(self):
        client.post("/presets", json={"name": "BT1", "preset_type": "backtest", "config": {}})
        r = client.get("/presets?preset_type=backtest")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["preset_type"] == "backtest"


class TestNotesAPI:
    """Test /notes endpoints."""

    def test_list_notes_empty(self):
        r = client.get("/notes")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_create_note(self):
        r = client.post("/notes", json={
            "title": "NVDA Bull Case",
            "content": "AI infrastructure spending accelerating",
            "note_type": "thesis",
            "tags": {"tags": ["ai", "semiconductor"]}
        })
        assert r.status_code == 200
        assert r.json()["title"] == "NVDA Bull Case"

    def test_update_note(self):
        r = client.post("/notes", json={
            "title": "Edit Me",
            "content": "Original",
            "note_type": "observation"
        })
        nid = r.json()["note_id"]
        r_up = client.put(f"/notes/{nid}", json={"content": "Updated content"})
        assert r_up.status_code == 200

    def test_delete_note(self):
        r = client.post("/notes", json={
            "title": "Remove Me",
            "content": "Temp",
        })
        nid = r.json()["note_id"]
        r_del = client.delete(f"/notes/{nid}")
        assert r_del.status_code == 200

    def test_filter_by_type(self):
        client.post("/notes", json={"title": "Risk note", "content": "x", "note_type": "risk"})
        r = client.get("/notes?note_type=risk")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["note_type"] == "risk"
