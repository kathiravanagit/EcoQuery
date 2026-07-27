import React, { useState, useEffect } from 'react';
import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { API_URL as API } from '../config';
import './ImpactStats.css';

interface StatCounterProps {
  end: number
  suffix?: string
  label: string
  detail?: string
}

const StatCounter = ({ end, suffix = '', label, detail }: StatCounterProps) => {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });

  useEffect(() => {
    if (isInView) {
      let start = 0;
      const duration = 2000;
      const increment = end / (duration / 16);

      const timer = setInterval(() => {
        start += increment;
        if (start >= end) {
          setCount(end);
          clearInterval(timer);
        } else {
          setCount(Math.ceil(start));
        }
      }, 16);

      return () => clearInterval(timer);
    }
  }, [end, isInView]);

  return (
    <div className="stat-item" ref={ref}>
      <div className="stat-number">
        {count}{suffix}
      </div>
      <div className="stat-label">{label}</div>
      {detail && <div className="stat-detail">{detail}</div>}
    </div>
  );
};

const ImpactStats = () => {
  const [totalQueries, setTotalQueries] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/stats`)
      .then(r => r.json())
      .then(d => setTotalQueries(d.total_queries || 0))
      .catch(() => {});
  }, []);

  return (
    <section className="section stats-section">
      <div className="container">
        <motion.div 
          className="stats-container card glass"
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <div className="stats-header">
            <h2>Target <span className="text-gradient">Impact</span></h2>
            <p>Design targets for sustainable AI routing. Real results vary by region and provider.</p>
          </div>
          
          <div className="stats-grid">
            <StatCounter end={40} suffix="%" label="CO₂ Reduction Target" detail="vs coal-baseline regions" />
            <StatCounter end={95} suffix="%+" label="Quality Preservation Target" detail="via intelligent model matching" />
            <StatCounter end={100} suffix="ms" label="Latency Overhead Target" detail="added by routing logic" />
          </div>

          {totalQueries > 0 && (
            <div className="stats-live-note">
              {totalQueries.toLocaleString()} queries routed so far
            </div>
          )}
        </motion.div>
      </div>
    </section>
  );
};

export default ImpactStats;
