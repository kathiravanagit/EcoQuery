import React from 'react';
import { Zap } from 'lucide-react';

interface RealtimeEvent {
  query: string;
  tier: string;
  model: string;
  region: string;
  co2_g: number;
  co2_saved_g: number;
  api_cost: number;
  time: string;
}

interface Props {
  events: RealtimeEvent[];
}

const DashboardRealtime = React.memo(({ events }: Props) => {
  return (
    <div className="dashboard-section">
      <h2><Zap size={20} /> Real-time Query Events</h2>
      {events.length === 0 ? (
        <p className="dashboard-hint">Waiting for queries... Send one from the Live Demo!</p>
      ) : (
        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
          {events.map((e, i) => (
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
  );
});

export default DashboardRealtime;
