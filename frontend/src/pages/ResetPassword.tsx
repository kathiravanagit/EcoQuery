import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { Lock, AlertCircle, Check } from 'lucide-react';
import './Pages.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const ResetPassword = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(false);

  const token = params.get('token');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setMessage({ type: 'error', text: 'Passwords do not match' }); return; }
    if (password.length < 6) { setMessage({ type: 'error', text: 'Password must be at least 6 characters' }); return; }
    setLoading(true); setMessage({ type: '', text: '' });
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password })
      });
      const data = await res.json();
      if (res.ok) { setMessage({ type: 'success', text: 'Password reset successfully!' }); setTimeout(() => navigate('/login'), 1500); }
      else setMessage({ type: 'error', text: data.detail || 'Reset failed' });
    } catch { setMessage({ type: 'error', text: 'Failed to connect to server' });
    } finally { setLoading(false); }
  };

  if (!token) return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ textAlign: 'center', paddingTop: '4rem' }}>
          <h2>Invalid Reset Link</h2>
          <p>This link is missing or invalid. <Link to="/forgot-password">Request a new one</Link>.</p>
        </div>
      </section>
    </div>
  );

  return (
    <div className="page">
      <section className="section">
        <div className="container">
          <motion.div className="auth-container" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="auth-card card">
              <h1 className="auth-title">Set New Password</h1>
              <p className="auth-subtitle">Enter your new password below.</p>
              {message.text && (
                <div className={`auth-error`} style={message.type === 'success' ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : {}}>
                  {message.type === 'success' ? <Check size={16} /> : <AlertCircle size={16} />} {message.text}
                </div>
              )}
              <form onSubmit={handleSubmit} className="auth-form">
                <label htmlFor="reset-password" style={{ display: 'none' }}>New password</label>
                <div className="input-group">
                  <Lock size={18} />
                  <input id="reset-password" type="password" placeholder="New password (min 6 chars)" value={password} onChange={e => setPassword(e.target.value)} required minLength={6} />
                </div>
                <label htmlFor="reset-confirm" style={{ display: 'none' }}>Confirm new password</label>
                <div className="input-group">
                  <Lock size={18} />
                  <input id="reset-confirm" type="password" placeholder="Confirm new password" value={confirm} onChange={e => setConfirm(e.target.value)} required />
                </div>
                <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
              </form>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default ResetPassword;
