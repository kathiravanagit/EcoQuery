import React from 'react';
import { motion } from 'framer-motion';
import './Pages.css';

const Privacy = () => {
  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>Privacy <span className="text-gradient">Policy</span></h1>
            <p className="page-subtitle">How we handle your data.</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="legal-content card">
            <h2>Data Collection</h2>
            <p>We collect only the data necessary to route your queries: the query text, timestamp, and selected model. We do not store query content beyond 30 days.</p>

            <h2>Carbon Data</h2>
            <p>Carbon intensity data is fetched from third-party APIs (Electricity Maps) and cached temporarily. No personally identifiable information is shared with these services.</p>

            <h2>Audit Trail</h2>
            <p>Aggregated carbon savings data may be used for platform analytics. Individual query audit logs are retained for compliance purposes only.</p>

            <h2>Third-Party Services</h2>
            <p>Queries are processed through OpenAI or OpenRouter APIs. Data handling by these providers is subject to their respective privacy policies.</p>

            <h2>Contact</h2>
            <p>For privacy-related inquiries, contact <a href="mailto:privacy@eco-query.dev" className="text-accent">privacy@eco-query.dev</a>.</p>

            <p className="legal-date">Last updated: July 2026</p>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Privacy;
