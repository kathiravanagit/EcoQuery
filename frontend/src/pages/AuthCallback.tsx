import React, { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Loader } from 'lucide-react';

const AuthCallback = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const token = params.get('token');
    const email = params.get('email');
    const name = params.get('name');
    if (token && email) {
      localStorage.setItem('token', token);
      localStorage.setItem('remember', 'true');
      window.dispatchEvent(new Event('auth-callback'));
    }
    setTimeout(() => navigate('/'), 500);
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
