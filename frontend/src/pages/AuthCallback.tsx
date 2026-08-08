import React, { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Loader } from 'lucide-react';
import { API_URL as API } from '../config';

const AuthCallback = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const code = params.get('code');
    if (code) {
      fetch(`${API}/api/auth/exchange?code=${code}`)
        .then(r => r.json())
        .then(data => {
          if (data.access_token) {
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('remember', 'true');
            return fetch(`${API}/api/auth/me`, {
              headers: { Authorization: `Bearer ${data.access_token}` }
            }).then(r => r.ok ? r.json() : null).then(u => {
              if (u) localStorage.setItem('user', JSON.stringify(u));
            });
          }
        })
        .catch(() => {})
        .finally(() => setTimeout(() => navigate('/'), 500));
    } else {
      setTimeout(() => navigate('/'), 500);
    }
  }, [params, navigate]);

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ textAlign: 'center', paddingTop: '4rem' }}>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Loader size={32} className="spinner" />
            <p style={{ marginTop: '1rem', color: 'var(--text-secondary)' }}>Completing sign in...</p>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default AuthCallback;
