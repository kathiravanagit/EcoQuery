import React from 'react';
import { motion } from 'framer-motion';
import './Pages.css';

const Terms = () => {
  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>Terms of <span className="text-gradient">Service</span></h1>
            <p className="page-subtitle">Last updated: July 2026</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container legal-content">
          <h2>1. Acceptance of Terms</h2>
          <p>By accessing or using EcoQuery ("the Service"), you agree to be bound by these Terms of Service. If you do not agree, please do not use the Service.</p>

          <h2>2. Description of Service</h2>
          <p>EcoQuery provides carbon-aware AI query routing and optimization. We route queries through various LLM providers and log carbon savings for audit purposes.</p>

          <h2>3. User Responsibilities</h2>
          <p>You agree to use the Service in compliance with all applicable laws. You are responsible for maintaining the confidentiality of your account credentials.</p>

          <h2>4. API Usage</h2>
          <p>API keys are provided for authorized users only. You may not share, distribute, or sell access to the Service without express written permission.</p>

          <h2>5. Limitation of Liability</h2>
          <p>EcoQuery is provided "as is" without warranties of any kind. We are not liable for damages arising from use of the Service.</p>

          <h2>6. Changes</h2>
          <p>We reserve the right to modify these terms at any time. Users will be notified of material changes.</p>

          <p className="legal-date">Contact: kathiravanawork@gmail.com</p>
        </div>
      </section>
    </div>
  );
};

export default Terms;
