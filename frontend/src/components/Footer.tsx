import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Globe } from 'lucide-react';
import './Footer.css';

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-50px" },
  transition: { duration: 0.5, ease: easeFn },
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
            Building the sustainable intelligence layer for the AI-powered future.
          </p>
          <div className="social-links">
            <motion.a href="https://github.com/kathiravanagit/EcoQuery" target="_blank" rel="noopener noreferrer" aria-label="GitHub" whileHover={{ scale: 1.15, y: -3 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
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
