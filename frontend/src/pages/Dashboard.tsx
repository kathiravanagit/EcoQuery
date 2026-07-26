import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Key, Award, Leaf, Server, BarChart3, Copy, Check, TrendingUp, DollarSign, Download, Zap, Search } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { useAuth } from '../context/AuthContext';
import { API_URL as API } from '../config';
import './Pages.css';

interface Stats {
  total_queries?: number; total_co2_saved_g?: number; total_api_cost?: number;
  latest_queries?: any[]; green_query_percent?: number;
}
interface Model { id: string; provider: string; tier: string; carbon_score: number; description: string; }
interface Cert { display_name?: string; user?: string; total_queries?: number; total_co2_saved_g?: number; green_query_percent?: number; }
interface AnalyticsData { data?: any[]; period?: string; }
interface QueryRecord { query?: string; model_used?: string; region?: string; co2_saved_vs_baseline?: number; tier?: string; api_cost?: number; }

const Dashboard = () => {
  const { token } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [apiKey, setApiKey] = useState('');
  const [cert, setCert] = useState<Cert | null>(null);
  const [analytics, setAnalytics] = useState<any[]>([]);
  const [analyticsPeriod, setAnalyticsPeriod] = useState('day');
  const [copied, setCopied] = useState('');
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [realtimeEvents, setRealtimeEvents] = useState<any[]>([]);
  const [querySearch, setQuerySearch] = useState('');
  const [loadedQueries, setLoadedQueries] = useState<QueryRecord[]>([]);
  const [querySkip, setQuerySkip] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    try {
      const [s, m, k, c, a] = await Promise.all([
        fetch(`${API}/api/user/stats`, { headers }).then(r => r.json()),
        fetch(`${API}/api/models`, { headers }).then(r => r.json()),
        fetch(`${API}/api/user/api-key`, { headers }).then(r => r.json()),
        fetch(`${API}/api/user/certificate`, { headers }).then(r => r.json()),
        fetch(`${API}/api/user/analytics?period=${analyticsPeriod}`, { headers }).then(r => r.json()),
      ]);
      setStats(s); setModels(m.models || []); setApiKey(k.api_key || '');
      setCert(c); setAnalytics(a.data || []);
    } catch (e) { console.error('Failed to fetch dashboard data', e); }
  }, [analyticsPeriod]);

  useEffect(() => {
    (async () => {
      try {
        const [s, m, k, c, a] = await Promise.all([
          fetch(`${API}/api/user/stats`, { headers }).then(r => r.json()),
          fetch(`${API}/api/models`, { headers }).then(r => r.json()),
          fetch(`${API}/api/user/api-key`, { headers }).then(r => r.json()),
          fetch(`${API}/api/user/certificate`, { headers }).then(r => r.json()),
          fetch(`${API}/api/user/analytics?period=day`, { headers }).then(r => r.json()),
        ]);
        setStats(s); setModels(m.models || []); setApiKey(k.api_key || '');
        setCert(c); setAnalytics(a.data || []);
      } catch (e) { console.error('Failed initial fetch', e); }
      finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => { if (!loading) fetchAll(); }, [analyticsPeriod]);

  useEffect(() => {
    const t = token;
    if (!t) return;
    const wsUrl = API.replace(/^http/, 'ws') + '/ws?token=' + t;
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => { setWsStatus('connected'); };
    ws.onclose = () => { setWsStatus('disconnected'); };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event === 'query.routed') {
          setRealtimeEvents(prev => [{ ...msg.data, time: new Date().toLocaleTimeString() }, ...prev].slice(0, 20));
        }
      } catch {}
    };
    wsRef.current = ws;
    return () => ws.close();
  }, [token]);

  const generateKey = async () => {
    try {
      const r = await fetch(`${API}/api/user/api-key`, { method: 'POST', headers });
      const d = await r.json(); setApiKey(d.api_key);
    } catch (e) { console.error('Failed to generate key', e); }
  };

  const downloadBadge = (data: any) => {
    const c = document.createElement('canvas');
    c.width = 500; c.height = 620;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    const accent = '#00d46a'; const dark = '#0a0a1a'; const card = '#111128'; const text = '#e0e0e0';
    ctx.fillStyle = dark; ctx.fillRect(0, 0, 500, 620);
    ctx.shadowColor = 'rgba(0,212,106,0.3)'; ctx.shadowBlur = 30;
    ctx.fillStyle = card;
    if (typeof ctx.roundRect === 'function') {
      ctx.beginPath(); ctx.roundRect(25, 25, 450, 570, 24); ctx.fill();
    } else {
      ctx.fillRect(25, 25, 450, 570);
    }
    ctx.shadowBlur = 0;
    ctx.fillStyle = accent; ctx.font = 'bold 48px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('EcoQuery', 250, 115); ctx.font = '22px sans-serif'; ctx.fillStyle = text;
    ctx.fillText('Celebrates You!', 250, 155);
    ctx.strokeStyle = accent; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(100, 185); ctx.lineTo(400, 185); ctx.stroke();
    ctx.font = 'bold 36px sans-serif'; ctx.fillStyle = '#ffffff';
    ctx.fillText(data.display_name || data.user, 250, 250); ctx.font = '18px sans-serif'; ctx.fillStyle = text;
    ctx.fillText(data.user, 250, 285); ctx.fillStyle = '#ffffff'; ctx.font = 'bold 32px sans-serif';
    ctx.fillText(`${data.total_queries}`, 250, 355); ctx.font = '16px sans-serif'; ctx.fillStyle = accent;
    ctx.fillText('Queries Routed', 250, 385); ctx.fillStyle = '#ffffff'; ctx.font = 'bold 32px sans-serif';
    ctx.fillText(`${data.total_co2_saved_g}g`, 250, 445); ctx.font = '16px sans-serif'; ctx.fillStyle = accent;
    ctx.fillText('CO₂ Saved', 250, 475); ctx.fillStyle = '#ffffff'; ctx.font = 'bold 32px sans-serif';
    ctx.fillText(`${data.green_query_percent}%`, 250, 535); ctx.font = '16px sans-serif'; ctx.fillStyle = accent;
    ctx.fillText('Green Queries', 250, 565); ctx.font = '14px sans-serif'; ctx.fillStyle = '#888';
    ctx.fillText('Every query makes a difference. Thank you!', 250, 610);
    const link = document.createElement('a'); link.download = 'ecoquery-badge.png';
    link.href = c.toDataURL('image/png'); link.click();
  };

  const loadMore = async () => {
    const newSkip = querySkip + 10;
    try {
      const r = await fetch(`${API}/api/audit?skip=${newSkip}&limit=10`, { headers });
      const d = await r.json();
      setLoadedQueries(prev => [...prev, ...(d.records || [])]);
      setQuerySkip(newSkip);
    } catch (e) { console.error('Failed to load more queries', e); }
  };

  const exportQueries = async (format: string) => {
    try {
      const r = await fetch(`${API}/api/user/export?format=${format}`, { headers });
      if (format === 'csv') {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'ecoquery-export.csv'; a.click();
        URL.revokeObjectURL(url);
      } else {
        const d = await r.json();
        const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'ecoquery-export.json'; a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) { console.error('Export failed', e); }
  };

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied(''), 2000);
    } catch { console.error('Clipboard write failed'); }
  };

  if (loading) return <div className="page"><section className="section"><div className="container" style={{ textAlign: 'center', padding: '4rem 0' }}>Loading dashboard...</div></section></div>;

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: 1000 }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="section-title">Your Dashboard</h1>
            <p className="section-subtitle" style={{ textAlign: 'center', marginBottom: '2rem' }}>
              Track carbon savings, costs, analytics, and manage your account.
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', marginLeft: '0.5rem', fontSize: '0.8rem', color: wsStatus === 'connected' ? 'var(--accent)' : '#ef4444' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: wsStatus === 'connected' ? 'var(--accent)' : '#ef4444', display: 'inline-block' }}></span>
                {wsStatus === 'connected' ? 'Live' : 'Offline'}
              </span>
            </p>

            <div className="dashboard-cards">
              <div className="dashboard-card" aria-label={`Total queries: ${stats?.total_queries || 0}`}>
                <BarChart3 size={24} style={{ color: 'var(--accent)' }} />
                <div className="dashboard-card-value">{stats?.total_queries || 0}</div>
                <div className="dashboard-card-label">Total Queries</div>
              </div>
              <div className="dashboard-card" aria-label={`CO2 saved: ${stats?.total_co2_saved_g || 0} grams`}>
                <Leaf size={24} style={{ color: 'var(--accent)' }} />
                <div className="dashboard-card-value">{stats?.total_co2_saved_g || 0}g</div>
                <div className="dashboard-card-label">CO₂ Saved</div>
              </div>
              <div className="dashboard-card" aria-label={`Total API cost: $${(stats?.total_api_cost || 0).toFixed(4)}`}>
                <DollarSign size={24} style={{ color: 'var(--accent)' }} />
                <div className="dashboard-card-value">${(stats?.total_api_cost || 0).toFixed(4)}</div>
                <div className="dashboard-card-label">Total API Cost</div>
              </div>
              <div className="dashboard-card" aria-label={`Green queries: ${cert?.green_query_percent || 0} percent`}>
                <Server size={24} style={{ color: 'var(--accent)' }} />
                <div className="dashboard-card-value">{cert?.green_query_percent || 0}%</div>
                <div className="dashboard-card-label">Green Queries</div>
              </div>
            </div>

            <div className="dashboard-section">
              <h2><Zap size={20} /> Real-time Query Events</h2>
              {realtimeEvents.length === 0 ? (
                <p className="dashboard-hint">Waiting for queries... Send one from the Live Demo!</p>
              ) : (
                <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                  {realtimeEvents.map((e, i) => (
                    <div key={i} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', padding: '0.4rem 0', borderBottom: '1px solid var(--border-color)', fontSize: '0.85rem' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>{e.time}</span>
                      <span className="meta-tag savings">+{e.co2_saved_g}g CO₂</span>
                      <span className="meta-tag">{e.model}</span>
                      <span className="meta-tag">{e.tier}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="dashboard-section">
              <h2><TrendingUp size={20} /> Usage Analytics</h2>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                {['day', 'week', 'month'].map(p => (
                  <button key={p} className={`btn ${analyticsPeriod === p ? 'btn-primary' : 'btn-secondary'}`} style={{ padding: '0.3rem 0.75rem', fontSize: '0.85rem' }} onClick={() => setAnalyticsPeriod(p)}>
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </button>
                ))}
              </div>
              <div style={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analytics}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                    <XAxis dataKey="period" stroke="var(--text-secondary)" fontSize={12} />
                    <YAxis stroke="var(--text-secondary)" fontSize={12} />
                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px' }} />
                    <Line type="monotone" dataKey="queries" stroke="#00d46a" strokeWidth={2} dot={false} name="Queries" />
                    <Line type="monotone" dataKey="co2_saved_g" stroke="#f59e0b" strokeWidth={2} dot={false} name="CO₂ Saved (g)" />
                    <Line type="monotone" dataKey="green" stroke="#3b82f6" strokeWidth={2} dot={false} name="Green Queries" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="dashboard-section">
              <h2><Key size={20} /> API Key & Data Export</h2>
              {apiKey ? (
                <div className="dashboard-api-key">
                  <code>{apiKey}</code>
                  <button className="btn-icon" onClick={() => copyToClipboard(apiKey, 'key')} aria-label="Copy API key">
                    {copied === 'key' ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </div>
              ) : (
                <button className="btn btn-primary" onClick={generateKey}>Generate API Key</button>
              )}
              <p className="dashboard-hint">Use this key to call EcoQuery API from your own apps: <code>Authorization: Bearer {apiKey || '&lt;key&gt;'}</code></p>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                <button className="btn btn-secondary" onClick={() => exportQueries('csv')}><Download size={16} /> Export CSV</button>
                <button className="btn btn-secondary" onClick={() => exportQueries('json')}><Download size={16} /> Export JSON</button>
              </div>
            </div>

            <div className="dashboard-section">
              <h2><Award size={20} /> EcoQuery Appreciation Badge</h2>
              {cert ? (
                <div className="dashboard-badge-wrap">
                  <div className="dashboard-badge" id="ecoquery-badge">
                    <div className="dashboard-badge-icon"><Leaf size={40} /></div>
                    <div className="dashboard-badge-title">EcoQuery</div>
                    <div className="dashboard-badge-sub">Celebrates You!</div>
                    <div className="dashboard-badge-divider"></div>
                    <div className="dashboard-badge-name">{cert.display_name || cert.user}</div>
                    <div className="dashboard-badge-stats">
                      <span>{cert.total_queries} queries</span>
                      <span className="dot">·</span>
                      <span>{cert.total_co2_saved_g}g CO₂ saved</span>
                      <span className="dot">·</span>
                      <span>{cert.green_query_percent}% green</span>
                    </div>
                    <div className="dashboard-badge-footer">Every query makes a difference. Thank you!</div>
                  </div>
                  <button className="btn btn-primary" onClick={() => downloadBadge(cert)} style={{ marginTop: '1rem' }}>
                    <Award size={16} /> Download Badge
                  </button>
                </div>
              ) : (
                <p className="dashboard-hint">No data yet. Send some queries first!</p>
              )}
            </div>

            <div className="dashboard-section">
              <h2><Server size={20} /> Carbon-Aware Model Catalog</h2>
              <div className="dashboard-model-grid">
                {['green', 'balanced', 'performance'].map(tier => (
                  <div key={tier} className="dashboard-model-tier">
                    <h3 style={{ color: tier === 'green' ? '#00d46a' : tier === 'balanced' ? '#f59e0b' : '#ef4444' }}>
                      {tier.charAt(0).toUpperCase() + tier.slice(1)}
                    </h3>
                    {models.filter(m => m.tier === tier).map(m => (
                      <div key={m.id} className="dashboard-model-item">
                        <div className="dashboard-model-name">{m.provider} {m.id}</div>
                        <div className="dashboard-model-score">Score: {m.carbon_score}/10</div>
                        <div className="dashboard-model-desc">{m.description}</div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="dashboard-section">
              <h2><BarChart3 size={20} /> Recent Queries</h2>
              <div className="input-group" style={{ marginBottom: '1rem', maxWidth: 400 }}>
                <Search size={18} />
                <input placeholder="Search queries..." value={querySearch} onChange={e => setQuerySearch(e.target.value)} aria-label="Search queries" />
              </div>
              {(() => {
                const all = [...(stats?.latest_queries || []), ...loadedQueries];
                const filtered = querySearch ? all.filter(q => q.query?.toLowerCase().includes(querySearch.toLowerCase()) || q.model_used?.toLowerCase().includes(querySearch.toLowerCase()) || q.region?.toLowerCase().includes(querySearch.toLowerCase())) : all;
                return filtered.length ? (
                  <div className="dashboard-query-list">
                    {filtered.map((q, i) => (
                      <div key={i} className="dashboard-query-item">
                        <div className="dashboard-query-query">{q.query?.substring(0, 80)}{q.query?.length > 80 ? '...' : ''}</div>
                        <div className="dashboard-query-meta">
                          <span className="meta-tag">{q.model_used}</span>
                          <span className="meta-tag">{q.region}</span>
                          <span className="meta-tag savings">+{q.co2_saved_vs_baseline}g CO₂</span>
                          <span className="meta-tag">{q.tier}</span>
                          {q.api_cost ? <span className="meta-tag">${q.api_cost.toFixed(6)}</span> : null}
                        </div>
                      </div>
                    ))}
                    <button className="btn btn-secondary" onClick={loadMore} style={{ marginTop: '0.75rem', width: '100%' }}>
                      Load More
                    </button>
                  </div>
                ) : (
                  <p className="dashboard-hint">{querySearch ? 'No matching queries found.' : 'No queries yet. Try the Live Demo!'}</p>
                );
              })()}
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
