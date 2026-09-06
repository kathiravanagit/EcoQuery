import React from 'react';
import { Award, Bolt, Globe2, Leaf, Medal, ShieldCheck, Sprout, Trophy } from 'lucide-react';
import { motion } from 'framer-motion';

interface Badge {
  id: string;
  name: string;
  description: string;
  icon: string;
  earned_at: string;
}

interface Props {
  badges: Badge[];
}

const badgeIcons = {
  first_query: Sprout,
  eco_explorer: Leaf,
  green_champion: Trophy,
  carbon_warrior: Bolt,
  carbon_saver: Globe2,
  eco_hero: Award,
  planet_guardian: ShieldCheck,
  pure_green: Medal,
} as const;

const DashboardBadges = React.memo(({ badges }: Props) => {
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
            <div style={{ color: 'var(--accent)', display: 'flex', justifyContent: 'center', marginBottom: '0.5rem' }}>
              {(() => {
                const Icon = badgeIcons[b.id as keyof typeof badgeIcons] || Medal;
                return <Icon size={28} strokeWidth={1.8} aria-hidden="true" />;
              })()}
            </div>
            <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{b.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{b.description}</div>
          </motion.div>
        ))}
      </div>
    </div>
  );
});

export default DashboardBadges;
