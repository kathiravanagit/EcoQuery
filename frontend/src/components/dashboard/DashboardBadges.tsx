import React from 'react';
import { Trophy } from 'lucide-react';
import { motion } from 'framer-motion';

interface Props {
  badges: any[];
}

const DashboardBadges = ({ badges }: Props) => {
  if (!badges.length) return null;

  return (
    <div className="dashboard-section">
      <h2><Trophy size={20} /> Your Badges ({badges.length})</h2>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
        {badges.map((b) => (
          <motion.div key={b.id} initial={{ scale: 0 }} animate={{ scale: 1 }} style={{
            background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '12px',
            padding: '12px 16px', minWidth: 140, textAlign: 'center',
          }}>
            <div style={{ fontSize: '2rem' }}>{b.icon}</div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{b.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{b.description}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export default DashboardBadges;
