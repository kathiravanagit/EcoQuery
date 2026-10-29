import React, { useState, useEffect } from 'react';
import { Key, Copy, Check, RotateCcw, Trash2, Loader2, BarChart3, Leaf, DollarSign, Eye, EyeOff } from 'lucide-react';
import { apiFailure, describeApiError } from '../apiError';
import Co2Estimate from './Co2Estimate';
import './ApiKeyManager.css';

interface ApiKeyStats {
  queries?: number;
  co2_saved_g?: number;
  cost?: number;
}

interface Props {
  token: string | null;
  API: string;
  /** Relative band (percent) from /api/stats, applied to the CO₂ figure. */
  uncertaintyPct?: number;
}

/**
 * `eq_` plus 48 hex characters is unreadable and too long to hide by eye, so
 * only the prefix stays visible — enough to tell two keys apart, not enough to
 * use one from a screenshot, a shoulder or a screen share.
 */
export const maskKey = (key: string): string =>
  key.length <= 10 ? '*'.repeat(key.length) : `${key.slice(0, 10)}${'*'.repeat(12)}`;

const ApiKeyManager: React.FC<Props> = ({ token, API, uncertaintyPct }) => {
  const [apiKey, setApiKey] = useState('');
  // Hidden on load and hidden again after a copy: the only moment the whole
  // key is on screen is right after it is generated.
  const [revealed, setRevealed] = useState(false);
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
      if (!r.ok) throw await apiFailure(r, 'Failed to load API key');
      const d = await r.json();
      const key = d.api_key || '';
      setApiKey(key);
      setRevealed(false);
      if (key) fetchStats();
    } catch (e) {
      setError(describeApiError(e, 'Failed to load API key'));
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
      if (!r.ok) throw await apiFailure(r, 'Failed to generate API key');
      const d = await r.json();
      setApiKey(d.api_key);
      setRevealed(true);
      setShowRevokeConfirm(false);
      fetchStats();
    } catch (e) {
      setError(describeApiError(e, 'Failed to generate API key'));
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
      } else {
        // Without this the modal stayed open with no explanation.
        setError((await apiFailure(r, 'Failed to revoke API key')).message);
      }
    } catch (e) {
      setError(describeApiError(e, 'Failed to revoke API key'));
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

  useEffect(() => { fetchKey(); }, [token]);

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
            <code>{revealed ? apiKey : maskKey(apiKey)}</code>
            <button
              className="btn-icon"
              onClick={() => setRevealed((shown) => !shown)}
              aria-label={revealed ? 'Hide API key' : 'Show API key'}
            >
              {revealed ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
            <button
              className="btn-icon"
              onClick={() => {
                copyToClipboard(apiKey, 'key');
                setRevealed(false);
              }}
              aria-label="Copy API key"
            >
              {copied === 'key' ? <Check size={16} /> : <Copy size={16} />}
            </button>
          </div>
          {revealed && (
            <p className="api-key-hint">Copy it now — it hides again after you copy.</p>
          )}

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
              <div className="api-key-stat" aria-label={`CO₂ saved: ${stats.co2_saved_g || 0}g, plus or minus ${Math.round(uncertaintyPct || 0)} percent`}>
                <div className="api-key-stat-value"><Leaf size={16} style={{ verticalAlign: 'middle', marginRight: 4 }} /><Co2Estimate value={stats.co2_saved_g || 0} band={{ relative: (uncertaintyPct ?? 0) / 100 }} /></div>
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
        Use this key to call EcoQuery API from your own apps: <code>Authorization: Bearer {revealed ? apiKey : (maskKey(apiKey) || '&lt;key&gt;')}</code>
      </p>
    </div>
  );
};

export default ApiKeyManager;
