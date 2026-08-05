import React from 'react';
import { TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface Props {
  analytics: any[];
  analyticsPeriod: string;
  setAnalyticsPeriod: (p: string) => void;
  tierData: any[];
}

const PIE_COLORS = ['#16a34a', '#ca8a04', '#dc2626', '#2563eb'];
const PIE_LABELS: Record<string, string> = { green: 'Green', balanced: 'Balanced', performance: 'Performance' };

const CustomTooltip = ({ active, payload, label, period }: any) => {
  if (!active || !payload?.length) return null;
  let displayLabel = label;
  if (period === 'day' && label) {
    const d = new Date(label + 'T00:00:00');
    displayLabel = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  } else if (period === 'week' && label) {
    const parts = label.split('-');
    displayLabel = parts[1] ? `Week ${parts[1].replace('W', '')}` : label;
  } else if (period === 'month' && label) {
    const parts = label.split('-');
    displayLabel = parts.length >= 2 ? new Date(parseInt(parts[0]), parseInt(parts[1]) - 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }) : label;
  }
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '0.75rem 1rem', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.5rem', fontWeight: 500 }}>{displayLabel}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ fontSize: '0.8rem', color: '#374151', display: 'flex', justifyContent: 'space-between', gap: '1.5rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color, display: 'inline-block' }} />
            {p.name}
          </span>
          <span style={{ fontWeight: 600 }}>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

const DashboardAnalytics = ({ analytics, analyticsPeriod, setAnalyticsPeriod, tierData }: Props) => {
  // Only show dates that have actual data (no empty gaps)
  const chartData = analytics.filter(d => d.count > 0);
  const totalQueries = chartData.reduce((s, d) => s + (d.count || 0), 0);
  const totalCo2 = chartData.reduce((s, d) => s + (d.co2_saved || 0), 0);
  const avgLatency = chartData.length ? (chartData.reduce((s, d) => s + (d.avg_latency || 0), 0) / chartData.length).toFixed(1) : '0';

  const formatXAxis = (val: string) => {
    if (!val) return '';
    if (analyticsPeriod === 'day') {
      const d = new Date(val + 'T00:00:00');
      return d.toLocaleDateString('en-US', { weekday: 'short' });
    }
    if (analyticsPeriod === 'week') {
      const parts = val.split('-');
      return parts[1] ? `W${parts[1].replace('W', '')}` : val;
    }
    const parts = val.split('-');
    return parts.length >= 2 ? new Date(parseInt(parts[0]), parseInt(parts[1]) - 1).toLocaleDateString('en-US', { month: 'short' }) : val;
  };

  return (
    <div className="dashboard-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2 style={{ margin: 0 }}><TrendingUp size={20} /> Usage Analytics</h2>
        <div style={{ display: 'flex', gap: '0.25rem', background: 'var(--bg-secondary)', borderRadius: '8px', padding: '3px', border: '1px solid var(--border-color)' }}>
          {['day', 'week', 'month'].map(p => (
            <button key={p} onClick={() => setAnalyticsPeriod(p)} style={{ padding: '0.35rem 0.85rem', fontSize: '0.8rem', borderRadius: '6px', border: 'none', cursor: 'pointer', fontWeight: analyticsPeriod === p ? 600 : 400, background: analyticsPeriod === p ? 'var(--accent)' : 'transparent', color: analyticsPeriod === p ? '#0a0a0a' : 'var(--text-secondary)', transition: 'all 0.15s' }}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
        {[
          { label: 'Total Queries', value: totalQueries, color: 'var(--accent)' },
          { label: 'CO2 Saved', value: `${totalCo2.toFixed(2)}g`, color: '#16a34a' },
          { label: 'Avg Latency', value: `${avgLatency}s`, color: '#3b82f6' },
        ].map(s => (
          <div key={s.label} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.75rem 1rem' }}>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '0.25rem' }}>{s.label}</div>
            <div style={{ fontSize: '1.3rem', fontWeight: 700, color: s.color, fontFamily: 'var(--font-mono)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 300, background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.75rem' }}>Query Volume & CO2 Over Time</div>
          {chartData.length === 0 ? (
            <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No data for this period</div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} tickFormatter={formatXAxis} />
                <YAxis stroke="var(--text-secondary)" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip period={analyticsPeriod} />} />
                <Line type="monotone" dataKey="count" stroke="#16a34a" strokeWidth={2} dot={{ r: 3, fill: '#16a34a' }} activeDot={{ r: 5 }} name="Queries" />
                <Line type="monotone" dataKey="co2_saved" stroke="#ca8a04" strokeWidth={2} dot={{ r: 3, fill: '#ca8a04' }} activeDot={{ r: 5 }} name="CO2 Saved (g)" />
              </LineChart>
            </ResponsiveContainer>
          )}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1.5rem', marginTop: '0.5rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#16a34a', display: 'inline-block' }} />Queries</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ca8a04', display: 'inline-block' }} />CO2 Saved</span>
          </div>
        </div>

        {tierData.length > 0 && (
          <div style={{ width: 220, background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Query Distribution</div>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={tierData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value" stroke="none">
                  {tierData.map((entry, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(value: any, name: any) => [`${value} queries`, PIE_LABELS[name] || name]} contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', marginTop: '0.25rem' }}>
              {tierData.map((d, i) => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)' }}>
                    <span style={{ width: 8, height: 8, borderRadius: '2px', background: PIE_COLORS[i % PIE_COLORS.length], display: 'inline-block' }} />
                    {PIE_LABELS[d.name] || d.name}
                  </span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardAnalytics;
