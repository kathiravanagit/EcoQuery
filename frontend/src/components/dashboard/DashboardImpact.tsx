import React from 'react';
import { motion } from 'framer-motion';
import { Leaf } from 'lucide-react';

interface Props {
  co2Saved: number;
}

const CO2_EQUIVALENTS = {
  trees: (g: number) => (g / 21.77).toFixed(1),
  driving: (g: number) => (g / 0.21).toFixed(0),
  ledHours: (g: number) => (g / 0.01).toFixed(0),
  phones: (g: number) => (g / 8.0).toFixed(1),
};

const DashboardImpact = React.memo(({ co2Saved }: Props) => {
  if (!co2Saved) return null;

  const equivalents = [
    { icon: <span style={{ fontSize: '1.5rem' }}>🌳</span>, value: CO2_EQUIVALENTS.trees(co2Saved), unit: 'trees absorbed CO₂', color: 'var(--color-success)' },
    { icon: <span style={{ fontSize: '1.5rem' }}>🚗</span>, value: CO2_EQUIVALENTS.driving(co2Saved), unit: 'km driving saved', color: '#3b82f6' },
    { icon: <span style={{ fontSize: '1.5rem' }}>💡</span>, value: CO2_EQUIVALENTS.ledHours(co2Saved), unit: 'hours LED bulb', color: 'var(--color-warning)' },
    { icon: <span style={{ fontSize: '1.5rem' }}>📱</span>, value: CO2_EQUIVALENTS.phones(co2Saved), unit: 'phone charges', color: '#8b5cf6' },
  ];

  return (
    <div className="dashboard-section">
      <h2><Leaf size={20} /> Your Impact in Real Terms</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        {equivalents.map((eq, i) => (
          <motion.div key={i} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.1 }}
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '12px', padding: '16px', textAlign: 'center' }}>
            <div>{eq.icon}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: eq.color, marginTop: '4px' }}>{eq.value}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{eq.unit}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
});

export default DashboardImpact;
