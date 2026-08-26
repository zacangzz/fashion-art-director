import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity,
  ArrowLeft,
  RefreshCw,
  Search,
  CheckCircle,
  AlertCircle,
  Clock,
  Code,
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
} from 'lucide-react';
import {
  fetchTelemetryEvents,
  fetchRequestTrace,
  fetchTelemetryStats,
  fetchSystemLogs,
  fetchDatabaseSummary,
  fetchDatabaseTableRecords,
} from '../services/apiClient';

const COMPONENT_COLORS = {
  generation: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  vision: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  wardrobe: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  inpaint: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/30',
  api: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
};

export default function ObservabilityPage() {
  const [activeTab, setActiveTab] = useState('events'); // 'events' | 'logs' | 'db' | 'stats'

  // Telemetry events state
  const [events, setEvents] = useState([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [requestTrace, setRequestTrace] = useState([]);
  const [isLoadingTrace, setIsLoadingTrace] = useState(false);
  const [copiedKey, setCopiedKey] = useState(null);

  // Filters state
  const [componentFilter, setComponentFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [pageOffset, setPageOffset] = useState(0);
  const pageSize = 50;

  // Stats state
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Logs state
  const [logs, setLogs] = useState([]);
  const [logLinesCount, setLogLinesCount] = useState(200);
  const [logLevelFilter, setLogLevelFilter] = useState('all');
  const [logSearch, setLogSearch] = useState('');
  const [autoRefreshLogs, setAutoRefreshLogs] = useState(false);
  const autoRefreshTimerRef = useRef(null);

  // Database state
  const [dbSummary, setDbSummary] = useState(null);
  const [selectedTable, setSelectedTable] = useState('generations');
  const [tableRecords, setTableRecords] = useState({ total: 0, rows: [] });
  const [dbPageOffset, setDbPageOffset] = useState(0);
  const [isLoadingDb, setIsLoadingDb] = useState(false);
  const [selectedDbRow, setSelectedDbRow] = useState(null);

  // Load telemetry data
  const loadTelemetry = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = {
        limit: pageSize,
        offset: pageOffset,
      };
      if (componentFilter !== 'all') params.component = componentFilter;
      if (statusFilter !== 'all') params.status = statusFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const [eventsRes, statsRes] = await Promise.all([
        fetchTelemetryEvents(params),
        fetchTelemetryStats().catch(() => null),
      ]);

      setEvents(eventsRes?.events || []);
      setTotalEvents(eventsRes?.total || 0);
      if (statsRes) setStats(statsRes);

      if (eventsRes?.events?.length > 0 && !selectedEvent) {
        setSelectedEvent(eventsRes.events[0]);
      }
    } catch (err) {
      console.error('Failed to load telemetry:', err);
    } finally {
      setIsLoading(false);
    }
  }, [componentFilter, statusFilter, searchQuery, pageOffset, selectedEvent]);

  // Load trace when selected event changes
  useEffect(() => {
    if (!selectedEvent?.request_id) {
      setRequestTrace([]);
      return;
    }

    let isMounted = true;
    setIsLoadingTrace(true);
    fetchRequestTrace(selectedEvent.request_id)
      .then((trace) => {
        if (isMounted) setRequestTrace(trace || []);
      })
      .catch((err) => {
        console.warn('Could not load trace:', err);
        if (isMounted) setRequestTrace([]);
      })
      .finally(() => {
        if (isMounted) setIsLoadingTrace(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedEvent?.request_id]);

  // Load system logs
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

  // Load DB Summary
  const loadDbSummary = useCallback(async () => {
    try {
      const res = await fetchDatabaseSummary();
      setDbSummary(res?.tables || {});
    } catch (err) {
      console.error('Failed to load database summary:', err);
    }
  }, []);

  // Load DB Table Records
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
      console.error(`Failed to load records for table ${selectedTable}:`, err);
    } finally {
      setIsLoadingDb(false);
    }
  }, [selectedTable, dbPageOffset]);

  // Initial load
  useEffect(() => {
    loadTelemetry();
    loadDbSummary();
  }, [loadTelemetry, loadDbSummary]);

  // Effect for logs tab
  useEffect(() => {
    if (activeTab === 'logs') {
      loadLogs();
    }
  }, [activeTab, loadLogs]);

  // Effect for auto-refreshing logs
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

  // Effect for database tab
  useEffect(() => {
    if (activeTab === 'db') {
      loadDbTable();
    }
  }, [activeTab, loadDbTable]);

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(typeof text === 'object' ? JSON.stringify(text, null, 2) : String(text));
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const downloadLogsAsFile = () => {
    const blob = new Blob([logs.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `studio_system_logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Filter logs by search term
  const filteredLogs = logs.filter((line) => {
    if (!logSearch.trim()) return true;
    return line.toLowerCase().includes(logSearch.toLowerCase());
  });

  return (
    <div className="min-h-screen bg-[#090b10] text-slate-100 flex flex-col font-sans selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Top Header */}
      <header className="border-b border-slate-800/80 bg-[#10141f]/90 backdrop-blur-md px-6 py-4 sticky top-0 z-30 shadow-lg">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <a
              href="/"
              className="px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs font-semibold flex items-center gap-2 transition"
              title="Return to Main Studio Pipeline"
            >
              <ArrowLeft size={14} />
              <span>Studio Pipeline</span>
            </a>
            <div className="h-5 w-px bg-slate-800" />
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-gradient-to-tr from-indigo-600/30 to-cyan-500/30 border border-indigo-500/40 shadow-inner">
                <Activity size={20} className="text-indigo-400 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold text-white tracking-tight">Studio Observability & System Intelligence</h1>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold tracking-wider uppercase">
                    Live Telemetry
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  Inspect structured execution traces, latency metrics, rotating logs, and SQLite state
                </p>
              </div>
            </div>
          </div>

          {/* Quick Actions & Navigation Tabs */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (activeTab === 'events' || activeTab === 'stats') loadTelemetry();
                if (activeTab === 'logs') loadLogs();
                if (activeTab === 'db') {
                  loadDbSummary();
                  loadDbTable();
                }
              }}
              disabled={isLoading || isLoadingDb}
              className="px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium flex items-center gap-2 transition disabled:opacity-50"
              title="Refresh All"
            >
              <RefreshCw size={13} className={isLoading || isLoadingDb ? 'animate-spin' : ''} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Global KPI Metrics Strip */}
        {stats && (
          <div className="max-w-7xl mx-auto grid grid-cols-2 sm:grid-cols-5 gap-3 mt-4 pt-3 border-t border-slate-800/60">
            <div className="px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center gap-3">
              <Zap size={16} className="text-indigo-400" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Total Events</div>
                <div className="text-sm font-bold text-slate-100">{stats.total_events.toLocaleString()}</div>
              </div>
            </div>
            <div className="px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center gap-3">
              <CheckCircle size={16} className="text-emerald-400" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Success Rate</div>
                <div className="text-sm font-bold text-emerald-300">{stats.success_rate.toFixed(1)}%</div>
              </div>
            </div>
            <div className="px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center gap-3">
              <AlertCircle size={16} className={stats.error_count > 0 ? 'text-rose-400' : 'text-slate-500'} />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Error Count</div>
                <div className="text-sm font-bold text-rose-300">{stats.error_count}</div>
              </div>
            </div>
            <div className="px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center gap-3">
              <Clock size={16} className="text-amber-400" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">Avg Image Latency</div>
                <div className="text-sm font-bold text-amber-300">
                  {stats.average_latencies_ms?.['gemini-3.1-flash-lite-image']
                    ? `${stats.average_latencies_ms['gemini-3.1-flash-lite-image'].toFixed(0)} ms`
                    : stats.average_latencies_ms?.['gemini-3.1-flash-lite']
                    ? `${stats.average_latencies_ms['gemini-3.1-flash-lite'].toFixed(0)} ms`
                    : 'N/A'}
                </div>
              </div>
            </div>
            <div className="px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center gap-3">
              <Database size={16} className="text-cyan-400" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-semibold">SQLite Generations</div>
                <div className="text-sm font-bold text-cyan-300">
                  {dbSummary?.generations?.row_count !== undefined ? dbSummary.generations.row_count : '...'}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="max-w-7xl mx-auto flex items-center gap-2 mt-4">
          <button
            onClick={() => setActiveTab('events')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'events'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Activity size={14} />
            <span>Telemetry Events & Traces</span>
            <span className="ml-1 px-1.5 py-0.2 rounded-full bg-black/30 text-[10px]">{totalEvents}</span>
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'logs'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Terminal size={14} />
            <span>Live System Logs</span>
          </button>
          <button
            onClick={() => setActiveTab('db')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'db'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Database size={14} />
            <span>Database Explorer</span>
          </button>
          <button
            onClick={() => setActiveTab('stats')}
            className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
              activeTab === 'stats'
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Sliders size={14} />
            <span>Metrics & Distribution</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {/* ========================================================================= */}
        {/* TAB 1: TELEMETRY EVENTS & REQUEST TRACES                                   */}
        {/* ========================================================================= */}
        {activeTab === 'events' && (
          <div className="flex flex-col gap-4">
            {/* Filter Bar */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3 shadow">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Filter size={12} /> Component:
                </span>
                {['all', 'generation', 'vision', 'wardrobe', 'inpaint', 'api'].map((comp) => (
                  <button
                    key={comp}
                    onClick={() => {
                      setComponentFilter(comp);
                      setPageOffset(0);
                    }}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition ${
                      componentFilter === comp
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {comp}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">Status:</span>
                  <select
                    value={statusFilter}
                    onChange={(e) => {
                      setStatusFilter(e.target.value);
                      setPageOffset(0);
                    }}
                    className="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded-md px-2.5 py-1 outline-none focus:border-indigo-500"
                  >
                    <option value="all">All Statuses</option>
                    <option value="success">Success</option>
                    <option value="error">Error</option>
                    <option value="started">Started / Request</option>
                  </select>
                </div>

                <div className="relative">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setPageOffset(0);
                    }}
                    placeholder="Search logs, prompts, IDs..."
                    className="bg-slate-800 border border-slate-700 rounded-md pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 w-52 focus:w-64 transition-all outline-none focus:border-indigo-500"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Split View: Left List / Right Details */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
              {/* Left Column: Event List */}
              <div className="lg:col-span-5 flex flex-col gap-2 rounded-xl bg-slate-900/60 border border-slate-800 p-3 h-[680px]">
                <div className="flex items-center justify-between px-2 py-1 text-xs text-slate-400 border-b border-slate-800 pb-2">
                  <span>Showing {events.length} of {totalEvents} recorded events</span>
                  {isLoading && <span className="text-indigo-400 animate-pulse">Loading...</span>}
                </div>

                <div className="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
                  {events.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-16">
                      <Compass size={32} className="mb-2 opacity-40" />
                      <p className="font-semibold">No telemetry events found</p>
                      <p className="text-[11px] text-slate-600">Run generations or moodboard analysis to produce telemetry.</p>
                    </div>
                  ) : (
                    events.map((ev, idx) => {
                      const isSelected =
                        selectedEvent &&
                        selectedEvent.request_id === ev.request_id &&
                        selectedEvent.timestamp === ev.timestamp;
                      const comp = ev.component || 'general';
                      const isErr = ev.status === 'error' || ev.event?.includes('error');

                      return (
                        <div
                          key={`${ev.request_id}-${ev.timestamp}-${idx}`}
                          onClick={() => setSelectedEvent(ev)}
                          className={`p-3 rounded-lg border cursor-pointer transition flex flex-col gap-1.5 ${
                            isSelected
                              ? 'bg-indigo-950/40 border-indigo-500/80 shadow-md shadow-indigo-950/50'
                              : 'bg-slate-950/40 border-slate-800/80 hover:bg-slate-800/50 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold border uppercase tracking-wider ${
                                  COMPONENT_COLORS[comp] || COMPONENT_COLORS.api
                                }`}
                              >
                                {comp}
                              </span>
                              <span className="text-xs font-mono font-bold text-slate-200 truncate max-w-[170px]">
                                {ev.event || ev.event_type}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              {ev.duration_ms !== undefined && (
                                <span className="text-[10px] font-mono text-amber-400 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-800/40">
                                  {ev.duration_ms}ms
                                </span>
                              )}
                              <span
                                className={`w-2 h-2 rounded-full ${
                                  isErr ? 'bg-rose-500 shadow-sm shadow-rose-500' : 'bg-emerald-500'
                                }`}
                              />
                            </div>
                          </div>

                          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                            <span className="truncate max-w-[200px]" title={ev.request_id}>
                              {ev.request_id || 'no-request-id'}
                            </span>
                            <span>{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : ''}</span>
                          </div>

                          {ev.model && (
                            <div className="text-[10px] text-slate-400 truncate">
                              Model: <span className="text-cyan-300 font-mono">{ev.model}</span>
                            </div>
                          )}

                          {ev.error && (
                            <div className="text-[11px] text-rose-300 bg-rose-950/40 p-1.5 rounded border border-rose-900/50 truncate font-mono">
                              {ev.error}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Pagination footer */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800 px-2 text-xs text-slate-400">
                  <button
                    disabled={pageOffset === 0}
                    onClick={() => setPageOffset(Math.max(0, pageOffset - pageSize))}
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 flex items-center gap-1"
                  >
                    <ChevronLeft size={13} /> Prev
                  </button>
                  <span>
                    {pageOffset + 1}–{Math.min(pageOffset + pageSize, totalEvents)} of {totalEvents}
                  </span>
                  <button
                    disabled={pageOffset + pageSize >= totalEvents}
                    onClick={() => setPageOffset(pageOffset + pageSize)}
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 flex items-center gap-1"
                  >
                    Next <ChevronRight size={13} />
                  </button>
                </div>
              </div>

              {/* Right Column: Detailed Event Inspector */}
              <div className="lg:col-span-7 flex flex-col gap-4 rounded-xl bg-slate-900/60 border border-slate-800 p-5 h-[680px] overflow-y-auto custom-scrollbar">
                {selectedEvent ? (
                  <>
                    {/* Header */}
                    <div className="flex items-start justify-between border-b border-slate-800 pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2.5 py-0.5 rounded text-xs font-semibold border uppercase tracking-wider ${
                              COMPONENT_COLORS[selectedEvent.component] || COMPONENT_COLORS.api
                            }`}
                          >
                            {selectedEvent.component || 'general'}
                          </span>
                          <h3 className="text-base font-bold text-white font-mono">
                            {selectedEvent.event || selectedEvent.event_type}
                          </h3>
                        </div>
                        <div className="text-xs text-slate-400 font-mono mt-1 flex items-center gap-3">
                          <span>Request ID: <strong className="text-slate-200">{selectedEvent.request_id}</strong></span>
                          <span>Timestamp: {selectedEvent.timestamp}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => copyToClipboard(selectedEvent, 'event-full')}
                        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition"
                      >
                        {copiedKey === 'event-full' ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                        <span>{copiedKey === 'event-full' ? 'Copied' : 'Copy JSON'}</span>
                      </button>
                    </div>

                    {/* Quick Insight Cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">Status</div>
                        <div className={`text-xs font-bold font-mono mt-0.5 ${selectedEvent.status === 'error' ? 'text-rose-400' : 'text-emerald-400'}`}>
                          {selectedEvent.status || 'success'}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">Execution Time</div>
                        <div className="text-xs font-bold font-mono text-amber-300 mt-0.5">
                          {selectedEvent.duration_ms ? `${selectedEvent.duration_ms} ms` : 'N/A'}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">Model</div>
                        <div className="text-xs font-bold font-mono text-cyan-300 truncate mt-0.5" title={selectedEvent.model || selectedEvent.config?.model}>
                          {selectedEvent.model || selectedEvent.config?.model || 'N/A'}
                        </div>
                      </div>
                      <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800">
                        <div className="text-[10px] text-slate-400 uppercase font-semibold">Locked Seed</div>
                        <div className="text-xs font-bold font-mono text-slate-200 mt-0.5">
                          {selectedEvent.seed !== undefined ? selectedEvent.seed : selectedEvent.config?.seed !== undefined ? selectedEvent.config.seed : 'unspecified'}
                        </div>
                      </div>
                    </div>

                    {/* Final Prompt / Input Inspection */}
                    {selectedEvent.final_prompt && (
                      <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
                        <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-1.5">
                          <span className="flex items-center gap-1.5 text-indigo-300">
                            <Sparkles size={13} /> Final Compiled Prompt Sent to Gemini:
                          </span>
                          <button
                            onClick={() => copyToClipboard(selectedEvent.final_prompt, 'prompt')}
                            className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1"
                          >
                            {copiedKey === 'prompt' ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                            Copy
                          </button>
                        </div>
                        <div className="text-xs text-slate-300 font-mono whitespace-pre-wrap bg-black/40 p-2.5 rounded border border-slate-800/80 max-h-36 overflow-y-auto custom-scrollbar">
                          {selectedEvent.final_prompt}
                        </div>
                      </div>
                    )}

                    {/* Inpainting / Spatial Telemetry (if present) */}
                    {selectedEvent.mask_analysis && (
                      <div className="rounded-lg bg-slate-950/60 border border-fuchsia-900/40 p-3">
                        <div className="text-xs font-bold text-fuchsia-300 mb-2 flex items-center gap-2">
                          <Layers size={13} /> Mask & Spatial Inpainting Telemetry:
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                          <div className="bg-black/30 p-2 rounded border border-slate-800">
                            <div className="text-[10px] text-slate-400">Coverage</div>
                            <div className="text-fuchsia-300 font-bold">{selectedEvent.mask_analysis.coverage_percentage}%</div>
                          </div>
                          <div className="bg-black/30 p-2 rounded border border-slate-800">
                            <div className="text-[10px] text-slate-400">Dimensions</div>
                            <div>{selectedEvent.mask_analysis.width} × {selectedEvent.mask_analysis.height} px</div>
                          </div>
                          <div className="bg-black/30 p-2 rounded border border-slate-800">
                            <div className="text-[10px] text-slate-400">Centroid (Norm)</div>
                            <div>x: {selectedEvent.mask_analysis.centroid?.norm_x}, y: {selectedEvent.mask_analysis.centroid?.norm_y}</div>
                          </div>
                          <div className="bg-black/30 p-2 rounded border border-slate-800">
                            <div className="text-[10px] text-slate-400">Mask SHA-256</div>
                            <div className="truncate text-[10px] text-slate-400" title={selectedEvent.mask_analysis.sha256}>
                              {selectedEvent.mask_analysis.sha256?.slice(0, 10)}...
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Request Lifecycle Trace Timeline */}
                    <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
                      <div className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-2">
                        <Activity size={13} className="text-indigo-400" />
                        Request Lifecycle Trace ({requestTrace.length} correlated events):
                      </div>

                      {isLoadingTrace ? (
                        <div className="text-xs text-slate-500 py-3 text-center animate-pulse">Loading correlated lifecycle trace...</div>
                      ) : requestTrace.length === 0 ? (
                        <div className="text-xs text-slate-500 py-2">No other events linked to this request ID.</div>
                      ) : (
                        <div className="space-y-1.5 font-mono text-xs">
                          {requestTrace.map((tr, tidx) => (
                            <div
                              key={tidx}
                              className="flex items-center justify-between p-2 rounded bg-black/40 border border-slate-800/80 text-[11px]"
                            >
                              <div className="flex items-center gap-2">
                                <span className="text-indigo-400 font-bold">#{tidx + 1}</span>
                                <span className="text-slate-200 font-semibold">{tr.event || tr.event_type}</span>
                                <span className={`px-1.5 py-0.2 rounded text-[9px] uppercase font-bold border ${COMPONENT_COLORS[tr.component] || COMPONENT_COLORS.api}`}>
                                  {tr.component}
                                </span>
                              </div>
                              <div className="flex items-center gap-3 text-slate-400">
                                {tr.duration_ms !== undefined && <span className="text-amber-400">{tr.duration_ms} ms</span>}
                                <span>{tr.timestamp ? new Date(tr.timestamp).toLocaleTimeString() : ''}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Complete JSON Payload */}
                    <div className="rounded-lg bg-slate-950/60 border border-slate-800 p-3">
                      <div className="flex items-center justify-between text-xs font-semibold text-slate-300 mb-1.5">
                        <span className="flex items-center gap-1.5 text-cyan-300">
                          <Code size={13} /> Full Structured Event Record:
                        </span>
                      </div>
                      <pre className="text-[11px] text-cyan-200/90 font-mono bg-black/60 p-3 rounded border border-slate-800/80 overflow-x-auto max-h-56 custom-scrollbar">
                        {JSON.stringify(selectedEvent, null, 2)}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-20">
                    <Eye size={36} className="mb-2 opacity-30" />
                    <p className="font-semibold text-sm">Select an event from the left list</p>
                    <p className="text-slate-600">Inspect full JSON details, prompt compiler inputs, and latency breakdowns.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: LIVE SYSTEM LOGS                                                    */}
        {/* ========================================================================= */}
        {activeTab === 'logs' && (
          <div className="flex flex-col gap-4">
            {/* Logs Controls Bar */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3 shadow">
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-slate-400">Level:</span>
                  {['all', 'INFO', 'WARNING', 'ERROR'].map((lvl) => (
                    <button
                      key={lvl}
                      onClick={() => setLogLevelFilter(lvl)}
                      className={`px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                        logLevelFilter === lvl
                          ? lvl === 'ERROR'
                            ? 'bg-rose-600 text-white'
                            : lvl === 'WARNING'
                            ? 'bg-amber-600 text-white'
                            : 'bg-indigo-600 text-white'
                          : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {lvl}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">Lines:</span>
                  <select
                    value={logLinesCount}
                    onChange={(e) => setLogLinesCount(Number(e.target.value))}
                    className="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded-md px-2 py-1 outline-none"
                  >
                    <option value={50}>50 lines</option>
                    <option value={100}>100 lines</option>
                    <option value={200}>200 lines</option>
                    <option value={500}>500 lines</option>
                  </select>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="relative">
                  <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="text"
                    value={logSearch}
                    onChange={(e) => setLogSearch(e.target.value)}
                    placeholder="Search logs stream..."
                    className="bg-slate-800 border border-slate-700 rounded-md pl-8 pr-3 py-1 text-xs text-slate-200 placeholder-slate-500 w-52 focus:w-64 outline-none focus:border-indigo-500"
                  />
                </div>

                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
                  <input
                    type="checkbox"
                    checked={autoRefreshLogs}
                    onChange={(e) => setAutoRefreshLogs(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-indigo-500"
                  />
                  <span>Auto-Refresh (3s)</span>
                </label>

                <button
                  onClick={downloadLogsAsFile}
                  className="px-3 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition"
                  title="Download raw logs to local disk"
                >
                  <Download size={13} />
                  <span>Download</span>
                </button>
              </div>
            </div>

            {/* Terminal Window */}
            <div className="rounded-xl bg-[#06080d] border border-slate-800 shadow-2xl overflow-hidden flex flex-col h-[650px]">
              {/* Terminal Titlebar */}
              <div className="bg-slate-900/90 border-b border-slate-800 px-4 py-2.5 flex items-center justify-between text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
                  </div>
                  <span className="font-mono text-slate-300 font-semibold ml-2">storage/logs/studio.log</span>
                </div>
                <div className="flex items-center gap-3 text-[11px] font-mono">
                  <span>Displaying: {filteredLogs.length} lines</span>
                  {autoRefreshLogs && <span className="text-emerald-400 flex items-center gap-1 font-bold animate-pulse">● Live Stream</span>}
                </div>
              </div>

              {/* Terminal Log Content */}
              <div className="flex-1 p-4 font-mono text-xs overflow-y-auto custom-scrollbar space-y-1 bg-[#07090e]">
                {filteredLogs.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-slate-600 text-xs">
                    No matching log entries found.
                  </div>
                ) : (
                  filteredLogs.map((line, idx) => {
                    const isErr = line.includes('[ERROR]');
                    const isWarn = line.includes('[WARNING]');
                    const isInfo = line.includes('[INFO]');

                    let textClass = 'text-slate-300';
                    if (isErr) textClass = 'text-rose-400 font-semibold';
                    else if (isWarn) textClass = 'text-amber-300';
                    else if (isInfo) textClass = 'text-emerald-300/90';

                    return (
                      <div
                        key={idx}
                        className={`leading-relaxed whitespace-pre-wrap break-all px-2 py-0.5 rounded hover:bg-slate-800/40 ${textClass}`}
                      >
                        {line}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: SQLITE DATABASE EXPLORER                                            */}
        {/* ========================================================================= */}
        {activeTab === 'db' && (
          <div className="flex flex-col gap-4">
            {/* Table Selector Pills */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3 shadow">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-slate-400 font-semibold flex items-center gap-1.5">
                  <Database size={13} className="text-cyan-400" /> Tables:
                </span>
                {['generations', 'moodboards', 'conversations', 'wardrobe_items', 'composition_assignments'].map((tName) => {
                  const count = dbSummary?.[tName]?.row_count;
                  return (
                    <button
                      key={tName}
                      onClick={() => {
                        setSelectedTable(tName);
                        setDbPageOffset(0);
                        setSelectedDbRow(null);
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono font-semibold flex items-center gap-2 transition ${
                        selectedTable === tName
                          ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                          : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700/80'
                      }`}
                    >
                      <span>{tName}</span>
                      {count !== undefined && (
                        <span className="px-1.5 py-0.2 rounded-full bg-black/40 text-[10px] text-cyan-200">
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    loadDbSummary();
                    loadDbTable();
                  }}
                  disabled={isLoadingDb}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <RefreshCw size={12} className={isLoadingDb ? 'animate-spin' : ''} />
                  <span>Reload Table</span>
                </button>
              </div>
            </div>

            {/* Table Data Viewer */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
              {/* Left Data Grid */}
              <div className="lg:col-span-8 flex flex-col rounded-xl bg-slate-900/60 border border-slate-800 p-4 h-[650px]">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 text-xs text-slate-400">
                  <span className="font-mono">
                    Table: <strong className="text-white">{selectedTable}</strong> ({tableRecords.total} total rows)
                  </span>
                  {isLoadingDb && <span className="text-cyan-400 animate-pulse">Loading records...</span>}
                </div>

                <div className="flex-1 overflow-x-auto overflow-y-auto mt-2 custom-scrollbar">
                  {tableRecords.rows.length === 0 ? (
                    <div className="h-full flex items-center justify-center text-slate-500 text-xs py-20">
                      No records stored in table '{selectedTable}'.
                    </div>
                  ) : (
                    <table className="w-full text-left text-xs font-mono border-collapse">
                      <thead className="sticky top-0 bg-slate-950 text-slate-400 text-[11px] uppercase border-b border-slate-800">
                        <tr>
                          {Object.keys(tableRecords.rows[0]).map((col) => (
                            <th key={col} className="p-2.5 font-semibold whitespace-nowrap">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {tableRecords.rows.map((row, rIdx) => {
                          const isSelected = selectedDbRow && selectedDbRow.id === row.id;
                          return (
                            <tr
                              key={rIdx}
                              onClick={() => setSelectedDbRow(row)}
                              className={`cursor-pointer transition ${
                                isSelected
                                  ? 'bg-cyan-950/40 text-cyan-200'
                                  : 'hover:bg-slate-800/40 text-slate-300'
                              }`}
                            >
                              {Object.entries(row).map(([k, v], cIdx) => {
                                let displayVal = v;
                                if (typeof v === 'object' && v !== null) {
                                  displayVal = JSON.stringify(v);
                                } else if (typeof v === 'boolean') {
                                  displayVal = v ? 'TRUE' : 'FALSE';
                                } else if (v === null || v === undefined) {
                                  displayVal = <span className="text-slate-600">NULL</span>;
                                }

                                return (
                                  <td
                                    key={cIdx}
                                    className="p-2.5 max-w-[200px] truncate whitespace-nowrap text-[11px]"
                                    title={String(v)}
                                  >
                                    {displayVal}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between pt-3 border-t border-slate-800 text-xs text-slate-400">
                  <button
                    disabled={dbPageOffset === 0}
                    onClick={() => setDbPageOffset(Math.max(0, dbPageOffset - 25))}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 flex items-center gap-1"
                  >
                    <ChevronLeft size={13} /> Prev 25
                  </button>
                  <span>
                    Offset {dbPageOffset}–{Math.min(dbPageOffset + 25, tableRecords.total)} of {tableRecords.total}
                  </span>
                  <button
                    disabled={dbPageOffset + 25 >= tableRecords.total}
                    onClick={() => setDbPageOffset(dbPageOffset + 25)}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 flex items-center gap-1"
                  >
                    Next 25 <ChevronRight size={13} />
                  </button>
                </div>
              </div>

              {/* Right Detail Pane */}
              <div className="lg:col-span-4 flex flex-col rounded-xl bg-slate-900/60 border border-slate-800 p-4 h-[650px] overflow-y-auto custom-scrollbar">
                {selectedDbRow ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                      <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                        Row Record Details
                      </h4>
                      <button
                        onClick={() => copyToClipboard(selectedDbRow, 'db-row')}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700 flex items-center gap-1"
                      >
                        {copiedKey === 'db-row' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        <span>Copy</span>
                      </button>
                    </div>

                    {/* Image Preview for Generations / Wardrobe Items */}
                    {selectedDbRow.master_image_url && (
                      <div className="rounded-lg bg-black/60 p-2 border border-slate-800 flex flex-col items-center">
                        <img
                          src={selectedDbRow.master_image_url}
                          alt="Master Render"
                          className="max-h-48 rounded object-contain"
                        />
                        <a
                          href={selectedDbRow.master_image_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-2 text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
                        >
                          <ExternalLink size={11} /> Open full-resolution master
                        </a>
                      </div>
                    )}

                    {selectedDbRow.cropped_image_path && selectedDbRow.id && (
                      <div className="rounded-lg bg-black/60 p-2 border border-slate-800 flex flex-col items-center">
                        <img
                          src={`/api/wardrobe/items/${selectedDbRow.id}/image`}
                          alt="Cropped Garment"
                          className="max-h-36 rounded object-contain"
                        />
                        <span className="text-[11px] text-slate-400 mt-1">{selectedDbRow.label}</span>
                      </div>
                    )}

                    {/* Formatted Row Fields */}
                    <div className="space-y-2 font-mono text-xs">
                      {Object.entries(selectedDbRow).map(([k, v]) => (
                        <div key={k} className="p-2 rounded bg-black/40 border border-slate-800/80">
                          <div className="text-[10px] text-slate-400 font-semibold">{k}</div>
                          <div className="text-slate-200 whitespace-pre-wrap break-all mt-0.5 max-h-32 overflow-y-auto custom-scrollbar">
                            {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-slate-500 text-xs py-20">
                    <Database size={32} className="mb-2 opacity-30" />
                    <p className="font-semibold">Select a table row</p>
                    <p className="text-slate-600">Inspect full JSON fields, column types, and image previews.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: METRICS & COMPONENT DISTRIBUTION                                    */}
        {/* ========================================================================= */}
        {activeTab === 'stats' && stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Component Volume Card */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col gap-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Layers size={16} className="text-indigo-400" />
                Component Request Volume
              </h3>
              <div className="space-y-3">
                {Object.entries(stats.components || {}).map(([comp, count]) => {
                  const pct = stats.total_events > 0 ? (count / stats.total_events) * 100 : 0;
                  return (
                    <div key={comp} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="capitalize text-slate-300 font-medium">{comp}</span>
                        <span className="font-mono text-slate-400">
                          {count} ({pct.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-indigo-500 transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Model Latencies Card */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col gap-4">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Clock size={16} className="text-amber-400" />
                Average Model Latency (ms)
              </h3>
              <div className="space-y-3">
                {Object.entries(stats.average_latencies_ms || {}).map(([modelName, lat]) => (
                  <div
                    key={modelName}
                    className="p-3 rounded-lg bg-black/40 border border-slate-800 flex items-center justify-between"
                  >
                    <div>
                      <div className="text-xs font-mono font-bold text-cyan-300">{modelName}</div>
                      <div className="text-[11px] text-slate-400">Google GenAI SDK</div>
                    </div>
                    <div className="text-base font-mono font-bold text-amber-300">
                      {lat.toFixed(1)} ms
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Event Types Breakdown Card */}
            <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 flex flex-col gap-4 md:col-span-2">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Sliders size={16} className="text-cyan-400" />
                Event Types Breakdown
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(stats.event_types || {}).map(([evt, count]) => (
                  <div
                    key={evt}
                    className="p-3 rounded-lg bg-black/40 border border-slate-800/80 flex flex-col justify-between"
                  >
                    <div className="text-xs font-mono text-slate-300 font-semibold truncate" title={evt}>
                      {evt}
                    </div>
                    <div className="text-lg font-mono font-bold text-indigo-400 mt-2">{count}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
