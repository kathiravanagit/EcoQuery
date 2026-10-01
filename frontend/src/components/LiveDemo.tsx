import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, X, ChevronDown, ChevronUp, Leaf, ShieldCheck, Zap } from 'lucide-react';
import { API_URL as API } from '../config';
import './LiveDemo.css';
import { Metadata, consumeSSE } from '../sse';
import { apiFailure, describeApiError, errorCodeMessage } from '../apiError';
import Co2Estimate from './Co2Estimate';

interface Message {
  role: string
  content: string
  metadata?: Metadata
  images?: string[]
  error?: boolean
  retryPrompt?: string
}

import { EASE_FN } from '../constants';

const msgVariants = {
  initial: { opacity: 0, y: 16, scale: 0.97 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: EASE_FN } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.6, ease: EASE_FN },
};

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
  if (isKnowledge) reason = 'Direct knowledge match (no external LLM inference)';
  else if (isCache) reason = 'Stored complex response (no external LLM inference)';
  else if (meta.routing_mode === 'manual') reason = 'User-selected override';

  // Shared uncertainty band: backend computes it once per response and every
  // CO₂ figure derived from that response inherits it.
  const co2Band = { relative: meta.uncertainty_relative, range: meta.uncertainty_range_g };

  return (
    <div className="eco-insight-container">
      <div className="eco-proof-summary">
        <div className="eco-proof-main">
          <div className="eco-proof-kicker"><span className="eco-proof-dot"></span> Decision trace</div>
          <strong>{isKnowledge || isCache ? 'Inference avoided' : 'Lowest-impact capable route selected'}</strong>
          <span>{reason}</span>
        </div>
        <div className="eco-proof-stat">
          <strong>
            {isKnowledge || isCache
              ? '0 g'
              : <Co2Estimate value={meta.co2_estimated_g ?? 0} band={co2Band} />}
          </strong>
          <span><span className={`measurement-badge ${meta.measurement_type || 'estimated'}`}>{meta.measurement_type === 'measured' ? 'Measured' : meta.measurement_type === 'provider_reported' ? 'Provider-reported' : 'Estimated'}</span> CO₂e</span>
        </div>
      </div>
      <button
        type="button"
        className="eco-insight-header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        <div className="eco-insight-title">
          <Leaf size={14} className="eco-leaf-icon" color="var(--color-success)" />
          <span>Eco Decision</span>
        </div>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            className="eco-insight-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: EASE_FN }}
          >
            <div className="eco-insight-grid">
              <div className="eco-insight-row">
                <span className="eco-label">Question:</span>
                <span className="eco-val">{tierName}</span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">Knowledge match:</span>
                <span className={`eco-val ${isKnowledge ? 'highlight-green' : ''}`}>
                  {isKnowledge ? 'Yes' : 'No'}
                </span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">LLM required:</span>
                <span className="eco-val">{llmRequired}</span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">Selected route:</span>
                <span className="eco-val">{route}</span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">Reason:</span>
                <span className="eco-val">{reason}</span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">Estimated CO₂e impact:</span>
                <span className="eco-val">
                  <Co2Estimate value={meta.co2_estimated_g ?? 0} band={co2Band} /> ({meta.region || 'auto'})
                </span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">Estimated emissions avoided compared with the selected baseline:</span>
                <span className="eco-val">
                  <Co2Estimate value={meta.co2_saved_g ?? 0} band={co2Band} />
                </span>
              </div>
              <div className="eco-insight-row">
                <span className="eco-label">Model verification signal:</span>
                <span className="eco-val highlight-green"><ShieldCheck size={13} /> {meta.verification_status === 'passed' ? 'passed' : (meta.verification_status || 'recorded')}</span>
              </div>
              {meta.grid_source && (
                <div className="eco-insight-row">
                  <span className="eco-label">Grid source:</span>
                  <span className="eco-val">{meta.grid_source} ({meta.measurement_type}) - {meta.grid_timestamp ? new Date(meta.grid_timestamp).toLocaleTimeString() : ''}</span>
                </div>
              )}
              {meta.energy_assumption_kwh_per_1000_tokens !== undefined && (
                <div className="eco-insight-row">
                  <span className="eco-label">Energy assumption:</span>
                  <span className="eco-val">{meta.energy_assumption_kwh_per_1000_tokens} kWh/1K tokens</span>
                </div>
              )}
              {meta.uncertainty_range_g && (
                <div className="eco-insight-row">
                  <span className="eco-label">Uncertainty range:</span>
                  <span className="eco-val">{meta.uncertainty_range_g.min}g - {meta.uncertainty_range_g.max}g</span>
                </div>
              )}
              {meta.uncertainty_components && Object.keys(meta.uncertainty_components).length > 0 && (
                <div className="eco-insight-row">
                  <span className="eco-label">Uncertainty inputs:</span>
                  <span className="eco-val">{Object.entries(meta.uncertainty_components).map(([key, value]) => `${key} ${(value * 100).toFixed(0)}%`).join(' · ')}</span>
                </div>
              )}
              {meta.fallback_reason && meta.final_provider && (
                <div className="eco-insight-row">
                  <span className="eco-label">Provider lineage:</span>
                  <span className="eco-val">
                    {meta.attempted_providers?.map((attempt) => attempt.provider || 'unknown').join(' -> ') || 'unknown'} {'->'} {meta.final_provider} ({meta.fallback_reason})
                  </span>
                </div>
              )}
              {(isKnowledge || isCache) && (
                <div className="eco-insight-row" style={{ gridColumn: "1 / -1", fontSize: "0.8em", color: "var(--text-muted)", marginTop: "4px" }}>
                  This request was answered from the local knowledge layer. The estimated direct emissions are 0 g. The saved value represents the estimated emissions avoided by not sending the request to the baseline LLM.
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


const LiveDemo = () => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'system', content: 'Ask a question. EcoQuery will show the route, model, region, and estimated impact.' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [routingStage, setRoutingStage] = useState<string>('Analyzing question...');
  const [overrideModel, setOverrideModel] = useState('');
  const [models, setModels] = useState<any[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API}/api/models`)
      .then(r => r.json())
      .then(d => setModels(d.models || []))
      .catch(() => {})
      .finally(() => setModelsLoading(false));
  }, []);

  const scrollToBottom = () => {
    const el = chatMessagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  useEffect(() => { scrollToBottom(); }, [messages, routingStage]);

  const MAX_IMAGES = 3;
  const MAX_FILE_SIZE_MB = 5;

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    let imagesQueued = attachedImages.length;
    Array.from(files).forEach(file => {
      if (!file.type.startsWith('image/')) {
        setMessages(prev => [...prev, { role: 'assistant', content: 'Only image files are supported. PDFs and other documents are not accepted.' }]);
        return;
      }
      if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        setMessages(prev => [...prev, { role: 'assistant', content: `File too large. Maximum size is ${MAX_FILE_SIZE_MB}MB.` }]);
        return;
      }
      if (imagesQueued >= MAX_IMAGES) {
        setMessages(prev => [...prev, { role: 'assistant', content: `Maximum ${MAX_IMAGES} images per message.` }]);
        return;
      }
      imagesQueued += 1;
      const reader = new FileReader();
      reader.onload = (event) => {
        const base64 = event.target?.result as string;
        const base64Data = base64.split(',')[1];
        setAttachedImages(prev => [...prev, base64Data]);
      };
      reader.readAsDataURL(file);
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index: number) => {
    setAttachedImages(prev => prev.filter((_, i) => i !== index));
  };

  const estimateQuickTier = (msg: string): string => {
    const words = msg.trim().split(/\s+/).length;
    if (words > 40 || msg.includes('```') || msg.includes('def ') || msg.includes('algorithm')) return 'Complex';
    if (words > 10 || msg.toLowerCase().includes('explain') || msg.toLowerCase().includes('how does')) return 'Moderate';
    return 'Simple';
  };

  const handleNewChat = () => {
    setMessages([
      { role: 'system', content: 'Ask a question. EcoQuery will show the route, model, region, and estimated impact.' }
    ]);
  };

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() && attachedImages.length === 0) return;
    const userMsg = input || (attachedImages.length > 0 ? 'Describe this image' : '');
    setMessages(prev => [...prev, { role: 'user', content: userMsg, images: attachedImages.length > 0 ? attachedImages : undefined }]);
    setInput('');
    setAttachedImages([]);
    setIsTyping(true);

    const isAuto = !overrideModel;
    const estimated = estimateQuickTier(userMsg);

    // Dynamic staged progression for EcoQuery Auto
    if (isAuto) {
      setRoutingStage('Analyzing question...');
      setTimeout(() => {
        setRoutingStage(`${estimated} question`);
        setTimeout(() => {
          setRoutingStage('Checking EcoQuery knowledge...');
        }, 400);
      }, 300);
    } else {
      setRoutingStage(`Routing to selected model...`);
    }

    try {
      const response = await fetch(`${API}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg,
          conversation: messages.filter(m => m.role !== 'system'),
          ...(overrideModel ? { model_id: overrideModel } : {}),
          ...(attachedImages.length > 0 ? { images: attachedImages } : {}),
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
        onError: (code, message) => setMessages(prev => [...prev, {
          role: 'assistant',
          content: errorCodeMessage(code, message),
          error: true,
          retryPrompt: userMsg,
        }]),
      });
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: describeApiError(e, 'The routing provider is unavailable.'),
        error: true,
        retryPrompt: userMsg,
      }]);
    } finally {
      setIsTyping(false);
      setRoutingStage('');
    }
  };

  return (
    <section id="demo" className="section demo-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Live <span className="text-gradient">EcoQuery Router</span></h2>
          <p>Experience zero-LLM direct knowledge matching and carbon-aware routing in real-time.</p>
        </motion.div>

        <motion.div className="demo-container" initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}>
          <div className="chat-interface">
            <div className="chat-header">
              <motion.div className="status-dot" animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}></motion.div>
              <span>EcoQuery Router Active</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--accent)', fontWeight: 600 }}>
                  {!overrideModel ? 'Auto Mode' : 'Manual Mode'}
                </span>
                <button type="button" onClick={handleNewChat} style={{ fontSize: '0.75rem', color: 'var(--accent)', background: 'none', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.25rem 0.5rem', cursor: 'pointer' }}>
                  New Chat
                </button>
                <select
                  aria-label="Model override"
                  value={overrideModel}
                  onChange={e => setOverrideModel(e.target.value)}
                  disabled={modelsLoading}
                  className="model-picker"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--text-primary)' }}
                >
                  <option value="">EcoQuery Auto</option>
                  {modelsLoading && <option disabled>Loading models...</option>}
                  <option disabled>──────────</option>
                  {['green', 'balanced', 'performance'].map(tier => {
                    const tierModels = models.filter(m => m.tier === tier);
                    return tierModels.length > 0 ? (
                      <optgroup key={tier} label={`${tier.charAt(0).toUpperCase() + tier.slice(1)} Tier`} className="model-picker-group">
                        {tierModels.map(m => (
                          <option key={m.id} value={m.id} className="model-picker-option" title={m.description}>
                            {m.provider} {m.id.split('/').pop()}
                          </option>
                        ))}
                      </optgroup>
                    ) : null;
                  })}
                </select>
              </div>
            </div>

            <div className="chat-messages" ref={chatMessagesRef}>
              {messages.map((msg, idx) => (
                <motion.div key={idx} className={`message ${msg.role}`} variants={msgVariants} initial="initial" animate="animate">
                  <div className="message-content">
                    {msg.images && msg.images.length > 0 && (
                      <div className="message-images">
                        {msg.images.map((img, i) => (
                          <img key={i} src={`data:image/jpeg;base64,${img}`} alt="Attached" className="message-image" />
                        ))}
                      </div>
                    )}
                    <p>{msg.content}</p>
                    {msg.error && msg.retryPrompt && (
                      <button type="button" className="retry-button" onClick={() => setInput(msg.retryPrompt || '')}>
                        Retry
                      </button>
                    )}

                    {msg.metadata && (
                      <motion.div className="message-metadata-wrapper" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
                        <div className="meta-tags-row">
                          <span className={`meta-tag ${(msg.metadata.answer_source === 'ecoquery_knowledge' || msg.metadata.answer_source === 'ecoquery_cache') ? 'knowledge-tag' : ''}`}>
                            {msg.metadata.answer_source === 'ecoquery_knowledge' ? (
                              <><Zap size={12} /> Knowledge Direct</>
                            ) : msg.metadata.answer_source === 'ecoquery_cache' ? (
                              <><Zap size={12} /> Stored Response</>
                            ) : msg.metadata.model_id}
                          </span>
                          <span className="meta-tag">
                            {formatTier(msg.metadata.tier)}
                          </span>
                          {msg.metadata.co2_saved_g && msg.metadata.co2_saved_g > 0 ? (
                            <span className="meta-tag savings">
                              <Co2Estimate
                                value={msg.metadata.co2_saved_g}
                                band={{
                                  relative: msg.metadata.uncertainty_relative,
                                  range: msg.metadata.uncertainty_range_g,
                                }}
                              />{' '}
                              CO₂ saved
                            </span>
                          ) : null}
                          {msg.metadata.region && (
                            <span className="meta-tag">
                              {msg.metadata.region}
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <span>Tokens: Input {msg.metadata.prompt_tokens ?? 0} • Output {msg.metadata.completion_tokens ?? 0}</span>
                        </div>
                        <EcoDecision meta={msg.metadata} />
                      </motion.div>
                    )}
                  </div>
                </motion.div>
              ))}

              <AnimatePresence>
                {isTyping && (
                  <motion.div className="message assistant typing" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
                    <div className="typing-indicator">
                      <span></span><span></span><span></span>
                      <em className="typing-status">{routingStage}</em>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>

            <form className="chat-input-form" onSubmit={handleSend} aria-label="Chat input form">
              {attachedImages.length > 0 && (
                <div className="attached-files" role="list" aria-label="Attached images">
                  {attachedImages.map((img, i) => (
                    <div key={`img-${i}`} className="attached-file" role="listitem">
                      <img src={`data:image/jpeg;base64,${img}`} alt={`Attached ${i}`} className="attached-image" />
                      <button type="button" className="remove-file" aria-label="Remove image" onClick={() => removeFile(i)}>
                        <X size={14} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="input-wrapper">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  multiple
                  accept="image/*"
                  style={{ display: 'none' }}
                  aria-label="Upload file"
                  tabIndex={-1}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="attach-btn"
                  title="Attach file or image"
                  aria-label="Attach file"
                >
                  <Paperclip size={16} aria-hidden="true" />
                </button>
                <input
                  type="text"
                  placeholder="Ask something (e.g. 'What is photosynthesis?')..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  aria-label="Chat message"
                />
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                  <motion.button type="button" onClick={handleSend} aria-label="Retry last message" title="Retry" disabled={isTyping} whileHover={{ y: -2 }} whileTap={{ y: 0 }} style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', padding: '0 12px', borderRadius: '8px', cursor: 'pointer' }}>
                    Retry
                  </motion.button>
                  <motion.button type="submit" aria-label="Send message" disabled={(!input.trim() && attachedImages.length === 0) || isTyping} whileHover={{ y: -2 }} whileTap={{ y: 0 }}>
                    <Send size={18} aria-hidden="true" />
                  </motion.button>
              </div>
            </form>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default LiveDemo;
