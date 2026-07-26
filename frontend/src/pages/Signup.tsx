import React, { useState, FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { UserPlus, Mail, Lock, User, Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { API_URL as API } from '../config';
import './Pages.css';

const Signup = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({ name: '', email: '', password: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const errs = { name: '', email: '', password: '' };
    if (!name.trim()) errs.name = 'Name is required';
    if (!email.trim()) errs.email = 'Email is required';
    if (password.length < 6) errs.password = 'Password must be at least 6 characters';
    if (errs.name || errs.email || errs.password) { setErrors(errs); return; }
    setErrors({ name: '', email: '', password: '' });
    setIsSubmitting(true);
    try {
      await signup(email, password, name);
      toast('success', 'Account created! Welcome to EcoQuery.');
      navigate('/');
    } catch (err: unknown) {
      toast('error', err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page">
      <section className="section">
        <div className="container">
          <motion.div className="auth-container" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <div className="auth-card card">
              <h1 className="auth-title">Create Account</h1>
              <p className="auth-subtitle">Join EcoQuery and track your carbon savings</p>

              <form onSubmit={handleSubmit} className="auth-form">
                <label htmlFor="signup-name" style={{ display: 'none' }}>Full Name</label>
                <div className="input-group" style={{ borderColor: errors.name ? '#ef4444' : undefined }}>
                  <User size={18} />
                  <input id="signup-name" type="text" placeholder="Full Name" value={name} onChange={e => { setName(e.target.value); setErrors(prev => ({ ...prev, name: '' })); }} required />
                </div>
                {errors.name && <span style={{ color: '#ef4444', fontSize: 12, display: 'block', marginTop: -12, marginBottom: 8 }}>{errors.name}</span>}
                <label htmlFor="signup-email" style={{ display: 'none' }}>Email</label>
                <div className="input-group" style={{ borderColor: errors.email ? '#ef4444' : undefined }}>
                  <Mail size={18} />
                  <input id="signup-email" type="email" placeholder="Email" value={email} onChange={e => { setEmail(e.target.value); setErrors(prev => ({ ...prev, email: '' })); }} required />
                </div>
                {errors.email && <span style={{ color: '#ef4444', fontSize: 12, display: 'block', marginTop: -12, marginBottom: 8 }}>{errors.email}</span>}
                <label htmlFor="signup-password" style={{ display: 'none' }}>Password</label>
                <div className="input-group" style={{ borderColor: errors.password ? '#ef4444' : undefined }}>
                  <Lock size={18} />
                  <input id="signup-password" type={showPassword ? 'text' : 'password'} placeholder="Password (min 6 chars)" value={password} onChange={e => { setPassword(e.target.value); setErrors(prev => ({ ...prev, password: '' })); }} required minLength={6} />
                  <button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} tabIndex={-1}>
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {errors.password && <span style={{ color: '#ef4444', fontSize: 12, display: 'block', marginTop: -12, marginBottom: 8 }}>{errors.password}</span>}
                <button type="submit" className="btn btn-primary btn-full" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating account...' : <><UserPlus size={18} /> Create Account</>}
                </button>
              </form>

              <div className="auth-divider"><span>or continue with</span></div>

              <a href={`${API}/api/auth/google`} className="btn btn-google btn-full">
                <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                Continue with Google
              </a>

              <p className="auth-footer-text">
                Already have an account? <Link to="/login" className="text-accent">Sign in</Link>
              </p>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default Signup;
