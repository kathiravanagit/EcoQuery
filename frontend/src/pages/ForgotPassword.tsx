import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Mail, AlertCircle, ArrowLeft } from 'lucide-react';
import './Pages.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setMessage({ type: '', text: '' });
    try {
      const res = await fetch(`${API}/api/auth/forgot-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (res.ok) setMessage({ type: 'success', text: data.message || 'Check your email for a reset link.' });
      else setMessage({ type: 'error', text: data.detail || 'Something went wrong' });
    } catch { setMessage({ type: 'error', text: 'Failed to connect to server' });
    } finally { setLoading(false); }
  };

  return (
    <div className="page">
      <section className="section">
        <div className="container">
          <motion.div className="auth-container" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="auth-card card">
              <Link to="/login" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.9rem' }}>
                <ArrowLeft size={16} /> Back to Login
              </Link>
              <h1 className="auth-title">Reset Password</h1>
              <p className="auth-subtitle">Enter your email and we'll send you a reset link.</p>
              {message.text && (
                <div className={`auth-error`} style={{ borderColor: message.type === 'success' ? 'var(--accent)' : undefined }}>
                  <AlertCircle size={16} /> {message.text}
                </div>
              )}
              <form onSubmit={handleSubmit} className="auth-form">
                <label htmlFor="forgot-email" style={{ display: 'none' }}>Your email</label>
                <div className="input-group">
                  <Mail size={18} />
                  <input id="forgot-email" type="email" placeholder="Your email" value={email} onChange={e => setEmail(e.target.value)} required />
                </div>
                <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                  {loading ? 'Sending...' : 'Send Reset Link'}
                </button>
              </form>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default ForgotPassword;
