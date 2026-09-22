import React from 'react';
import { motion } from 'framer-motion';
import { Brain, CloudRain, Cpu, BarChart3, Fingerprint } from 'lucide-react';
import './Features.css';

const featureList = [
  { title: 'Request classification', icon: Brain, description: 'Classifies each request to estimate the capability it needs before choosing a model.' },
  { title: 'Grid data', icon: CloudRain, description: 'Uses regional carbon-intensity data when selecting a lower-impact inference route.' },
  { title: 'Model routing', icon: Cpu, description: 'Chooses a suitable provider and model instead of defaulting to the largest available option.' },
  { title: 'Response checks', icon: Fingerprint, description: 'Records what was requested, what ran, and which response checks completed.' },
  { title: 'Usage records', icon: BarChart3, description: 'Keeps query, cost, latency, and estimated emissions data for later review.' },
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
          <p>The parts of the project that decide, estimate, and record each request.</p>
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
