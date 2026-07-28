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
  decimals?: number
}

const StatCounter = ({ end, suffix = '', label, detail, decimals }: StatCounterProps) => {
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
          setCount(decimals !== undefined ? Number(start.toFixed(decimals)) : Math.ceil(start));
        }
      }, 16);

      return () => clearInterval(timer);
    }
  }, [end, isInView, decimals]);

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
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    fetch(`${API}/api/stats`)
      .then(r => r.json())
      .then(d => setStats(d))
      .catch(() => {});
  }, []);

  const totalQueries = stats?.total_queries || 0;
  const hasData = stats && stats.total_queries > 0;

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
            {hasData ? (
              <>
                <StatCounter end={stats.green_query_pct} suffix="%" label="Queries on Green Tier" />
                <StatCounter end={stats.avg_latency_s} suffix="s" label="Average Latency" decimals={3} />
                <StatCounter end={stats.total_queries} label="Total Queries Routed" />
              </>
            ) : (
              <>
                <StatCounter end={40} suffix="%" label="CO₂ Reduction Target (Design Target)" detail="vs coal-baseline regions" />
                <StatCounter end={95} suffix="%+" label="Quality Preservation Target (Design Target)" detail="via intelligent model matching" />
                <StatCounter end={100} suffix="ms" label="Latency Overhead Target (Design Target)" detail="added by routing logic" />
              </>
            )}
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
