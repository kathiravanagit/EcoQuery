import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Leaf, ChevronDown, ChevronUp, RefreshCw, AlertCircle } from 'lucide-react';
import { API_URL as API } from '../../config';
import './WorkspaceChat.css';
import { EASE_FN } from '../../constants';

interface Metadata {
  model_used?: string;
  model_id?: string;
  model_tier?: string;
  carbon_score?: number;
  region?: string;
  energy_source?: string;
  co2_estimated_g?: number;
  co2_saved_g?: number;
  tier?: string;
  confidence?: number;
  api_cost?: number;
  latency_seconds?: number;
  estimated_latency_s?: number;
  verification_status?: string;
  verification_reason?: string;
  observed_tps?: number;
  routing_mode?: string;
  answer_source?: string;
  knowledge_match?: boolean;
  knowledge_confidence?: number;
  llm_used?: boolean;
  cache_hit?: boolean;
}

interface Message {
  role: string
  content: string
  metadata?: Metadata
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
  
  let reason = 'Suitable capability + lower-carbon route';
  if (isKnowledge) reason = 'Direct knowledge match (Zero emissions)';
  else if (isCache) reason = 'Stored complex response (Zero emissions)';
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
                {meta.co2_estimated_g ?? 0}g ({meta.region || 'auto'})
              </span>
            </div>
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
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: userMsg,
          conversation: conversation,
          ...(overrideModel ? { model_id: overrideModel } : {}),
          max_output_tokens: 200
        })
      });

      if (!response.body) throw new Error('No readable stream');
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let currentReply = '';
      let meta: Metadata | undefined;

      setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              if (data.token) {
                currentReply += data.token;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].content = currentReply;
                  return newMsgs;
                });
              }
              if (data.done) {
                meta = data.metadata;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].metadata = meta;
                  return newMsgs;
                });
              }
            } catch (e) {
              console.error('Error parsing SSE', e);
            }
          }
        }
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'An error occurred connecting to the backend.' }]);
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
