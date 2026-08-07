import React from 'react';
import { Server } from 'lucide-react';

interface Model {
  id: string;
  provider: string;
  tier: string;
  carbon_score: number;
  description: string;
}

interface Props {
  models: Model[];
}

const DashboardCatalog = ({ models }: Props) => {
  return (
    <div className="dashboard-section">
      <h2><Server size={20} /> Carbon-Aware Model Catalog</h2>
      <div className="dashboard-model-grid">
        {['green', 'balanced', 'performance'].map(tier => (
          <div key={tier} className="dashboard-model-tier">
            <h3 style={{ color: tier === 'green' ? 'var(--color-success)' : tier === 'balanced' ? 'var(--color-warning)' : 'var(--color-error)' }}>
              {tier.charAt(0).toUpperCase() + tier.slice(1)}
            </h3>
            {models.filter(m => m.tier === tier).map(m => (
              <div key={m.id} className="dashboard-model-item">
                <div className="dashboard-model-name">{m.provider} {m.id}</div>
                <div className="dashboard-model-score">Score: {m.carbon_score}/10</div>
                <div className="dashboard-model-desc">{m.description}</div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

export default DashboardCatalog;
