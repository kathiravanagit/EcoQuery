import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { motion } from 'framer-motion';
import { Award, Leaf, ArrowRight } from 'lucide-react';
import { Skeleton, PageSkeleton } from '../components/Skeleton';
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

const StatsSkeleton = () => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
    {[1,2,3].map(i => (
      <div key={i} style={{ padding: '1.25rem', border: '1px solid var(--border-color)', borderRadius: 12 }}>
        <Skeleton height={14} width="40%" />
        <Skeleton height={28} width="60%" style={{ marginTop: 8 }} />
      </div>
    ))}
  </div>
);

const ChartSkeleton = () => (
  <div style={{ padding: '1.5rem', border: '1px solid var(--border-color)', borderRadius: 12, marginBottom: 24 }}>
    <Skeleton height={18} width="30%" />
    <Skeleton height={200} style={{ marginTop: 12 }} />
  </div>
);

const ListSkeleton = () => (
  <div style={{ padding: '1.5rem', border: '1px solid var(--border-color)', borderRadius: 12, marginBottom: 24 }}>
    <Skeleton height={18} width="25%" />
    {[1,2,3].map(i => (
      <div key={i} style={{ display: 'flex', gap: 12, marginTop: 12, alignItems: 'center' }}>
        <Skeleton height={32} width={32} style={{ borderRadius: '50%' }} />
        <div style={{ flex: 1 }}>
          <Skeleton height={14} width="70%" />
          <Skeleton height={12} width="40%" style={{ marginTop: 4 }} />
        </div>
      </div>
    ))}
  </div>
);

interface Stats {
  total_queries?: number; total_co2_saved_g?: number; total_api_cost?: number;
  latest_queries?: Record<string, unknown>[]; green_query_percent?: number;
  avg_latency_s?: number; flagged_queries?: number;
  queries_by_tier?: Record<string, number>; queries_by_model?: Record<string, number>;
}
interface Model { id: string; provider: string; tier: string; carbon_score: number; description: string; }
interface Cert { display_name?: string; user?: string; total_queries?: number; total_co2_saved_g?: number; green_query_percent?: number; }
interface Badge { id: string; name: string; description: string; icon: string; earned_at: string; }
interface AnalyticsPoint { date: string; queries: number; co2_g: number; }
interface RealtimeEvent { query: string; tier: string; model: string; region: string; co2_g: number; co2_saved_g: number; api_cost: number; time: string; }

