import React from 'react';
import { motion } from 'framer-motion';
import { Brain, CloudRain, Cpu, BarChart3, Fingerprint } from 'lucide-react';
import './Features.css';

const featureList = [
  { title: 'Smart Classifier', icon: Brain, description: 'Automatically analyzes query complexity to determine the minimal LLM capability required for high-quality results.' },
  { title: 'Carbon Estimator', icon: CloudRain, description: 'Connects to real-time grid intensity data to estimate the carbon footprint of executing a query in different regions.' },
  { title: 'Intelligent Router', icon: Cpu, description: 'Dynamically routes queries to models running in data centers with the highest renewable energy mix.' },
  { title: 'Verification Engine', icon: Fingerprint, description: 'Maintains an immutable audit trail of carbon savings for CSR reporting and compliance.' },
  { title: 'Live Dashboard', icon: BarChart3, description: 'Provides deep visibility into your organization\'s LLM usage, cost savings, and emissions avoided.' },
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
