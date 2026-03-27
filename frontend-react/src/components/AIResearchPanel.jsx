/**
 * AIResearchPanel — Structured AI research analysis display.
 *
 * Shows three sections:
 * 1. Primary Research Summary (GPT-4o)
 * 2. Validation / Second Opinion (Gemini 2.5 Pro)
 * 3. Risk Checklist
 *
 * All output is advisory research context only — NOT trading recommendations.
 * Degraded/fallback results are explicitly marked.
 */
import { useState } from 'react';
import {
  Brain, ShieldCheck, AlertTriangle, CheckCircle, XCircle,
  ChevronDown, ChevronUp, RefreshCw, Target, Zap, HelpCircle,
  TrendingUp, TrendingDown, Minus, Eye, FileWarning, Info,
} from 'lucide-react';
import { apiPost } from '../hooks/useApi';

const CARD = 'bg-card rounded-xl border border-border shadow-card';

// Confidence badge colors
const CONFIDENCE_STYLE = {
  high: 'bg-green-50 text-green-700 border-green-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-orange-50 text-orange-700 border-orange-200',
  insufficient_data: 'bg-gray-100 text-gray-600 border-gray-200',
};

// Thesis type indicators
const THESIS_ICON = {
  bullish: { icon: TrendingUp, color: 'text-green-600', label: 'Bullish' },
  bearish: { icon: TrendingDown, color: 'text-red-600', label: 'Bearish' },
  neutral: { icon: Minus, color: 'text-gray-600', label: 'Neutral' },
  unclear: { icon: HelpCircle, color: 'text-amber-600', label: 'Unclear' },
};

