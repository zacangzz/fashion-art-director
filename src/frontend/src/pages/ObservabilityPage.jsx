import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity,
  ArrowLeft,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Code2,
  Sliders,
  Layers,
  Copy,
  Check,
  Terminal,
  ChevronRight,
  Filter,
  Zap,
  Database,
  FileText,
  Sparkles,
  Download,
  ExternalLink,
  ChevronLeft,
  Eye,
  ShieldAlert,
  Calendar,
  Compass,
  Coins,
  Cpu,
  ImageIcon,
  Maximize2,
  X,
  PlayCircle,
  Tag,
  Hash,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { formatSpendSGD } from '../utils/formatters';
import {
  fetchGenerationRuns,
  fetchTelemetryEvents,
  fetchRequestTrace,
  fetchTelemetryStats,
  fetchSystemLogs,
  fetchDatabaseSummary,
  fetchDatabaseTableRecords,
  resolveImageUrl,
} from '../services/apiClient';
import PromptInspector from '../components/PromptInspector';

const COMPONENT_TAG_CLASSES = {
  generation: 'obs-badge-generation',
  vision: 'obs-badge-vision',
  wardrobe: 'obs-badge-wardrobe',
  inpaint: 'obs-badge-inpaint',
  background: 'obs-badge-background',
  api: 'obs-badge-api',
};

const STAGE_COLORS = {
  vision: '#06b6d4',
  prompt: '#a855f7',
  generation: '#6366f1',
  inpaint: '#ec4899',
  background: '#10b981',
  api: '#64748b',
};

