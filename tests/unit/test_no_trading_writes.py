"""Source-grep guards — the near-real-time broker truth feature must not
introduce any path from a live readonly endpoint, the cache layer, or the
sync_trading212_readonly module to a T212 write endpoint or to the
controlled-execution objects.

These tests run a static inspection over the changed modules' executable
source (with docstrings, comments, and string literals stripped — those
deliberately mention forbidden symbols in negation form, e.g. "this
module NEVER calls ..."). They do not exercise runtime behavior — that
is covered by the other test files.
"""
from __future__ import annotations

import ast
import inspect
import io
import tokenize

import pytest

from apps.api.routers import broker as broker_router
from libs.ingestion import sync_trading212_readonly as sync_module
from libs.portfolio import broker_live_cache as cache_module
from libs.portfolio import portfolio_service as portfolio_module


FORBIDDEN_T212_WRITE_PATHS = (
    "/equity/orders/limit",
    "/equity/orders/market",
    "submit_limit_order",
    "submit_market_order",
    "submit_order",
)

FORBIDDEN_EXEC_OBJECTS = (
    "OrderIntent",
    "OrderDraft",
    "order_intent",
    "order_draft",
)


def _strip_python(src: str) -> str:
    """Return executable Python source with comments and string literals removed.

    Mirrors the convention established in `tests/unit/test_sync_eod_prices_universe.py`
    so that docstrings / negation-language comments don't trip the grep.
    """
    out: list[str] = []
    try:
        tokens = tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline)
        for tok in tokens:
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            if tok.type == tokenize.ENCODING:
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    stripped = "".join(out)
    # Also remove module-level docstrings via AST (in case the tokenizer
    # missed an f-string or similar).
    try:
        tree = ast.parse(src)
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            tree.body = tree.body[1:]
        return stripped + "\n" + ast.unparse(tree)
    except Exception:
        return stripped


def _all_modules():
    return [
        ("apps.api.routers.broker", broker_router),
        ("libs.ingestion.sync_trading212_readonly", sync_module),
        ("libs.portfolio.broker_live_cache", cache_module),
        ("libs.portfolio.portfolio_service", portfolio_module),
    ]


@pytest.mark.unit
@pytest.mark.parametrize("name,module", _all_modules())
def test_module_does_not_call_t212_write_endpoint(name, module):
    src = _strip_python(inspect.getsource(module))
    for needle in FORBIDDEN_T212_WRITE_PATHS:
        assert needle not in src, (
            f"{name} must not reference {needle} (T212 write surface)"
        )


@pytest.mark.unit
@pytest.mark.parametrize("name,module", _all_modules())
def test_module_does_not_touch_execution_objects(name, module):
    src = _strip_python(inspect.getsource(module))
    for needle in FORBIDDEN_EXEC_OBJECTS:
        assert needle not in src, (
            f"{name} must not reference {needle} (execution-side object)"
        )


@pytest.mark.unit
def test_live_submit_flag_is_not_mutated_by_new_modules():
    """The feature flag is set in libs/core/config.py and read by the
    adapter. None of the new files should write or override it."""
    for _name, module in _all_modules():
        src = _strip_python(inspect.getsource(module))
        for pattern in (
            "feature_t212_live_submit = True",
            "FEATURE_T212_LIVE_SUBMIT = True",
            "feature_t212_live_submit=True",
        ):
            assert pattern not in src
