import { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, ShieldCheck, Play, TrendingUp, BarChart3,
  TrendingDown, Search, Filter, Layers, Award, RefreshCw, FileJson,
  Save, Bookmark, Star, ChevronRight, StickyNote, Plus, X, History,
} from 'lucide-react';
import { apiFetch, apiPost, apiDelete } from '../hooks/useApi';
import { useWorkspace } from '../hooks/useWorkspace';
import { formatDate } from '../utils';
import AIResearchPanel from '../components/AIResearchPanel';
import PortfolioContextStrip from '../components/PortfolioContextStrip';

const CARD = 'bg-card rounded-xl border border-border shadow-card p-6';
const BTN_PRIMARY = 'inline-flex items-center gap-2 px-5 h-9 bg-gradient-to-r from-brand to-brand-dark text-white font-semibold text-sm rounded-lg shadow-[0_4px_14px_rgba(103,194,58,0.25)] hover:brightness-105 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed';
const BTN_OUTLINE = 'inline-flex items-center gap-2 px-4 h-9 border border-border rounded-lg text-sm font-medium text-secondary hover:bg-surface transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed';
const INPUT = 'w-full h-10 px-4 bg-card border border-border rounded-lg text-sm focus:border-brand focus:ring-2 focus:ring-brand-light outline-none transition-all';
const LABEL = 'text-[11px] font-bold uppercase tracking-wider text-muted mb-1.5 block';

