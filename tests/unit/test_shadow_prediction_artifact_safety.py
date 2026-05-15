"""Shadow-prediction artifact safety guard tests.

These tests anchor invariants that EVERY committed shadow-prediction
JSON artifact under `docs/premarket-shadow-prediction-*.json` must
satisfy. They are explicitly NOT about prediction quality — they
guarantee that the artifact itself is research-only, contains no
secrets, contains no banned trade-action language in
platform-generated fields, never references an external web price
source, and that every excluded ticker has an explicit watch_only
reason.

Scope:

  * The v1 artifact `docs/premarket-shadow-prediction-20260512.json`
    (committed, FROZEN — these tests must not change it).
  * The v2.1 artifact
    `docs/premarket-shadow-prediction-20260515-v2.1.json` (just
    committed).
  * Any future artifact matching the glob — scanned automatically so
    the guard travels with new captures.

These tests are pure file reads — no DB, no provider HTTP, no
network. They never modify the JSON they read.

If the test file lives alongside the artifact in the repo, the
artifact's committed contents are the test fixture. The tests will
auto-skip if the docs/ directory or matching files are absent (e.g.
on a fresh checkout that hasn't synced docs yet).
"""
from __future__ import annotations

import glob
import json
import os
import re
import string
from typing import Any

import pytest


REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
ARTIFACT_GLOB = os.path.join(
    REPO_ROOT, "docs", "premarket-shadow-prediction-*.json"
)


def _discover_artifacts() -> list[str]:
    files = sorted(glob.glob(ARTIFACT_GLOB))
    # Filter out anything that is clearly NOT a prediction artifact
    # (e.g. accidental sibling files). Each real artifact must be
    # valid JSON with a top-level `schema_version`.
    out = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(d, dict) and "schema_version" in d:
            out.append(f)
    return out


ARTIFACTS = _discover_artifacts()


# Banned trade-action vocabulary. Platform-generated fields in the
# artifact MUST NOT contain these. (External news headlines, if
# embedded as `recent_news[].title`, are publisher language and are
# EXEMPT — see §1 of every prediction narrative — but the v2.1
# artifact never embeds news titles, so this is currently a clean
# check across all platform-generated fields.)
BANNED_PLATFORM_PHRASES = (
    "buy now", "sell now", "enter long", "enter short",
    "target price", "position siz", "guaranteed",
    "必涨", "必跌", "买入建议", "卖出建议", "目标价", "仓位建议",
)


# Patterns that indicate a secret has leaked into the committed
# artifact (it never should — these are docs files).
SECRET_PATTERNS = [
    (re.compile(r"AIzaSy[A-Za-z0-9_-]{20,}"), "google api key"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "openai-style key"),
    (re.compile(r"Bearer\s+[A-Za-z0-9_-]{30,}"), "bearer token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (
        re.compile(
            r"postgres(?:ql)?://[A-Za-z0-9_]+:[A-Za-z0-9!@#%^&*()_+=\-]+@"
        ),
        "DSN with creds",
    ),
    (re.compile(r"github_pat_[A-Za-z0-9_]{30,}"), "GitHub PAT"),
    (re.compile(r"gh[opsu]_[A-Za-z0-9]{30,}"), "GitHub token"),
]


# Hosts that indicate the artifact pulled price data from an
# external web source — strictly forbidden as a primary eval source.
EXTERNAL_PRICE_HOSTS = (
    "finance.yahoo.com",
    "query1.finance.yahoo.com",
    "query2.finance.yahoo.com",
    "marketwatch.com",
    "investing.com",
    "tradingview.com",
    "bloomberg.com",
    "wsj.com",
    "stockanalysis.com",
    "nasdaq.com/market-activity",
    "morningstar.com",
    "barchart.com",
    "tipranks.com",
)


# ---------------------------------------------------------------------------
# Discovery: there must always be at least one artifact (we just
# committed v2.1 and v1 is already in the repo). If somehow none are
# found, the test plan flags it loudly.
# ---------------------------------------------------------------------------


def test_at_least_one_shadow_artifact_present():
    """If this fails on a fresh checkout, the docs/ directory is
    missing or the artifacts are gitignored. They should be tracked."""
    assert ARTIFACTS, (
        "no shadow-prediction artifact found under "
        f"{ARTIFACT_GLOB!r}. The v1 (20260512) and v2.1 (20260515) "
        "artifacts should both be committed."
    )


