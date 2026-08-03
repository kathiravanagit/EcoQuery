import React from 'react';
import { motion } from 'framer-motion';
import { BookOpen, ExternalLink } from 'lucide-react';
import './Research.css';

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const cardVariants = {
  initial: { opacity: 0, x: -30, scale: 0.97 },
  whileInView: { opacity: 1, x: 0, scale: 1 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

const Research = () => {
  return (
    <section id="research" className="section research-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Research & <span className="text-gradient">Transparency</span></h2>
          <p>Built on peer-reviewed methodologies for calculating AI emissions.</p>
        </motion.div>

        <div className="research-content">
          <motion.div className="research-card card" {...cardVariants}>
            <div className="card-header">
              <BookOpen className="text-accent" size={24} />
              <h3>The Literature Gap</h3>
            </div>
            <div className="card-body">
              <p>Current AI carbon estimators primarily focus on <strong>training emissions</strong>, which are a one-time sunk cost. However, the <strong>inference phase</strong> (answering user queries) is rapidly surpassing training in total energy consumption as models are deployed at scale.</p>
              <p>Most existing tools provide broad, generic estimates based on parameter count, but fail to account for:</p>
              <ul>
                <li>Real-time regional grid carbon intensity (e.g., solar abundance during the day).</li>
                <li>Dynamic model routing based on query complexity.</li>
                <li>Hardware-specific utilization rates during inference.</li>
              </ul>
            </div>
          </motion.div>

          <motion.div className="research-card card" {...cardVariants} transition={{ ...cardVariants.transition, delay: 0.2 }}>
            <div className="card-header">
              <BookOpen className="text-accent" size={24} />
              <h3>Our Methodology</h3>
            </div>
            <div className="card-body">
              <p>EcoQuery bridges this gap by implementing a highly granular, context-aware estimation and routing framework:</p>
              <ol>
                <li><strong>Complexity Classification:</strong> Using a lightweight <span className="highlight">distil-bert</span> model, we classify user intent to avoid over-provisioning compute for simple tasks.</li>
                <li><strong>Grid-Aware API:</strong> We integrate with <em>Electricity Maps API</em> to determine the live carbon intensity of data center regions.</li>
                <li><strong>Verification:</strong> An immutable ledger logs the delta between the requested model and the optimally routed model, proving verifiable CSR impact.</li>
              </ol>
              <a href="/Whitepaper.pdf" target="_blank" rel="noopener noreferrer" className="read-paper-link">Read our whitepaper <ExternalLink size={16} /></a>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
};

export default Research;