export default function Research({ onNavigate }) {
  const { setActiveInstrument, setActivePreset, recordAction } = useWorkspace();
  // Core state
  const [instruments, setInstruments] = useState([]);
  const [selectedInstrument, setSelectedInstrument] = useState('');
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10));
  const [eventTicker, setEventTicker] = useState('');
  const [eventWindow, setEventWindow] = useState('5');
  const [results, setResults] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState(null);
  const [resultsLabel, setResultsLabel] = useState('');

  // Watchlist state
  const [watchlists, setWatchlists] = useState([]);
  const [selectedWatchlist, setSelectedWatchlist] = useState('all');
  const [watchlistItems, setWatchlistItems] = useState([]);

  // Presets state
  const [presets, setPresets] = useState([]);
  const [showPresets, setShowPresets] = useState(false);
  const [showPresetSave, setShowPresetSave] = useState(false);
  const [presetNameInput, setPresetNameInput] = useState('');

  // Notes state
  const [recentNotes, setRecentNotes] = useState([]);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');

  // Load initial data
  useEffect(() => {
    Promise.allSettled([
      apiFetch('/instruments?limit=50'),
      apiFetch('/watchlist/groups'),
      apiFetch('/presets?preset_type=research'),
      apiFetch('/notes?limit=5'),
    ]).then(([instRes, wlRes, prRes, notesRes]) => {
      if (instRes.status === 'fulfilled') {
        const d = instRes.value;
        setInstruments(Array.isArray(d) ? d : d.items || d.instruments || []);
      }
      if (wlRes.status === 'fulfilled') setWatchlists(wlRes.value?.groups || []);
      if (prRes.status === 'fulfilled') setPresets(prRes.value?.items || []);
      if (notesRes.status === 'fulfilled') setRecentNotes(notesRes.value?.items || []);
    });
  }, []);

  // When watchlist changes, load its items
  useEffect(() => {
    if (selectedWatchlist === 'all') {
      setWatchlistItems([]);
      return;
    }
    apiFetch(`/watchlist/groups/${selectedWatchlist}/items`)
      .then(res => setWatchlistItems(res?.items || []))
      .catch(() => setWatchlistItems([]));
  }, [selectedWatchlist]);

  const filteredInstruments = selectedWatchlist === 'all'
    ? instruments
    : instruments.filter(inst => {
        const id = inst.instrument_id || inst.id;
        return watchlistItems.some(wi => wi.instrument_id === id);
      });

  const runAnalysis = async (type) => {
    if (!selectedInstrument) return;
    setResultsLoading(true); setResultsError(null); setResultsLabel(`${type} Analysis`);
    try {
      const params = asOfDate ? `?as_of_date=${asOfDate}` : '';
      setResults(await apiFetch(`/research/instrument/${selectedInstrument}/${type}${params}`));
    } catch (e) { setResultsError(e.message); setResults(null); }
    finally { setResultsLoading(false); }
  };

  const runEventStudy = async () => {
    if (!eventTicker) return;
    setResultsLoading(true); setResultsError(null); setResultsLabel('Event Study');
    try {
      setResults(await apiPost('/research/event-study/earnings', { ticker: eventTicker, window: parseInt(eventWindow) || 5 }));
    } catch (e) { setResultsError(e.message); setResults(null); }
    finally { setResultsLoading(false); }
  };

  const runScreener = async (type) => {
    setResultsLoading(true); setResultsError(null); setResultsLabel(`${type} Screener`);
    try { setResults(await apiFetch(`/research/screener/${type}`)); }
    catch (e) { setResultsError(e.message); setResults(null); }
    finally { setResultsLoading(false); }
  };

  const savePreset = async (name) => {
    if (!name?.trim()) return;
    try {
      const saved = await apiPost('/presets', {
        name: name.trim(),
        preset_type: 'research',
        config: { selectedInstrument, asOfDate, eventTicker, eventWindow, selectedWatchlist },
        description: `Research preset: ${resultsLabel || 'Quick Analysis'}`,
      });
      setPresets(prev => [saved, ...prev].slice(0, 10));
      setShowPresetSave(false);
      setPresetNameInput('');
    } catch (e) { console.error(e); }
  };

  const loadPreset = (preset) => {
    const c = preset.config || {};
    if (c.selectedInstrument) setSelectedInstrument(c.selectedInstrument);
    if (c.asOfDate) setAsOfDate(c.asOfDate);
    if (c.eventTicker) setEventTicker(c.eventTicker);
    if (c.eventWindow) setEventWindow(c.eventWindow);
    if (c.selectedWatchlist) setSelectedWatchlist(c.selectedWatchlist);
    // Record usage
    apiPost(`/presets/${preset.preset_id}/use`).catch(() => {});
  };

  const saveNote = async () => {
    if (!noteTitle.trim()) return;
    try {
      const saved = await apiPost('/notes', {
        title: noteTitle,
        content: noteContent || `Research result: ${resultsLabel}`,
        note_type: 'observation',
        instrument_id: selectedInstrument || null,
        context: { research_type: resultsLabel, watchlist: selectedWatchlist },
      });
      setShowNoteForm(false); setNoteTitle(''); setNoteContent('');
      setRecentNotes(prev => [saved, ...prev].slice(0, 5));
    } catch (e) { console.error(e); }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-heading flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-brand" /> Research Workbench
          </h1>
          <p className="text-sm text-muted mt-1">PIT-safe quantitative analysis with explicit time boundaries</p>
        </div>
        <div className="flex items-center gap-2">
          {showPresetSave ? (
            <div className="flex items-center gap-1">
              <input type="text" value={presetNameInput} onChange={e => setPresetNameInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') savePreset(presetNameInput); if (e.key === 'Escape') setShowPresetSave(false); }}
                placeholder="Preset name..." autoFocus
                className="h-9 px-3 border border-brand rounded-lg text-sm w-40 focus:ring-2 focus:ring-brand-light outline-none" />
              <button onClick={() => savePreset(presetNameInput)} className={BTN_PRIMARY + ' !px-3'}><Save className="w-4 h-4" /></button>
              <button onClick={() => setShowPresetSave(false)} className="p-1 rounded hover:bg-surface"><X className="w-4 h-4 text-muted" /></button>
            </div>
          ) : (
            <button onClick={() => setShowPresetSave(true)} className={BTN_OUTLINE}>
              <Save className="w-4 h-4" /> Save Preset
            </button>
          )}
          <button onClick={() => setShowPresets(!showPresets)} className={BTN_OUTLINE}>
            <Bookmark className="w-4 h-4" /> Presets {presets.length > 0 && `(${presets.length})`}
          </button>
        </div>
      </div>

      {/* PIT Notice */}
      <div className="flex items-center gap-3 px-5 py-3 rounded-xl bg-brand-light border border-brand/20">
        <ShieldCheck className="w-5 h-5 text-brand-dark shrink-0" />
        <span className="text-sm font-semibold text-brand-dark">PIT Guarantee</span>
        <span className="text-sm text-brand-dark/80">All queries use as-of-date semantics — no look-ahead bias</span>
      </div>

      {/* Presets Panel (collapsible) */}
      {showPresets && (
        <div className={CARD}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-heading flex items-center gap-2">
              <Star className="w-4 h-4 text-brand" /> Saved Research Presets
            </h3>
            <button onClick={() => setShowPresets(false)} className="p-1 rounded hover:bg-surface"><X className="w-4 h-4 text-muted" /></button>
          </div>
          {presets.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {presets.map(p => (
                <button key={p.preset_id} onClick={() => loadPreset(p)}
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-border/50 text-sm font-medium text-heading hover:border-brand hover:bg-brand-light/50 transition-all">
                  <Bookmark className="w-3 h-3 text-brand" /> {p.name}
                  {p.use_count > 0 && <span className="text-[10px] text-muted">×{p.use_count}</span>}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted py-2">No saved presets yet. Save your current research config to reuse later.</p>
          )}
        </div>
      )}

      {/* Universe Selector */}
      <div className="flex items-center gap-3 px-1">
        <span className="text-[11px] font-bold uppercase tracking-wider text-muted">Universe:</span>
        <select value={selectedWatchlist} onChange={e => setSelectedWatchlist(e.target.value)}
          className="h-8 px-3 bg-card border border-border rounded-lg text-sm focus:border-brand outline-none">
          <option value="all">All Instruments ({instruments.length})</option>
          {watchlists.map(g => (
            <option key={g.group_id} value={g.group_id}>{g.name} ({g.item_count})</option>
          ))}
        </select>
        {selectedWatchlist !== 'all' && (
          <span className="text-xs text-brand font-medium">{filteredInstruments.length} instruments in scope</span>
        )}
      </div>

      {/* Quick Analysis + Event Study */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className={CARD}>
          <h2 className="text-base font-bold text-heading mb-5">Quick Analysis</h2>
          <div className="space-y-4">
            <div>
              <label className={LABEL}>Instrument</label>
              <select value={selectedInstrument} onChange={e => {
                setSelectedInstrument(e.target.value);
                const inst = instruments.find(i => (i.instrument_id || i.id) === e.target.value);
                if (inst) setActiveInstrument({ id: e.target.value, name: inst.issuer_name_current || '', ticker: inst.ticker || '' });
              }} className={INPUT}>
                <option value="">Select instrument...</option>
                {filteredInstruments.map(inst => {
                  const id = inst.instrument_id || inst.id;
                  return <option key={id} value={id}>{inst.issuer_name_current || inst.ticker || inst.name} ({inst.ticker || id?.slice(0,8)})</option>;
                })}
              </select>
            </div>
            <div>
              <label className={LABEL}>As-of Date</label>
              <input type="date" value={asOfDate} onChange={e => setAsOfDate(e.target.value)} className={INPUT} />
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              <button onClick={() => runAnalysis('summary')} disabled={!selectedInstrument || resultsLoading} className={BTN_PRIMARY}><Play className="w-3.5 h-3.5" /> Summary</button>
              <button onClick={() => runAnalysis('performance')} disabled={!selectedInstrument || resultsLoading} className={BTN_OUTLINE}><TrendingUp className="w-3.5 h-3.5" /> Performance</button>
              <button onClick={() => runAnalysis('valuation')} disabled={!selectedInstrument || resultsLoading} className={BTN_OUTLINE}><BarChart3 className="w-3.5 h-3.5" /> Valuation</button>
              <button onClick={() => runAnalysis('drawdown')} disabled={!selectedInstrument || resultsLoading} className={BTN_OUTLINE}><TrendingDown className="w-3.5 h-3.5" /> Drawdown</button>
            </div>
          </div>
        </div>

        <div className={CARD}>
          <h2 className="text-base font-bold text-heading mb-5">Event Study</h2>
          <div className="space-y-4">
            <div>
              <label className={LABEL}>Ticker</label>
              <input type="text" placeholder="e.g. AAPL" value={eventTicker} onChange={e => setEventTicker(e.target.value)} className={INPUT} />
            </div>
            <div>
              <label className={LABEL}>Window (days)</label>
              <input type="number" value={eventWindow} onChange={e => setEventWindow(e.target.value)} className={INPUT} />
            </div>
            <button onClick={runEventStudy} disabled={!eventTicker || resultsLoading} className={BTN_PRIMARY}><Play className="w-3.5 h-3.5" /> Run Study</button>
          </div>
        </div>
      </div>

      {/* Screeners */}
      <div className={CARD}>
        <h2 className="text-base font-bold text-heading mb-4">Screeners</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <button onClick={() => runScreener('liquidity')} disabled={resultsLoading} className={BTN_OUTLINE}><Filter className="w-3.5 h-3.5" /> Liquidity</button>
          <button onClick={() => runScreener('returns')} disabled={resultsLoading} className={BTN_OUTLINE}><TrendingUp className="w-3.5 h-3.5" /> Returns</button>
          <button onClick={() => runScreener('fundamentals')} disabled={resultsLoading} className={BTN_OUTLINE}><Layers className="w-3.5 h-3.5" /> Fundamentals</button>
          <button onClick={() => runScreener('rank')} disabled={resultsLoading} className={BTN_OUTLINE}><Award className="w-3.5 h-3.5" /> Composite Rank</button>
        </div>
      </div>

      {/* Portfolio Context Strip */}
      {selectedInstrument && (() => {
        const inst = instruments.find(i => (i.instrument_id || i.id) === selectedInstrument);
        return (
          <PortfolioContextStrip
            instrumentId={selectedInstrument}
            instrumentName={inst?.issuer_name_current || inst?.name || ''}
            ticker={inst?.ticker || ''}
          />
        );
      })()}

      {/* AI Research Analysis */}
      {(() => {
        const inst = instruments.find(i => (i.instrument_id || i.id) === selectedInstrument);
        const instName = inst?.issuer_name_current || inst?.name || '';
        const instTicker = inst?.ticker || '';
        return (
          <AIResearchPanel
            instrumentName={instName}
            ticker={instTicker}
            instrumentId={selectedInstrument}
            context={`As-of date: ${asOfDate}. ${selectedWatchlist !== 'all' ? `Working universe: watchlist ${selectedWatchlist}` : 'Full universe'}.`}
            onNavigate={onNavigate}
          />
        );
      })()}

      {/* Results */}
      <div className={CARD}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold text-heading">{resultsLabel ? `Results: ${resultsLabel}` : 'Results'}</h2>
          <div className="flex items-center gap-2">
            {results && (
              <>
                <button onClick={() => setShowNoteForm(true)} className={BTN_OUTLINE + ' !h-7 !px-3 !text-xs'}>
                  <StickyNote className="w-3 h-3" /> Save Note
                </button>
                <button onClick={() => {
                  try {
                    const inst = instruments.find(i => (i.instrument_id || i.id) === selectedInstrument);
                    const ticker = inst?.ticker || inst?.issuer_name_current || '';
                    sessionStorage.setItem('backtest_context', JSON.stringify({
                      tickers: ticker,
                      from_research: true,
                      research_type: resultsLabel,
                    }));
                  } catch {}
                  onNavigate?.('backtest');
                }} className={BTN_OUTLINE + ' !h-7 !px-3 !text-xs'}>
                  <History className="w-3 h-3" /> Run as Backtest
                </button>
                <button onClick={() => { setResults(null); setResultsLabel(''); }} className="text-xs text-muted hover:text-secondary cursor-pointer">Clear</button>
              </>
            )}
          </div>
        </div>

        {resultsLoading ? (
          <div className="flex items-center justify-center py-12 text-muted text-sm animate-pulse opacity-80">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Running analysis...
          </div>
        ) : resultsError ? (
          <div className="text-sm text-red-500 p-3 bg-red-50 rounded-lg">{resultsError}</div>
        ) : results ? (
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-heading uppercase tracking-wider">
              Analysis Results
            </h3>
            {Array.isArray(results) ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      {results.length > 0 && Object.keys(results[0]).map(k => (
                        <th key={k} className="text-left py-2 px-3 text-xs font-bold text-muted uppercase tracking-wider">{k.replace(/_/g, ' ')}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.slice(0, 20).map((row, i) => (
                      <tr key={i} className="border-b border-border/50 hover:bg-surface-hover">
                        {Object.values(row).map((v, j) => (
                          <td key={j} className="py-2 px-3 text-secondary">
                            {v === null || v === undefined ? '--' : typeof v === 'number' ? Number(v).toLocaleString('en-US', {maximumFractionDigits: 4}) : String(v)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : typeof results === 'object' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(results).filter(([k, v]) => v !== null && v !== undefined && k !== 'raw_payload').map(([k, v]) => (
                  <div key={k} className="bg-surface rounded-lg p-3">
                    <div className="text-[10px] font-bold text-muted uppercase tracking-wider mb-1">{k.replace(/_/g, ' ')}</div>
                    <div className="text-sm font-semibold text-heading">
                      {typeof v === 'number' ? Number(v).toLocaleString('en-US', {maximumFractionDigits: 4}) : typeof v === 'object' ? (Array.isArray(v) ? `[${v.length} items]` : Object.entries(v).filter(([,val]) => val != null).map(([k,val]) => `${k.replace(/_/g,' ')}: ${typeof val === 'number' ? Number(val).toLocaleString('en-US', {maximumFractionDigits: 2}) : val}`).join(', ')) : String(v)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-secondary text-sm">{String(results)}</p>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center py-12 text-center">
            <div className="w-12 h-12 rounded-xl bg-surface flex items-center justify-center mb-3">
              <FlaskConical className="w-5 h-5 text-muted" />
            </div>
            <p className="text-sm font-medium text-heading mb-1">Ready to Analyze</p>
            <p className="text-xs text-muted max-w-[300px]">Select an instrument and run a Quick Analysis, Event Study, or Screener to see results here.</p>
          </div>
        )}
      </div>

      {/* Save Note Form (inline) */}
      {showNoteForm && (
        <div className={CARD}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-heading flex items-center gap-2"><StickyNote className="w-4 h-4 text-purple-500" /> Save Research Note</h3>
            <button onClick={() => setShowNoteForm(false)} className="p-1 rounded hover:bg-surface"><X className="w-4 h-4 text-muted" /></button>
          </div>
          <div className="space-y-3">
            <input type="text" placeholder="Note title..." value={noteTitle} onChange={e => setNoteTitle(e.target.value)} className={INPUT} />
            <textarea placeholder="Your observations, thesis, or conclusions..." value={noteContent} onChange={e => setNoteContent(e.target.value)} className={INPUT + ' !h-24 py-3'} />
            <button onClick={saveNote} disabled={!noteTitle.trim()} className={BTN_PRIMARY}><Save className="w-3.5 h-3.5" /> Save Note</button>
          </div>
        </div>
      )}

      {/* Recent Notes */}
      {recentNotes.length > 0 && (
        <div className={CARD}>
          <h3 className="text-sm font-bold text-heading flex items-center gap-2 mb-4">
            <StickyNote className="w-4 h-4 text-purple-500" /> Recent Research Notes
          </h3>
          <div className="space-y-2">
            {recentNotes.map(n => (
              <div key={n.note_id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-surface/60 transition-colors border border-border/30">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-heading truncate">{n.title}</p>
                  <p className="text-xs text-muted">{n.note_type} · {formatDate(n.created_at)}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-muted shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
