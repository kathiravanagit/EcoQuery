import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Terminal } from 'lucide-react';
import './Hero.css';
import { API_URL as API } from '../config';

import { EASE_FN } from '../constants';

interface HeroStats {
  total_queries: number;
  total_co2_saved_g: number;
  green_query_pct: number;
}

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE_FN } },
};

const Hero = () => {
  const [stats, setStats] = useState<HeroStats | null>(null);
  const [typedText, setTypedText] = useState('');
  const fullText = 'ecoquery --route --greenest';

  useEffect(() => {
    fetch(`${API}/api/stats`)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(d => setStats(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      if (i <= fullText.length) {
        setTypedText(fullText.slice(0, i));
        i++;
      } else {
        clearInterval(timer);
      }
    }, 50);
    return () => clearInterval(timer);
  }, []);

  return (
    <section id="home" className="hero-section scanlines">
      <div className="hero-bg"></div>

      <div className="container hero-container">
        <motion.div 
          className="hero-content"
          initial="initial"
          animate="animate"
          variants={{ animate: { transition: { staggerChildren: 0.1, delayChildren: 0.1 } } }}
        >
          <motion.div className="badge" variants={{ initial: { opacity: 0, scale: 0.95 }, animate: { opacity: 1, scale: 1, transition: { duration: 0.4 } } }}>
            <span className="badge-dot"></span>
            {typedText}<span className="cursor-blink">|</span>
          </motion.div>
          
          <motion.h1 className="hero-title" variants={fadeUp}>
            route queries<span className="text-gradient"> greener</span>
          </motion.h1>
          
          <p className="hero-subtitle">
            carbon-aware llm routing + independent verification for lower emissions without sacrificing quality.
          </p>

          {stats && stats.total_queries > 0 && (
            <motion.div className="hero-stats-bar" variants={fadeUp}>
              <span className="hero-stat-item"><span className="value">{stats.total_queries}</span> queries</span>
              <span className="hero-stat-dot"></span>
              <span className="hero-stat-item"><span className="value">{stats.total_co2_saved_g}g</span> co2 saved</span>
              <span className="hero-stat-dot"></span>
              <span className="hero-stat-item"><span className="value">{stats.green_query_pct}%</span> green</span>
            </motion.div>
          )}

          <motion.div className="hero-actions" variants={fadeUp}>
            <a href="#demo" className="btn btn-primary">
              <Terminal size={16} /> try demo
            </a>
            <a href="#how-it-works" className="btn btn-secondary">
              read docs <ArrowRight size={14} />
            </a>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
