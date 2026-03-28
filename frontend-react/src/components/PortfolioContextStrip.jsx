/**
 * PortfolioContextStrip — Shows portfolio-aware context for current instrument.
 *
 * Displays:
 * 1. Holding status (broker truth)
 * 2. Related research artifacts (derived context)
 * 3. Research workflow position hint
 *
 * This is research context enrichment — NOT trading advice.
 * Broker truth and derived context are visually separated.
 */
import { useState, useEffect } from 'react';
import {
  Briefcase, Eye, FileText, AlertTriangle, Target, BookOpen,
  ChevronRight, Clock, StickyNote, Zap
} from 'lucide-react';
import { apiFetch } from '../hooks/useApi';
import { useWorkspace } from '../hooks/useWorkspace';
import { formatDate } from '../utils';

export default function PortfolioContextStrip({ instrumentId, instrumentName, ticker }) {
  const { isHeld, portfolioSummary } = useWorkspace();
  const [relatedNotes, setRelatedNotes] = useState([]);
  const [notesLoaded, setNotesLoaded] = useState(false);

  const held = instrumentId ? isHeld(instrumentId) : false;
  const brokerConnected = portfolioSummary?.connected || false;

  // Find position details if held
  const position = held && portfolioSummary?.positions
    ? portfolioSummary.positions.find(p =>
        p.instrument_id === instrumentId || p.ticker === ticker
      )
    : null;

  // Load related notes for this instrument (once per instrument change)
  useEffect(() => {
    if (!instrumentId) {
      setRelatedNotes([]);
      setNotesLoaded(false);
      return;
    }
    setNotesLoaded(false);
    apiFetch(`/notes?instrument_id=${instrumentId}&limit=5`)
      .then(res => {
        setRelatedNotes(res?.items || []);
        setNotesLoaded(true);
      })
      .catch(() => {
        setRelatedNotes([]);
        setNotesLoaded(true);
      });
  }, [instrumentId]);

  if (!instrumentId) return null;

  // Derive research workflow position
  const hasThesis = relatedNotes.some(n => n.note_type === 'thesis');
  const hasRiskNote = relatedNotes.some(n => n.note_type === 'risk');
  const hasObservation = relatedNotes.some(n => n.note_type === 'observation');
  const aiNotes = relatedNotes.filter(n => n.context?.source === 'ai_research');
  const latestDecisionHint = aiNotes[0]?.context?.decision_hint || null;

  // Determine workflow label
  let workflowLabel = 'New idea';
  let workflowColor = 'text-gray-500';
  if (held) {
    workflowLabel = 'Existing holding';
    workflowColor = 'text-blue-600';
  } else if (latestDecisionHint === 'watch_only') {
    workflowLabel = 'Watched (not held)';
    workflowColor = 'text-purple-600';
  } else if (latestDecisionHint === 'backtest_candidate') {
    workflowLabel = 'Backtest candidate';
    workflowColor = 'text-indigo-600';
  } else if (hasThesis) {
    workflowLabel = 'Has thesis';
    workflowColor = 'text-blue-600';
  } else if (relatedNotes.length > 0) {
    workflowLabel = 'Previously researched';
    workflowColor = 'text-gray-600';
  }

  const NOTE_TYPE_COLORS = {
    thesis: 'bg-blue-50 text-blue-700',
    risk: 'bg-amber-50 text-amber-700',
    observation: 'bg-gray-100 text-gray-600',
    general: 'bg-gray-100 text-gray-500',
  };

  return (
    <div className="bg-card rounded-xl border border-border shadow-card px-5 py-4">
      <div className="flex flex-col sm:flex-row flex-wrap items-start sm:items-center gap-3 sm:gap-x-6 sm:gap-y-3">

        {/* 1. Holding Status — BROKER TRUTH */}
        <div className="flex items-center gap-2">
          {brokerConnected ? (
            held ? (
              <>
                <div className="w-7 h-7 rounded-lg bg-green-50 flex items-center justify-center">
                  <Briefcase className="w-3.5 h-3.5 text-green-600" />
                </div>
                <div>
                  <span className="text-xs font-bold text-green-700">Holding</span>
                  {position?.quantity && (
                    <span className="text-[10px] text-green-600 ml-1.5">{position.quantity} shares</span>
                  )}
                  <span className="block text-[10px] text-muted font-medium">Broker snapshot</span>
                </div>
              </>
            ) : (
              <>
                <div className="w-7 h-7 rounded-lg bg-gray-100 flex items-center justify-center">
                  <Eye className="w-3.5 h-3.5 text-gray-400" />
                </div>
                <div>
                  <span className="text-xs font-medium text-gray-500">Not held</span>
                  <span className="block text-[10px] text-muted">No current position</span>
                </div>
              </>
            )
          ) : (
            <div className="flex items-center gap-1.5">
              <div className="w-7 h-7 rounded-lg bg-gray-50 flex items-center justify-center">
                <Briefcase className="w-3.5 h-3.5 text-gray-300" />
              </div>
              <span className="text-[10px] text-muted">Broker not connected</span>
            </div>
          )}
        </div>

        {/* Separator */}
        <div className="w-px h-8 bg-border hidden sm:block" />

        {/* 2. Workflow Position — DERIVED CONTEXT */}
        <div className="flex items-center gap-2">
          <Target className="w-3.5 h-3.5 text-muted" />
          <span className={`text-xs font-semibold ${workflowColor}`}>{workflowLabel}</span>
        </div>

        {/* Separator */}
        <div className="w-px h-8 bg-border hidden sm:block" />

        {/* 3. Research Artifacts — DERIVED CONTEXT */}
        <div className="flex items-center gap-3">
          {notesLoaded && relatedNotes.length > 0 ? (
            <>
              <div className="flex items-center gap-1">
                <StickyNote className="w-3.5 h-3.5 text-purple-400" />
                <span className="text-[10px] font-semibold text-secondary">{relatedNotes.length} note{relatedNotes.length !== 1 ? 's' : ''}</span>
              </div>
              {hasThesis && (
                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-600">
                  <BookOpen className="w-2.5 h-2.5" /> Thesis
                </span>
              )}
              {hasRiskNote && (
                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-600">
                  <AlertTriangle className="w-2.5 h-2.5" /> Risk
                </span>
              )}
              {aiNotes.length > 0 && (
                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-50 text-purple-600">
                  <Zap className="w-2.5 h-2.5" /> AI×{aiNotes.length}
                </span>
              )}
            </>
          ) : notesLoaded ? (
            <span className="text-[10px] text-muted">No research notes yet</span>
          ) : (
            <span className="text-[10px] text-muted animate-pulse">Loading...</span>
          )}
        </div>
      </div>

      {/* Latest note preview (if exists) */}
      {relatedNotes.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/50">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-muted uppercase tracking-wider">Latest Note</span>
            <span className="text-[10px] text-muted">{formatDate(relatedNotes[0].created_at)}</span>
          </div>
          <div className="flex items-start gap-2 mt-1.5">
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold shrink-0 ${NOTE_TYPE_COLORS[relatedNotes[0].note_type] || NOTE_TYPE_COLORS.general}`}>
              {relatedNotes[0].note_type}
            </span>
            <p className="text-xs text-secondary line-clamp-2">{relatedNotes[0].title}</p>
          </div>
          {relatedNotes[0].context?.is_degraded && (
            <p className="text-[10px] text-amber-500 mt-1 flex items-center gap-1">
              <AlertTriangle className="w-2.5 h-2.5" /> Based on degraded AI output
            </p>
          )}
        </div>
      )}
    </div>
  );
}
