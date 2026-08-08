import React from 'react';
import { motion } from 'framer-motion';
import { User, Activity, Leaf, GitBranch, ShieldCheck, BarChart3, Globe } from 'lucide-react';
import './HowItWorks.css';

const steps = [
  { 
    id: 1, title: 'User Request', icon: User, 
    desc: 'Query is initiated by the application.',
    detail: 'Supported: text, code, analysis, creative writing, and more.',
  },
  { 
    id: 2, title: 'Smart Classifier', icon: Activity, 
    desc: 'Determines query complexity and model requirements.',
    detail: 'GPT-4o-mini powered classifier understands context, not just keywords.',
  },
  { 
    id: 3, title: 'Carbon Estimator', icon: Leaf, 
    desc: 'Calculates real-time grid carbon intensity across 13 regions.',
    detail: 'Electricity Maps API + IEA static baselines for fallback.',
  },
  { 
    id: 4, title: 'Intelligent Router', icon: GitBranch, 
    desc: 'Routes to the most eco-friendly suitable model.',
    detail: 'Always carbon-first. Picks greenest provider based on real-time data.',
  },
  { 
    id: 5, title: 'Verification Engine', icon: ShieldCheck, 
    desc: 'Audits and logs the carbon savings independently.',
    detail: 'TPS analysis, latency verification, SHA-256 integrity hashes.',
  },
  { 
    id: 6, title: 'Impact Dashboard', icon: BarChart3, 
    desc: 'Tracks cumulative environmental impact in real-time.',
    detail: 'CO₂ equivalents, cost savings, gamification badges, ESG reports.',
  },
];

const regionData = [
  { name: 'Stockholm', intensity: 13, source: 'Hydro/Wind', pct: 3 },
  { name: 'Paris', intensity: 56, source: 'Nuclear', pct: 12 },
  { name: 'São Paulo', intensity: 75, source: 'Hydro', pct: 16 },
  { name: 'Oregon', intensity: 80, source: 'Hydro/Wind', pct: 17 },
  { name: 'London', intensity: 220, source: 'Gas/Wind', pct: 46 },
  { name: 'Frankfurt', intensity: 350, source: 'Coal/Gas', pct: 74 },
  { name: 'Virginia', intensity: 380, source: 'Gas/Coal', pct: 80 },
];

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const HowItWorks = () => {
  return (
    <section id="how-it-works" className="section how-it-works-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>How <span className="text-gradient">EcoQuery</span> Works</h2>
          <p>A seamless pipeline that optimizes for both performance and sustainability.</p>
        </motion.div>

        <div className="flowchart-container">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <React.Fragment key={step.id}>
                <motion.div 
                  className="flow-step card"
                  initial={{ opacity: 0, x: -30, scale: 0.95 }}
                  whileInView={{ opacity: 1, x: 0, scale: 1 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ duration: 0.5, delay: index * 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
                >
                  <div className="step-icon-wrapper">
                    <Icon size={24} className="step-icon" />
                  </div>
                  <div className="step-content">
                    <h3>{step.title}</h3>
                    <p>{step.desc}</p>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>{step.detail}</p>
                  </div>
                </motion.div>
                
                {index < steps.length - 1 && (
                  <motion.div 
                    className="flow-connector"
                    initial={{ height: 0, opacity: 0 }}
                    whileInView={{ height: '40px', opacity: 1 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.4, delay: index * 0.15 + 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
                  >
                    <div className="connector-line"></div>
                    <div className="connector-arrow"></div>
                  </motion.div>
                )}
              </React.Fragment>
            );
          })}
        </div>

        <motion.div {...fadeUp} style={{ marginTop: '3rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem', justifyContent: 'center' }}>
            <Globe size={20} style={{ color: 'var(--accent)' }} />
            <h3 style={{ margin: 0 }}>Drop-In OpenAI Replacement</h3>
          </div>
          <div style={{
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
            padding: '1.5rem', maxWidth: 600, margin: '0 auto',
          }}>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem', textAlign: 'center' }}>
              Change one line. Your queries are now carbon-aware.
            </p>
            <pre style={{
              background: '#0a0a0a', color: 'var(--accent)', padding: '1rem',
              borderRadius: '8px', fontSize: '0.75rem', overflow: 'auto',
              border: '1px solid var(--border)', lineHeight: 1.6,
            }}>
{`# Before
client = OpenAI(api_key="sk-...")

# After — just change the base URL
client = OpenAI(
    api_key="eq_your_ecoquery_key",
    base_url="https://api.ecoquery.ai/v1"
)

# That's it. Every query is now carbon-optimized.`}
            </pre>
          </div>
        </motion.div>

        <motion.div {...fadeUp} style={{ marginTop: '3rem' }}>
          <div style={{ 
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
            padding: '1.5rem', maxWidth: 600, margin: '0 auto',
          }}>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem', textAlign: 'center' }}>
              Real-time carbon intensity (g CO₂/kWh) across regions — lower is greener
            </p>
            {regionData.map((r, i) => (
              <motion.div key={r.name} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }} transition={{ delay: i * 0.08 }}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', fontSize: '0.8rem' }}
              >
                <span style={{ width: 80, color: 'var(--text-secondary)' }}>{r.name}</span>
                <div style={{ flex: 1, height: 8, background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'hidden' }}>
                  <motion.div 
                    initial={{ width: 0 }}
                    whileInView={{ width: `${r.pct}%` }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8, delay: i * 0.08 }}
                    style={{ 
                      height: '100%', borderRadius: 4,
                      background: r.intensity < 100 ? 'var(--color-success)' : r.intensity < 250 ? 'var(--color-warning)' : 'var(--color-error)',
                    }}
                  />
                </div>
                <span style={{ width: 40, textAlign: 'right', fontWeight: 600, color: r.intensity < 100 ? 'var(--color-success)' : r.intensity < 250 ? 'var(--color-warning)' : 'var(--color-error)' }}>
                  {r.intensity}
                </span>
                <span style={{ width: 80, color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{r.source}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default HowItWorks;
