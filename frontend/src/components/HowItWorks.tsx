import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { User, Activity, Leaf, GitBranch, ShieldCheck, BarChart3, Globe } from 'lucide-react';
import { API_URL } from '../config';
import './HowItWorks.css';

const steps = [
  { 
    id: 1, title: 'User Request', icon: User, 
    desc: 'Query is initiated by the application.',
    detail: 'Supported: text, code, analysis, creative writing, and more.',
  },
  { 
    id: 2, title: 'Compute Sufficiency', icon: Activity,
    desc: 'Determines query complexity and model requirements.',
    detail: 'Trained classifier with ML fallback and simple heuristic rules for reliability.',
  },
  { 
    id: 3, title: 'Grid Intelligence', icon: Leaf,
    desc: 'Calculates real-time grid carbon intensity across 13 regions.',
    detail: 'Electricity Maps API + IEA static baselines for fallback.',
  },
  { 
    id: 4, title: 'Green Route Control', icon: GitBranch,
    desc: 'Routes to the most eco-friendly suitable model.',
    detail: 'Always carbon-first. Picks greenest provider based on real-time data.',
  },
  { 
    id: 5, title: 'Model Integrity Proof', icon: ShieldCheck,
    desc: 'Audits and logs the carbon savings independently.',
    detail: 'TPS analysis, latency verification, SHA-256 integrity hashes.',
  },
  { 
    id: 6, title: 'Impact Ledger', icon: BarChart3,
    desc: 'Tracks cumulative environmental impact in real-time.',
    detail: 'CO₂ equivalents, cost savings, gamification badges, ESG reports.',
  },
];

// Last-known values, used only if /api/carbon/regions is unreachable so the
// section still renders. The component labels this state explicitly rather
// than presenting the numbers as live.
const fallbackRegions = [
  { name: 'Stockholm', intensity: 34, source: 'Hydro/Wind/Solar' },
  { name: 'Paris', intensity: 35, source: 'Nuclear' },
  { name: 'São Paulo', intensity: 75, source: 'Hydro' },
  { name: 'Oregon', intensity: 80, source: 'Hydro/Wind' },
  { name: 'London', intensity: 212, source: 'Gas/Wind' },
  { name: 'Frankfurt', intensity: 380, source: 'Coal/Gas' },
  { name: 'N. Virginia', intensity: 380, source: 'Gas/Coal' },
];

interface LiveRegion {
  intensity: number;
  name: string;
  source?: string;
  country?: string;
}

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const HowItWorks = () => {
  const [regions, setRegions] = useState(() => fallbackRegions);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/carbon/regions`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        const all = data?.all_regions as Record<string, LiveRegion> | undefined;
        if (cancelled || !all) return;
        const rows = Object.values(all)
          .filter(r => r && typeof r.intensity === 'number')
          .sort((a, b) => a.intensity - b.intensity)
          .map(r => ({ name: r.name, intensity: r.intensity, source: r.source ?? 'Grid' }));
        if (rows.length) {
          setRegions(rows);
          setLive(true);
        }
      })
      .catch(() => { /* keep fallback values and the static-data label */ });
    return () => { cancelled = true; };
  }, []);

  const maxIntensity = Math.max(...regions.map(r => r.intensity), 1);
  return (
    <section id="how-it-works" className="section how-it-works-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>How <span className="text-gradient">EcoQuery</span> Works</h2>
          <p>Every request becomes a measurable routing decision, from capability to carbon evidence.</p>
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
            <h3 style={{ margin: 0 }}>Try It Now</h3>
          </div>
          <div style={{
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
            padding: '1.5rem', maxWidth: 600, margin: '0 auto',
          }}>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem', textAlign: 'center' }}>
              Carbon-aware routing via a single API call.
            </p>
            <pre style={{
              background: '#0a0a0a', color: 'var(--accent)', padding: '1rem',
              borderRadius: '8px', fontSize: '0.75rem', overflow: 'auto',
              border: '1px solid var(--border)', lineHeight: 1.6,
            }}>
{`curl -X POST https://ecoquery.onrender.com/api/chat \\
  -H "Authorization: Bearer eq_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Explain quantum computing"}'`}
            </pre>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.75rem', textAlign: 'center' }}>
              Response includes model routing, CO₂ savings, region, and verification status.
            </p>
          </div>
        </motion.div>

        <motion.div {...fadeUp} style={{ marginTop: '3rem' }}>
          <div style={{ 
            background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
            padding: '1.5rem', maxWidth: 600, margin: '0 auto',
          }}>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem', textAlign: 'center' }}>
              {live
                ? 'Live grid carbon intensity (g CO₂/kWh) across regions. Lower is greener.'
                : 'Latest cached grid carbon intensity (g CO₂/kWh) — live feed unavailable.'}
            </p>
            {regions.map((r, i) => (
              <motion.div key={r.name} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }} transition={{ delay: i * 0.08 }}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', fontSize: '0.8rem' }}
              >
                <span style={{ width: 80, color: 'var(--text-secondary)' }}>{r.name}</span>
                <div style={{ flex: 1, height: 8, background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'hidden' }}>
                  <motion.div 
                    initial={{ width: 0 }}
                    whileInView={{ width: `${Math.round((r.intensity / maxIntensity) * 100)}%` }}
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
