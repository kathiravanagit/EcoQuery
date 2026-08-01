import React, { useState, FormEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Mail, MapPin, Clock, CheckCircle } from 'lucide-react';
import { API_URL } from '../config';
import { useToast } from '../context/ToastContext';
import './Pages.css';

const Contact = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const { toast } = useToast();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus('sending');
    try {
      const res = await fetch(`${API_URL}/api/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, message }),
      });
      if (res.ok) {
        setStatus('sent');
        setName(''); setEmail(''); setMessage('');
        toast('success', 'Message sent successfully!');
        setTimeout(() => setStatus('idle'), 5000);
      } else {
        setStatus('error');
        toast('error', 'Failed to send message. Please try again.');
      }
    } catch {
      setStatus('error');
      toast('error', 'Failed to send message. Please try again.');
    }
  };

  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>Get in <span className="text-gradient">Touch</span></h1>
            <p className="page-subtitle">Have questions? We'd love to hear from you.</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="contact-grid">
            <motion.div className="contact-info" initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <div className="contact-item"><Mail size={20} className="text-accent" /><div><h4>Email</h4><p>kathiravanawork@gmail.com</p></div></div>
              <div className="contact-item"><MapPin size={20} className="text-accent" /><div><h4>Location</h4><p>Puducherry, India</p></div></div>
              <div className="contact-item"><Clock size={20} className="text-accent" /><div><h4>Response Time</h4><p>Within 24 hours</p></div></div>
            </motion.div>

            <AnimatePresence mode="wait">
              {status === 'sent' ? (
                <motion.div
                  key="success"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  style={{
                    display: 'flex', flexDirection: 'column', alignItems: 'center',
                    justifyContent: 'center', padding: '4rem 2rem', textAlign: 'center',
                    border: '1px solid var(--accent)', background: 'var(--bg-secondary)',
                  }}
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                    style={{ color: 'var(--accent)', marginBottom: '1.5rem' }}
                  >
                    <CheckCircle size={64} />
                  </motion.div>
                  <h2 style={{ fontSize: '1.5rem', marginBottom: '0.75rem', fontFamily: 'var(--font-sans)' }}>
                    Message Sent!
                  </h2>
                  <p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '0.85rem', marginBottom: '2rem' }}>
                    // we'll get back to you within 24 hours
                  </p>
                  <button
                    onClick={() => setStatus('idle')}
                    className="btn btn-secondary"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}
                  >
                    send another message
                  </button>
                </motion.div>
              ) : (
                <motion.form
                  key="form"
                  className="contact-form card"
                  onSubmit={handleSubmit}
                  initial={{ opacity: 0, x: 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  exit={{ opacity: 0, x: -20 }}
                >
                  <label htmlFor="contact-name" style={{ display: 'none' }}>Your Name</label>
                  <input id="contact-name" type="text" placeholder="$ your name" value={name} onChange={e => setName(e.target.value)} required />
                  <label htmlFor="contact-email" style={{ display: 'none' }}>Your Email</label>
                  <input id="contact-email" type="email" placeholder="$ your email" value={email} onChange={e => setEmail(e.target.value)} required />
                  <label htmlFor="contact-message" style={{ display: 'none' }}>Your Message</label>
                  <textarea id="contact-message" rows={5} placeholder="$ your message" value={message} onChange={e => setMessage(e.target.value)} required></textarea>
                  <button type="submit" className="btn btn-primary" disabled={status === 'sending'}>
                    {status === 'sending' ? 'sending...' : 'send message'}
                    <Send size={14} />
                  </button>
                  {status === 'error' && (
                    <motion.p
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      style={{ color: '#ff5555', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', marginTop: '0.5rem' }}
                    >
                      // error: failed to send message
                    </motion.p>
                  )}
                </motion.form>
              )}
            </AnimatePresence>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Contact;
