import React, { useState } from 'react';
import { BarChart3, Search, ArrowRight } from 'lucide-react';
import { API_URL as API } from '../../config';

interface Props {
  stats: any;
  loadedQueries: any[];
  setLoadedQueries: (q: any[]) => void;
  token: string | null;
}

const DashboardQueries = ({ stats, loadedQueries, setLoadedQueries, token }: Props) => {
  const [querySearch, setQuerySearch] = useState('');
  const [querySkip, setQuerySkip] = useState(0);

  const headers = { Authorization: `Bearer ${token}` };

  const loadMore = async () => {
    const newSkip = querySkip + 10;
    try {
      const r = await fetch(`${API}/api/audit?skip=${newSkip}&limit=10`, { headers });
      const d = await r.json();
      setLoadedQueries([...loadedQueries, ...(d.records || [])]);
      setQuerySkip(newSkip);
    } catch (e) { console.error('Failed to load more queries', e); }
  };

  const all = [...(stats?.latest_queries || []), ...loadedQueries];
  const filtered = querySearch ? all.filter(q =>
    q.query?.toLowerCase().includes(querySearch.toLowerCase()) ||
    q.model_used?.toLowerCase().includes(querySearch.toLowerCase()) ||
    q.region?.toLowerCase().includes(querySearch.toLowerCase())
  ) : all;

  return (
    <div className="dashboard-section">
      <h2><BarChart3 size={20} /> Recent Queries</h2>
      <div className="input-group" style={{ marginBottom: '1rem', maxWidth: 400 }}>
        <Search size={18} />
        <input placeholder="Search queries..." value={querySearch} onChange={e => setQuerySearch(e.target.value)} aria-label="Search queries" />
      </div>
      {filtered.length ? (
        <div className="dashboard-query-list">
          {filtered.map((q, i) => (
            <div key={i} className="dashboard-query-item">
              <div className="dashboard-query-query">{q.query?.substring(0, 80)}{q.query?.length > 80 ? '...' : ''}</div>
              <div className="dashboard-query-meta">
                <span className="meta-tag">{q.model_used}</span>
                <span className="meta-tag">{q.region}</span>
                <span className="meta-tag savings">+{q.co2_saved_vs_baseline}g CO₂</span>
                <span className="meta-tag">{q.tier}</span>
                {q.latency_seconds ? <span className="meta-tag">{q.latency_seconds}s</span> : null}
                {q.verification_status && (
                  <span className="meta-tag" style={{ borderColor: q.verification_status === 'flagged_substitution' ? 'var(--color-error)' : 'var(--color-success)', color: q.verification_status === 'flagged_substitution' ? 'var(--color-error)' : 'var(--color-success)' }}>
                    {q.verification_status === 'flagged_substitution' ? '⚠️' : '🛡️'}
                  </span>
                )}
                {q.api_cost ? <span className="meta-tag">${q.api_cost.toFixed(6)}</span> : null}
              </div>
            </div>
          ))}
          <button className="btn btn-secondary" onClick={loadMore} style={{ marginTop: '0.75rem', width: '100%' }}>
            Load More
          </button>
        </div>
      ) : (
        <p className="dashboard-hint">{querySearch ? 'No matching queries found.' : 'No queries yet. Try the Live Demo!'}</p>
      )}
    </div>
  );
};

export default DashboardQueries;
