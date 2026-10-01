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
            <p className="page-subtitle">Last updated: October 2026</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container legal-content">
          <h2>1. What Are Cookies</h2>
          <p>Cookies are small text files stored on your device by your web browser. They help us improve your experience on EcoQuery.</p>

          <h2>2. How We Use Cookies</h2>
          <p>We use strictly necessary storage for authentication and session management. We do not use tracking cookies for advertising or analytics purposes.</p>
          <ul>
            <li><strong>Session token:</strong> Keeps you signed in. It is written to this device's local storage when you tick &quot;Remember me&quot;, otherwise to session storage, and is removed when you sign out.</li>
            <li><strong>Remembered email address:</strong> Saved to this device only if you tick &quot;Remember me&quot; at sign-in, so you do not have to retype it.</li>
            <li><strong>Your cookie choice:</strong> The answer you give the cookie banner is stored on this device so we do not ask you again.</li>
          </ul>

          <h2>3. Third-Party Cookies</h2>
          <p>We do not embed advertising, analytics or social plugins, and we do not share your data with third parties for tracking.</p>
          <p>The one third-party origin we load is Google Fonts, which serves our typefaces; Google states that this service sets no cookies. The contact form posts to EcoQuery's own API — no third-party form service is involved.</p>

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
