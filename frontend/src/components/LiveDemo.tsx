import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Leaf, Server, Zap, Shield, TreePine, Timer, Paperclip, X, Image as ImageIcon, FileText } from 'lucide-react';
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
  routing_mode?: string
  integrity_hash?: string
  estimated_latency_s?: number
  what_if?: {
    baseline_model: string
    baseline_region: string
    baseline_co2_g: number
    actual_model: string
    actual_region: string
    actual_co2_g: number
    co2_saved_g: number
    baseline_cost: number
    actual_cost: number
  }
}

interface Message {
  role: string
  content: string
  metadata?: Metadata
  images?: string[]
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
  const [attachedFiles, setAttachedFiles] = useState<{name: string; type: string; data: string}[]>([]);
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatMessagesRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch(`${API}/api/models`).then(r => r.json()).then(d => setModels(d.models || [])).catch(() => {});
  }, []);

  const scrollToBottom = () => {
    const el = chatMessagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = (event) => {
        const base64 = event.target?.result as string;
        const base64Data = base64.split(',')[1];

        if (file.type.startsWith('image/')) {
          setAttachedImages(prev => [...prev, base64Data]);
        } else {
          setAttachedFiles(prev => [...prev, {
            name: file.name,
            type: file.type,
            data: base64Data
          }]);
        }
      };
      reader.readAsDataURL(file);
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index: number, type: 'image' | 'file') => {
    if (type === 'image') {
      setAttachedImages(prev => prev.filter((_, i) => i !== index));
    } else {
      setAttachedFiles(prev => prev.filter((_, i) => i !== index));
    }
  };

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() && attachedImages.length === 0 && attachedFiles.length === 0) return;
    const userMsg = input || (attachedImages.length > 0 ? 'Describe this image' : 'Analyze this file');
    setMessages(prev => [...prev, { role: 'user', content: userMsg, images: attachedImages.length > 0 ? attachedImages : undefined }]);
    setInput('');
    setIsTyping(true);
    try {
      const response = await fetch(`${API}/api/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg,
          ...(overrideModel ? { model_id: overrideModel } : {}),
          ...(attachedImages.length > 0 ? { images: attachedImages } : {}),
          ...(attachedFiles.length > 0 ? { files: attachedFiles } : {}),
        })
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
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: '#00d46a', fontWeight: 600 }}>
                  <TreePine size={12} style={{ marginRight: 3, verticalAlign: 'middle' }} />Eco Mode
                </span>
                <select aria-label="Model override" value={overrideModel} onChange={e => setOverrideModel(e.target.value)} className="model-picker" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                  <option value="">🌿 Auto (Greenest)</option>
                  <option disabled>──────────</option>
                  {['green', 'balanced', 'performance'].map(tier => {
                    const tierModels = models.filter(m => m.tier === tier);
                    return tierModels.length > 0 ? (
                      <optgroup key={tier} label={`${tier.charAt(0).toUpperCase() + tier.slice(1)} Tier`} className="model-picker-group">
                        {tierModels.map(m => (
                          <option key={m.id} value={m.id} className="model-picker-option" title={m.description}>
                            {m.provider} {m.id} <span className="model-picker-carbon">Score {m.carbon_score}/10</span>
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
                  {msg.role === 'assistant' && <div className="avatar"><Leaf size={16} /></div>}
                  <div className="message-content">
                    {msg.images && msg.images.length > 0 && (
                      <div className="message-images">
                        {msg.images.map((img, i) => (
                          <img key={i} src={`data:image/jpeg;base64,${img}`} alt="Attached" className="message-image" />
                        ))}
                      </div>
                    )}
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
                          {msg.metadata.routing_mode && (
                            <span className="meta-tag" style={{ borderColor: '#00d46a', color: '#00d46a' }}>
                              <TreePine size={12} style={{ marginRight: 3, verticalAlign: 'middle' }} />Eco Mode
                            </span>
                          )}
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
                          {msg.metadata.integrity_hash && (
                            <span className="meta-tag" style={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
                              <Shield size={11} /> {msg.metadata.integrity_hash.slice(0, 8)}
                            </span>
                          )}
                          {msg.metadata.verification_status && (
                            <span className="meta-tag" style={{
                              borderColor: msg.metadata.verification_status === 'flagged_substitution' ? '#ef4444' : '#00C853',
                              color: msg.metadata.verification_status === 'flagged_substitution' ? '#ef4444' : '#00C853',
                              background: msg.metadata.verification_status === 'flagged_substitution' ? 'rgba(239,68,68,0.1)' : 'rgba(0,200,83,0.1)'
                            }}>
                              {msg.metadata.verification_status === 'flagged_substitution' ? '⚠️ Flagged' : '🛡️ Verified'}
                            </span>
                          )}
                        </div>
                        {msg.metadata.what_if && (
                          <details style={{ marginTop: '0.5rem', fontSize: '0.8rem', cursor: 'pointer' }}>
                            <summary style={{ color: 'var(--accent)' }}>📊 What-If Comparison</summary>
                            <div style={{ marginTop: '0.5rem', padding: '0.75rem', background: 'var(--bg-card)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                                <div style={{ fontWeight: 600 }}>✅ Eco Mode (used)</div>
                                <div style={{ fontWeight: 600, color: '#ef4444' }}>❌ Baseline (GPT-4.5)</div>
                                <div>CO₂: {msg.metadata.what_if.actual_co2_g}g</div>
                                <div style={{ color: '#ef4444' }}>CO₂: {msg.metadata.what_if.baseline_co2_g}g</div>
                                <div>Cost: ${msg.metadata.what_if.actual_cost}</div>
                                <div style={{ color: '#ef4444' }}>Cost: ${msg.metadata.what_if.baseline_cost}</div>
                                <div style={{ gridColumn: '1 / -1', color: 'var(--accent)', fontWeight: 600 }}>
                                  Saved: {msg.metadata.what_if.co2_saved_g}g CO₂
                                </div>
                              </div>
                            </div>
                          </details>
                        )}
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
              {(attachedImages.length > 0 || attachedFiles.length > 0) && (
                <div className="attached-files">
                  {attachedImages.map((img, i) => (
                    <div key={`img-${i}`} className="attached-file">
                      <img src={`data:image/jpeg;base64,${img}`} alt={`Attached ${i}`} className="attached-image" />
                      <button type="button" className="remove-file" onClick={() => removeFile(i, 'image')}>
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                  {attachedFiles.map((file, i) => (
                    <div key={`file-${i}`} className="attached-file">
                      <FileText size={20} />
                      <span>{file.name}</span>
                      <button type="button" className="remove-file" onClick={() => removeFile(i, 'file')}>
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="input-wrapper" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileSelect}
                  multiple
                  accept="image/*,.pdf,.txt,.csv,.json,.md"
                  style={{ display: 'none' }}
                  aria-label="Upload file"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="attach-btn"
                  title="Attach file or image"
                >
                  <Paperclip size={18} />
                </button>
                <input type="text" placeholder="Ask something to test the routing..." value={input} onChange={(e) => setInput(e.target.value)} aria-label="Chat message" style={{ flex: 1 }} />
              </div>
              <motion.button type="submit" disabled={(!input.trim() && attachedImages.length === 0 && attachedFiles.length === 0) || isTyping} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
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
