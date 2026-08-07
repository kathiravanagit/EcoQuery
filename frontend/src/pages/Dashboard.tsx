import React, { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { motion } from 'framer-motion';
import { Award, Leaf, ArrowRight } from 'lucide-react';
import { Skeleton, PageSkeleton } from '../components/Skeleton';
import ApiKeyManager from '../components/ApiKeyManager';
import ErrorBoundary from '../components/ErrorBoundary';
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
  latest_queries?: { query?: string; model_used?: string; region?: string; co2_saved_vs_baseline?: number; tier?: string; latency_seconds?: number; verification_status?: string; api_cost?: number }[];
  green_query_percent?: number;
  avg_latency_s?: number; flagged_queries?: number;
  queries_by_tier?: Record<string, number>; queries_by_model?: Record<string, number>;
}
interface Model { id: string; provider: string; tier: string; carbon_score: number; description: string; }
interface Cert { display_name?: string; user?: string; total_queries?: number; total_co2_saved_g?: number; green_query_percent?: number; }
interface Badge { id: string; name: string; description: string; icon: string; earned_at: string; }
interface AnalyticsPoint { date: string; count: number; co2_saved: number; avg_latency: number; }
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
  const [loadedQueries, setLoadedQueries] = useState<{ query?: string; model_used?: string; region?: string; co2_saved_vs_baseline?: number; tier?: string; latency_seconds?: number; verification_status?: string; api_cost?: number }[]>([]);
  const [badges, setBadges] = useState<Badge[]>([]);
  const [carbonAlert, setCarbonAlert] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    try {
      const [s, m, c, a, b] = await Promise.all([
        fetch(`${API}/api/user/stats`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/models`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/user/certificate`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/analytics?days=${analyticsPeriod === 'day' ? 7 : analyticsPeriod === 'week' ? 30 : 90}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/user/badges`, { headers }).then(r => r.ok ? r.json() : null),
      ]);
      setStats(s); setModels(m?.models || []);
      setCert(c); setAnalytics(a?.queries_by_day || []); setBadges(b?.badges || []);
    } catch (e) { console.error('Failed to fetch dashboard data', e); }
    finally { setLoading(false); }
  }, [analyticsPeriod, token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    const t = token;
    if (!t) return;
    let ws: WebSocket;
    let retryDelay = 1000;
    let retryTimer: ReturnType<typeof setTimeout>;
    let unmounted = false;

    const connect = () => {
      if (unmounted) return;
      const wsUrl = API.replace(/^http/, 'ws') + '/ws?token=' + t;
      ws = new WebSocket(wsUrl);
      ws.onopen = () => { setWsStatus('connected'); retryDelay = 1000; };
      ws.onclose = () => {
        setWsStatus('disconnected');
        if (!unmounted) {
          retryTimer = setTimeout(() => { retryDelay = Math.min(retryDelay * 2, 30000); connect(); }, retryDelay);
        }
      };
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
    };

    connect();
    return () => { unmounted = true; clearTimeout(retryTimer); ws?.close(); };
  }, [token]);

  const downloadBadge = (data: Cert) => {
    const c = document.createElement('canvas');
    c.width = 800; c.height = 600;
    const ctx = c.getContext('2d');
    if (!ctx) return;

    const w = 800, h = 600;

    // Cream background
    ctx.fillStyle = '#fdfcf8';
    ctx.fillRect(0, 0, w, h);

    // Outer border
    ctx.strokeStyle = '#1a3a2a';
    ctx.lineWidth = 3;
    ctx.strokeRect(20, 20, w - 40, h - 40);

    // Inner border
    ctx.strokeStyle = '#1a3a2a';
    ctx.lineWidth = 1;
    ctx.strokeRect(30, 30, w - 60, h - 60);

    // Decorative corner flourishes
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 1.5;
    const drawFlourish = (x: number, y: number, flipX: boolean, flipY: boolean) => {
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(flipX ? -1 : 1, flipY ? -1 : 1);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.bezierCurveTo(15, 0, 25, 10, 25, 25);
      ctx.moveTo(0, 0);
      ctx.bezierCurveTo(0, 15, 10, 25, 25, 25);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(12, 12, 3, 0, Math.PI * 2);
      ctx.fillStyle = '#b8860b';
      ctx.fill();
      ctx.restore();
    };
    drawFlourish(40, 40, false, false);
    drawFlourish(w - 40, 40, true, false);
    drawFlourish(40, h - 40, false, true);
    drawFlourish(w - 40, h - 40, true, true);

    // Gold accent line
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 100, 55);
    ctx.lineTo(w / 2 + 100, 55);
    ctx.stroke();

    // Header
    ctx.fillStyle = '#1a3a2a';
    ctx.font = '13px Georgia, serif';
    ctx.textAlign = 'center';
    ctx.fillText('CERTIFICATE OF IMPACT', w / 2, 80);

    // Gold line under header
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 100, 90);
    ctx.lineTo(w / 2 + 100, 90);
    ctx.stroke();

    // Title
    ctx.fillStyle = '#1a3a2a';
    ctx.font = 'bold 48px Georgia, serif';
    ctx.fillText('EcoQuery', w / 2, 145);

    // Subtitle
    ctx.fillStyle = '#555555';
    ctx.font = 'italic 14px Georgia, serif';
    ctx.fillText('Carbon-Aware AI Routing Platform', w / 2, 170);

    // Presented to
    ctx.fillStyle = '#777777';
    ctx.font = '12px Georgia, serif';
    ctx.fillText('This certificate is presented to', w / 2, 215);

    // Name
    ctx.fillStyle = '#1a3a2a';
    ctx.font = 'bold 32px Georgia, serif';
    ctx.fillText(data.display_name || data.user || '', w / 2, 255);

    // Email
    ctx.fillStyle = '#888888';
    ctx.font = '12px Georgia, serif';
    ctx.fillText(data.user || '', w / 2, 278);

    // Divider
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 120, 300);
    ctx.lineTo(w / 2 + 120, 300);
    ctx.stroke();

    // In recognition text
    ctx.fillStyle = '#555555';
    ctx.font = 'italic 12px Georgia, serif';
    ctx.fillText('in recognition of meaningful contributions toward sustainable AI usage', w / 2, 325);

    // Stats row
    const statsY = 375;
    const stats = [
      { value: `${data.total_queries ?? 0}`, label: 'Total Queries', x: w / 2 - 180 },
      { value: `${data.total_co2_saved_g ?? 0}g`, label: 'CO2 Saved', x: w / 2 },
      { value: `${data.green_query_percent ?? 0}%`, label: 'Green Queries', x: w / 2 + 180 },
    ];

    // Stats background
    ctx.fillStyle = '#f5f3ee';
    ctx.beginPath();
    ctx.roundRect(w / 2 - 240, statsY - 30, 480, 70, 6);
    ctx.fill();
    ctx.strokeStyle = '#d4c9a8';
    ctx.lineWidth = 1;
    ctx.stroke();

    stats.forEach(s => {
      ctx.fillStyle = '#1a3a2a';
      ctx.font = 'bold 24px Georgia, serif';
      ctx.fillText(s.value, s.x, statsY + 5);
      ctx.fillStyle = '#888888';
      ctx.font = '10px Georgia, serif';
      ctx.fillText(s.label.toUpperCase(), s.x, statsY + 25);
    });

    // Bottom divider
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 100, 470);
    ctx.lineTo(w / 2 + 100, 470);
    ctx.stroke();

    // Seal circle
    ctx.beginPath();
    ctx.arc(w / 2, 510, 25, 0, Math.PI * 2);
    ctx.fillStyle = '#f5f3ee';
    ctx.fill();
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Seal inner
    ctx.beginPath();
    ctx.arc(w / 2, 510, 18, 0, Math.PI * 2);
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Seal text
    ctx.fillStyle = '#1a3a2a';
    ctx.font = 'bold 8px Georgia, serif';
    ctx.fillText('VERIFIED', w / 2, 508);
    ctx.font = '7px Georgia, serif';
    ctx.fillText('ECOQUERY', w / 2, 518);

    // Date
    ctx.fillStyle = '#888888';
    ctx.font = '11px Georgia, serif';
    ctx.fillText(new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }), w / 2 - 180, 560);

    // Signature line
    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(w / 2 + 80, 555);
    ctx.lineTo(w / 2 + 220, 555);
    ctx.stroke();
    ctx.fillStyle = '#555555';
    ctx.font = '10px Georgia, serif';
    ctx.fillText('EcoQuery Team', w / 2 + 150, 570);

    // Bottom gold line
    ctx.strokeStyle = '#b8860b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(w / 2 - 100, h - 30);
    ctx.lineTo(w / 2 + 100, h - 30);
    ctx.stroke();

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

            <ErrorBoundary>
              <Suspense fallback={<StatsSkeleton />}>
                <DashboardStats stats={stats} cert={cert} />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary>
              <Suspense fallback={<ListSkeleton />}>
                <DashboardBadges badges={badges} />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary>
              <Suspense fallback={<ChartSkeleton />}>
                <DashboardImpact co2Saved={stats?.total_co2_saved_g || 0} />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary>
              <Suspense fallback={<ListSkeleton />}>
                <DashboardRealtime events={realtimeEvents} />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary>
              <Suspense fallback={<ChartSkeleton />}>
                <DashboardAnalytics analytics={analytics} analyticsPeriod={analyticsPeriod} setAnalyticsPeriod={setAnalyticsPeriod} tierData={tierData} />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary>
              <ApiKeyManager token={token} API={API} />
            </ErrorBoundary>
            <ErrorBoundary>
              <DashboardExport token={token} />
            </ErrorBoundary>

            {cert && cert.total_queries != null && cert.total_queries !== 0 && (
              <div className="dashboard-section">
                <h2><Award size={20} /> Certificate of Impact</h2>
                <div className="dashboard-badge-wrap">
                  <div className="dashboard-badge" id="ecoquery-badge" style={{ background: '#fdfcf8', color: '#1a3a2a', border: '2px solid #1a3a2a', padding: '2rem', fontFamily: 'Georgia, serif', maxWidth: '400px', margin: '0 auto' }}>
                    <div style={{ borderBottom: '1px solid #b8860b', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
                      <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: '#777', textTransform: 'uppercase' }}>Certificate of Impact</div>
                    </div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#1a3a2a', fontFamily: 'Georgia, serif' }}>EcoQuery</div>
                    <div style={{ fontSize: '0.75rem', color: '#888', fontStyle: 'italic', marginBottom: '1rem' }}>Carbon-Aware AI Routing Platform</div>
                    <div style={{ fontSize: '0.7rem', color: '#777', marginBottom: '0.25rem' }}>This certificate is presented to</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: '#1a3a2a', fontFamily: 'Georgia, serif' }}>{cert.display_name || cert.user}</div>
                    <div style={{ fontSize: '0.7rem', color: '#888', marginBottom: '1rem' }}>{cert.user}</div>
                    <div style={{ borderTop: '1px solid #d4c9a8', borderBottom: '1px solid #d4c9a8', padding: '0.75rem 0', margin: '0.5rem 0', background: '#f5f3ee', borderRadius: '4px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-around' }}>
                        <div style={{ textAlign: 'center' }}><div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#1a3a2a' }}>{cert.total_queries}</div><div style={{ fontSize: '0.55rem', color: '#888', letterSpacing: '1px' }}>QUERIES</div></div>
                        <div style={{ textAlign: 'center' }}><div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#1a3a2a' }}>{cert.total_co2_saved_g}g</div><div style={{ fontSize: '0.55rem', color: '#888', letterSpacing: '1px' }}>CO2 SAVED</div></div>
                        <div style={{ textAlign: 'center' }}><div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#1a3a2a' }}>{cert.green_query_percent}%</div><div style={{ fontSize: '0.55rem', color: '#888', letterSpacing: '1px' }}>GREEN</div></div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: '1rem' }}>
                      <div style={{ fontSize: '0.65rem', color: '#888' }}>{new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</div>
                      <div style={{ textAlign: 'right' }}><div style={{ borderBottom: '1px solid #333', width: '120px', marginBottom: '2px' }}></div><div style={{ fontSize: '0.6rem', color: '#555' }}>EcoQuery Team</div></div>
                    </div>
                  </div>
                  <button className="btn btn-primary" onClick={() => downloadBadge(cert)} style={{ marginTop: '1rem' }}>
                    <Award size={16} /> Download Certificate
                  </button>
                </div>
              </div>
            )}

            <ErrorBoundary>
              <DashboardCatalog models={models} />
            </ErrorBoundary>
            <ErrorBoundary>
              <DashboardQueries stats={stats} loadedQueries={loadedQueries} setLoadedQueries={setLoadedQueries} token={token} />
            </ErrorBoundary>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
