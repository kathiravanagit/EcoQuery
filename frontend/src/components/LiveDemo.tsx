import React, { useState, useRef, useEffect, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Paperclip, X, FileText } from 'lucide-react';
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
                  Auto Mode
                </span>
                <select aria-label="Model override" value={overrideModel} onChange={e => setOverrideModel(e.target.value)} className="model-picker" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                  <option value="">Auto (Greenest)</option>
                  <option disabled>──────────</option>
                  {['green', 'balanced', 'performance'].map(tier => {
                    const tierModels = models.filter(m => m.tier === tier);
                    return tierModels.length > 0 ? (
                      <optgroup key={tier} label={`${tier.charAt(0).toUpperCase() + tier.slice(1)} Tier`} className="model-picker-group">
                        {tierModels.map(m => (
                          <option key={m.id} value={m.id} className="model-picker-option" title={m.description}>
                            {m.provider} {m.id}
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
                    {msg.metadata && (
                      <motion.div className="message-metadata" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          <span className="meta-tag">
                            {msg.metadata.model_id}
                          </span>
                          <span className="meta-tag">
                            auto picked by query heavy
                          </span>
                        </div>
                      </motion.div>
                    )}
                  </div>
                </motion.div>
              ))}
              <AnimatePresence>
                {isTyping && (
                  <motion.div className="message assistant typing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
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
