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
            <h2>Why we built EcoQuery</h2>
            <p>
              Large language models are powerful, but developers usually cannot see the energy or carbon impact of each request. EcoQuery was built as an AIML project to study whether query classification, local answers, and model routing can reduce unnecessary inference.
            </p>
            <p>
              Our goal is not to claim perfect carbon measurement. It is to make AI usage more visible, measurable, and easier to optimize with the data and assumptions documented in our methodology.
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
