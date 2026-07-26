import React from 'react';
import { motion } from 'framer-motion';
import './Pages.css';

const CookiePolicy = () => {
  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>Cookie <span className="text-gradient">Policy</span></h1>
            <p className="page-subtitle">Last updated: July 2026</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container legal-content">
          <h2>1. What Are Cookies</h2>
          <p>Cookies are small text files stored on your device by your web browser. They help us improve your experience on EcoQuery.</p>

          <h2>2. How We Use Cookies</h2>
          <p>We use essential cookies for authentication and session management. We do not use tracking cookies for advertising purposes.</p>
          <ul>
            <li><strong>Authentication cookies:</strong> Required to keep you signed in.</li>
            <li><strong>Theme preference:</strong> Stores your dark/light mode selection.</li>
          </ul>

          <h2>3. Third-Party Cookies</h2>
          <p>We use Formspree for contact form submissions. Formspree may set cookies necessary for form functionality.</p>

          <h2>4. Managing Cookies</h2>
          <p>You can control cookies through your browser settings. Disabling essential cookies may affect the functionality of the Service.</p>

          <h2>5. Changes</h2>
          <p>We may update this Cookie Policy from time to time. Continued use of the Service constitutes acceptance of any changes.</p>

          <p className="legal-date">Contact: kathiravanawork@gmail.com</p>
        </div>
      </section>
    </div>
  );
};

export default CookiePolicy;