# ---------------------------------------------------------------------------
# Per-artifact parametrised checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "artifact_path", ARTIFACTS, ids=[os.path.basename(p) for p in ARTIFACTS],
)
class TestArtifactSafety:
    """Each test runs once per discovered artifact."""

    def _load(self, path: str) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _all_strings(self, obj: Any) -> list[str]:
        """Walk the JSON tree, return every string value the artifact
        carries (keys + values).

        News title fields are EXEMPT (publisher language) but the
        current v1 / v2.1 artifacts do not embed news titles, so we
        check everything. If a future artifact does embed news, this
        function should be extended to skip `recent_news[*].title`.
        """
        out: list[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str):
                    out.append(k)
                out.extend(self._all_strings(v))
        elif isinstance(obj, list):
            for item in obj:
                out.extend(self._all_strings(item))
        elif isinstance(obj, str):
            out.append(obj)
        return out

    # --- Required top-level shape ----------------------------------------

    def test_has_schema_version_and_test_id(self, artifact_path):
        d = self._load(artifact_path)
        assert "schema_version" in d
        assert "test_id" in d
        assert "preregistered_at" in d

    def test_side_effects_block_present_and_clean(self, artifact_path):
        d = self._load(artifact_path)
        se = d.get("side_effects")
        assert se, f"missing side_effects in {artifact_path}"
        assert se.get("db_writes") == "NONE"
        assert se.get("broker_writes") == "NONE"
        assert se.get("execution_objects") == "NONE"
        assert "LOCKED" in (se.get("live_submit") or "")
        assert "FEATURE_T212_LIVE_SUBMIT=false" in (
            se.get("live_submit") or ""
        )
        assert se.get("scheduler_changes") == "NONE"
        assert int(se.get("order_intents_created", 0)) == 0
        assert int(se.get("order_drafts_created", 0)) == 0

    def test_language_policy_present(self, artifact_path):
        d = self._load(artifact_path)
        lp = d.get("language_policy") or ""
        # Must reference research-only OR contain a no-trading-advice
        # equivalent phrase.
        assert "Research-only" in lp or "research-only" in lp.lower()
        assert "NEVER issues buy" in lp or "never issues buy" in lp.lower()

    # --- Banned-language guard ------------------------------------------

    def test_no_banned_trade_action_phrases_in_platform_fields(
        self, artifact_path,
    ):
        """The artifact's platform-generated text MUST NOT contain
        buy/sell/target/position-sizing language. The `language_policy`
        field IS the negation contract — it intentionally NAMES the
        banned phrases as things the platform never produces — so we
        exempt that specific field."""
        d = self._load(artifact_path)
        # Strip the negation-contract field
        d_for_scan = {k: v for k, v in d.items() if k != "language_policy"}
        all_strings = self._all_strings(d_for_scan)
        joined = " \n ".join(all_strings).lower()
        for phrase in BANNED_PLATFORM_PHRASES:
            assert phrase.lower() not in joined, (
                f"banned phrase {phrase!r} appears in "
                f"{artifact_path} (platform-generated fields)"
            )

    # --- Secret leak guard ----------------------------------------------

    def test_no_secret_patterns(self, artifact_path):
        with open(artifact_path, encoding="utf-8") as f:
            src = f.read()
        for pat, label in SECRET_PATTERNS:
            for m in pat.finditer(src):
                chunk = m.group(0)
                if "***" in chunk:
                    continue
                pytest.fail(
                    f"{label} pattern leaked into {artifact_path}: "
                    f"{chunk[:60]}"
                )

    # --- External web price source guard --------------------------------

    def test_no_external_web_price_sources(self, artifact_path):
        """The eval must use production `price_bar_raw` only. The
        artifact must NOT embed any external-web URL that looks like
        a price source."""
        with open(artifact_path, encoding="utf-8") as f:
            src = f.read().lower()
        for host in EXTERNAL_PRICE_HOSTS:
            assert host not in src, (
                f"{artifact_path} references external price source "
                f"{host!r} — strictly forbidden as a primary eval data "
                "source"
            )

    # --- Watch-only explicit-reason guard -------------------------------

    def test_watch_only_entries_have_explicit_reasons(self, artifact_path):
        """Every excluded ticker must carry a non-empty, finite-string
        reason. Empty / null / whitespace-only reasons are rejected."""
        d = self._load(artifact_path)
        wo = d.get("watch_only") or []
        if not wo:
            pytest.skip(
                f"artifact {os.path.basename(artifact_path)} has no "
                "watch_only entries — nothing to check"
            )
        for entry in wo:
            assert isinstance(entry, dict), (
                f"watch_only entry not a dict: {entry!r}"
            )
            assert entry.get("ticker"), (
                f"watch_only entry missing ticker: {entry!r}"
            )
            reason = entry.get("reason")
            assert reason and str(reason).strip(), (
                f"watch_only entry for {entry.get('ticker')!r} has "
                f"empty/missing reason: {entry!r}"
            )
            # The reason must be from the documented vocabulary
            # (v2.1 §2.1: unmapped / no_close_in_db / anchor_too_stale
            # / change_1d_pct_missing). Match by substring.
            vocab = (
                "mapping_status",  # "unmapped" wrapper
                "no_close_in_db",
                "anchor_too_stale",
                "change_1d_pct",
                # legacy v1 reasons (kept lenient)
                "unmapped",
                "mirror_bootstrap_bar_less",
                "missing",
            )
            assert any(v in str(reason).lower() for v in vocab), (
                f"watch_only reason {reason!r} for "
                f"{entry.get('ticker')!r} is not in the documented "
                f"vocabulary; got {reason!r}"
            )

    # --- Predictions structural guard -----------------------------------

    def test_predictions_have_required_per_row_fields(self, artifact_path):
        d = self._load(artifact_path)
        preds = d.get("predictions") or []
        if not preds:
            pytest.skip("artifact has no predictions[]")
        for p in preds:
            assert p.get("ticker"), f"prediction missing ticker: {p!r}"
            # Either v1's `predicted_direction` or any sibling label
            assert "predicted_direction" in p, p.keys()
            assert "predicted_return_bucket" in p
            assert "confidence" in p
            # The confidence must be one of the documented values
            assert p["confidence"] in ("low", "medium", "high")
            # If the row carries a `predicted_direction` string, it
            # must be one of the documented direction values across
            # v1 / v2 / v2.1. v1 used 3-state (up/flat/down); v2 and
            # v2.1 use 4-state (up/flat-up/flat-down/down).
            assert p["predicted_direction"] in (
                "up", "flat", "down", "flat-up", "flat-down",
            ), f"unknown direction in {p!r}"

    # --- v2.1-specific honesty guard ------------------------------------

    def test_v21_horizon_label_is_honest(self, artifact_path):
        """If the artifact's schema_version starts with 'v2.1', the
        horizon label MUST be the explicit
        `latest_db_close_to_target_close` to avoid claiming a pure
        T-1-to-T return under provider lag."""
        d = self._load(artifact_path)
        if not str(d.get("schema_version", "")).startswith("v2.1"):
            pytest.skip("not a v2.1 artifact")
        # Either the top-level horizon or every row's
        # prediction_horizon must carry the v2.1 label.
        top = d.get("preregistration_horizon") or d.get("prediction_horizon")
        if top:
            assert top == "latest_db_close_to_target_close", (
                f"v2.1 artifact has top-level horizon {top!r}; "
                "must be 'latest_db_close_to_target_close'"
            )
        for p in d.get("predictions") or []:
            ph = p.get("prediction_horizon")
            if ph is not None:
                assert ph == "latest_db_close_to_target_close", (
                    f"v2.1 row {p.get('ticker')!r} has horizon "
                    f"{ph!r}; must be 'latest_db_close_to_target_close'"
                )

    def test_v21_anchor_metadata_present(self, artifact_path):
        """v2.1 §2.1 requires per-row anchor_trade_date. We also
        accept a top-level anchor field when each row uses the same
        anchor (which is the normal case)."""
        d = self._load(artifact_path)
        if not str(d.get("schema_version", "")).startswith("v2.1"):
            pytest.skip("not a v2.1 artifact")
        top_anchor = (
            d.get("intended_anchor_trade_date")
            or d.get("anchor_trade_date")
        )
        for p in d.get("predictions") or []:
            row_anchor = p.get("anchor_trade_date")
            assert row_anchor or top_anchor, (
                f"v2.1 row {p.get('ticker')!r} has no anchor_trade_date "
                "and no top-level fallback"
            )

    def test_v21_target_after_anchor(self, artifact_path):
        """The target trade-date must be strictly after the anchor
        trade-date on every row."""
        from datetime import date

        d = self._load(artifact_path)
        if not str(d.get("schema_version", "")).startswith("v2.1"):
            pytest.skip("not a v2.1 artifact")
        top_target = d.get("target_trade_date")
        for p in d.get("predictions") or []:
            tgt = p.get("target_trade_date") or top_target
            anc = p.get("anchor_trade_date") or d.get(
                "intended_anchor_trade_date"
            )
            assert tgt and anc, (
                f"v2.1 row {p.get('ticker')!r} missing target or anchor"
            )
            tgt_d = date.fromisoformat(tgt)
            anc_d = date.fromisoformat(anc)
            assert tgt_d > anc_d, (
                f"v2.1 row {p.get('ticker')!r}: "
                f"target {tgt} is not strictly after anchor {anc}"
            )


# Note: this test module deliberately omits a self-referential
# "the test file must not contain banned needles" check, because such
# a check would always trip on its own banned-vocab catalog above.
# The broader repo-level source-grep run in CI / pre-commit covers
# the same concern with smarter context-aware filtering.
