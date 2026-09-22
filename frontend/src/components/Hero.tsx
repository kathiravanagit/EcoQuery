import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Check, Database, GitBranch, MapPin, ShieldCheck, Terminal } from 'lucide-react';
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
            the control plane<span className="text-gradient"> for sustainable AI</span>
          </motion.h1>
          
          <p className="hero-subtitle">
            EcoQuery decides whether inference is needed, selects the smallest capable model in the cleanest available region, and records evidence for every decision.
          </p>

          <motion.div className="hero-decision" variants={fadeUp}>
            <div className="decision-topline">
              <span><span className="live-dot"></span> decision trace / sample query</span>
              <span className="decision-status"><Check size={13} /> verified path</span>
            </div>
            <div className="decision-question">"Explain how REST APIs work"</div>
            <div className="decision-flow">
              <div className="decision-node">
                <Database size={16} />
                <span>Knowledge layer</span>
                <strong>matched · 96%</strong>
              </div>
              <div className="decision-arrow">→</div>
              <div className="decision-node decision-node-active">
                <GitBranch size={16} />
                <span>Inference</span>
                <strong>not needed</strong>
              </div>
              <div className="decision-arrow">→</div>
              <div className="decision-node">
                <MapPin size={16} />
                <span>Impact</span>
                <strong>0 g CO₂</strong>
              </div>
            </div>
            <div className="decision-footer">
              <span><ShieldCheck size={14} /> Evidence logged for this route</span>
              <span>zero-inference answer</span>
            </div>
          </motion.div>

          <motion.div className="hero-actions" variants={fadeUp}>
            <a href="#demo" className="btn btn-primary">
              <Terminal size={16} /> try demo
            </a>
            <a href="#how-it-works" className="btn btn-secondary">
              see the system <ArrowRight size={14} />
            </a>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
};

export default Hero;
