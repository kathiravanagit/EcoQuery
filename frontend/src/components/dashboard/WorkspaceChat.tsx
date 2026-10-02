import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Leaf, ChevronDown, ChevronUp, RefreshCw, AlertCircle } from 'lucide-react';
import { API_URL as API } from '../../config';
import './WorkspaceChat.css';
import { EASE_FN } from '../../constants';
import { Metadata, consumeSSE } from '../../sse';
import { ApiFailure, apiFailure, describeApiError, errorCodeMessage } from '../../apiError';
import { byokHeaders } from '../../byok';
import Co2Estimate from '../Co2Estimate';

interface Message {
  role: string
  content: string
  metadata?: Metadata
  error?: boolean
  retryPrompt?: string
}

function formatTier(tier?: string): string {
  if (!tier) return 'Moderate';
  if (tier.toLowerCase() === 'medium') return 'Moderate';
  return tier.charAt(0).toUpperCase() + tier.slice(1).toLowerCase();
}

function EcoDecision({ meta }: { meta: Metadata }) {
  const [expanded, setExpanded] = useState(false);
  const tierName = formatTier(meta.tier);
  const isKnowledge = meta.answer_source === 'ecoquery_knowledge';
  const isCache = meta.answer_source === 'ecoquery_cache';
  const llmRequired = meta.llm_used ? 'Yes' : 'No';
  const route = meta.model_id || meta.model_used;
  const measurementLabel = meta.measurement_type === 'measured' ? 'Measured' : meta.measurement_type === 'provider_reported' ? 'Provider-reported' : 'Estimated';
  
  let reason = 'Suitable capability + lower-carbon route';
  if (isKnowledge) reason = 'Direct knowledge match (no external LLM inference)';
  else if (isCache) reason = 'Stored complex response (no external LLM inference)';
  else if (meta.routing_mode === 'manual') reason = 'User-selected override';

  return (
    <div className="eco-decision-panel">
      <button 
        type="button" 
        className="eco-decision-header" 
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <div className="eco-decision-title">
          <Leaf size={14} className="eco-leaf-icon" color="var(--color-success)" />
          <span>Eco Decision</span>
        </div>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            className="eco-decision-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: EASE_FN }}
          >
            <div className="eco-decision-row">
              <span className="eco-decision-label">Question:</span>
              <span className="eco-decision-value">{tierName}</span>
            </div>
            <div className="eco-decision-row">
              <span className="eco-decision-label">Knowledge match:</span>
              <span className={`eco-decision-value ${isKnowledge ? 'highlight-green' : ''}`}>
                {isKnowledge ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="eco-decision-row">
              <span className="eco-decision-label">LLM required:</span>
              <span className="eco-decision-value">{llmRequired}</span>
            </div>
            <div className="eco-decision-row">
              <span className="eco-decision-label">Selected route:</span>
              <span className="eco-decision-value">{route}</span>
            </div>
            <div className="eco-decision-row">
              <span className="eco-decision-label">Reason:</span>
              <span className="eco-decision-value">{reason}</span>
            </div>
            <div className="eco-decision-row">
              <span className="eco-decision-label">Carbon:</span>
              <span className="eco-decision-value">
                <span className={`measurement-badge ${meta.measurement_type || 'estimated'}`}>{measurementLabel}</span>{' '}
                <Co2Estimate
                  value={meta.co2_estimated_g ?? 0}
                  band={{ relative: meta.uncertainty_relative, range: meta.uncertainty_range_g }}
                /> ({meta.region || 'auto'})
                {meta.carbon_estimate_is_approximate && <> <span className="measurement-badge estimated">Approximate provider proxy</span></>}
              </span>
            </div>
            {meta.carbon_estimate_is_approximate && <div className="eco-decision-row"><span className="eco-decision-label">Carbon basis:</span><span className="eco-decision-value">{meta.carbon_estimate_basis || 'Approximate provider/model proxy'}</span></div>}
            {meta.api_cost_is_estimate && <div className="eco-decision-row"><span className="eco-decision-label">API cost:</span><span className="eco-decision-value">{meta.api_cost == null ? 'Unavailable' : `$${meta.api_cost.toFixed(6)} (approximate)`}</span></div>}
            <div className="eco-decision-row"><span className="eco-decision-label">Energy:</span><span className="eco-decision-value">{meta.energy_kwh == null ? 'Unavailable' : `${meta.energy_kwh} kWh`} ({meta.energy_measurement_source || 'estimate'})</span></div>
            <div className="eco-decision-row"><span className="eco-decision-label">Grid source:</span><span className="eco-decision-value">{meta.grid_source || 'Unavailable'}</span></div>
            <div className="eco-decision-row"><span className="eco-decision-label">Final provider:</span><span className="eco-decision-value">{meta.final_provider || 'None'}</span></div>
            <div className="eco-decision-row"><span className="eco-decision-label">Fallback:</span><span className="eco-decision-value">{meta.fallback_reason || 'None'}</span></div>
            {meta.uncertainty_components && <div className="eco-decision-row"><span className="eco-decision-label">Uncertainty inputs:</span><span className="eco-decision-value">{Object.entries(meta.uncertainty_components).map(([key, value]) => `${key} ${(value * 100).toFixed(0)}%`).join(' · ')}</span></div>}
            {isKnowledge && <div className="eco-disclaimer">0 g direct estimate means no external LLM inference; it does not mean total application electricity was zero.</div>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface Props {
  token: string | null;
}

const WorkspaceChat = ({ token }: Props) => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'system', content: 'Workspace chat is ready. I will automatically use the most efficient and greenest model available for your query.' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [overrideModel, setOverrideModel] = useState('');
  const [models, setModels] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API}/api/models`)
      .then(r => r.json())
      .then(d => setModels(d.models || []))
      .catch(() => {});
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleNewChat = () => {
    setMessages([
      { role: 'system', content: 'Workspace chat is ready. I will automatically use the most efficient and greenest model available for your query.' }
    ]);
  };

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !token) return;
    
    const userMsg = input;
    const conversation = messages.filter(m => m.role !== 'system');
    
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch(`${API}/api/chat/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          ...byokHeaders()
        },
        body: JSON.stringify({
          message: userMsg,
          conversation: conversation,
          ...(overrideModel ? { model_id: overrideModel } : {}),
          max_output_tokens: 200
        })
      });

      // A 401/429/5xx arrives as an ordinary JSON body, not an event stream —
      // consuming it as SSE would leave a permanently empty reply bubble.
      if (!response.ok) {
        throw await apiFailure(response, 'The provider is unavailable.');
      }
      if (!response.body) throw new Error('No readable stream');

      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      await consumeSSE(response.body, {
        onText: (text) => setMessages(prev => {
          const newMsgs = [...prev];
          newMsgs[newMsgs.length - 1].content = text;
          return newMsgs;
        }),
        onMetadata: (metadata) => setMessages(prev => {
          const newMsgs = [...prev];
          newMsgs[newMsgs.length - 1].metadata = metadata;
          return newMsgs;
        }),
        onKeysExpired: () => setMessages(prev => {
          const newMsgs = [...prev];
          newMsgs[newMsgs.length - 1].content = "⚠️ All configured API keys have expired or reached their limits. Please update your API keys on the dashboard to continue.";
          return newMsgs;
        }),
        onError: (code, message) => setMessages(prev => {
          const newMsgs = [...prev];
          newMsgs[newMsgs.length - 1].content = errorCodeMessage(code, message);
          newMsgs[newMsgs.length - 1].error = true;
          newMsgs[newMsgs.length - 1].retryPrompt = userMsg;
          return newMsgs;
        }),
      });
    } catch (e) {
      // 402 = the platform's own credits are exhausted, distinct from a
      // provider being briefly unavailable (which is worth retrying).
      const creditsExhausted =
        (e instanceof ApiFailure && e.status === 402) ||
        (e instanceof Error && e.message.includes('402'));
      if (creditsExhausted) {
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ All configured API keys have expired or reached their limits. Please update your API keys on the dashboard to continue.' }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: describeApiError(e, 'The provider is unavailable. Please retry later.'), error: true, retryPrompt: userMsg }]);
      }
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="workspace-chat-container">
      <div className="workspace-chat-header">
        <div className="workspace-chat-title">
          <Leaf size={18} color="var(--color-success)" /> Workspace Chat
        </div>
        <div className="workspace-chat-controls">
          <button type="button" onClick={handleNewChat} className="workspace-new-chat-btn">
            <RefreshCw size={14} /> New Chat
          </button>
          <select
            value={overrideModel}
            onChange={e => setOverrideModel(e.target.value)}
            className="workspace-model-picker"
          >
            <option value="">EcoQuery Auto</option>
            <option disabled>──────────</option>
            {models.map(m => (
              <option key={m.id} value={m.id}>{m.provider} {m.id}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="workspace-chat-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`workspace-message ${msg.role}`}>
            <p>{msg.content}</p>
            {msg.error && msg.retryPrompt && (
              <button type="button" className="workspace-retry-button" onClick={() => setInput(msg.retryPrompt || '')}>
                Retry
              </button>
            )}
            {msg.metadata && (
              <>
                <div className="workspace-token-info">
                  <span>Tokens: Input {Math.max(5, Math.floor(msg.content.length / 4))} • Output {msg.content.split(' ').length}</span>
                </div>
                <EcoDecision meta={msg.metadata} />
              </>
            )}
          </div>
        ))}
        {isTyping && (
          <div className="workspace-message assistant typing">
            <p>...</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="workspace-chat-input-container">
        <div className="token-limit-indicator">
          <AlertCircle size={12} style={{ display: 'inline', marginRight: 4 }} />
          Workspace chat output is capped at 200 tokens per response
        </div>
        <form className="workspace-chat-form" onSubmit={handleSend}>
          <div className="workspace-chat-input-wrapper">
            <textarea
              className="workspace-chat-textarea"
              placeholder="Ask anything..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend(e as unknown as FormEvent);
                }
              }}
              rows={1}
            />
          </div>
          <button type="submit" className="workspace-chat-submit" disabled={!input.trim() || isTyping}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
};

export default WorkspaceChat;
