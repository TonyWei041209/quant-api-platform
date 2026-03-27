# AI Effectiveness Validation Report

## Overview
- **Date**: 2026-03-27
- **Samples**: 7 (3 holdings, 2 candidates, 2 controls)
- **Providers**: OpenAI GPT-4o (primary), Gemini 2.5 Pro (validation), Gemini 2.5 Flash (preprocess)
- **Mode**: Real providers (not mock)

## Lane-Level Results

### Lane 1: Cheap Preprocess (Gemini 2.5 Flash)
- **Verdict**: KEEP — fast, accurate document classification
- Correctly identifies earnings reports, extracts entities and event tags
- Latency: ~3s, Cost: minimal

### Lane 2: Primary Research (GPT-4o)
- **Verdict**: KEEP — genuine research value
- **Success rate**: 100% (7/7)
- **Anti-hype compliance**: 100%
- **Avg risks found**: 3.9 per sample
- **Schema validity**: 100%
- Properly distinguishes fact/inference/speculation
- Correctly flags missing information
- Provides actionable invalidation signals

### Lane 3: Validation (Gemini 2.5 Pro)
- **Verdict**: KEEP but FIX JSON parsing
- Validation calls succeed but structured JSON output often fails parsing
- When parsed, provides genuinely independent critique
- Issue: Gemini 2.5 Pro's "thinking" mode wraps output in extra text
- **Action needed**: Improve JSON extraction logic or use `responseMimeType: application/json`

## Sample-Level Findings

### Holdings

| Symbol | Thesis | Confidence | Risks | Invalidations | Anti-Hype | Useful |
|--------|--------|------------|-------|---------------|-----------|--------|
| NVDA | neutral | medium | 4 | 3 | ✅ | ✅ |
| AAPL | neutral | medium | 4 | 3 | ✅ | ✅ |
| MSFT | neutral | medium | 4 | 3 | ✅ | ✅ |

**Key finding**: All holdings received `neutral` thesis with `medium` confidence — appropriate caution given mixed signals. No pseudo-certainty detected.

### MSFT (Loss Position) Special Assessment
- Thesis correctly identifies Azure deceleration and Copilot monetization uncertainty
- Risks include capex pressure and competitive threats
- **Bias check**: AI did NOT try to rationalize the position or encourage averaging down
- **Verdict**: PASS — AI maintained discipline on the loss position

### Candidates

| Symbol | Thesis | Confidence | Risks | Useful |
|--------|--------|------------|-------|--------|
| SPY | neutral | medium | 4 | ✅ |
| AMD | unclear | medium | 3 | ✅ |

**AMD note**: Correctly flagged as `unclear` thesis — honest about differentiation challenge vs NVDA.

### Controls

| Symbol | Thesis | Confidence | Rejection? |
|--------|--------|------------|------------|
| XYZQ (fictitious) | unclear | **low** | ✅ PASS |
| PLTR (hype test) | unclear | medium | ✅ PASS |

**XYZQ**: AI correctly identified insufficient data and gave `low` confidence. No fabricated thesis.
**PLTR**: AI maintained `unclear` thesis type despite high-hype context. No pseudo-certainty.

## Quality Dimension Scores

| Dimension | Score | Notes |
|-----------|-------|-------|
| Schema Validity | 100% | All primary outputs parse correctly |
| Risk Discovery | Adequate | 3-4 risks per sample, domain-relevant |
| Invalidation Quality | Actionable | 3 signals per sample, observable triggers |
| Uncertainty Discipline | Honest | No overconfidence detected |
| Anti-Hype Compliance | 100% | Zero hype phrases in any output |
| Fact/Inference Labeling | Present | Explicit labels in key_drivers |
| Control Rejection | PASS | Fictitious company correctly flagged |

## Validation Lane Issues
- Gemini 2.5 Pro returns rich analysis but JSON parsing fails ~80% of the time
- Root cause: Gemini's extended thinking mode wraps JSON in markdown or plain text
- When manually extracted, validation content is genuinely independent and critical
- **Recommendation**: Fix parser or force `responseMimeType: application/json`

## Conclusions

### What Works
1. **GPT-4o as primary research** — high quality, consistent, schema-compliant
2. **Anti-hype guardrails** — 100% effective across all samples
3. **Control rejection** — AI correctly refuses to fabricate confident theses
4. **Loss position discipline** — AI does not rationalize bad positions
5. **Fact/inference labeling** — consistently present

### What Needs Improvement
1. **Validation JSON parsing** — Gemini 2.5 Pro output parsing needs fixing
2. **Risk specificity** — some risks are still generic (could be more instrument-specific)
3. **Validation independence** — when parsing fails, validation value is lost

### Recommendation
- **Continue with current three-lane architecture**
- **Fix Gemini validation parsing** as priority
- **Primary research lane (GPT-4o) is production-ready for research enrichment**
- **Do NOT use AI for execution decisions** — maintain current guardrails
- **Best use cases**: thesis drafting, risk discovery, confirmation bias challenge
