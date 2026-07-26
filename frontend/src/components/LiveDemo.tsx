import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Leaf, Server, Zap } from 'lucide-react';
import { API_URL as API } from '../config';
import './LiveDemo.css';

interface Metadata {
  model_used: string
  model_id: string
  model_tier: string
  carbon_score: number
  region: string
  energy_source: string
  co2_estimated_g: number
  co2_saved_g: number
  is_mocked: boolean
  verification_status?: string
  verification_reason?: string
  observed_tps?: number
  is_local_inference?: boolean
}

interface Message {
  role: string
  content: string
  metadata?: Metadata
}

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const msgVariants = {
  initial: { opacity: 0, y: 16, scale: 0.97 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.4, ease: easeFn } },
};

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.6, ease: easeFn },
};

const modelTierColors: Record<string, string> = {
  green: '#00d46a',
  balanced: '#f59e0b',
  performance: '#ef4444',
};

const LiveDemo = () => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'system', content: 'Welcome to EcoQuery Demo. Try asking a question!' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [overrideModel, setOverrideModel] = useState('');
  const [models, setModels] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API}/api/models`).then(r => r.json()).then(d => setModels(d.models || [])).catch(() => {});
  }, []);

  const scrollToBottom = () => {
    const el = chatMessagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    const userMsg = input;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setIsTyping(true);
    try {
      const response = await fetch(`${API}/api/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, ...(overrideModel ? { model_id: overrideModel } : {}) })
      });
      const data = await response.json();
      const meta = data.metadata as Metadata;
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply, metadata: meta }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Error connecting to the routing backend. Please ensure the backend server is running.' }]);
    } finally { setIsTyping(false); }
  };

  return (
    <section id="demo" className="section demo-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Live <span className="text-gradient">Dashboard Demo</span></h2>
          <p>Experience carbon-aware model routing in real-time.</p>
        </motion.div>

        <motion.div className="demo-container" initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6, delay: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}>
          <div className="chat-interface card">
            <div className="chat-header">
              <motion.div className="status-dot" animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}></motion.div>
              <span>EcoQuery Router Active</span>
              <div style={{ marginLeft: 'auto' }}>
                <select aria-label="Model override" value={overrideModel} onChange={e => setOverrideModel(e.target.value)} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.25rem 0.5rem', fontSize: '0.8rem', color: 'var(--text-primary)' }}>
                  <option value="">Auto Route</option>
                  {models.map(m => (
                    <option key={m.id} value={m.id}>{m.provider} {m.id} ({m.tier})</option>
                  ))}
                </select>
              </div>
            </div>
            
            <div className="chat-messages" ref={chatMessagesRef}>
              {messages.map((msg, idx) => (
                <motion.div key={idx} className={`message ${msg.role}`} variants={msgVariants} initial="initial" animate="animate">
                  {msg.role === 'assistant' && <div className="avatar"><Leaf size={16} /></div>}
                  <div className="message-content">
                    <p>{msg.content}</p>
                    {msg.metadata && (
                      <motion.div className="message-metadata" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '4px' }}>
                          <span className="meta-tag" style={{ borderColor: modelTierColors[msg.metadata.model_tier] || 'var(--border)' }}>
                            <Zap size={12} style={{ color: modelTierColors[msg.metadata.model_tier] || 'var(--text-secondary)' }} />
                            {msg.metadata.model_tier.charAt(0).toUpperCase() + msg.metadata.model_tier.slice(1)} Tier
                          </span>
                          <span className="meta-tag"><Server size={12}/> {msg.metadata.model_id}</span>
                          <span className="meta-tag"><Leaf size={12} style={{ color: 'var(--accent)' }}/> {msg.metadata.energy_source}</span>
                          {msg.metadata.is_local_inference && (
                            <span className="meta-tag" style={{ borderColor: '#00C853', color: '#00C853', background: 'rgba(0,200,83,0.1)' }}>
                              💻 Local Ollama (0 Cloud CO₂)
                            </span>
                          )}
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          <span className="meta-tag savings">~{msg.metadata.co2_estimated_g}g CO₂</span>
                          <span className="meta-tag savings">Saved {msg.metadata.co2_saved_g}g vs baseline</span>
                          <span className="meta-tag">{msg.metadata.region}</span>
                          {msg.metadata.observed_tps ? (
                            <span className="meta-tag">⚡ {msg.metadata.observed_tps} TPS</span>
                          ) : null}
                          {msg.metadata.verification_status && (
                            <span className="meta-tag" style={{
                              borderColor: msg.metadata.verification_status === 'flagged_substitution' ? '#ef4444' : '#00C853',
                              color: msg.metadata.verification_status === 'flagged_substitution' ? '#ef4444' : '#00C853',
                              background: msg.metadata.verification_status === 'flagged_substitution' ? 'rgba(239,68,68,0.1)' : 'rgba(0,200,83,0.1)'
                            }}>
                              {msg.metadata.verification_status === 'flagged_substitution' ? '⚠️ Flagged Substitution' : '🛡️ Verified Integrity'}
                            </span>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </div>
                </motion.div>
              ))}
              <AnimatePresence>
                {isTyping && (
                  <motion.div className="message assistant typing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <div className="avatar"><Leaf size={16} /></div>
                    <div className="typing-indicator"><span></span><span></span><span></span></div>
                  </motion.div>
                )}
              </AnimatePresence>
              <div ref={messagesEndRef} />
            </div>
            
            <form className="chat-input-form" onSubmit={handleSend}>
              <motion.div className="input-wrapper" whileFocus={{ scale: 1.01 }}>
                <input type="text" placeholder="Ask something to test the routing..." value={input} onChange={(e) => setInput(e.target.value)} aria-label="Chat message" />
              </motion.div>
              <motion.button type="submit" disabled={!input.trim() || isTyping} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                <Send size={18} />
              </motion.button>
            </form>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default LiveDemo;
