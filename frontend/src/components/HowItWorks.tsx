import React from 'react';
import { motion } from 'framer-motion';
import { User, Activity, Leaf, GitBranch, ShieldCheck } from 'lucide-react';
import './HowItWorks.css';

const steps = [
  { id: 1, title: 'User Request', icon: User, desc: 'Query is initiated by the application.' },
  { id: 2, title: 'Smart Classifier', icon: Activity, desc: 'Determines query complexity and model requirements.' },
  { id: 3, title: 'Carbon Estimator', icon: Leaf, desc: 'Calculates real-time grid carbon intensity.' },
  { id: 4, title: 'Intelligent Router', icon: GitBranch, desc: 'Routes to the most eco-friendly suitable model.' },
  { id: 5, title: 'Verification Engine', icon: ShieldCheck, desc: 'Audits and logs the carbon savings independently.' },
];

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: easeFn },
};

const HowItWorks = () => {
  return (
    <section id="how-it-works" className="section how-it-works-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>How <span className="text-gradient">EcoQuery</span> Works</h2>
          <p>A seamless pipeline that optimizes for both performance and sustainability.</p>
        </motion.div>

        <div className="flowchart-container">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <React.Fragment key={step.id}>
                <motion.div 
                  className="flow-step card"
                  initial={{ opacity: 0, x: -30, scale: 0.95 }}
                  whileInView={{ opacity: 1, x: 0, scale: 1 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ duration: 0.5, delay: index * 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
                >
                  <div className="step-icon-wrapper">
                    <Icon size={24} className="step-icon" />
                  </div>
                  <div className="step-content">
                    <h3>{step.title}</h3>
                    <p>{step.desc}</p>
                  </div>
                </motion.div>
                
                {index < steps.length - 1 && (
                  <motion.div 
                    className="flow-connector"
                    initial={{ height: 0, opacity: 0 }}
                    whileInView={{ height: '40px', opacity: 1 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.4, delay: index * 0.15 + 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
                  >
                    <div className="connector-line"></div>
                    <div className="connector-arrow"></div>
                  </motion.div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
