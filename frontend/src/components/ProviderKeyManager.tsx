import React, { useEffect, useState } from 'react';
import { Key, ShieldCheck, Trash2, Check } from 'lucide-react';
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

/**
 * Lets a user supply their own provider keys for chat requests.
 *
 * One row per provider. Each key is written to sessionStorage only and travels
 * as its own `X-<Provider>-Key` header; nothing is sent to EcoQuery for storage
 * and no saved key is ever rendered back out — `active` holds provider names,
 * never values.
 */
const ProviderKeyManager: React.FC = () => {
  const [active, setActive] = useState<ByokProvider[]>([]);
  const [drafts, setDrafts] = useState<Record<ByokProvider, string>>({
    openrouter: '', google: '', grok: '', openai: '', groq: '', anthropic: '',
  });
  const [prefer, setPrefer] = useState(true);
  const [error, setError] = useState('');
  const [justSaved, setJustSaved] = useState<ByokProvider | null>(null);

  useEffect(() => {
    // Provider names only — the key itself is never pulled into component state.
    setActive(Object.keys(loadByokKeys()) as ByokProvider[]);
    setPrefer(preferMyKeys());
  }, []);

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

    if (saveByokKey(provider, value)) {
      setActive((prev) => (prev.includes(provider) ? prev : [...prev, provider]));
      setDrafts((prev) => ({ ...prev, [provider]: '' }));
      setJustSaved(provider);
    } else {
      setError('Could not save that key for this tab.');
    }
  };

  const remove = (provider: ByokProvider) => {
    clearByokKey(provider);
    setActive((prev) => prev.filter((p) => p !== provider));
    setDrafts((prev) => ({ ...prev, [provider]: '' }));
    setJustSaved(null);
    setError('');
  };

  const count = active.length;

  return (
    <div className="byok-card">
      <h3><Key size={18} /> Bring Your Own Keys (Optional)</h3>

      <p className="byok-intro">
        Add your own API keys for OpenRouter, Google AI Studio, Grok, OpenAI, Groq or Anthropic.
        Keys are stored only in
        your browser and are never saved on our servers. When present, your keys are used instead
        of EcoQuery&apos;s keys for that provider.
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
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => remove(provider)}
                  aria-label={`Remove ${PROVIDER_LABELS[provider]} key`}
                >
                  <Trash2 size={14} />
                </button>
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
        Sent only as request headers on each chat call. EcoQuery never stores or logs them, and
        they are dropped when this tab closes. If a request fails on your key, it falls back to
        EcoQuery&apos;s own key automatically.
      </p>
    </div>
  );
};

export default ProviderKeyManager;
