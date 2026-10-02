import React, { useEffect, useState } from 'react';
import { Key, ShieldCheck, Trash2, Check } from 'lucide-react';
import {
  BYOK_MAX_KEY_LENGTH,
  BYOK_PROVIDERS,
  ByokProvider,
  byokHeaders,
  clearByok,
  isByokProvider,
  loadByok,
  saveByok,
} from '../byok';
import './ProviderKeyManager.css';

const PROVIDER_LABELS: Record<ByokProvider, string> = {
  openrouter: 'OpenRouter',
  google: 'Google',
  grok: 'Grok (xAI)',
};

/**
 * Lets a user supply their own provider key for chat requests.
 *
 * The key is written to sessionStorage only and travels as an `X-Provider-Key`
 * header; it is never sent to EcoQuery for storage and is never rendered back
 * out after saving.
 */
const ProviderKeyManager: React.FC = () => {
  const [provider, setProvider] = useState<ByokProvider>('openrouter');
  const [draft, setDraft] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const existing = loadByok();
    if (existing) {
      setHasKey(true);
      setProvider(existing.provider);
    }
    // Only the provider is read back — never the key itself.
  }, []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSaved(false);

    if (!draft.trim()) {
      setError('Enter a provider key, or remove the saved one.');
      return;
    }
    if (draft.trim().length > BYOK_MAX_KEY_LENGTH) {
      // The server silently ignores anything longer, which would look like
      // "BYOK is on" while every request still used EcoQuery's own keys.
      setError(`Keys longer than ${BYOK_MAX_KEY_LENGTH} characters are rejected by the provider.`);
      return;
    }

    if (saveByok({ provider, key: draft })) {
      setHasKey(true);
      setDraft('');
      setSaved(true);
    } else {
      setError('Could not save that key for this tab.');
    }
  };

  const remove = () => {
    clearByok();
    setHasKey(false);
    setDraft('');
    setSaved(false);
    setError('');
  };

  const headerSample = byokHeaders()['X-Provider'];

  return (
    <div className="byok-card">
      <h3><Key size={18} /> Provider Key (Bring Your Own)</h3>

      <form onSubmit={submit}>
        <div className="byok-row">
          <div className="byok-field byok-field--provider">
            <label htmlFor="byok-provider">Provider</label>
            <select
              id="byok-provider"
              value={provider}
              onChange={(e) => {
                const next = e.target.value;
                setProvider(isByokProvider(next) ? next : 'openrouter');
                setSaved(false);
              }}
            >
              {BYOK_PROVIDERS.map((id) => (
                <option key={id} value={id}>{PROVIDER_LABELS[id]}</option>
              ))}
            </select>
          </div>

          <div className="byok-field">
            <label htmlFor="byok-key">API key</label>
            <input
              id="byok-key"
              type="password"
              value={draft}
              onChange={(e) => { setDraft(e.target.value); setError(''); setSaved(false); }}
              placeholder={hasKey ? 'A key is saved for this tab' : 'sk-...'}
              autoComplete="off"
              spellCheck={false}
              aria-describedby="byok-hint"
            />
          </div>
        </div>

        {error && <div className="byok-error" role="alert">{error}</div>}

        <div className="byok-actions">
          <button type="submit" className="btn btn-primary" aria-label="Save provider key">
            <Check size={14} /> Save for this tab
          </button>
          {hasKey && (
            <button type="button" className="btn btn-secondary" onClick={remove} aria-label="Remove provider key">
              <Trash2 size={14} /> Remove
            </button>
          )}
        </div>
      </form>

      <div className={`byok-status ${hasKey ? '' : 'byok-status--empty'}`}>
        <ShieldCheck size={14} />
        {saved
          ? 'Saved for this tab — it will be sent with your next request.'
          : hasKey
            ? `Active — requests will send your ${PROVIDER_LABELS[headerSample as ByokProvider] ?? 'saved'} key.`
            : 'No key saved — requests use EcoQuery\'s own keys.'}
      </div>

      <p className="byok-hint" id="byok-hint">
        Sent only as the <code>X-Provider</code> / <code>X-Provider-Key</code> request headers. EcoQuery
        never stores or logs it, and it is dropped when this tab closes. If a request fails on your key,
        it falls back to EcoQuery's own key automatically.
      </p>
    </div>
  );
};

export default ProviderKeyManager;
