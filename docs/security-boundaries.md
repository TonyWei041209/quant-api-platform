# Security Boundaries & Guardrail Matrix

## Platform Identity

This platform is a **quantitative research workstation with controlled execution** — not an auto-trading bot.

Research and execution are architecturally decoupled:
- Research actions are **open by default** (low friction, no approval)
- Execution actions are **guarded by default** (approval required, live submit locked)
- AI outputs are advisory research context only — never trading instructions

## Three-Layer Guardrail Matrix

### Layer 1 — Research-open (default allow, no approval)

These actions execute immediately with no blocking gate:

| Category | Actions |
|---|---|
| AI Research | Generate Analysis, Validate (Second Opinion), Generate Risk Checklist |
| Research Save | Save as Thesis, Save Risk Note, Watch Only, Save Note (inline) |
| Research Navigation | Test as Backtest (context handoff), Switch universe/instrument, Navigate between pages |
| Data Query | Quick Analysis (summary/performance/valuation/drawdown), Event Study, Screeners |
| Backtest | Run Backtest, View results |
| Read-only Display | View Holdings, Instruments, Watchlists, DQ Rules, Settings, Portfolio Detail |
| User Preferences | Theme toggle, Language switch, Save Preset, Search/Filter |
| System | Refresh data, Sync status display |

**Rationale:** These actions only create research artifacts (notes, backtest runs, presets) or query existing data. They never create execution objects, never write to the broker, and never move money.

### Layer 2 — Soft Guard (lightweight confirm, not approval)

These actions have a confirmation step but don't enter the execution approval pipeline:

| Action | Guard Type | Reason |
|---|---|---|
| Create Watchlist | Inline form submit | Creates a persistent organizational object |
| Delete Note/Preset | Confirm dialog (if implemented) | Irreversible deletion |
| Batch research operations | Scope summary + confirm (future) | Can produce noise at scale |

**Rationale:** These actions modify persistent state but have no execution or financial impact. A simple confirmation prevents accidental bulk operations.

### Layer 3 — Execution-guarded (strict gate, approval required)

These actions are blocked or require explicit human approval:

| Action | Guard | Implementation |
|---|---|---|
| Create Execution Intent | Form submit + validation | `POST /execution/intents` with required fields |
| Generate Draft from Intent | Backend approval gate | Intent must be explicitly converted |
| Approve Draft | Human approval required | `draft.approved_at` must be set |
| Submit to Broker (live) | **LOCKED** | `FEATURE_T212_LIVE_SUBMIT=false` env var |
| Any broker write | **BLOCKED** | `LiveSubmitDisabledError` in adapter |
| Modify execution policies | No UI write access | Display-only in Settings |
| Change feature flags | Environment variables only | No runtime UI toggle |

**Rationale:** These actions have real financial consequences or affect system safety. They require explicit human intent and cannot be triggered by AI research output or automated workflows.

## Boundary Rules

### AI Cannot Bypass Execution Gates
- AI research output (thesis, risks, validation) flows into `research_note` table only
- No code path exists from AI output to `order_intent` or `order_draft`
- "Test as Backtest" passes context via `sessionStorage` — never creates execution objects
- The Research Workflow buttons (Save/Watch/Backtest) only create notes or navigate

### Broker Integration is Read-Only
- T212 adapter: `get_account_summary()`, `get_positions()`, `get_orders()` — all GET requests
- Live submit: disabled by `FEATURE_T212_LIVE_SUBMIT=false` (environment variable, not runtime toggle)
- Submit path raises `LiveSubmitDisabledError` if flag is false
- No UI button exists to enable live submit

### Research and Execution Are Decoupled
- Research notes (`research_note` table) and execution objects (`order_intent`, `order_draft` tables) have no foreign keys between them
- No backend endpoint converts a research note into an execution intent
- The only bridge is human decision: user reads research, then manually creates an intent

## Current Status

| System | State |
|---|---|
| Research-open actions | All functioning, low friction |
| Execution approval gate | Active, mandatory |
| Live submit | **LOCKED** (env var) |
| Broker write operations | **BLOCKED** (adapter guard) |
| AI → Execution path | **Does not exist** |
| Research → Execution bridge | Human-only, manual intent creation |

## Extension Policy

When adding new features:
1. Default to Layer 1 (research-open) unless the action has execution or financial impact
2. Batch operations that affect persistent state should be Layer 2
3. Any action that creates execution objects or writes to broker must be Layer 3
4. Never create an automated path from AI output to execution objects
5. Feature flags for new execution capabilities must default to `false`

## Automated Sync Boundary

The T212 readonly sync runs as a **Cloud Run Job** on a schedule (2x daily, weekdays).

- It only **reads** from T212 API (GET requests only)
- It only **writes** to `broker_*_snapshot` tables (fact layer)
- It **never** creates execution objects (intents, drafts, orders)
- It **never** calls T212 write endpoints
- It runs in a separate container from the main API service
- Failed jobs do not affect the live application
