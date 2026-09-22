import React from 'react';
import { motion } from 'framer-motion';
import { Brain, CloudRain, Cpu, BarChart3, Fingerprint } from 'lucide-react';
import './Features.css';

const featureList = [
  { title: 'Compute Sufficiency Engine', icon: Brain, description: 'Classifies each request to determine the smallest capability that can answer it well.' },
  { title: 'Live Grid Intelligence', icon: CloudRain, description: 'Reads regional carbon intensity so routing reflects the grid actually powering inference.' },
  { title: 'Green Route Control', icon: Cpu, description: 'Chooses the cleanest capable provider and region instead of defaulting to the largest model.' },
  { title: 'Model Integrity Proof', icon: Fingerprint, description: 'Records what was requested, what ran, and whether the response passed verification.' },
  { title: 'Impact Ledger', icon: BarChart3, description: 'Turns routing decisions into auditable usage, cost, and emissions evidence for teams.' },
];

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const cardVariant = {
  initial: { opacity: 0, y: 40, scale: 0.95 },
  whileInView: { opacity: 1, y: 0, scale: 1 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.5, ease: EASE_FN },
};

const Features = () => {
  return (
    <section id="features" className="section features-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Platform <span className="text-gradient">Features</span></h2>
          <p>Everything you need to minimize your AI infrastructure footprint.</p>
        </motion.div>

        <div className="features-grid">
          {featureList.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={index}
                className="feature-card card"
                {...cardVariant}
                transition={{ ...cardVariant.transition, delay: index * 0.08 }}
              >
                <div className="feature-icon"><Icon size={28} /></div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default Features;
