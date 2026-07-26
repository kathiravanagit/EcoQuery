import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Home } from 'lucide-react';
import './Pages.css';

const NotFound = () => {
  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ textAlign: 'center', paddingTop: '4rem' }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 style={{ fontSize: '6rem', fontWeight: 900, color: 'var(--accent)', lineHeight: 1 }}>404</h1>
            <p style={{ fontSize: '1.25rem', color: 'var(--text-secondary)', margin: '1rem 0 2rem' }}>
              Page not found
            </p>
            <Link to="/" className="btn btn-primary">
              <Home size={18} /> Back to Home
            </Link>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default NotFound;
