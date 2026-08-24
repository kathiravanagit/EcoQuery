import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Terminal } from 'lucide-react';
import './Hero.css';
import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE_FN } },
};

const Hero = () => {
  const [typedText, setTypedText] = useState('');
  const fullText = 'ecoquery --route --greenest';

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      if (i <= fullText.length) {
        setTypedText(fullText.slice(0, i));
        i++;
      } else {
        clearInterval(timer);
      }
    }, 50);
    return () => clearInterval(timer);
  }, []);

  return (
    <section id="home" className="hero-section scanlines">
      <div className="hero-bg"></div>

      <div className="container hero-container">
        <motion.div 
          className="hero-content"
          initial="initial"
          animate="animate"
          variants={{ animate: { transition: { staggerChildren: 0.1, delayChildren: 0.1 } } }}
        >
          <motion.div className="badge" variants={{ initial: { opacity: 0, scale: 0.95 }, animate: { opacity: 1, scale: 1, transition: { duration: 0.4 } } }}>
            <span className="badge-dot"></span>
            {typedText}<span className="cursor-blink">|</span>
          </motion.div>
          
          <motion.h1 className="hero-title" variants={fadeUp}>
            route queries<span className="text-gradient"> greener</span>
          </motion.h1>
          
          <p className="hero-subtitle">
            carbon-aware llm routing + independent verification for lower emissions without sacrificing quality.
          </p>

          <motion.div className="hero-actions" variants={fadeUp}>
            <a href="#demo" className="btn btn-primary">
              <Terminal size={16} /> try demo
            </a>
            <a href="#how-it-works" className="btn btn-secondary">
              read docs <ArrowRight size={14} />
            </a>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
