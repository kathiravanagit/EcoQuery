import React from 'react';
import { motion } from 'framer-motion';
import './Research.css';

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const Research = () => {
  return (
    <section id="research" className="section research-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Proof over <span className="text-gradient">promises</span></h2>
          <p>Every route carries its source, decision, estimate, and verification state.</p>
        </motion.div>

        <motion.div className="transparency-strip" {...fadeUp}>
          <div><span className="transparency-value">13</span><span>g CO₂/kWh</span><small>lowest reference region</small></div>
          <div><span className="transparency-value">13</span><span>regions</span><small>compared before routing</small></div>
          <div><span className="transparency-value">SHA-256</span><span>integrity hash</span><small>attached to audit records</small></div>
          <div><span className="transparency-value">0 g</span><span>when knowledge matches</span><small>inference avoided entirely</small></div>
        </motion.div>

      </div>
    </section>
  );
};

export default Research;
