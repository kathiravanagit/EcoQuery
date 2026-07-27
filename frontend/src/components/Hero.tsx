import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Play, Shield, Leaf, Zap, TreePine, Car, Lightbulb } from 'lucide-react';
import './Hero.css';

const stagger = {
  animate: { transition: { staggerChildren: 0.12, delayChildren: 0.1 } },
};

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.7, ease: easeFn } },
};

const fadeScale = {
  initial: { opacity: 0, scale: 0.8 },
  animate: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: easeFn } },
};

const co2Equivalents = [
  { icon: <TreePine size={16} />, value: "12.5", unit: "trees", label: "CO₂ absorption target", color: "#00d46a" },
  { icon: <Car size={16} />, value: "50", unit: "km", label: "Driving distance target", color: "#3b82f6" },
  { icon: <Lightbulb size={16} />, value: "1,250", unit: "hours", label: "LED runtime target", color: "#f59e0b" },
];

const heroStats = [
  { value: "13", label: "Regions tracked" },
  { value: "15", label: "Models available" },
  { value: "8", label: "Gamification badges" },
];

const featureCards = [
  { icon: <Leaf size={20} />, title: "Carbon-Aware Routing", desc: "Routes through greenest data center in real-time across 13 regions", color: "#00d46a" },
  { icon: <Shield size={20} />, title: "Integrity Verification", desc: "Detects model substitution with TPS-based analysis + SHA-256 hashing", color: "#3b82f6" },
  { icon: <Zap size={20} />, title: "Eco & Performance Modes", desc: "Choose carbon-first or latency-first routing", color: "#f59e0b" },
];

const Hero = () => {
  return (
    <section id="home" className="hero-section">
      <div className="hero-bg">
        <div className="globe-container">
          <div className="globe"></div>
          <div className="flow-lines">
            <div className="line line-1"></div>
            <div className="line line-2"></div>
            <div className="line line-3"></div>
          </div>
        </div>
      </div>

      <div className="container hero-container">
        <motion.div 
          className="hero-content"
          variants={stagger}
          initial="initial"
          animate="animate"
        >
          <motion.div className="badge" variants={fadeScale}>
            <span className="badge-dot"></span>
            EcoQuery v2.0 is live
          </motion.div>
          
          <motion.h1 className="hero-title" variants={fadeUp}>
            Make Every LLM Call <span className="text-gradient">Greener</span>
          </motion.h1>
          
          <motion.p className="hero-subtitle" variants={fadeUp}>
            Intelligent routing + independent verification for lower carbon footprint without sacrificing quality.
          </motion.p>

          <motion.p variants={fadeUp} style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '-0.5rem', marginBottom: '0.75rem', textAlign: 'center', fontStyle: 'italic' }}>
            Carbon targets based on IEA 2024 averages. Numbers are estimates, not measured real-time data.
          </motion.p>

          <motion.div variants={fadeUp} style={{ 
            display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center',
            marginBottom: '1.5rem', padding: '12px 16px', borderRadius: '12px',
            background: 'rgba(0, 212, 106, 0.05)', border: '1px solid rgba(0, 212, 106, 0.15)',
          }}>
            {co2Equivalents.map((eq, i) => (
              <motion.div key={i} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} 
                transition={{ delay: 0.6 + i * 0.1 }}
                style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
              >
                <span style={{ color: eq.color }}>{eq.icon}</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{eq.value} {eq.unit}</span>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.65rem' }}>{eq.label}</span>
              </motion.div>
            ))}
          </motion.div>

          <motion.div variants={fadeUp} style={{ 
            display: 'flex', gap: '12px', flexWrap: 'wrap', justifyContent: 'center',
            marginBottom: '1.5rem', padding: '12px 16px', borderRadius: '12px',
            background: 'rgba(59, 130, 246, 0.05)', border: '1px solid rgba(59, 130, 246, 0.15)',
          }}>
            {heroStats.map((s, i) => (
              <motion.div key={i} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} 
                transition={{ delay: 0.75 + i * 0.1 }}
                style={{ textAlign: 'center' }}
              >
                <span style={{ fontWeight: 700, fontSize: '1.25rem', color: '#3b82f6' }}>{s.value}</span>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>{s.label}</div>
              </motion.div>
            ))}
          </motion.div>
          
          <motion.div className="hero-actions" variants={fadeUp}>
            <a href="#demo" className="btn btn-primary">
              Try Demo <ArrowRight size={18} />
            </a>
            <a href="#how-it-works" className="btn btn-secondary">
              <Play size={18} /> Learn How It Works
            </a>
          </motion.div>

          <motion.div variants={fadeUp} style={{ display: 'flex', gap: '16px', marginTop: '2rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            {featureCards.map((f, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 + i * 0.15 }}
                style={{
                  background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
                  padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '10px',
                  fontSize: '0.8rem', minWidth: 200,
                }}
              >
                <div style={{ color: f.color }}>{f.icon}</div>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{f.title}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{f.desc}</div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