const Dashboard = () => {
  const { token } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [cert, setCert] = useState<Cert | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsPoint[]>([]);
  const [analyticsPeriod, setAnalyticsPeriod] = useState('day');
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [realtimeEvents, setRealtimeEvents] = useState<RealtimeEvent[]>([]);
  const [loadedQueries, setLoadedQueries] = useState<Record<string, unknown>[]>([]);
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
    finally { setLoading(false); }
  }, [analyticsPeriod, token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

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

  const downloadBadge = (data: Cert) => {
    const c = document.createElement('canvas');
    c.width = 600; c.height = 750;
    const ctx = c.getContext('2d');
    if (!ctx) return;

    const accent = '#00ff41';
    const accentDim = 'rgba(0, 255, 65, 0.15)';
    const dark = '#0a0a0a';
    const card = '#111118';
    const text = '#e0e0e0';
    const muted = '#888888';
    const w = 600, h = 750;

    ctx.fillStyle = dark;
    ctx.fillRect(0, 0, w, h);

    // Outer glow
    ctx.shadowColor = 'rgba(0, 255, 65, 0.2)';
    ctx.shadowBlur = 40;
    ctx.fillStyle = card;
    ctx.beginPath();
    ctx.roundRect(30, 30, w - 60, h - 60, 16);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Inner border
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.2;
    ctx.beginPath();
    ctx.roundRect(42, 42, w - 84, h - 84, 10);
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Corner accents
    const cornerSize = 24;
    const corners = [
      [42, 42], [w - 42 - cornerSize, 42],
      [42, h - 42 - cornerSize], [w - 42 - cornerSize, h - 42 - cornerSize]
    ];
    ctx.strokeStyle = accent;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.35;
    corners.forEach(([x, y], i) => {
      ctx.beginPath();
      if (i === 0) { ctx.moveTo(x, y + cornerSize); ctx.lineTo(x, y); ctx.lineTo(x + cornerSize, y); }
      else if (i === 1) { ctx.moveTo(x, y); ctx.lineTo(x + cornerSize, y); ctx.lineTo(x + cornerSize, y + cornerSize); }
      else if (i === 2) { ctx.moveTo(x, y); ctx.lineTo(x, y + cornerSize); ctx.lineTo(x + cornerSize, y + cornerSize); }
      else { ctx.moveTo(x + cornerSize, y); ctx.lineTo(x + cornerSize, y + cornerSize); ctx.lineTo(x, y + cornerSize); }
      ctx.stroke();
    });
    ctx.globalAlpha = 1;

    // Top accent line
    ctx.fillStyle = accent;
    ctx.fillRect(w / 2 - 60, 30, 120, 3);

    // Leaf icon (simple circle with accent)
    ctx.fillStyle = accentDim;
    ctx.beginPath();
    ctx.arc(w / 2, 110, 30, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = accent;
    ctx.font = '28px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('🍃', w / 2, 120);

    // Title
    ctx.fillStyle = accent;
    ctx.font = 'bold 42px monospace';
    ctx.fillText('EcoQuery', w / 2, 175);

    // Subtitle
    ctx.fillStyle = muted;
    ctx.font = '13px monospace';
    ctx.letterSpacing = '4px';
    ctx.fillText('CERTIFICATE OF IMPACT', w / 2, 200);

    // Divider
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 80, 225);
    ctx.lineTo(w / 2 + 80, 225);
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Name
    ctx.fillStyle = text;
    ctx.font = 'bold 28px monospace';
    ctx.fillText(data.display_name || data.user || '', w / 2, 275);

    // Email
    ctx.fillStyle = muted;
    ctx.font = '14px monospace';
    ctx.fillText(data.user || '', w / 2, 300);

    // Stats section background
    ctx.fillStyle = 'rgba(0, 255, 65, 0.04)';
    ctx.beginPath();
    ctx.roundRect(60, 330, w - 120, 140, 8);
    ctx.fill();

    // Stats
    const stats = [
      { value: `${data.total_queries}`, label: 'QUERIES', x: w / 2 - 150 },
      { value: `${data.total_co2_saved_g}g`, label: 'CO₂ SAVED', x: w / 2 },
      { value: `${data.green_query_percent}%`, label: 'GREEN', x: w / 2 + 150 },
    ];
    stats.forEach(s => {
      ctx.fillStyle = accent;
      ctx.font = 'bold 32px monospace';
      ctx.fillText(s.value, s.x, 385);
      ctx.fillStyle = muted;
      ctx.font = '11px monospace';
      ctx.fillText(s.label, s.x, 415);
    });

    // Divider 2
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 80, 495);
    ctx.lineTo(w / 2 + 80, 495);
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Footer text
    ctx.fillStyle = accent;
    ctx.font = '12px monospace';
    ctx.globalAlpha = 0.6;
    ctx.fillText('Every query makes a difference', w / 2, 530);
    ctx.globalAlpha = 1;

    // Bottom accent line
    ctx.fillStyle = accent;
    ctx.fillRect(w / 2 - 60, h - 33, 120, 3);

    // Date
    ctx.fillStyle = muted;
    ctx.font = '11px monospace';
    ctx.fillText(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }), w / 2, h - 55);

    const link = document.createElement('a');
    link.download = 'ecoquery-certificate.png';
    link.href = c.toDataURL('image/png');
    link.click();
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

            <Suspense fallback={<StatsSkeleton />}>
              <DashboardStats stats={stats} cert={cert} />
            </Suspense>
            <Suspense fallback={<ListSkeleton />}>
              <DashboardBadges badges={badges} />
            </Suspense>
            <Suspense fallback={<ChartSkeleton />}>
              <DashboardImpact co2Saved={stats?.total_co2_saved_g || 0} />
            </Suspense>
            <Suspense fallback={<ListSkeleton />}>
              <DashboardRealtime events={realtimeEvents} />
            </Suspense>
            <Suspense fallback={<ChartSkeleton />}>
              <DashboardAnalytics analytics={analytics} analyticsPeriod={analyticsPeriod} setAnalyticsPeriod={setAnalyticsPeriod} tierData={tierData} />
            </Suspense>
            <ApiKeyManager token={token} API={API} />
            <DashboardExport token={token} />

            {cert && (
              <div className="dashboard-section">
                <h2><Award size={20} /> EcoQuery Appreciation Badge</h2>
                <div className="dashboard-badge-wrap">
                  <div className="dashboard-badge" id="ecoquery-badge">
                    <div className="dashboard-badge-corner tl"></div>
                    <div className="dashboard-badge-corner tr"></div>
                    <div className="dashboard-badge-corner bl"></div>
                    <div className="dashboard-badge-corner br"></div>
                    <div className="dashboard-badge-icon"><Leaf size={36} /></div>
                    <div className="dashboard-badge-title">EcoQuery</div>
                    <div className="dashboard-badge-sub">Certificate of Impact</div>
                    <div className="dashboard-badge-divider"></div>
                    <div className="dashboard-badge-name">{cert.display_name || cert.user}</div>
                    <div className="dashboard-badge-email">{cert.user}</div>
                    <div className="dashboard-badge-stats">
                      <div className="dashboard-badge-stat">
                        <span className="dashboard-badge-stat-value">{cert.total_queries}</span>
                        <span className="dashboard-badge-stat-label">Queries</span>
                      </div>
                      <div className="dashboard-badge-stat">
                        <span className="dashboard-badge-stat-value">{cert.total_co2_saved_g}g</span>
                        <span className="dashboard-badge-stat-label">CO₂ Saved</span>
                      </div>
                      <div className="dashboard-badge-stat">
                        <span className="dashboard-badge-stat-value">{cert.green_query_percent}%</span>
                        <span className="dashboard-badge-stat-label">Green</span>
                      </div>
                    </div>
                    <div className="dashboard-badge-footer">Every query makes a difference</div>
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
