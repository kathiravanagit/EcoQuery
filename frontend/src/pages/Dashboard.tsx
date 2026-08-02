import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { motion } from 'framer-motion';
import { Award, Leaf, ArrowRight } from 'lucide-react';
import { PageSkeleton } from '../components/Skeleton';
import ApiKeyManager from '../components/ApiKeyManager';
import { useAuth } from '../context/AuthContext';
import { API_URL as API } from '../config';
import './Pages.css';

const DashboardStats = React.lazy(() => import('../components/dashboard/DashboardStats'));
const DashboardImpact = React.lazy(() => import('../components/dashboard/DashboardImpact'));
const DashboardRealtime = React.lazy(() => import('../components/dashboard/DashboardRealtime'));
const DashboardAnalytics = React.lazy(() => import('../components/dashboard/DashboardAnalytics'));
const DashboardBadges = React.lazy(() => import('../components/dashboard/DashboardBadges'));
const DashboardCatalog = React.lazy(() => import('../components/dashboard/DashboardCatalog'));
const DashboardQueries = React.lazy(() => import('../components/dashboard/DashboardQueries'));
const DashboardExport = React.lazy(() => import('../components/dashboard/DashboardExport'));

interface Stats {
  total_queries?: number; total_co2_saved_g?: number; total_api_cost?: number;
  latest_queries?: any[]; green_query_percent?: number;
  avg_latency_s?: number; flagged_queries?: number;
  queries_by_tier?: Record<string, number>; queries_by_model?: Record<string, any>;
}
interface Model { id: string; provider: string; tier: string; carbon_score: number; description: string; }
interface Cert { display_name?: string; user?: string; total_queries?: number; total_co2_saved_g?: number; green_query_percent?: number; }
interface Badge { id: string; name: string; description: string; icon: string; earned_at: string; }

const Dashboard = () => {
  const { token } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [cert, setCert] = useState<Cert | null>(null);
  const [analytics, setAnalytics] = useState<any[]>([]);
  const [analyticsPeriod, setAnalyticsPeriod] = useState('day');
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [realtimeEvents, setRealtimeEvents] = useState<any[]>([]);
  const [loadedQueries, setLoadedQueries] = useState<any[]>([]);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [carbonAlert, setCarbonAlert] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    try {
      const [s, m, c, a, b] = await Promise.all([
        fetch(`${API}/api/user/stats`, { headers }).then(r => r.json()),
        fetch(`${API}/api/models`, { headers }).then(r => r.json()),
        fetch(`${API}/api/user/certificate`, { headers }).then(r => r.json()),
        fetch(`${API}/api/analytics?days=${analyticsPeriod === 'day' ? 7 : analyticsPeriod === 'week' ? 30 : 90}`, { headers }).then(r => r.json()),
        fetch(`${API}/api/user/badges`, { headers }).then(r => r.json()),
      ]);
      setStats(s); setModels(m.models || []);
      setCert(c); setAnalytics(a.queries_by_day || []); setBadges(b.badges || []);
    } catch (e) { console.error('Failed to fetch dashboard data', e); }
  }, [analyticsPeriod, token]);

  useEffect(() => {
    (async () => {
      try {
        const [s, m, c, a, b] = await Promise.all([
          fetch(`${API}/api/user/stats`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
          fetch(`${API}/api/models`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
          fetch(`${API}/api/user/certificate`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
          fetch(`${API}/api/analytics?days=7`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
          fetch(`${API}/api/user/badges`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
        ]);
        setStats(s); setModels(m.models || []);
        setCert(c); setAnalytics(a.queries_by_day || []); setBadges(b.badges || []);
      } catch (e) { console.error('Failed initial fetch', e); }
      finally { setLoading(false); }
    })();
  }, [token]);

  useEffect(() => { if (!loading) fetchAll(); }, [fetchAll, loading]);

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
        } else if (msg.event === 'carbon.alert') {
          setCarbonAlert(msg.data.message);
        }
      } catch {}
    };
    wsRef.current = ws;
    return () => ws.close();
  }, [token]);

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

  if (loading) return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: 600, margin: '0 auto', padding: '4rem 1rem' }}>
          <PageSkeleton />
          <p style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '1rem' }}>
            Waking up the server... Give it a moment.
          </p>
        </div>
      </section>
    </div>
  );

  const tierData = stats?.queries_by_tier ? Object.entries(stats.queries_by_tier).map(([name, value]) => ({ name, value })) : [];

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

            {carbonAlert && (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: '12px', padding: '1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ flex: 1, color: '#ef4444', fontSize: '0.9rem' }}>{carbonAlert}</span>
                <button onClick={() => setCarbonAlert(null)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '1.2rem' }}>×</button>
              </div>
            )}

            {stats && stats.total_queries === 0 && (
              <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
                style={{ background: 'var(--bg-card)', border: '1px solid var(--accent)', borderRadius: '12px', padding: '1.25rem', marginBottom: '1.5rem', textAlign: 'center' }}>
                <p style={{ margin: '0 0 0.75rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  No queries yet. Send your first one from the <a href="/#demo" style={{ color: 'var(--accent)' }}>Live Demo</a> below.
                </p>
                <a href="/#demo" className="btn btn-primary" style={{ fontSize: '0.85rem' }}>Try Live Demo <ArrowRight size={16} /></a>
              </motion.div>
            )}

            <Suspense fallback={<div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</div>}>
              <DashboardStats stats={stats} cert={cert} />
              <DashboardBadges badges={badges} />
              <DashboardImpact co2Saved={stats?.total_co2_saved_g || 0} />
              <DashboardRealtime events={realtimeEvents} />
              <DashboardAnalytics analytics={analytics} analyticsPeriod={analyticsPeriod} setAnalyticsPeriod={setAnalyticsPeriod} tierData={tierData} />
              <ApiKeyManager token={token} API={API} />
              <DashboardExport token={token} />
            </Suspense>

            {cert && (
              <div className="dashboard-section">
                <h2><Award size={20} /> EcoQuery Appreciation Badge</h2>
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
              </div>
            )}

            <DashboardCatalog models={models} />
            <DashboardQueries stats={stats} loadedQueries={loadedQueries} setLoadedQueries={setLoadedQueries} token={token} />
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
