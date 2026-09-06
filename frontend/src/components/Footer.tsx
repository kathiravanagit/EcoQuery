import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { GitBranch, Mail } from 'lucide-react';
import './Footer.css';

import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-50px" },
  transition: { duration: 0.5, ease: EASE_FN },
};

const Footer = () => {
  return (
    <motion.footer id="footer" className="footer" {...fadeUp} transition={{ ...fadeUp.transition, duration: 0.6 }}>
      <div className="container footer-container">
        <motion.div className="footer-brand" {...fadeUp}>
          <Link to="/" className="logo">
            <img src="/logo.png" alt="EcoQuery" className="logo-icon" />
          </Link>
          <p className="footer-desc">
            Carbon-aware infrastructure for production AI.
          </p>
          <div className="social-links">
            <motion.a href="https://github.com/kathiravanagit/EcoQuery" target="_blank" rel="noopener noreferrer" aria-label="GitHub" whileHover={{ scale: 1.15, y: -3 }}>
              <GitBranch size={20} aria-hidden="true" />
            </motion.a>
            <motion.a href="mailto:kathiravanawork@gmail.com" aria-label="Email Support" whileHover={{ y: -2 }}>
              <Mail size={20} />
            </motion.a>
          </div>
        </motion.div>

        <div className="footer-links">
          <motion.div className="link-group" {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.1 }}>
            <h4>Product</h4>
            <Link to="/">Home</Link>
            <Link to="/pricing">Pricing</Link>
            <a href="/Whitepaper.pdf" target="_blank" rel="noopener noreferrer">Whitepaper</a>
            <a href="#demo">Live Demo</a>
          </motion.div>
          <motion.div className="link-group" {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.2 }}>
            <h4>Company</h4>
            <Link to="/about">About Us</Link>
            <a href="#research">Research</a>
            <Link to="/contact">Contact</Link>
          </motion.div>
          <motion.div className="link-group" {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.3 }}>
            <h4>Legal</h4>
            <Link to="/privacy">Privacy Policy</Link>
            <Link to="/terms">Terms of Service</Link>
            <Link to="/cookies">Cookie Policy</Link>
          </motion.div>
        </div>
      </div>

      <motion.div className="footer-bottom" {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.4 }}>
        <div className="container">
          <p>&copy; {new Date().getFullYear()} EcoQuery Inc. All rights reserved.</p>
        </div>
      </motion.div>
    </motion.footer>
  );
};

export default Footer;
