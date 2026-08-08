import React, { useState, useEffect, useRef, useCallback } from 'react';
import { BarChart3, Search, ArrowRight, Filter } from 'lucide-react';
import { API_URL as API } from '../../config';

interface QueryRecord {
  query?: string;
  model_used?: string;
  region?: string;
  co2_saved_vs_baseline?: number;
  tier?: string;
  latency_seconds?: number;
  verification_status?: string;
  api_cost?: number;
  timestamp?: string;
}

interface Props {
  token: string | null;
}

const SORT_OPTIONS = [
  { value: 'timestamp', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'co2', label: 'CO₂ Saved' },
  { value: 'cost', label: 'Cost' },
  { value: 'latency', label: 'Latency' },
];

const TIER_OPTIONS = ['green', 'balanced', 'performance', ''];

const DashboardQueries = ({ token }: Props) => {
  const [queries, setQueries] = useState<QueryRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('timestamp');
  const [tier, setTier] = useState('');
  const [model, setModel] = useState('');
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const limit = 10;

  const headers = { Authorization: `Bearer ${token}` };

  const fetchQueries = useCallback(async (reset: boolean = false) => {
    if (!token) return;
    setLoading(true);
    const offset = reset ? 0 : skip;
    const params = new URLSearchParams({ limit: String(limit), skip: String(offset), sort });
    if (search) params.set('q', search);
    if (tier) params.set('tier', tier);
    if (model) params.set('model', model);
    try {
      const r = await fetch(`${API}/api/audit?${params}`, { headers });
      const d = await r.json();
      if (reset) {
        setQueries(d.records || []);
        setSkip(0);
      } else {
        setQueries(prev => [...prev, ...(d.records || [])]);
      }
      setTotal(d.total || 0);
    } catch (e) {
      console.error('Failed to fetch queries', e);
    } finally {
      setLoading(false);
    }
  }, [token, search, sort, tier, model, skip]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchQueries(true);
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search, sort, tier, model]);

  const loadMore = () => {
    const nextSkip = skip + limit;
    setSkip(nextSkip);
    fetchQueries(false);
  };

  return (
    <div className="dashboard-section">
      <h2><BarChart3 size={20} /> Query History</h2>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        <div className="input-group" style={{ flex: 1, minWidth: 200 }}>
          <Search size={18} />
          <input
            placeholder="Search queries..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search queries"
          />
        </div>
        <div className="input-group" style={{ minWidth: 120 }}>
          <Filter size={18} />
          <select value={tier} onChange={e => setTier(e.target.value)} aria-label="Filter by tier">
            <option value="">All tiers</option>
            {TIER_OPTIONS.filter(Boolean).map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="input-group" style={{ minWidth: 120 }}>
          <select value={sort} onChange={e => setSort(e.target.value)} aria-label="Sort queries">
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>
      {queries.length ? (
        <div className="dashboard-query-list">
          {queries.map((q, i) => (
            <div key={i} className="dashboard-query-item">
              <div className="dashboard-query-query">{q.query?.substring(0, 100)}{q.query && q.query.length > 100 ? '...' : ''}</div>
              <div className="dashboard-query-meta">
                <span className="meta-tag">{q.model_used}</span>
                <span className="meta-tag">{q.region}</span>
                <span className="meta-tag savings">+{q.co2_saved_vs_baseline}g CO₂</span>
                <span className="meta-tag">{q.tier}</span>
                {q.latency_seconds ? <span className="meta-tag">{q.latency_seconds}s</span> : null}
                {q.verification_status && (
                  <span className="meta-tag" style={{
                    borderColor: q.verification_status === 'flagged_substitution' ? 'var(--color-error)' : 'var(--color-success)',
                    color: q.verification_status === 'flagged_substitution' ? 'var(--color-error)' : 'var(--color-success)',
                  }}>
                    {q.verification_status === 'flagged_substitution' ? 'flagged' : 'verified'}
                  </span>
                )}
                {q.api_cost ? <span className="meta-tag">${q.api_cost.toFixed(6)}</span> : null}
              </div>
            </div>
          ))}
          {queries.length < total && (
            <button className="btn btn-secondary" onClick={loadMore} disabled={loading} style={{ marginTop: '0.75rem', width: '100%' }}>
              {loading ? 'Loading...' : `Load More (${queries.length}/${total})`}
            </button>
          )}
        </div>
      ) : (
        <p className="dashboard-hint">{search ? 'No matching queries found.' : 'No queries yet. Try the Live Demo!'}</p>
      )}
    </div>
  );
};

export default DashboardQueries;
