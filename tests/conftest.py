"""Shared test fixtures."""
import json
import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sec_company_tickers():
    with open(FIXTURES_DIR / "sec" / "company_tickers_sample.json") as f:
        return json.load(f)


@pytest.fixture
def sec_submissions():
    with open(FIXTURES_DIR / "sec" / "submissions_sample.json") as f:
        return json.load(f)


@pytest.fixture
def openfigi_mapping():
    with open(FIXTURES_DIR / "openfigi" / "mapping_sample.json") as f:
        return json.load(f)


@pytest.fixture
def massive_eod_bars():
    with open(FIXTURES_DIR / "massive" / "eod_bars_sample.json") as f:
        return json.load(f)


@pytest.fixture
def massive_splits():
    with open(FIXTURES_DIR / "massive" / "splits_sample.json") as f:
        return json.load(f)


@pytest.fixture
def massive_dividends():
    with open(FIXTURES_DIR / "massive" / "dividends_sample.json") as f:
        return json.load(f)


@pytest.fixture
def fmp_income_statement():
    with open(FIXTURES_DIR / "fmp" / "income_statement_sample.json") as f:
        return json.load(f)


@pytest.fixture
def fmp_balance_sheet():
    with open(FIXTURES_DIR / "fmp" / "balance_sheet_sample.json") as f:
        return json.load(f)


@pytest.fixture
def fmp_cashflow():
    with open(FIXTURES_DIR / "fmp" / "cashflow_sample.json") as f:
        return json.load(f)


@pytest.fixture
def fmp_earnings_calendar():
    with open(FIXTURES_DIR / "fmp" / "earnings_calendar_sample.json") as f:
        return json.load(f)


@pytest.fixture
def t212_account_cash():
    with open(FIXTURES_DIR / "trading212" / "account_cash_sample.json") as f:
        return json.load(f)


@pytest.fixture
def t212_positions():
    with open(FIXTURES_DIR / "trading212" / "positions_sample.json") as f:
        return json.load(f)


@pytest.fixture
def t212_orders():
    with open(FIXTURES_DIR / "trading212" / "orders_sample.json") as f:
        return json.load(f)
