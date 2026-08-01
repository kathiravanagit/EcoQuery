import React from 'react';
import { TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

interface Props {
  analytics: any[];
  analyticsPeriod: string;
  setAnalyticsPeriod: (p: string) => void;
  tierData: any[];
}

const PIE_COLORS = ['#00d46a', '#f59e0b', '#ef4444'];

const DashboardAnalytics = ({ analytics, analyticsPeriod, setAnalyticsPeriod, tierData }: Props) => {
  return (
    <div className="dashboard-section">
      <h2><TrendingUp size={20} /> Usage Analytics</h2>
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        {['day', 'week', 'month'].map(p => (
          <button key={p} className={`btn ${analyticsPeriod === p ? 'btn-primary' : 'btn-secondary'}`} style={{ padding: '0.3rem 0.75rem', fontSize: '0.85rem' }} onClick={() => setAnalyticsPeriod(p)}>
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 280, height: 250 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={analytics}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis dataKey="date" stroke="var(--text-secondary)" fontSize={12} />
              <YAxis stroke="var(--text-secondary)" fontSize={12} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '8px' }} />
              <Line type="monotone" dataKey="count" stroke="#00d46a" strokeWidth={2} dot={false} name="Queries" />
              <Line type="monotone" dataKey="co2_saved" stroke="#f59e0b" strokeWidth={2} dot={false} name="CO₂ Saved (g)" />
              <Line type="monotone" dataKey="avg_latency" stroke="#3b82f6" strokeWidth={2} dot={false} name="Avg Latency (s)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
        {tierData.length > 0 && (
          <div style={{ width: 200, height: 250 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={tierData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }: any) => `${name || ''} ${((percent || 0) * 100).toFixed(0)}%`}>
                  {tierData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardAnalytics;
