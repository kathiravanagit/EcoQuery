import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { API_URL } from '../config';
import './Pages.css';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    const email = searchParams.get('email');

    if (!token || !email) {
      setStatus('error');
      setMessage('Invalid verification link.');
      return;
    }

    const verify = async () => {
      try {
        const res = await fetch(`${API_URL}/api/auth/verify-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, token }),
        });
        const data = await res.json();

        if (res.ok) {
          setStatus('success');
          setMessage('Your email has been verified successfully!');
          setTimeout(() => navigate('/'), 3000);
        } else {
          setStatus('error');
          setMessage(data.detail || 'Verification failed. The link may have expired.');
        }
      } catch {
        setStatus('error');
        setMessage('Network error. Please try again.');
      }
    };

    verify();
  }, [searchParams, navigate]);

  return (
    <div className="auth-container">
      <motion.div
        className="auth-card"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {status === 'loading' && (
          <>
            <img src="/logo.png" alt="EcoQuery" width={48} height={48} style={{ borderRadius: 8, marginBottom: 16 }} />
            <h2 className="auth-title">Verifying your email...</h2>
            <p className="auth-subtitle">Please wait while we confirm your email address.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <img src="/logo.png" alt="EcoQuery" width={48} height={48} style={{ borderRadius: 8, marginBottom: 16 }} />
            <div style={{ fontSize: 48, color: '#00d46a', marginBottom: 8 }}>&#10003;</div>
            <h2 className="auth-title">Email Verified!</h2>
            <p className="auth-subtitle">{message}</p>
            <p className="auth-subtitle" style={{ color: '#888', fontSize: 14 }}>Redirecting to home page in 3 seconds...</p>
          </>
        )}

        {status === 'error' && (
          <>
            <img src="/logo.png" alt="EcoQuery" width={48} height={48} style={{ borderRadius: 8, marginBottom: 16 }} />
            <div style={{ fontSize: 48, color: '#ef4444', marginBottom: 8 }}>&#10007;</div>
            <h2 className="auth-title">Verification Failed</h2>
            <p className="auth-subtitle">{message}</p>
            <button className="auth-btn" onClick={() => navigate('/')}>
              Go to Home
            </button>
          </>
        )}
      </motion.div>
    </div>
  );
}
