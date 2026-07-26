import React from 'react';
import { motion } from 'framer-motion';
import { Leaf, Target, Users, TrendingUp } from 'lucide-react';
import './Pages.css';

const About = () => {
  const values = [
    { icon: Leaf, title: 'Sustainability First', desc: 'Every query routed to minimize carbon impact without compromising quality.' },
    { icon: Target, title: 'Radical Transparency', desc: 'Open-source methodology and verifiable audit trails for every decision.' },
    { icon: Users, title: 'Developer-Centric', desc: 'Simple API integration that works with your existing LLM infrastructure.' },
    { icon: TrendingUp, title: 'Continuous Improvement', desc: 'Models and routing algorithms improve over time as grid data evolves.' },
  ];

  return (
    <div className="page">
      <section className="page-hero">
        <div className="container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <h1>About <span className="text-gradient">EcoQuery</span></h1>
            <p className="page-subtitle">Building the sustainable intelligence layer for AI.</p>
          </motion.div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="about-story card">
            <h2>Our Mission</h2>
            <p>
              AI inference is projected to consume more energy than training by 2027. Yet most optimization tools focus only on the training phase. EcoQuery was built to close this gap—intelligently routing queries to the most carbon-efficient model and region in real-time.
            </p>
            <p>
              Founded on peer-reviewed research, we provide the first verifiable, real-time carbon-aware routing layer for LLM inference.
            </p>
          </div>

          <div className="values-grid">
            {values.map((v, i) => {
              const Icon = v.icon;
              return (
                <motion.div
                  key={i}
                  className="value-card card"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1 }}
                >
                  <Icon size={28} className="text-accent" />
                  <h3>{v.title}</h3>
                  <p>{v.desc}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
};

export default About;
