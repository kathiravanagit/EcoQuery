import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Loader, AlertCircle } from 'lucide-react';
import { API_URL as API } from '../config';
import { ApiFailure, apiFailure, describeApiError } from '../apiError';

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
        const response = await fetch(`${API}/api/auth/exchange?code=${encodeURIComponent(code)}`, { credentials: 'include' });
        if (!response.ok) {
          throw await apiFailure(response, 'Sign in failed. Please try again.');
        }
        const data = await response.json().catch(() => ({}));
        if (!data.access_token) {
          // 200 without a token is a contract violation, not a network fault.
          throw new ApiFailure('Sign in failed. Please try again.', {
            status: response.status, code: '', retryAfterSeconds: null,
          });
        }
        sessionStorage.setItem('token', data.access_token);
        const userResponse = await fetch(`${API}/api/auth/me`, { credentials: 'include',
          headers: { Authorization: `Bearer ${data.access_token}` }
        });
        if (userResponse.ok) sessionStorage.setItem('user', JSON.stringify(await userResponse.json()));
        if (!cancelled) {
          window.dispatchEvent(new Event('auth-callback'));
          navigate('/');
        }
      } catch (err) {
        if (!cancelled) setError(describeApiError(err, 'Sign in failed. Please try again.'));
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
