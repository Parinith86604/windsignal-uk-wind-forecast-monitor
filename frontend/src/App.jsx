import { useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertCircle, ArrowDownRight, ArrowUpRight, CalendarDays,
  CheckCircle2, ChevronDown, Clock3, CloudDownload, Database, ExternalLink,
  Gauge, RefreshCw, ShieldCheck, Wind, Zap,
} from 'lucide-react';
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  Bar, BarChart, ReferenceLine,
} from 'recharts';
import { getAnalysis } from './api.js';

const HORIZONS = [
  { hours: 12, label: '12h' },
  { hours: 24, label: '24h' },
  { hours: 36, label: '36h' },
  { hours: 48, label: '48h' },
  { hours: 60, label: '60h' },
  { hours: 72, label: '72h', disabled: true, title: 'No data: WINDFOR feed publication lookahead caps at 66.5h' },
];

const fmt = (value, digits = 0) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: digits });
const signed = (value, digits = 0) => value == null ? '—' : `${value > 0 ? '+' : ''}${fmt(value, digits)}`;
const compactDate = (value) => new Date(`${value}T00:00:00Z`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' });
const timeLabel = (value) => new Date(value).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC';

function StatCard({ icon: Icon, label, value, unit, note, tone = 'default' }) {
  return (
    <article className={`stat-card ${tone}`}>
      <div className="stat-top"><span className="stat-icon"><Icon size={17} /></span><span className="stat-label">{label}</span></div>
      <div className="stat-value">{value}<small>{unit}</small></div>
      <div className="stat-note">{note}</div>
    </article>
  );
}

function SourceLink({ href, children }) {
  return <a className="source-link" href={href} target="_blank" rel="noreferrer">{children}<ExternalLink size={12} /></a>;
}

function EmptyChart({ text }) {
  return <div className="empty-chart"><Activity size={24} /><p>{text}</p></div>;
}

export default function App() {
  const [horizonHours, setHorizonHours] = useState(24);
  const [payload, setPayload] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [showAllIntervals, setShowAllIntervals] = useState(false);

  const refresh = async () => {
    setStatus('loading');
    setError('');
    try {
      const result = await getAnalysis({ month: '2026-01', horizonHours });
      setPayload(result);
      setSelectedDate((old) => old && result.daily.some((day) => day.date === old) ? old : (result.daily[0]?.date || ''));
      setStatus('success');
    } catch (err) {
      setError(err.message || 'Unable to load Elexon data.');
      setStatus('error');
    }
  };

  useEffect(() => { refresh(); }, [horizonHours]);

  const selectedIntervals = useMemo(() => {
    if (!payload) return [];
    return payload.intervals.filter((row) => row.date === selectedDate);
  }, [payload, selectedDate]);

  const intervalRows = useMemo(() => {
    const rows = [...selectedIntervals].sort((a, b) => a.time.localeCompare(b.time));
    return showAllIntervals ? rows : rows.slice(0, 12);
  }, [selectedIntervals, showAllIntervals]);

  const latestPublish = useMemo(() => {
    if (!selectedIntervals.length) return null;
    return selectedIntervals.reduce((latest, row) => !latest || row.publish_time > latest ? row.publish_time : latest, null);
  }, [selectedIntervals]);

  const metrics = payload?.metrics;
  const coverage = payload?.coverage;
  const daily = payload?.daily || [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Wind size={20} /></div><div><strong>WindSignal</strong><span>FORECAST INTELLIGENCE</span></div></div>
        <div className="nav-caption">WORKSPACE</div>
        <button className="nav-item active"><Activity size={17} /><span>Forecast monitor</span><span className="nav-dot" /></button>
        <button className="nav-item" onClick={() => document.getElementById('accuracy-panel')?.scrollIntoView({ behavior: 'smooth' })}><Gauge size={17} /><span>Accuracy analysis</span></button>
        <button className="nav-item" onClick={() => document.getElementById('interval-panel')?.scrollIntoView({ behavior: 'smooth' })}><Database size={17} /><span>Interval data</span></button>
        <div className="sidebar-spacer" />
        <div className="sidebar-status"><span className="status-pulse" /><div><strong>Data source</strong><span>Elexon Insights API</span></div><CheckCircle2 size={15} /></div>
        <div className="sidebar-footer">PILOT BUILD <span>v1.0.0</span></div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">ENERGY TRADING <span>/</span> FORECAST INTELLIGENCE</div>
          <div className="topbar-right"><span className="live-indicator"><i /> Hourly analysis</span><div className="avatar">UK</div></div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> NATIONAL WIND / GREAT BRITAIN</div>
            <h1>Wind forecast <em>monitor</em></h1>
            <p className="page-description">Evaluating hourly WINDFOR forecasts against aggregated FUELHH actual generation (arithmetic mean MW per hour).</p>
          </div>
          <div className="heading-actions"><div className="date-chip"><CalendarDays size={15} /><span>01 — 31 JAN 2026</span></div><button className="refresh-button" onClick={refresh} disabled={status === 'loading'}><RefreshCw size={15} className={status === 'loading' ? 'spinning' : ''} /> Refresh data</button></div>
        </section>

        <section className="control-strip">
          <div className="control-title"><div className="control-icon"><Clock3 size={16} /></div><div><strong>Forecast decision horizon</strong><span>Only forecasts published at least this long before each target hour are eligible.</span></div></div>
          <div className="horizon-control" role="group" aria-label="Forecast lead time">
            {HORIZONS.map((h) => (
              <button
                key={h.hours}
                onClick={() => !h.disabled && setHorizonHours(h.hours)}
                className={`${horizonHours === h.hours ? 'selected' : ''} ${h.disabled ? 'disabled' : ''}`}
                disabled={h.disabled}
                title={h.title || `${h.hours}h lead time`}
              >
                {h.label}
              </button>
            ))}
          </div>
          <div className="assumption"><ShieldCheck size={14} /> Explicit lead-time assumption</div>
        </section>

        {status === 'error' && <section className="error-banner"><AlertCircle size={20} /><div><strong>Data could not be loaded</strong><p>{error}</p><span>No placeholder metrics are being shown. Check API availability and retry.</span></div><button onClick={refresh}>Retry</button></section>}

        {status === 'loading' && !payload && <section className="loading-panel"><div className="loader" /><strong>Connecting to Elexon Insights</strong><span>Loading wind generation actuals and forecast publication history…</span></section>}

        <section className="section-heading"><div><h2>Forecast performance ({horizonHours}h horizon)</h2><p>Hourly actuals are the mean MW of both half-hour settlement periods. Error energy uses 1.0h duration per interval.</p></div><span className={`data-state ${status === 'success' ? 'connected' : status === 'error' ? 'failed' : ''}`}><i />{status === 'success' ? 'API data loaded' : status === 'error' ? 'API unavailable' : 'Fetching data'}</span></section>

        <section className="stats-grid">
          <StatCard icon={Zap} label="Mean absolute error" value={fmt(metrics?.mae_mw, 0)} unit="MW" note="Average hourly absolute error" />
          <StatCard icon={Activity} label="Root mean square error" value={fmt(metrics?.rmse_mw, 0)} unit="MW" note="Penalises large hourly misses" />
          <StatCard icon={metrics?.bias_mw < 0 ? ArrowDownRight : ArrowUpRight} label="Forecast bias" value={signed(metrics?.bias_mw, 0)} unit="MW" note="Mean MW error (forecast − actual)" tone={metrics?.bias_mw < 0 ? 'warning' : 'teal'} />
          <StatCard icon={Gauge} label="Weighted absolute error" value={fmt(metrics?.wape_pct, 1)} unit="%" note="Σ |error| / Σ actual generation" />
        </section>

        <section className="coverage-strip">
          <div className="coverage-copy"><Database size={16} /><span><strong>Evaluation coverage ({horizonHours}h horizon)</strong><small>{fmt(coverage?.matched_hours ?? coverage?.matched_intervals)} matched of {fmt(coverage?.expected_hours ?? coverage?.expected_intervals)} expected hours ({fmt(coverage?.complete_actual_hours ?? coverage?.actual_hours)} complete)</small></span></div>
          <div className="coverage-meter"><div style={{ width: `${Math.min(100, (coverage?.matched_hours ?? coverage?.matched_intervals) / Math.max(1, coverage?.expected_hours ?? coverage?.expected_intervals) * 100 || 0)}%` }} /></div>
          <div className="coverage-percent">{fmt((coverage?.matched_hours ?? coverage?.matched_intervals) / Math.max(1, coverage?.expected_hours ?? coverage?.expected_intervals) * 100, 1)}<small>%</small></div>
          <div className="coverage-divider" />
          <div className="coverage-stat"><span>Complete actuals</span><strong>{fmt(coverage?.complete_actual_hours ?? coverage?.actual_hours)}</strong></div>
          <div className="coverage-stat"><span>Unmatched hours</span><strong>{fmt(coverage?.hours_without_eligible_forecast ?? coverage?.actual_intervals_without_eligible_forecast)}</strong></div>
          <div className="coverage-stat"><span>Energy error</span><strong>{signed(metrics?.forecast_minus_actual_mwh, 0)} <small style={{ fontSize: '9px', color: '#8898aa' }}>MWh</small></strong></div>
        </section>

        <section className="chart-grid" id="accuracy-panel">
          <article className="panel main-chart-panel">
            <div className="panel-heading"><div><div className="panel-kicker">01 / GENERATION PROFILE</div><h3>Actual vs forecast</h3><p>Daily average generation, MW (hourly actual mean vs hourly forecast)</p></div><div className="chart-legend"><span><i className="legend-actual" /> Actual (MW)</span><span><i className="legend-forecast" /> Forecast (MW)</span></div></div>
            <div className="chart-body">{daily.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={daily} margin={{ top: 12, right: 14, bottom: 0, left: 0 }}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#243246" /><XAxis dataKey="date" tickFormatter={compactDate} tick={{ fill: '#8291a7', fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={18} /><YAxis tick={{ fill: '#8291a7', fontSize: 11 }} tickLine={false} axisLine={false} width={56} tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`} /><Tooltip contentStyle={{ background: '#101b2b', border: '1px solid #29374b', borderRadius: 9, color: '#e8eef7' }} labelFormatter={compactDate} formatter={(value, name) => [`${fmt(value, 0)} MW`, name === 'actual_avg_mw' ? 'Actual (mean)' : 'Forecast']} /><Line type="monotone" dataKey="actual_avg_mw" name="actual_avg_mw" stroke="#36d7c1" strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} connectNulls /><Line type="monotone" dataKey="forecast_avg_mw" name="forecast_avg_mw" stroke="#8da9ff" strokeWidth={2} strokeDasharray="5 5" dot={false} activeDot={{ r: 4 }} connectNulls /></LineChart></ResponsiveContainer> : <EmptyChart text="No matched data available for the selected horizon." />}</div>
            <div className="panel-footnote"><span><span className="footnote-bullet" /> Source: Elexon FUELHH + WINDFOR</span><span>UTC · Jan 2026 · Hourly evaluation</span></div>
          </article>
          <article className="panel error-chart-panel">
            <div className="panel-heading"><div><div className="panel-kicker">02 / ERROR PROFILE</div><h3>Daily forecast error</h3><p>Mean absolute error by day, MW</p></div><div className="mini-badge">MAE</div></div>
            <div className="chart-body">{daily.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={daily} margin={{ top: 12, right: 8, bottom: 0, left: -14 }}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#243246" /><XAxis dataKey="date" tickFormatter={compactDate} tick={{ fill: '#8291a7', fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={20} /><YAxis tick={{ fill: '#8291a7', fontSize: 10 }} tickLine={false} axisLine={false} width={48} /><Tooltip contentStyle={{ background: '#101b2b', border: '1px solid #29374b', borderRadius: 9, color: '#e8eef7' }} labelFormatter={compactDate} formatter={(value) => [`${fmt(value, 0)} MW`, 'Daily MAE']} /><ReferenceLine y={metrics?.mae_mw || 0} stroke="#f5a85d" strokeDasharray="4 4" /><Bar dataKey="mae_mw" fill="#f5a85d" radius={[3, 3, 0, 0]} maxBarSize={13} /></BarChart></ResponsiveContainer> : <EmptyChart text="Error profile appears when actual and forecast records are matched." />}</div>
            <div className="panel-footnote"><span><span className="footnote-bullet orange" /> Dashed line = full-period MAE ({fmt(metrics?.mae_mw, 0)} MW)</span><span>MW</span></div>
          </article>
        </section>

        <section className="lower-grid">
          <article className="panel date-panel">
            <div className="panel-heading"><div><div className="panel-kicker">03 / DELIVERY HOURS</div><h3>Hourly inspection</h3><p>Inspect aggregated actuals, forecasts, and publication times.</p></div><label className="date-select-label"><span>Delivery date</span><strong>{selectedDate ? compactDate(selectedDate) : '—'}</strong><ChevronDown size={13} /><select value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} aria-label="Select delivery date">{daily.map((day) => <option key={day.date} value={day.date}>{compactDate(day.date)}</option>)}</select></label></div>
            <div className="interval-summary"><div><span>Hours matched</span><strong>{fmt(selectedIntervals.length)}</strong></div><div><span>Daily mean absolute error</span><strong>{fmt(daily.find((d) => d.date === selectedDate)?.mae_mw, 0)} <small>MW</small></strong></div><div><span>Latest selected forecast</span><strong className="latest-time">{latestPublish ? timeLabel(latestPublish) : '—'}</strong></div></div>
            <div className="table-wrap" id="interval-panel"><table><thead><tr><th>Target hour (UTC)</th><th>Actual MW (mean)</th><th>Forecast MW</th><th>Error MW</th><th>Published (UTC)</th></tr></thead><tbody>{intervalRows.map((row) => <tr key={row.time}><td className="time-cell">{new Date(row.time).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' })}</td><td>{fmt(row.actual_mw)}</td><td>{fmt(row.forecast_mw)}</td><td><span className={`error-value ${row.error_mw < 0 ? 'negative' : row.error_mw > 0 ? 'positive' : ''}`}>{signed(row.error_mw)}</span></td><td className="publish-cell">{new Date(row.publish_time).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false })}</td></tr>)}</tbody></table>{selectedIntervals.length === 0 && <EmptyChart text="No matched hours for this delivery date." />}</div>
            {selectedIntervals.length > 12 && <button className="table-more" onClick={() => setShowAllIntervals((value) => !value)}>{showAllIntervals ? 'Show fewer hours' : `Show all ${selectedIntervals.length} hours`}<ChevronDown size={14} className={showAllIntervals ? 'rotate-up' : ''} /></button>}
          </article>
          <aside className="panel insight-panel">
            <div className="panel-kicker">04 / DECISION CONTEXT</div><h3>How to read this view</h3>
            <div className="insight-item"><div className="insight-icon teal"><Wind size={16} /></div><div><strong>Hourly aggregation</strong><p>Elexon WINDFOR forecasts are published on an hourly cadence, while FUELHH actuals are half-hourly. Actuals are aggregated to arithmetic hourly means ((P1 + P2) / 2) to evaluate against forecasts fairly without fabricating data.</p></div></div>
            <div className="insight-item"><div className="insight-icon blue"><Gauge size={16} /></div><div><strong>Measure uncertainty</strong><p>MAE gives average MW miss; RMSE penalises larger misses; bias indicates over/underforecasting. Net energy error reflects 1.0 hour duration per interval (MW x 1h = MWh).</p></div></div>
            <div className="insight-item"><div className="insight-icon amber"><AlertCircle size={16} /></div><div><strong>Dataset scope limitation</strong><p>FUELHH captures transmission-metered outturn; WINDFOR represents National Grid ESO transmission wind forecast models. Variations in embedded/unmetered wind inclusion between sources may contribute to baseline offsets.</p></div></div>
            <div className="insight-callout"><ShieldCheck size={16} /><span>Decision support only. This pilot compares wind output; it does not calculate net demand, procurement volume, or market prices.</span></div>
          </aside>
        </section>

        <section className="methodology-panel">
          <div><div className="panel-kicker">METHODOLOGY & DATA LINEAGE</div><h3>Transparent by design</h3><p>The challenge limits scope to national wind actuals (FUELHH) and forecasts (WINDFOR) published by Elexon. Values are joined by hourly target <code>startTime</code> with lead-time cutoff enforcement.</p></div>
          <div className="method-sources"><div><Database size={16} /><span><strong>Actual generation</strong><small>FUELHH stream (fuelType WIND, aggregated to hourly mean MW)</small><SourceLink href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream">FUELHH stream</SourceLink></span></div><div><CloudDownload size={16} /><span><strong>Forecast generation</strong><small>WINDFOR stream (1-hour target resolution)</small><SourceLink href="https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream">WINDFOR stream</SourceLink></span></div></div>
          <div className="method-foot"><span>Selected lead time: <strong>{horizonHours} hours</strong></span><span>All timestamps normalised to UTC</span><span>AI-assisted development disclosed in README</span></div>
        </section>

        <footer className="footer"><span>WindSignal <span className="footer-separator">·</span> Full Stack SWE pilot challenge</span><span>Data source: Elexon Insights <ExternalLink size={12} /></span></footer>
      </main>
    </div>
  );
}
