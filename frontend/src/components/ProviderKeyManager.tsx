import React, { useEffect, useState } from 'react';
import { Key, ShieldCheck, Trash2, Ban, Check } from 'lucide-react';
import {
  BYOK_MAX_KEY_LENGTH,
  BYOK_PROVIDERS,
  ByokProvider,
  PROVIDER_HEADERS,
  PROVIDER_KEY_HINTS,
  PROVIDER_LABELS,
  clearByokKey,
  loadByokKeys,
  preferMyKeys,
  saveByokKey,
  setPreferMyKeys,
} from '../byok';
import './ProviderKeyManager.css';
import { API_URL as API } from '../config';

interface Props {
  token: string | null;
}

/**
 * Lets a user supply their own provider keys for chat requests.
 *
 * One row per provider. Authenticated users may persist encrypted provider
 * credentials; the browser never receives them back after saving.
 */
const ProviderKeyManager: React.FC<Props> = ({ token }) => {
  const [active, setActive] = useState<ByokProvider[]>([]);
  const [drafts, setDrafts] = useState<Record<ByokProvider, string>>({
    openrouter: '', google: '', grok: '', openai: '', groq: '', anthropic: '',
  });
  const [prefer, setPrefer] = useState(true);
  const [error, setError] = useState('');
  const [justSaved, setJustSaved] = useState<ByokProvider | null>(null);

  useEffect(() => {
    const load = async () => {
      if (token) {
        const response = await fetch(`${API}/api/user/byok`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.ok) {
          const data = await response.json();
          setActive(data.providers as ByokProvider[]);
          return;
        }
      }
      setActive(Object.keys(loadByokKeys()) as ByokProvider[]);
    };
    void load();
    setPrefer(preferMyKeys());
  }, [token]);

  const submit = (e: React.FormEvent, provider: ByokProvider) => {
    e.preventDefault();
    setError('');
    setJustSaved(null);

    const value = drafts[provider].trim();
    if (!value) {
      setError(`Enter a ${PROVIDER_LABELS[provider]} key, or remove the saved one.`);
      return;
    }
    if (value.length > BYOK_MAX_KEY_LENGTH) {
      // The server silently ignores anything longer, which would look like
      // "BYOK is on" while every request still used EcoQuery's own keys.
      setError(`Keys longer than ${BYOK_MAX_KEY_LENGTH} characters are rejected by the provider.`);
      return;
    }

    const persist = async () => {
      if (token) {
        const response = await fetch(`${API}/api/user/byok`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ provider, key: value }),
        });
        if (!response.ok) {
          setError('Could not save that key securely on the server.');
          return;
        }
      } else if (!saveByokKey(provider, value)) {
        setError('Sign in to securely persist keys, or save one for this tab only.');
        return;
      }
      setActive((prev) => (prev.includes(provider) ? prev : [...prev, provider]));
      setDrafts((prev) => ({ ...prev, [provider]: '' }));
      setJustSaved(provider);
    };
    void persist();
  };

  const remove = (provider: ByokProvider) => {
    const deletePersisted = async () => {
      if (token) {
        const response = await fetch(`${API}/api/user/byok/${provider}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          setError('Could not delete the saved key.');
          return;
        }
      } else {
        clearByokKey(provider);
      }
    };

    void deletePersisted();
    setActive((prev) => prev.filter((p) => p !== provider));
    setDrafts((prev) => ({ ...prev, [provider]: '' }));
    setJustSaved(null);
    setError('');
  };

  const revoke = async (provider: ByokProvider) => {
    if (token) {
      const response = await fetch(`${API}/api/user/byok/${provider}/revoke`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setError('Could not revoke the saved key.');
        return;
      }
    } else {
      clearByokKey(provider);
    }
    setActive((prev) => prev.filter((p) => p !== provider));
    setJustSaved(null);
  };

  const count = active.length;

  return (
    <div className="byok-card">
      <h3><Key size={18} /> Bring Your Own Keys (Optional)</h3>

      <p className="byok-intro">
        Add your own API keys for OpenRouter, Google AI Studio, Grok, OpenAI, Groq or Anthropic.
        {token ? 'Keys are encrypted at rest and tied to your account. ' : 'Keys are stored only in your browser for this tab. '}
        When present, your keys are used instead of EcoQuery&apos;s key for that same provider. EcoQuery still
        chooses the model, routing mode, and region.
      </p>

      <div className="byok-rows">
        {BYOK_PROVIDERS.map((provider) => {
          const hasKey = active.includes(provider);
          return (
            <form
              key={provider}
              className="byok-row"
              onSubmit={(e) => submit(e, provider)}
            >
              <div className="byok-provider">
                <span className="byok-provider-name">{PROVIDER_LABELS[provider]}</span>
                <code className="byok-header">{PROVIDER_HEADERS[provider]}</code>
              </div>

              <input
                type="password"
                value={drafts[provider]}
                onChange={(e) => {
                  setDrafts((prev) => ({ ...prev, [provider]: e.target.value }));
                  setError('');
                  setJustSaved(null);
                }}
                placeholder={hasKey ? 'A key is saved for this tab' : PROVIDER_KEY_HINTS[provider]}
                aria-label={`${PROVIDER_LABELS[provider]} API key`}
                autoComplete="off"
                spellCheck={false}
              />

              <button type="submit" className="btn btn-primary" aria-label={`Save ${PROVIDER_LABELS[provider]} key`}>
                {justSaved === provider ? <Check size={14} /> : <Key size={14} />}
                {hasKey ? 'Replace' : 'Save'}
              </button>

              {hasKey && (
                <>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void revoke(provider)}
                    aria-label={`Revoke ${PROVIDER_LABELS[provider]} key`}
                    title="Revoke key"
                  >
                    <Ban size={14} />
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => remove(provider)}
                    aria-label={`Delete ${PROVIDER_LABELS[provider]} key`}
                    title="Delete key permanently"
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </form>
          );
        })}
      </div>

      {error && <div className="byok-error" role="alert">{error}</div>}

      <label className="byok-toggle">
        <input
          type="checkbox"
          checked={prefer}
          onChange={(e) => {
            setPreferMyKeys(e.target.checked);
            setPrefer(e.target.checked);
          }}
        />
        <span>Prefer my keys when available</span>
      </label>

      <div className={`byok-status ${count ? '' : 'byok-status--empty'}`}>
        <ShieldCheck size={14} />
        {!prefer
          ? 'Your keys are saved but not attached — requests use EcoQuery\'s own keys.'
          : count
            ? `Using ${count} of your ${count === 1 ? 'key' : 'keys'} + EcoQuery keys for the rest.`
            : 'No keys saved — requests use EcoQuery\'s own keys.'}
      </div>

      <p className="byok-hint">
        Provider keys are decrypted only for the provider request, never returned to the browser,
        logged, or included in analytics. Your provider key is never used as the EcoQuery
        API authentication token. If a request fails on your key, it falls back to EcoQuery&apos;s
        own key for that provider automatically.
      </p>
    </div>
  );
};

export default ProviderKeyManager;
