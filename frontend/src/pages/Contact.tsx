import React, { useState, FormEvent } from 'react';
import { motion } from 'framer-motion';
import { Send, Mail, MapPin, Clock } from 'lucide-react';
import { API_URL } from '../config';
import './Pages.css';

const Contact = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

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
        setTimeout(() => setStatus('idle'), 5000);
      } else {
        setStatus('error');
      }
    } catch {
      setStatus('error');
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

            <motion.form className="contact-form card" onSubmit={handleSubmit} initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }}>
              <label htmlFor="contact-name" style={{ display: 'none' }}>Your Name</label>
              <input id="contact-name" type="text" placeholder="Your Name" value={name} onChange={e => setName(e.target.value)} required />
              <label htmlFor="contact-email" style={{ display: 'none' }}>Your Email</label>
              <input id="contact-email" type="email" placeholder="Your Email" value={email} onChange={e => setEmail(e.target.value)} required />
              <label htmlFor="contact-message" style={{ display: 'none' }}>Your Message</label>
              <textarea id="contact-message" rows={5} placeholder="Your Message" value={message} onChange={e => setMessage(e.target.value)} required></textarea>
              <button type="submit" className="btn btn-primary" disabled={status === 'sending'}>
                {status === 'sent' ? 'Message Sent!' : status === 'sending' ? 'Sending...' : 'Send Message'}
                <Send size={16} />
              </button>
              {status === 'error' && <p style={{ color: '#ef4444', fontSize: '0.85rem', marginTop: '0.5rem' }}>Failed to send. Please try again.</p>}
            </motion.form>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Contact;
