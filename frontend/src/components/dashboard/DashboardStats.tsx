import React from 'react';
import { BarChart3, Leaf, DollarSign, Server, Clock, Shield } from 'lucide-react';

interface Props {
  stats: any;
  cert: any;
}

const DashboardStats = React.memo(({ stats, cert }: Props) => {
  return (
    <div className="dashboard-cards">
      <div className="dashboard-card">
        <BarChart3 size={24} style={{ color: 'var(--accent)' }} />
        <div className="dashboard-card-value">{stats?.total_queries || 0}</div>
        <div className="dashboard-card-label">Total Queries</div>
      </div>
      <div className="dashboard-card">
        <Leaf size={24} style={{ color: 'var(--accent)' }} />
        <div className="dashboard-card-value">{stats?.total_co2_saved_g || 0}g</div>
        <div className="dashboard-card-label">CO₂ Saved</div>
      </div>
      <div className="dashboard-card">
        <DollarSign size={24} style={{ color: 'var(--accent)' }} />
        <div className="dashboard-card-value">${(stats?.total_api_cost || 0).toFixed(4)}</div>
        <div className="dashboard-card-label">Total API Cost</div>
      </div>
      <div className="dashboard-card">
        <Server size={24} style={{ color: 'var(--accent)' }} />
        <div className="dashboard-card-value">{cert?.green_query_percent || 0}%</div>
        <div className="dashboard-card-label">Green Queries</div>
      </div>
      <div className="dashboard-card">
        <Clock size={24} style={{ color: 'var(--color-warning)' }} />
        <div className="dashboard-card-value">{stats?.avg_latency_s || 0}s</div>
        <div className="dashboard-card-label">Avg Latency</div>
      </div>
      <div className="dashboard-card">
        <Shield size={24} style={{ color: stats?.flagged_queries ? 'var(--color-error)' : 'var(--color-success)' }} />
        <div className="dashboard-card-value">{stats?.flagged_queries || 0}</div>
        <div className="dashboard-card-label">Flagged Queries</div>
      </div>
    </div>
  );
});

export default DashboardStats;