// Validation verdict styles
const VERDICT_STYLE = {
  agree: { bg: 'bg-green-50 border-green-200', text: 'text-green-700', label: 'Agrees' },
  agree_with_reservations: { bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700', label: 'Agrees with Reservations' },
  disagree: { bg: 'bg-red-50 border-red-200', text: 'text-red-700', label: 'Disagrees' },
  insufficient_information: { bg: 'bg-gray-100 border-gray-200', text: 'text-gray-600', label: 'Insufficient Information' },
};

function ConfidenceBadge({ level }) {
  const style = CONFIDENCE_STYLE[level] || CONFIDENCE_STYLE.insufficient_data;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${style}`}>
      {level?.replace(/_/g, ' ').toUpperCase() || 'UNKNOWN'}
    </span>
  );
}

function DegradedBanner({ meta }) {
  if (meta?.schema_valid && meta?.parse_strategy !== 'degraded_fallback') return null;
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs">
      <FileWarning className="w-3.5 h-3.5 shrink-0" />
      <span className="font-medium">Degraded result</span>
      <span className="text-amber-600">— AI output could not be fully parsed. Confidence markers may be unreliable.</span>
    </div>
  );
}

function RiskList({ items, emptyText = 'None identified' }) {
  if (!items?.length) return <p className="text-xs text-muted italic">{emptyText}</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-secondary">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function BulletList({ items, icon: Icon = CheckCircle, color = 'text-brand' }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-secondary">
          <Icon className={`w-3.5 h-3.5 ${color} shrink-0 mt-0.5`} />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export default function AIResearchPanel({ instrumentName, ticker, instrumentId, context }) {
  const [primaryResult, setPrimaryResult] = useState(null);
  const [primaryMeta, setPrimaryMeta] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [validationMeta, setValidationMeta] = useState(null);
  const [riskResult, setRiskResult] = useState(null);
  const [riskMeta, setRiskMeta] = useState(null);

  const [loading, setLoading] = useState({ primary: false, validation: false, risk: false });
  const [errors, setErrors] = useState({ primary: null, validation: null, risk: null });
  const [expanded, setExpanded] = useState({ primary: true, validation: true, risk: true });

  const canRun = ticker || instrumentName;

  const runPrimary = async () => {
    setLoading(l => ({ ...l, primary: true }));
    setErrors(e => ({ ...e, primary: null }));
    try {
      const res = await apiPost('/ai/research-summary', {
        instrument_name: instrumentName || ticker || '',
        ticker: ticker || '',
        context: context || '',
      });
      setPrimaryResult(res.result);
      setPrimaryMeta(res.meta);
    } catch (e) {
      setErrors(er => ({ ...er, primary: e.message }));
      setPrimaryResult(null);
    }
    setLoading(l => ({ ...l, primary: false }));
  };

  const runValidation = async () => {
    if (!primaryResult) return;
    setLoading(l => ({ ...l, validation: true }));
    setErrors(e => ({ ...e, validation: null }));
    try {
      const res = await apiPost('/ai/validate', {
        primary_analysis: JSON.stringify(primaryResult),
        instrument_name: instrumentName || ticker || '',
        ticker: ticker || '',
        context: context || '',
      });
      setValidationResult(res.result);
      setValidationMeta(res.meta);
    } catch (e) {
      setErrors(er => ({ ...er, validation: e.message }));
      setValidationResult(null);
    }
    setLoading(l => ({ ...l, validation: false }));
  };

  const runRiskChecklist = async () => {
    setLoading(l => ({ ...l, risk: true }));
    setErrors(e => ({ ...e, risk: null }));
    try {
      const res = await apiPost('/ai/risk-checklist', {
        instrument_name: instrumentName || ticker || '',
        ticker: ticker || '',
        thesis: primaryResult?.thesis || '',
        context: context || '',
      });
      setRiskResult(res.result);
      setRiskMeta(res.meta);
    } catch (e) {
      setErrors(er => ({ ...er, risk: e.message }));
      setRiskResult(null);
    }
    setLoading(l => ({ ...l, risk: false }));
  };

  const runAll = async () => {
    await runPrimary();
    // Validation and risk run after primary completes (need primary result)
  };

  // After primary loads, auto-offer validation
  const hasPrimary = !!primaryResult;

  return (
    <div className={`${CARD} overflow-hidden`}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-gradient-to-r from-purple-50/50 to-blue-50/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-600" />
            <h2 className="text-base font-bold text-heading">AI Research Analysis</h2>
          </div>
          <div className="flex items-center gap-2">
            {canRun && (
              <button onClick={runAll} disabled={loading.primary}
                className="inline-flex items-center gap-1.5 px-4 h-8 bg-purple-600 text-white font-semibold text-xs rounded-lg hover:bg-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                {loading.primary ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                Generate Analysis
              </button>
            )}
          </div>
        </div>
        <p className="text-[11px] text-muted mt-1.5">
          AI-powered research assistance — not a trading recommendation. All claims require independent verification.
        </p>
        {ticker && <p className="text-xs text-purple-600 font-semibold mt-1">Analyzing: {instrumentName || ticker} ({ticker})</p>}
      </div>

      <div className="p-6 space-y-5">
        {/* No instrument selected */}
        {!canRun && (
          <div className="text-center py-8">
            <Brain className="w-8 h-8 text-muted mx-auto mb-2 opacity-40" />
            <p className="text-sm text-muted">Select an instrument above to run AI research analysis</p>
          </div>
        )}

        {/* Primary Research Summary */}
        {canRun && (
          <div>
            <button onClick={() => setExpanded(e => ({ ...e, primary: !e.primary }))}
              className="w-full flex items-center justify-between py-2 cursor-pointer group">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-bold text-heading">Primary Research</span>
                <span className="text-[10px] text-muted px-1.5 py-0.5 bg-blue-50 rounded">GPT-4o</span>
              </div>
              {expanded.primary ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
            </button>

            {expanded.primary && (
              <div className="mt-2 space-y-3">
                {loading.primary ? (
                  <div className="flex items-center gap-2 py-6 justify-center text-sm text-muted animate-pulse">
                    <RefreshCw className="w-4 h-4 animate-spin" /> Generating research summary...
                  </div>
                ) : errors.primary ? (
                  <div className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">{errors.primary}</div>
                ) : primaryResult ? (
                  <div className="space-y-4">
                    <DegradedBanner meta={primaryMeta} />

                    {/* Thesis header */}
                    <div className="flex items-center gap-3 flex-wrap">
                      {(() => {
                        const tt = THESIS_ICON[primaryResult.thesis_type] || THESIS_ICON.unclear;
                        const Icon = tt.icon;
                        return <span className={`inline-flex items-center gap-1 text-xs font-bold ${tt.color}`}><Icon className="w-3.5 h-3.5" /> {tt.label}</span>;
                      })()}
                      <ConfidenceBadge level={primaryResult.confidence_level} />
                    </div>

                    {/* Core thesis */}
                    <p className="text-sm text-heading leading-relaxed">{primaryResult.thesis}</p>

                    {/* Key drivers */}
                    {primaryResult.key_drivers?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Key Drivers</h4>
                        <BulletList items={primaryResult.key_drivers} icon={CheckCircle} color="text-green-500" />
                      </div>
                    )}

                    {/* Key risks */}
                    {primaryResult.key_risks?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Key Risks</h4>
                        <RiskList items={primaryResult.key_risks} />
                      </div>
                    )}

                    {/* Thesis invalidation */}
                    {primaryResult.thesis_invalidation_signals?.length > 0 && (
                      <div className="border-l-2 border-red-300 pl-3">
                        <h4 className="text-[11px] font-bold text-red-600 uppercase tracking-wider mb-2">Thesis Breaks If</h4>
                        <ul className="space-y-1">
                          {primaryResult.thesis_invalidation_signals.map((s, i) => (
                            <li key={i} className="text-sm text-red-700 flex items-start gap-1.5">
                              <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" /> {s}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Missing info */}
                    {primaryResult.missing_information?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Missing Information</h4>
                        <BulletList items={primaryResult.missing_information} icon={HelpCircle} color="text-gray-400" />
                      </div>
                    )}

                    {/* Next steps */}
                    {primaryResult.suggested_next_steps?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-2">Suggested Next Steps</h4>
                        <BulletList items={primaryResult.suggested_next_steps} icon={ChevronDown} color="text-blue-400" />
                      </div>
                    )}

                    {/* Meta */}
                    <div className="flex items-center gap-3 text-[10px] text-muted pt-2 border-t border-border/50">
                      <span>Provider: {primaryMeta?.provider}/{primaryMeta?.model}</span>
                      <span>Latency: {primaryMeta?.latency_ms}ms</span>
                      {primaryMeta?.tokens && <span>Tokens: {primaryMeta.tokens}</span>}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted py-3">Click "Generate Analysis" to run AI research</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Validation / Second Opinion */}
        {hasPrimary && (
          <div className="border-t border-border pt-4">
            <button onClick={() => setExpanded(e => ({ ...e, validation: !e.validation }))}
              className="w-full flex items-center justify-between py-2 cursor-pointer">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                <span className="text-sm font-bold text-heading">Second Opinion</span>
                <span className="text-[10px] text-muted px-1.5 py-0.5 bg-indigo-50 rounded">Gemini Pro</span>
              </div>
              <div className="flex items-center gap-2">
                {!validationResult && !loading.validation && (
                  <button onClick={(e) => { e.stopPropagation(); runValidation(); }}
                    className="inline-flex items-center gap-1 px-3 h-7 text-xs font-semibold text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-all">
                    <Eye className="w-3 h-3" /> Validate
                  </button>
                )}
                {expanded.validation ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
              </div>
            </button>

            {expanded.validation && (
              <div className="mt-2 space-y-3">
                {loading.validation ? (
                  <div className="flex items-center gap-2 py-4 justify-center text-sm text-muted animate-pulse">
                    <RefreshCw className="w-4 h-4 animate-spin" /> Running second opinion validation...
                  </div>
                ) : errors.validation ? (
                  <div className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">{errors.validation}</div>
                ) : validationResult ? (
                  <div className="space-y-3">
                    <DegradedBanner meta={validationMeta} />

                    {/* Verdict */}
                    {(() => {
                      const v = VERDICT_STYLE[validationResult.agrees_with_primary] || VERDICT_STYLE.insufficient_information;
                      return (
                        <div className={`px-4 py-3 rounded-lg border ${v.bg}`}>
                          <span className={`text-sm font-bold ${v.text}`}>{v.label}</span>
                          <ConfidenceBadge level={validationResult.confidence_level} />
                        </div>
                      );
                    })()}

                    {/* Disagreements */}
                    {validationResult.disagreement_points?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-red-600 uppercase tracking-wider mb-2">Points of Disagreement</h4>
                        <RiskList items={validationResult.disagreement_points} />
                      </div>
                    )}

                    {/* Overlooked risks */}
                    {validationResult.overlooked_risks?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-amber-600 uppercase tracking-wider mb-2">Overlooked Risks</h4>
                        <RiskList items={validationResult.overlooked_risks} />
                      </div>
                    )}

                    {/* Unsupported claims */}
                    {validationResult.unsupported_claims?.length > 0 && (
                      <div>
                        <h4 className="text-[11px] font-bold text-orange-600 uppercase tracking-wider mb-2">Unsupported Claims</h4>
                        <BulletList items={validationResult.unsupported_claims} icon={XCircle} color="text-orange-500" />
                      </div>
                    )}

                    {/* Recommendation */}
                    {validationResult.recommendation && (
                      <div>
                        <h4 className="text-[11px] font-bold text-muted uppercase tracking-wider mb-1">Validator Recommendation</h4>
                        <p className="text-sm text-secondary">{validationResult.recommendation}</p>
                      </div>
                    )}

                    <div className="flex items-center gap-3 text-[10px] text-muted pt-2 border-t border-border/50">
                      <span>Provider: {validationMeta?.provider}/{validationMeta?.model}</span>
                      <span>Latency: {validationMeta?.latency_ms}ms</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted py-2">Click "Validate" to get a critical second opinion on the primary analysis</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Risk Checklist */}
        {canRun && (
          <div className="border-t border-border pt-4">
            <button onClick={() => setExpanded(e => ({ ...e, risk: !e.risk }))}
              className="w-full flex items-center justify-between py-2 cursor-pointer">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span className="text-sm font-bold text-heading">Risk Checklist</span>
              </div>
              <div className="flex items-center gap-2">
                {!riskResult && !loading.risk && (
                  <button onClick={(e) => { e.stopPropagation(); runRiskChecklist(); }}
                    className="inline-flex items-center gap-1 px-3 h-7 text-xs font-semibold text-amber-600 border border-amber-200 rounded-lg hover:bg-amber-50 transition-all">
                    <AlertTriangle className="w-3 h-3" /> Generate
                  </button>
                )}
                {expanded.risk ? <ChevronUp className="w-4 h-4 text-muted" /> : <ChevronDown className="w-4 h-4 text-muted" />}
              </div>
            </button>

            {expanded.risk && (
              <div className="mt-2">
                {loading.risk ? (
                  <div className="flex items-center gap-2 py-4 justify-center text-sm text-muted animate-pulse">
                    <RefreshCw className="w-4 h-4 animate-spin" /> Generating risk checklist...
                  </div>
                ) : errors.risk ? (
                  <div className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">{errors.risk}</div>
                ) : riskResult ? (
                  <div className="space-y-2">
                    {typeof riskResult === 'object' && !riskResult.raw_text ? (
                      Object.entries(riskResult).filter(([k]) => k !== 'raw_payload').map(([category, items]) => (
                        <div key={category}>
                          <h4 className="text-[11px] font-bold text-heading uppercase tracking-wider mb-1.5">
                            {category.replace(/_/g, ' ')}
                          </h4>
                          {Array.isArray(items) ? (
                            <RiskList items={items} />
                          ) : typeof items === 'string' ? (
                            <p className="text-sm text-secondary ml-5">{items}</p>
                          ) : null}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-secondary whitespace-pre-wrap">{riskResult?.raw_text || JSON.stringify(riskResult, null, 2)}</p>
                    )}
                    <div className="flex items-center gap-3 text-[10px] text-muted pt-2 border-t border-border/50">
                      <span>Provider: {riskMeta?.provider}/{riskMeta?.model}</span>
                      <span>Latency: {riskMeta?.latency_ms}ms</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted py-2">Click "Generate" to create a structured risk assessment</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Disclaimer */}
        <div className="flex items-start gap-2 px-3 py-2.5 rounded-lg bg-gray-50 border border-gray-200 mt-4">
          <Info className="w-3.5 h-3.5 text-gray-400 shrink-0 mt-0.5" />
          <p className="text-[10px] text-gray-500 leading-relaxed">
            AI-generated research assistance only. Not a trading recommendation. All claims require independent verification.
            Execution decisions must go through the platform's approval gate. Live submission is disabled by default.
          </p>
        </div>
      </div>
    </div>
  );
}
