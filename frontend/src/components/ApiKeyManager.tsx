import React, { useState, useEffect } from 'react';
import { Key, Copy, Check, RotateCcw, Trash2, Loader2, BarChart3, Leaf, DollarSign } from 'lucide-react';
import './ApiKeyManager.css';

interface ApiKeyStats {
  queries?: number;
  co2_saved_g?: number;
  cost?: number;
}

interface Props {
  token: string | null;
  API: string;
}

const ApiKeyManager: React.FC<Props> = ({ token, API }) => {
  const [apiKey, setApiKey] = useState('');
  const [copied, setCopied] = useState('');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [showRevokeConfirm, setShowRevokeConfirm] = useState(false);
  const [stats, setStats] = useState<ApiKeyStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [error, setError] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchKey = async () => {
    try {
      setLoading(true);
      setError('');
      const r = await fetch(`${API}/api/user/api-key`, { headers });
      if (!r.ok) throw new Error();
      const d = await r.json();
      const key = d.api_key || '';
      setApiKey(key);
      if (key) fetchStats();
    } catch {
      setError('Failed to load API key');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      setStatsLoading(true);
      const r = await fetch(`${API}/api/user/api-key/stats`, { headers });
      if (r.ok) {
        const d = await r.json();
        setStats(d);
      }
    } catch {
      // stats optional
    } finally {
      setStatsLoading(false);
    }
  };

  const generateKey = async () => {
    try {
      setGenerating(true);
      setError('');
      const r = await fetch(`${API}/api/user/api-key`, { method: 'POST', headers });
      const d = await r.json();
      setApiKey(d.api_key);
      setShowRevokeConfirm(false);
      fetchStats();
    } catch {
      setError('Failed to generate API key');
    } finally {
      setGenerating(false);
    }
  };

  const revokeKey = async () => {
    try {
      setRevoking(true);
      setError('');
      const r = await fetch(`${API}/api/user/api-key/revoke`, { method: 'POST', headers });
      if (r.ok) {
        setApiKey('');
        setStats(null);
        setShowRevokeConfirm(false);
      }
    } catch {
      setError('Failed to revoke API key');
    } finally {
      setRevoking(false);
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied(''), 2000);
    } catch {
      setError('Failed to copy');
    }
  };

  useEffect(() => { fetchKey(); }, []);

  if (loading) {
    return (
      <div className="api-key-card">
        <h3><Key size={18} /> API Key & Data Export</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          <Loader2 size={16} className="spinner" /> Loading API key...
        </div>
      </div>
    );
  }

  return (
    <div className="api-key-card">
      <h3><Key size={18} /> API Key & Data Export</h3>

      {error && <div className="api-key-error">{error}</div>}

      {apiKey ? (
        <>
          <div className="api-key-display">
            <code>{apiKey}</code>
            <button
              className="btn-icon"
              onClick={() => copyToClipboard(apiKey, 'key')}
              aria-label="Copy API key"
            >
              {copied === 'key' ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>

          <div className="api-key-actions">
            {showRevokeConfirm ? (
              <div className="api-key-confirm">
                <span>Are you sure you want to revoke this key? This cannot be undone.</span>
                <button
                  className="btn btn-primary"
                  style={{ background: '#ef4444', borderColor: '#ef4444' }}
                  onClick={revokeKey}
                  disabled={revoking}
                  aria-label="Confirm revoke API key"
                >
                  {revoking ? <Loader2 size={14} className="spinner" /> : <Trash2 size={14} />} Confirm Revoke
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowRevokeConfirm(false)}
                  aria-label="Cancel revoke"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <>
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowRevokeConfirm(true)}
                  aria-label="Revoke API key"
                >
                  <Trash2 size={14} /> Revoke
                </button>
                <button
                  className="btn btn-primary"
                  onClick={generateKey}
                  disabled={generating}
                  aria-label="Generate new API key"
                >
                  {generating ? <Loader2 size={14} className="spinner" /> : <RotateCcw size={14} />} Generate New
                </button>
              </>
            )}
          </div>

          {statsLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '1rem' }}>
              <Loader2 size={14} className="spinner" /> Loading stats...
            </div>
          ) : stats ? (
            <div className="api-key-stats">
              <div className="api-key-stat" aria-label={`Queries: ${stats.queries || 0}`}>
                <div className="api-key-stat-value"><BarChart3 size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} />{stats.queries || 0}</div>
                <div className="api-key-stat-label">Queries</div>
              </div>
              <div className="api-key-stat" aria-label={`CO₂ saved: ${stats.co2_saved_g || 0}g`}>
                <div className="api-key-stat-value"><Leaf size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} />{stats.co2_saved_g || 0}g</div>
                <div className="api-key-stat-label">CO₂ Saved</div>
              </div>
              <div className="api-key-stat" aria-label={`Cost: $${(stats.cost || 0).toFixed(4)}`}>
                <div className="api-key-stat-value"><DollarSign size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} />${(stats.cost || 0).toFixed(4)}</div>
                <div className="api-key-stat-label">Cost</div>
              </div>
            </div>
          ) : null}
        </>
      ) : (
        <button
          className="btn btn-primary"
          onClick={generateKey}
          disabled={generating}
          aria-label="Generate API key"
        >
          {generating ? <Loader2 size={16} className="spinner" /> : <Key size={16} />} Generate API Key
        </button>
      )}

      <p className="api-key-hint">
        Use this key to call EcoQuery API from your own apps: <code>Authorization: Bearer {apiKey || '&lt;key&gt;'}</code>
      </p>
    </div>
  );
};

export default ApiKeyManager;
