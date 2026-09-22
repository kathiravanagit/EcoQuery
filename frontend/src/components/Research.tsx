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
          <h2>What we <span className="text-gradient">measure</span></h2>
          <p>The dashboard reports routing evidence and estimates, with the assumptions documented in the methodology.</p>
        </motion.div>

        <motion.div className="transparency-strip" {...fadeUp}>
          <div><span className="transparency-value">13</span><span>g CO₂/kWh</span><small>lowest reference intensity</small></div>
          <div><span className="transparency-value">13</span><span>regions</span><small>reference data used for routing</small></div>
          <div><span className="transparency-value">SHA-256</span><span>record hash</span><small>helps detect audit changes</small></div>
          <div><span className="transparency-value">0 g</span><span>estimated impact</span><small>when a local answer avoids inference</small></div>
        </motion.div>

        <motion.div className="research-limitations" {...fadeUp}>
          <div>
            <h3>What EcoQuery does not claim</h3>
            <ul>
              <li>It does not directly measure GPU electricity for every request.</li>
              <li>It cannot guarantee the physical data center used by an external provider.</li>
              <li>CO₂ values are estimates based on tokens, model assumptions, and regional intensity.</li>
              <li>A hash shows whether our audit record changed; it does not prove hidden provider execution details.</li>
            </ul>
          </div>
          <div className="research-links">
            <a href="/Whitepaper.pdf" target="_blank" rel="noopener noreferrer">Read the whitepaper</a>
            <a href="https://github.com/kathiravanagit/EcoQuery/blob/main/docs/METHODOLOGY.md" target="_blank" rel="noopener noreferrer">View the methodology</a>
            <a href="https://github.com/kathiravanagit/EcoQuery/blob/main/docs/EVALUATION.md" target="_blank" rel="noopener noreferrer">View the evaluation</a>
          </div>
        </motion.div>

      </div>
    </section>
  );
};

export default Research;