export default function ObservabilityPage() {
  const { currentUser, userProfile, loading: isAuthLoading, isDevBypass } = useAuth();

  // Navigation tabs: 'runs' | 'events' | 'logs' | 'db'
  const [activeTab, setActiveTab] = useState('runs');

  // Stats state
  const [stats, setStats] = useState(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  const [copiedKey, setCopiedKey] = useState(null);
  const [loadError, setLoadError] = useState(null);

  // Tab 1: Generation Runs & Visual Pipeline state
  const [runs, setRuns] = useState([]);
  const [totalRuns, setTotalRuns] = useState(0);
  const [selectedRun, setSelectedRun] = useState(null);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const [runComponentFilter, setRunComponentFilter] = useState('all');
  const [runStatusFilter, setRunStatusFilter] = useState('all');
  const [runSearchQuery, setRunSearchQuery] = useState('');
  const [runPageOffset, setRunPageOffset] = useState(0);
  const runsPageSize = 30;

  // Selected Run Detail / Trace state
  const [activeTraceStep, setActiveTraceStep] = useState(null);
  const [previewImage, setPreviewImage] = useState(null);

  // Tab 2: Audit Events Data-Grid state
  const [events, setEvents] = useState([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
  const [eventComponentFilter, setEventComponentFilter] = useState('all');
  const [eventStatusFilter, setEventStatusFilter] = useState('all');
  const [eventSearchQuery, setEventSearchQuery] = useState('');
  const [eventPageOffset, setEventPageOffset] = useState(0);
  const eventsPageSize = 50;

  // Tab 3: System Logs state
  const [logs, setLogs] = useState([]);
  const [logLinesCount, setLogLinesCount] = useState(200);
  const [logLevelFilter, setLogLevelFilter] = useState('all');
  const [logSearch, setLogSearch] = useState('');
  const [autoRefreshLogs, setAutoRefreshLogs] = useState(false);
  const autoRefreshTimerRef = useRef(null);

  // Tab 4: Database Explorer state
  const [dbSummary, setDbSummary] = useState(null);
  const [selectedTable, setSelectedTable] = useState('generations');
  const [tableRecords, setTableRecords] = useState({ total: 0, rows: [] });
  const [dbPageOffset, setDbPageOffset] = useState(0);
  const [isLoadingDb, setIsLoadingDb] = useState(false);
  const [selectedDbRow, setSelectedDbRow] = useState(null);

  // Load KPI stats
  const loadStats = useCallback(async () => {
    setIsLoadingStats(true);
    try {
      const statsRes = await fetchTelemetryStats();
      if (statsRes) {
        setStats(statsRes);
        setLoadError(null);
      }
    } catch (err) {
      console.warn('Could not load telemetry stats:', err);
      setLoadError(err.message || 'Failed to load telemetry metrics');
    } finally {
      setIsLoadingStats(false);
    }
  }, []);

  // Load Generation Runs
  const loadRuns = useCallback(async () => {
    setIsLoadingRuns(true);
    try {
      const res = await fetchGenerationRuns({
        component: runComponentFilter !== 'all' ? runComponentFilter : undefined,
        status: runStatusFilter !== 'all' ? runStatusFilter : undefined,
        search: runSearchQuery.trim() || undefined,
        limit: runsPageSize,
        offset: runPageOffset,
      });

      const fetchedRuns = res?.runs || [];
      setRuns(fetchedRuns);
      setTotalRuns(res?.total || 0);

      if (fetchedRuns.length > 0) {
        setSelectedRun((prev) => {
          if (!prev) return fetchedRuns[0];
          const matched = fetchedRuns.find((r) => r.request_id === prev.request_id);
          return matched || fetchedRuns[0];
        });
      } else {
        setSelectedRun(null);
      }
    } catch (err) {
      console.error('Failed to load generation runs:', err);
      setLoadError(err.message || 'Failed to load generation runs');
    } finally {
      setIsLoadingRuns(false);
    }
  }, [runComponentFilter, runStatusFilter, runSearchQuery, runPageOffset]);

  // Load Raw Audit Events
  const loadEvents = useCallback(async () => {
    setIsLoadingEvents(true);
    try {
      const res = await fetchTelemetryEvents({
        component: eventComponentFilter !== 'all' ? eventComponentFilter : undefined,
        status: eventStatusFilter !== 'all' ? eventStatusFilter : undefined,
        search: eventSearchQuery.trim() || undefined,
        limit: eventsPageSize,
        offset: eventPageOffset,
      });

      setEvents(res?.events || []);
      setTotalEvents(res?.total || 0);
    } catch (err) {
      console.error('Failed to load telemetry events:', err);
    } finally {
      setIsLoadingEvents(false);
    }
  }, [eventComponentFilter, eventStatusFilter, eventSearchQuery, eventPageOffset]);

  // Load System Logs
  const loadLogs = useCallback(async () => {
    try {
      const res = await fetchSystemLogs({
        lines: logLinesCount,
        level: logLevelFilter !== 'all' ? logLevelFilter : undefined,
      });
      setLogs(res?.logs || []);
    } catch (err) {
      console.error('Failed to load logs:', err);
    }
  }, [logLinesCount, logLevelFilter]);

  // Load Database Summary & Selected Table
  const loadDbSummary = useCallback(async () => {
    try {
      const res = await fetchDatabaseSummary();
      setDbSummary(res?.tables || {});
    } catch (err) {
      console.error('Failed to load database summary:', err);
    }
  }, []);

  const loadDbTable = useCallback(async () => {
    if (!selectedTable) return;
    setIsLoadingDb(true);
    try {
      const res = await fetchDatabaseTableRecords(selectedTable, {
        limit: 25,
        offset: dbPageOffset,
      });
      setTableRecords(res || { total: 0, rows: [] });
    } catch (err) {
      console.error(`Failed to load records for collection ${selectedTable}:`, err);
    } finally {
      setIsLoadingDb(false);
    }
  }, [selectedTable, dbPageOffset]);

  // Initial load & Auth synchronization
  useEffect(() => {
    if (!isAuthLoading) {
      loadStats();
      if (activeTab === 'runs') loadRuns();
      if (activeTab === 'events') loadEvents();
      if (activeTab === 'logs') loadLogs();
      if (activeTab === 'db') {
        loadDbSummary();
        loadDbTable();
      }
    }
  }, [isAuthLoading, currentUser, isDevBypass, activeTab, loadStats, loadRuns, loadEvents, loadLogs, loadDbSummary, loadDbTable]);

  // Auto-refresh logs timer
  useEffect(() => {
    if (activeTab === 'logs' && autoRefreshLogs) {
      autoRefreshTimerRef.current = setInterval(() => {
        loadLogs();
      }, 3000);
    } else {
      if (autoRefreshTimerRef.current) {
        clearInterval(autoRefreshTimerRef.current);
        autoRefreshTimerRef.current = null;
      }
    }
    return () => {
      if (autoRefreshTimerRef.current) clearInterval(autoRefreshTimerRef.current);
    };
  }, [activeTab, autoRefreshLogs, loadLogs]);

  // Copy helper
  const copyToClipboard = (text, key) => {
    const val = typeof text === 'object' ? JSON.stringify(text, null, 2) : String(text);
    navigator.clipboard.writeText(val);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Download logs
  const downloadLogsAsFile = () => {
    const blob = new Blob([logs.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `studio_system_logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Format timestamp helper
  const formatTimestamp = (ts) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return String(ts);
    }
  };

  // Helpers to extract run stages
  const getRunStages = (run) => {
    if (!run || !run.events) return [];
    return run.events.map((ev, index) => {
      const name = ev.event || ev.event_type || `Step ${index + 1}`;
      const isError = ev.status === 'error' || name.toLowerCase().includes('error');
      const duration = ev.duration_ms ? `${(ev.duration_ms / 1000).toFixed(2)}s` : '—';
      const comp = ev.component || 'general';

      let stageLabel = name.replace(/_/g, ' ');
      if (name.includes('vision')) stageLabel = 'Vision Analysis';
      else if (name.includes('baseline')) stageLabel = 'Imagen Baseline';
      else if (name.includes('fine_tune')) stageLabel = 'Prompt Compilation';
      else if (name.includes('inpaint')) stageLabel = 'Inpaint Synthesis';

      return {
        id: ev.id || `step_${index}`,
        rawName: name,
        label: stageLabel,
        component: comp,
        duration,
        durationMs: ev.duration_ms || 0,
        status: isError ? 'error' : (ev.status || 'success'),
        event: ev,
      };
    });
  };

  const stages = selectedRun ? getRunStages(selectedRun) : [];
  const totalStageDurationMs = stages.reduce((acc, s) => acc + s.durationMs, 0) || selectedRun?.duration_ms || 1;

  return (
    <div className="obs-page-wrapper">
      {/* Header Bar */}
      <header className="obs-header">
        <div className="obs-header-container">
          <div className="obs-header-top">
            <div className="obs-header-brand">
              <a href="/" className="obs-back-btn" title="Back to Studio Pipeline">
                <ArrowLeft size={14} />
                <span>Studio Pipeline</span>
              </a>
              <div className="obs-brand-icon">
                <Activity size={20} />
              </div>
              <div className="obs-header-title-wrap">
                <h1>
                  <span>Studio Observability & System Intelligence</span>
                  <span className="obs-live-badge">
                    <span className="obs-live-dot" />
                    Live Tracing
                  </span>
                </h1>
                <p>Monitor end-to-end generation lifecycles, structured audit telemetry, and runtime intelligence</p>
              </div>
            </div>

            {/* Navigation Tabs & Actions */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div className="obs-nav-tabs">
                <button
                  type="button"
                  className={`obs-tab-btn ${activeTab === 'runs' ? 'active' : ''}`}
                  onClick={() => setActiveTab('runs')}
                >
                  <PlayCircle size={14} />
                  <span>Pipeline Traces</span>
                  {totalRuns > 0 && <span className="obs-tab-count">{totalRuns}</span>}
                </button>
                <button
                  type="button"
                  className={`obs-tab-btn ${activeTab === 'events' ? 'active' : ''}`}
                  onClick={() => setActiveTab('events')}
                >
                  <Code2 size={14} />
                  <span>Audit Events</span>
                  {totalEvents > 0 && <span className="obs-tab-count">{totalEvents}</span>}
                </button>
                <button
                  type="button"
                  className={`obs-tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
                  onClick={() => setActiveTab('logs')}
                >
                  <Terminal size={14} />
                  <span>System Logs</span>
                </button>
                <button
                  type="button"
                  className={`obs-tab-btn ${activeTab === 'db' ? 'active' : ''}`}
                  onClick={() => setActiveTab('db')}
                >
                  <Database size={14} />
                  <span>Database Explorer</span>
                </button>
              </div>

              <button
                type="button"
                className="obs-refresh-btn"
                onClick={() => {
                  loadStats();
                  if (activeTab === 'runs') loadRuns();
                  if (activeTab === 'events') loadEvents();
                  if (activeTab === 'logs') loadLogs();
                  if (activeTab === 'db') {
                    loadDbSummary();
                    loadDbTable();
                  }
                }}
                disabled={isLoadingRuns || isLoadingEvents || isLoadingDb}
                title="Refresh View"
              >
                <RefreshCw size={13} className={isLoadingRuns || isLoadingEvents || isLoadingDb ? 'animate-spin' : ''} />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {loadError && (
            <div style={{
              margin: '0.75rem 0',
              padding: '0.6rem 0.9rem',
              backgroundColor: '#FEF2F2',
              border: '1px solid #FEE2E2',
              borderRadius: 'var(--radius-xs)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.75rem',
              color: '#DC2626',
              fontSize: '0.78rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertCircle size={15} color="#DC2626" />
                <span style={{ fontWeight: 500 }}>{loadError}</span>
              </div>
              <button
                type="button"
                className="obs-copy-btn"
                style={{ color: '#DC2626', borderColor: '#FEE2E2', background: '#FFFFFF' }}
                onClick={() => {
                  setLoadError(null);
                  loadStats();
                  if (activeTab === 'runs') loadRuns();
                  if (activeTab === 'events') loadEvents();
                  if (activeTab === 'logs') loadLogs();
                  if (activeTab === 'db') {
                    loadDbSummary();
                    loadDbTable();
                  }
                }}
              >
                Retry
              </button>
            </div>
          )}

          {/* Global KPI Strip */}
          {stats && (
            <div className="obs-kpi-ribbon">
              <div className="obs-kpi-card">
                <div className="obs-kpi-icon-wrap obs-kpi-icon-indigo">
                  <Zap size={16} />
                </div>
                <div className="obs-kpi-details">
                  <span className="obs-kpi-label">Total Events</span>
                  <span className="obs-kpi-val">{stats.total_events?.toLocaleString() || 0}</span>
                </div>
              </div>

              <div className="obs-kpi-card">
                <div className="obs-kpi-icon-wrap obs-kpi-icon-emerald">
                  <CheckCircle2 size={16} />
                </div>
                <div className="obs-kpi-details">
                  <span className="obs-kpi-label">Success Rate</span>
                  <span className="obs-kpi-val">{stats.success_rate ?? 100}%</span>
                </div>
              </div>

              <div className="obs-kpi-card">
                <div className="obs-kpi-icon-wrap obs-kpi-icon-cyan">
                  <Coins size={16} />
                </div>
                <div className="obs-kpi-details">
                  <span className="obs-kpi-label">Total Estimated Cost</span>
                  <span className="obs-kpi-val">{formatSpendSGD(stats.total_cost_sgd, stats.total_cost_usd)}</span>
                </div>
              </div>

              <div className="obs-kpi-card">
                <div className="obs-kpi-icon-wrap obs-kpi-icon-purple">
                  <Cpu size={16} />
                </div>
                <div className="obs-kpi-details">
                  <span className="obs-kpi-label">Tokens Processed</span>
                  <span className="obs-kpi-val">{stats.total_tokens?.toLocaleString() || 0}</span>
                </div>
              </div>

              <div className="obs-kpi-card">
                <div className="obs-kpi-icon-wrap obs-kpi-icon-amber">
                  <Clock size={16} />
                </div>
                <div className="obs-kpi-details">
                  <span className="obs-kpi-label">Average Latency</span>
                  <span className="obs-kpi-val">
                    {stats.average_latencies_ms && Object.values(stats.average_latencies_ms)[0]
                      ? `${(Object.values(stats.average_latencies_ms)[0] / 1000).toFixed(1)}s`
                      : '1.4s'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Main Workspace Body */}
      <main className="obs-main-content">
        {/* ========================================================================= */}
        {/* TAB 1: VISUAL PIPELINE RUNS & END-TO-END JOURNEY                          */}
        {/* ========================================================================= */}
        {activeTab === 'runs' && (
          <div className="obs-runs-layout">
            {/* Left Sidebar: Runs List */}
            <aside className="obs-runs-sidebar">
              <div className="obs-sidebar-header">
                <div className="obs-search-input-wrap">
                  <Search size={14} className="obs-search-icon" />
                  <input
                    type="text"
                    placeholder="Search prompt, model, ID..."
                    className="obs-search-input"
                    value={runSearchQuery}
                    onChange={(e) => {
                      setRunSearchQuery(e.target.value);
                      setRunPageOffset(0);
                    }}
                  />
                </div>

                {/* Component Filter Pills */}
                <div className="obs-filter-pill-group">
                  {['all', 'generation', 'vision', 'wardrobe', 'inpaint', 'background'].map((comp) => (
                    <button
                      key={comp}
                      type="button"
                      className={`obs-filter-pill ${runComponentFilter === comp ? 'active' : ''}`}
                      onClick={() => {
                        setRunComponentFilter(comp);
                        setRunPageOffset(0);
                      }}
                    >
                      {comp === 'all' ? 'All Modules' : comp}
                    </button>
                  ))}
                </div>
              </div>

              {/* Scrollable Runs List */}
              <div className="obs-runs-list">
                {isLoadingRuns && runs.length === 0 ? (
                  <div className="obs-empty-state">
                    <RefreshCw size={24} className="animate-spin text-muted" />
                    <span>Loading pipeline traces...</span>
                  </div>
                ) : runs.length === 0 ? (
                  <div className="obs-empty-state">
                    <Compass size={28} />
                    <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>No Generation Runs Found</p>
                    <p style={{ fontSize: '0.75rem' }}>Execute a moodboard generation or refinement to record telemetry traces.</p>
                  </div>
                ) : (
                  runs.map((run) => {
                    const isSelected = selectedRun?.request_id === run.request_id;
                    const isError = run.status === 'error';
                    return (
                      <div
                        key={run.request_id}
                        className={`obs-run-card ${isSelected ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedRun(run);
                          setActiveTraceStep(null);
                        }}
                      >
                        <div className="obs-run-card-top">
                          <span className="obs-run-id">{run.request_id}</span>
                          <span className={`obs-badge ${isError ? 'obs-badge-error' : 'obs-badge-success'}`}>
                            {isError ? 'Error' : 'Success'}
                          </span>
                        </div>

                        <p className="obs-run-prompt-preview">
                          {run.prompt || 'End-to-end studio pipeline execution without explicit prompt text.'}
                        </p>

                        <div className="obs-run-card-bottom">
                          <span>{formatTimestamp(run.timestamp)}</span>
                          <div className="obs-run-metrics-mini">
                            {run.duration_ms > 0 && <span>{(run.duration_ms / 1000).toFixed(1)}s</span>}
                            {(run.cost_sgd > 0 || run.cost_usd > 0) && <span>{formatSpendSGD(run.cost_sgd, run.cost_usd)}</span>}
                            <span className="obs-badge obs-badge-api" style={{ padding: '0.1rem 0.4rem', fontSize: '0.62rem' }}>
                              {run.step_count || 1} steps
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </aside>

            {/* Right Main Panel: Selected Run Detailed Pipeline */}
            {selectedRun ? (
              <div className="obs-detail-container">
                {/* Run Summary Header Card */}
                <div className="obs-panel-card">
                  <div className="obs-panel-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <div className="obs-panel-title">
                        <PlayCircle size={18} style={{ color: '#818cf8' }} />
                        <span>Run Trace: {selectedRun.request_id}</span>
                      </div>
                      <span className={`obs-badge ${selectedRun.status === 'error' ? 'obs-badge-error' : 'obs-badge-success'}`}>
                        {selectedRun.status === 'error' ? 'Failed' : 'Completed'}
                      </span>
                      <button
                        type="button"
                        className="obs-copy-btn"
                        onClick={() => copyToClipboard(selectedRun.request_id, 'req_id')}
                      >
                        {copiedKey === 'req_id' ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                        <span>{copiedKey === 'req_id' ? 'Copied' : 'Copy ID'}</span>
                      </button>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      <span>Started: <strong style={{ color: 'var(--text-primary)' }}>{formatTimestamp(selectedRun.timestamp)}</strong></span>
                      <span>Total Time: <strong style={{ color: 'var(--accent-primary)' }}>{(selectedRun.duration_ms / 1000).toFixed(2)}s</strong></span>
                      <span>Est. Cost: <strong style={{ color: '#059669' }}>{formatSpendSGD(selectedRun.cost_sgd, selectedRun.cost_usd)}</strong></span>
                    </div>
                  </div>

                  {/* Visual Stage Stepper Bar */}
                  <div>
                    <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.04em', display: 'block', marginBottom: '0.6rem' }}>
                      Lifecycle Pipeline Stages ({stages.length} events)
                    </span>
                    <div className="obs-stage-flow">
                      {stages.map((stage, idx) => {
                        const isActive = activeTraceStep?.id === stage.id;
                        return (
                          <React.Fragment key={stage.id}>
                            <div
                              className={`obs-stage-node ${stage.status === 'error' ? 'error-stage' : 'success-stage'} ${isActive ? 'active-stage' : ''}`}
                              style={{ cursor: 'pointer' }}
                              onClick={() => setActiveTraceStep(stage)}
                            >
                              <div className="obs-stage-node-top">
                                <span className="obs-stage-name">{stage.label}</span>
                                {stage.status === 'error' ? (
                                  <AlertCircle size={14} color="#ef4444" />
                                ) : (
                                  <CheckCircle2 size={14} color="#10b981" />
                                )}
                              </div>
                              <span className="obs-stage-sub">{stage.rawName}</span>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.2rem' }}>
                                <span className={`obs-badge ${COMPONENT_TAG_CLASSES[stage.component] || 'obs-badge-api'}`} style={{ fontSize: '0.62rem', padding: '0.1rem 0.35rem' }}>
                                  {stage.component}
                                </span>
                                <span className="obs-stage-time">{stage.duration}</span>
                              </div>
                            </div>
                            {idx < stages.length - 1 && <ChevronRight size={16} className="obs-stage-arrow" />}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  </div>

                  {/* Waterfall Latency Breakdown */}
                  <div className="obs-waterfall-container">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.04em' }}>
                        Execution Latency Waterfall
                      </span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                        Total: {(totalStageDurationMs / 1000).toFixed(2)}s
                      </span>
                    </div>

                    <div className="obs-waterfall-bar-track">
                      {stages.map((stage) => {
                        const pct = Math.max(8, (stage.durationMs / totalStageDurationMs) * 100);
                        const color = STAGE_COLORS[stage.component] || '#6366f1';
                        return (
                          <div
                            key={stage.id}
                            className="obs-waterfall-segment"
                            style={{
                              width: `${pct}%`,
                              backgroundColor: color,
                            }}
                            title={`${stage.label}: ${(stage.durationMs / 1000).toFixed(2)}s (${pct.toFixed(0)}%)`}
                          >
                            {(stage.durationMs / 1000).toFixed(1)}s
                          </div>
                        );
                      })}
                    </div>

                    <div className="obs-waterfall-legend">
                      {stages.map((stage) => (
                        <div key={stage.id} className="obs-legend-item">
                          <span className="obs-legend-dot" style={{ backgroundColor: STAGE_COLORS[stage.component] || '#6366f1' }} />
                          <span>{stage.label} ({(stage.durationMs / 1000).toFixed(2)}s)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Media & Generated Assets Previews */}
                {(selectedRun.output_images?.length > 0 || selectedRun.input_images?.length > 0) && (
                  <div className="obs-panel-card">
                    <div className="obs-panel-header">
                      <div className="obs-panel-title">
                        <ImageIcon size={18} style={{ color: '#06b6d4' }} />
                        <span>Visual Artifacts & Image Outputs</span>
                      </div>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {selectedRun.output_images?.length || 0} Generated Output(s) • {selectedRun.input_images?.length || 0} Moodboard Input(s)
                      </span>
                    </div>

                    <div className="obs-media-grid">
                      {selectedRun.input_images?.map((url, idx) => (
                        <div key={`input_${idx}`} className="obs-media-card">
                          <div className="obs-media-thumb-wrap" onClick={() => setPreviewImage(url)} style={{ cursor: 'pointer' }}>
                            <img src={resolveImageUrl(url)} alt={`Reference Input ${idx + 1}`} className="obs-media-thumb" />
                          </div>
                          <div className="obs-media-label">
                            <span>Input Ref #{idx + 1}</span>
                            <span className="obs-badge obs-badge-vision" style={{ fontSize: '0.6rem' }}>Reference</span>
                          </div>
                        </div>
                      ))}

                      {selectedRun.output_images?.map((url, idx) => (
                        <div key={`out_${idx}`} className="obs-media-card">
                          <div className="obs-media-thumb-wrap" onClick={() => setPreviewImage(url)} style={{ cursor: 'pointer' }}>
                            <img src={resolveImageUrl(url)} alt={`Generated Baseline ${idx + 1}`} className="obs-media-thumb" />
                          </div>
                          <div className="obs-media-label">
                            <span>Baseline #{idx + 1}</span>
                            <span className="obs-badge obs-badge-generation" style={{ fontSize: '0.6rem' }}>Imagen</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Prompt & Compiler Inspector */}
                <PromptInspector
                  run={selectedRun}
                  activeStep={activeTraceStep}
                  onResetStep={() => setActiveTraceStep(null)}
                />

                {/* Selected Stage Step Detailed Inspector (if clicked) */}
                {activeTraceStep && (
                  <div className="obs-panel-card">
                    <div className="obs-panel-header">
                      <div className="obs-panel-title">
                        <Sliders size={18} style={{ color: '#10b981' }} />
                        <span>Inspecting Step: {activeTraceStep.label}</span>
                      </div>
                      <button
                        type="button"
                        className="obs-copy-btn"
                        onClick={() => copyToClipboard(activeTraceStep.event, 'step_json')}
                      >
                        {copiedKey === 'step_json' ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                        <span>{copiedKey === 'step_json' ? 'Copied JSON' : 'Copy JSON'}</span>
                      </button>
                    </div>

                    <div className="obs-json-box">
                      {JSON.stringify(activeTraceStep.event, null, 2)}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="obs-panel-card" style={{ alignItems: 'center', justifyContent: 'center', minHeight: '300px' }}>
                <Compass size={36} color="var(--text-muted)" />
                <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.5rem' }}>Select a generation run from the left</p>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Inspect step-by-step pipeline flows, prompts, latencies, and generated images.</p>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: AUDIT EVENTS DATA-GRID & DRAWER                                    */}
        {/* ========================================================================= */}
        {activeTab === 'events' && (
          <div className="obs-table-wrapper">
            <div className="obs-table-toolbar">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <div className="obs-search-input-wrap" style={{ width: '280px' }}>
                  <Search size={14} className="obs-search-icon" />
                  <input
                    type="text"
                    placeholder="Search events, prompts, error..."
                    className="obs-search-input"
                    value={eventSearchQuery}
                    onChange={(e) => {
                      setEventSearchQuery(e.target.value);
                      setEventPageOffset(0);
                    }}
                  />
                </div>

                <div className="obs-filter-pill-group">
                  {['all', 'generation', 'vision', 'wardrobe', 'inpaint', 'background', 'api'].map((comp) => (
                    <button
                      key={comp}
                      type="button"
                      className={`obs-filter-pill ${eventComponentFilter === comp ? 'active' : ''}`}
                      onClick={() => {
                        setEventComponentFilter(comp);
                        setEventPageOffset(0);
                      }}
                    >
                      {comp === 'all' ? 'All Components' : comp}
                    </button>
                  ))}
                </div>

                <select
                  className="obs-search-input"
                  style={{ width: '130px', padding: '0.45rem 0.65rem' }}
                  value={eventStatusFilter}
                  onChange={(e) => {
                    setEventStatusFilter(e.target.value);
                    setEventPageOffset(0);
                  }}
                >
                  <option value="all">All Statuses</option>
                  <option value="success">Success</option>
                  <option value="error">Error</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>Showing {events.length} of {totalEvents} events</span>
              </div>
            </div>

            <div className="obs-table-scroll">
              <table className="obs-data-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Component</th>
                    <th>Event Type</th>
                    <th>Request ID</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Cost</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoadingEvents ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '2rem' }}>
                        <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto', display: 'block', color: 'var(--text-muted)' }} />
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.5rem', display: 'block' }}>Loading audit events...</span>
                      </td>
                    </tr>
                  ) : events.length === 0 ? (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                        No audit events match the current filters.
                      </td>
                    </tr>
                  ) : (
                    events.map((ev) => {
                      const isError = ev.status === 'error' || (ev.event || '').toLowerCase().includes('error');
                      const isSelected = selectedEvent?.id === ev.id;
                      return (
                        <tr key={ev.id || Math.random()} className={isSelected ? 'selected' : ''}>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                            {formatTimestamp(ev.timestamp)}
                          </td>
                          <td>
                            <span className={`obs-badge ${COMPONENT_TAG_CLASSES[ev.component] || 'obs-badge-api'}`}>
                              {ev.component || 'general'}
                            </span>
                          </td>
                          <td style={{ fontWeight: 600 }}>{ev.event || ev.event_type}</td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                            {ev.request_id ? `${ev.request_id.slice(0, 16)}...` : '—'}
                          </td>
                          <td>
                            <span className={`obs-badge ${isError ? 'obs-badge-error' : 'obs-badge-success'}`}>
                              {isError ? 'Error' : 'Success'}
                            </span>
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
                            {ev.duration_ms ? `${(ev.duration_ms / 1000).toFixed(2)}s` : '—'}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: '#10b981' }}>
                            {(ev.cost_sgd || ev.cost_usd) ? formatSpendSGD(ev.cost_sgd, ev.cost_usd) : '—'}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="obs-copy-btn"
                              onClick={() => setSelectedEvent(ev)}
                            >
                              <Eye size={12} />
                              <span>Inspect</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination footer */}
            <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Page {Math.floor(eventPageOffset / eventsPageSize) + 1} of {Math.max(1, Math.ceil(totalEvents / eventsPageSize))}
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="obs-refresh-btn"
                  disabled={eventPageOffset === 0}
                  onClick={() => setEventPageOffset((prev) => Math.max(0, prev - eventsPageSize))}
                >
                  <ChevronLeft size={14} />
                  <span>Previous</span>
                </button>
                <button
                  type="button"
                  className="obs-refresh-btn"
                  disabled={eventPageOffset + eventsPageSize >= totalEvents}
                  onClick={() => setEventPageOffset((prev) => prev + eventsPageSize)}
                >
                  <span>Next</span>
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: LIVE SYSTEM LOGS TERMINAL                                          */}
        {/* ========================================================================= */}
        {activeTab === 'logs' && (
          <div className="obs-terminal-container">
            <div className="obs-terminal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Terminal size={16} color="#818cf8" />
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>Structured Console Stream</span>
                </div>

                <div className="obs-search-input-wrap" style={{ width: '220px' }}>
                  <Search size={13} className="obs-search-icon" />
                  <input
                    type="text"
                    placeholder="Search logs..."
                    className="obs-search-input"
                    value={logSearch}
                    onChange={(e) => setLogSearch(e.target.value)}
                  />
                </div>

                <select
                  className="obs-search-input"
                  style={{ width: '120px', padding: '0.45rem 0.65rem' }}
                  value={logLevelFilter}
                  onChange={(e) => setLogLevelFilter(e.target.value)}
                >
                  <option value="all">All Levels</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                </select>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={autoRefreshLogs}
                    onChange={(e) => setAutoRefreshLogs(e.target.checked)}
                  />
                  <span>Auto-Refresh (3s)</span>
                </label>

                <button
                  type="button"
                  className="obs-refresh-btn"
                  onClick={downloadLogsAsFile}
                  title="Download Log File"
                >
                  <Download size={13} />
                  <span>Download Log</span>
                </button>
              </div>
            </div>

            <div className="obs-terminal-body">
              {logs.length === 0 ? (
                <span className="obs-log-info">No log entries found.</span>
              ) : (
                logs
                  .filter((l) => !logSearch.trim() || l.toLowerCase().includes(logSearch.toLowerCase()))
                  .map((line, idx) => {
                    const isError = line.includes('[ERROR]') || line.includes('CRITICAL');
                    const isWarn = line.includes('[WARNING]') || line.includes('[WARN]');
                    let lineClass = 'obs-log-info';
                    if (isError) lineClass = 'obs-log-error';
                    else if (isWarn) lineClass = 'obs-log-warn';

                    return (
                      <div key={idx} className={`obs-log-line ${lineClass}`}>
                        {line}
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: DATABASE & FIRESTORE COLLECTION EXPLORER                           */}
        {/* ========================================================================= */}
        {activeTab === 'db' && (
          <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1.25rem' }}>
            {/* Collections Sidebar */}
            <div className="obs-panel-card" style={{ padding: '0.85rem' }}>
              <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.04em', display: 'block', marginBottom: '0.5rem' }}>
                Firestore Collections
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {dbSummary && Object.keys(dbSummary).length > 0 ? (
                  Object.entries(dbSummary).map(([colName, meta]) => {
                    const isSelected = selectedTable === colName;
                    const docCount = typeof meta === 'object' ? meta.row_count ?? meta.count ?? meta.total ?? '—' : meta;
                    return (
                      <button
                        key={colName}
                        type="button"
                        className={`obs-tab-btn ${isSelected ? 'active' : ''}`}
                        style={{ justifyContent: 'space-between', width: '100%' }}
                        onClick={() => {
                          setSelectedTable(colName);
                          setDbPageOffset(0);
                        }}
                      >
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{colName}</span>
                        <span className="obs-tab-count">{docCount}</span>
                      </button>
                    );
                  })
                ) : (
                  ['generations', 'telemetry_events', 'users', 'moodboards', 'sessions'].map((col) => (
                    <button
                      key={col}
                      type="button"
                      className={`obs-tab-btn ${selectedTable === col ? 'active' : ''}`}
                      style={{ justifyContent: 'space-between', width: '100%' }}
                      onClick={() => {
                        setSelectedTable(col);
                        setDbPageOffset(0);
                      }}
                    >
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{col}</span>
                    </button>
                  ))
                )}
              </div>
            </div>

            {/* Collection Records Data-Grid */}
            <div className="obs-table-wrapper">
              <div className="obs-table-toolbar">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Database size={16} color="var(--accent-primary)" />
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                    Collection: <code style={{ color: 'var(--accent-primary)' }}>{selectedTable}</code>
                  </span>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Total: {tableRecords.total || 0} documents
                </span>
              </div>

              <div className="obs-table-scroll">
                <table className="obs-data-table">
                  <thead>
                    <tr>
                      <th>Document ID</th>
                      <th>Created / Updated</th>
                      <th>Summary Data</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoadingDb ? (
                      <tr>
                        <td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>
                          <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto', display: 'block', color: 'var(--text-muted)' }} />
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.5rem', display: 'block' }}>Loading collection records...</span>
                        </td>
                      </tr>
                    ) : tableRecords.rows.length === 0 ? (
                      <tr>
                        <td colSpan={4} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                          No documents found in collection <code>{selectedTable}</code>.
                        </td>
                      </tr>
                    ) : (
                      tableRecords.rows.map((row, idx) => (
                        <tr key={row.id || idx}>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: '#818cf8', fontWeight: 600 }}>
                            {row.id || `doc_${idx}`}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
                            {formatTimestamp(row.timestamp || row.created_at || row.updated_at)}
                          </td>
                          <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {JSON.stringify(row)}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="obs-copy-btn"
                              onClick={() => setSelectedDbRow(row)}
                            >
                              <Eye size={12} />
                              <span>View JSON</span>
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Slide-out Drawer: Event Detail Inspector */}
      {selectedEvent && (
        <div className="obs-drawer-overlay" onClick={() => setSelectedEvent(null)}>
          <div className="obs-drawer" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Code2 size={18} color="var(--accent-primary)" />
                <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedEvent.event || selectedEvent.event_type}
                </span>
              </div>
              <button
                type="button"
                className="obs-copy-btn"
                onClick={() => setSelectedEvent(null)}
                title="Close"
              >
                <X size={14} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Component:</span>
                <span className={`obs-badge ${COMPONENT_TAG_CLASSES[selectedEvent.component] || 'obs-badge-api'}`}>{selectedEvent.component}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Status:</span>
                <span className={`obs-badge ${selectedEvent.status === 'error' ? 'obs-badge-error' : 'obs-badge-success'}`}>{selectedEvent.status}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Request ID:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{selectedEvent.request_id || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
                <span style={{ color: 'var(--text-muted)' }}>Timestamp:</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{selectedEvent.timestamp}</span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700 }}>
                Full JSON Document
              </span>
              <button
                type="button"
                className="obs-copy-btn"
                onClick={() => copyToClipboard(selectedEvent, 'drawer_event_json')}
              >
                {copiedKey === 'drawer_event_json' ? <Check size={12} color="#10b981" /> : <Copy size={12} />}
                <span>{copiedKey === 'drawer_event_json' ? 'Copied' : 'Copy'}</span>
              </button>
            </div>

            <div className="obs-json-box" style={{ flex: 1 }}>
              {JSON.stringify(selectedEvent, null, 2)}
            </div>
          </div>
        </div>
      )}

      {/* Modal: DB Row Inspector */}
      {selectedDbRow && (
        <div className="obs-drawer-overlay" onClick={() => setSelectedDbRow(null)}>
          <div className="obs-drawer" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Database size={18} color="var(--accent-primary)" />
                <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Document: {selectedDbRow.id || 'Record'}
                </span>
              </div>
              <button
                type="button"
                className="obs-copy-btn"
                onClick={() => setSelectedDbRow(null)}
              >
                <X size={14} />
              </button>
            </div>

            <div className="obs-json-box" style={{ flex: 1 }}>
              {JSON.stringify(selectedDbRow, null, 2)}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Fullscreen Image Preview */}
      {previewImage && (
        <div className="obs-drawer-overlay" onClick={() => setPreviewImage(null)} style={{ alignItems: 'center', justifyContent: 'center' }}>
          <div
            style={{
              position: 'relative',
              maxWidth: '90vw',
              maxHeight: '90vh',
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-interactive, #e2e4e9)',
              borderRadius: 'var(--radius-xs, 0px)',
              boxShadow: 'var(--shadow-modal)',
              overflow: 'hidden',
              padding: '0.5rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="obs-copy-btn"
              style={{ position: 'absolute', top: '1rem', right: '1rem', zIndex: 10 }}
              onClick={() => setPreviewImage(null)}
            >
              <X size={16} />
            </button>
            <img
              src={resolveImageUrl(previewImage)}
              alt="Asset Preview"
              style={{ maxWidth: '100%', maxHeight: '85vh', objectFit: 'contain', borderRadius: 'var(--radius-md)' }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
