"""Integration tests — real database operations."""
from __future__ import annotations

import uuid
from datetime import date, datetime, UTC

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from libs.db.base import Base
from libs.db.models import *


def get_test_session() -> Session:
    """Get a session connected to the real test database."""
    engine = create_engine(
        "postgresql+psycopg2://quant:quant_dev_password@localhost:5432/quant_platform",
        echo=False,
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    return factory()


@pytest.fixture
def db():
    session = get_test_session()
    yield session
    session.rollback()
    session.close()


@pytest.mark.integration
class TestMigration:
    def test_all_tables_exist(self, db):
        """Verify all 19 tables were created by Alembic migration."""
        result = db.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ))
        tables = [row[0] for row in result]
        expected = [
            "alembic_version", "broker_account_snapshot", "broker_order_snapshot",
            "broker_position_snapshot", "corporate_action", "data_issue",
            "earnings_event", "exchange_calendar", "filing",
            "financial_fact_std", "financial_period", "instrument",
            "instrument_identifier", "macro_observation", "macro_series",
            "order_draft", "order_intent", "price_bar_raw",
            "source_run", "ticker_history",
        ]
        for t in expected:
            assert t in tables, f"Table {t} not found in database"


@pytest.mark.integration
class TestInstrumentWrite:
    def test_create_instrument(self, db):
        """Test writing an instrument to the database."""
        iid = uuid.uuid4()
        inst = Instrument(
            instrument_id=iid,
            asset_type="common_stock",
            issuer_name_current="Test Corp",
            exchange_primary="NYSE",
            currency="USD",
            country_code="US",
            is_active=True,
        )
        db.add(inst)
        db.flush()

        loaded = db.query(Instrument).get(iid)
        assert loaded is not None
        assert loaded.issuer_name_current == "Test Corp"
        assert loaded.asset_type == "common_stock"

    def test_create_instrument_with_identifiers(self, db):
        """Test writing instrument + identifiers."""
        iid = uuid.uuid4()
        db.add(Instrument(
            instrument_id=iid,
            asset_type="common_stock",
            issuer_name_current="Test Inc",
            currency="USD",
            is_active=True,
        ))
        db.add(InstrumentIdentifier(
            instrument_id=iid,
            id_type="ticker",
            id_value="TEST",
            source="test",
            valid_from=date(2020, 1, 1),
            is_primary=True,
        ))
        db.flush()

        idents = db.query(InstrumentIdentifier).filter_by(instrument_id=iid).all()
        assert len(idents) == 1
        assert idents[0].id_value == "TEST"


@pytest.mark.integration
class TestPriceBarWrite:
    def test_write_raw_bar(self, db):
        """Test writing a raw price bar."""
        iid = uuid.uuid4()
        db.add(Instrument(
            instrument_id=iid,
            asset_type="etf",
            issuer_name_current="Price Test ETF",
            currency="USD",
            is_active=True,
        ))
        db.flush()

        bar = PriceBarRaw(
            instrument_id=iid,
            trade_date=date(2024, 1, 2),
            source="test",
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1000000,
            raw_payload={"test": True},
        )
        db.add(bar)
        db.flush()

        result = db.execute(text(
            "SELECT open, high, low, close, volume FROM price_bar_raw "
            "WHERE instrument_id = :iid AND trade_date = '2024-01-02'"
        ), {"iid": str(iid)})
        row = result.fetchone()
        assert row is not None
        assert float(row[0]) == 100.0
        assert float(row[1]) == 105.0
        assert int(row[4]) == 1000000


@pytest.mark.integration
class TestFinancialWrite:
    def test_write_financial_period_and_facts(self, db):
        """Test writing financial_period + financial_fact_std."""
        iid = uuid.uuid4()
        db.add(Instrument(
            instrument_id=iid,
            asset_type="common_stock",
            issuer_name_current="Financials Test Corp",
            currency="USD",
            is_active=True,
        ))
        db.flush()

        fp_id = uuid.uuid4()
        fp = FinancialPeriod(
            financial_period_id=fp_id,
            instrument_id=iid,
            statement_scope="annual",
            fiscal_year=2024,
            period_end=date(2024, 12, 31),
            reported_at=datetime(2025, 2, 15, tzinfo=UTC),
            source="test",
        )
        db.add(fp)
        db.flush()

        facts = [
            FinancialFactStd(
                financial_period_id=fp_id,
                statement_type="income",
                metric_code="revenue",
                source="test",
                metric_value=1000000000,
                unit="USD",
            ),
            FinancialFactStd(
                financial_period_id=fp_id,
                statement_type="income",
                metric_code="netIncome",
                source="test",
                metric_value=200000000,
                unit="USD",
            ),
        ]
        for f in facts:
            db.add(f)
        db.flush()

        result = db.execute(text(
            "SELECT metric_code, metric_value FROM financial_fact_std "
            "WHERE financial_period_id = :fpid ORDER BY metric_code"
        ), {"fpid": str(fp_id)})
        rows = result.fetchall()
        assert len(rows) == 2
        codes = [r[0] for r in rows]
        assert "revenue" in codes
        assert "netIncome" in codes


@pytest.mark.integration
class TestAPIWithRealDB:
    def test_health_endpoint(self):
        """API health check works with real DB."""
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_instruments_endpoint_empty(self):
        """Instruments endpoint returns valid structure."""
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get("/instruments?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
