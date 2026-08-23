import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Loader, AlertCircle } from 'lucide-react';
import { API_URL as API } from '../config';

const AuthCallback = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState('');

  useEffect(() => {
    const code = params.get('code');
    const oauthError = params.get('error');
    if (!code) {
      setError(oauthError || 'Sign in was cancelled. Please try again.');
      return;
    }

    let cancelled = false;
    const completeSignIn = async () => {
      try {
        const response = await fetch(`${API}/api/auth/exchange?code=${encodeURIComponent(code)}`);
        const data = await response.json();
        if (!response.ok || !data.access_token) {
          throw new Error(data.detail || 'Sign in failed. Please try again.');
        }
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('remember', 'true');
        const userResponse = await fetch(`${API}/api/auth/me`, {
          headers: { Authorization: `Bearer ${data.access_token}` }
        });
        if (userResponse.ok) localStorage.setItem('user', JSON.stringify(await userResponse.json()));
        if (!cancelled) navigate('/');
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Network error. Please try again.');
      }
    };
    completeSignIn();
    return () => { cancelled = true; };
  }, [params, navigate]);

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ textAlign: 'center', paddingTop: '4rem' }}>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            {error ? (
              <>
                <AlertCircle size={32} style={{ color: 'var(--color-error)' }} />
                <p style={{ marginTop: '1rem', color: 'var(--color-error)' }}>{error}</p>
                <button className="btn btn-primary" onClick={() => navigate('/login')} style={{ marginTop: '1rem' }}>
                  Back to Login
                </button>
              </>
            ) : (
              <>
                <Loader size={32} className="spinner" />
                <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>Completing sign in...</p>
              </>
            )}
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default AuthCallback;
