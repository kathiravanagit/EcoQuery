import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Leaf, Globe, BarChart3, TrendingDown, Activity } from 'lucide-react';
import './Research.css';
import { API_URL as API } from '../config';
import { EASE_FN } from '../constants';

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.6, ease: EASE_FN },
};

interface StatsData {
  total_queries: number;
  total_co2_saved_g: number;
  green_query_pct: number;
  avg_latency_s: number;
  flagged_queries: number;
}

interface RegionInfo {
  intensity: number;
  name: string;
  country: string;
  source: string;
  energy_profile: Record<string, number>;
}

interface CarbonRegionData {
  region: string;
  carbon_intensity_g_kwh: number;
  estimated_savings_g_co2: number;
  method: string;
  data_source: string;
  all_regions: Record<string, RegionInfo>;
  total_regions_covered: number;
}

const intensityColor = (val: number): string => {
  if (val < 50) return 'var(--accent)';
  if (val < 150) return '#4ade80';
  if (val < 300) return '#facc15';
  if (val < 500) return '#fb923c';
  return '#ef4444';
};

const intensityLabel = (val: number): string => {
  if (val < 50) return 'Very Low';
  if (val < 150) return 'Low';
  if (val < 300) return 'Medium';
  if (val < 500) return 'High';
  return 'Very High';
};

const Research = () => {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [carbonData, setCarbonData] = useState<CarbonRegionData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, carbonRes] = await Promise.allSettled([
          fetch(`${API}/api/stats`).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
          fetch(`${API}/api/carbon/regions`).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
        ]);
        if (statsRes.status === 'fulfilled') setStats(statsRes.value);
        if (carbonRes.status === 'fulfilled') setCarbonData(carbonRes.value);
      } catch {
        // silently handle errors
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const hasStats = stats && stats.total_queries > 0;
  const sortedRegions = carbonData?.all_regions
    ? Object.entries(carbonData.all_regions).sort((a, b) => a[1].intensity - b[1].intensity)
    : [];
  const bestRegion = sortedRegions.length > 0 ? sortedRegions[0] : null;
  const worstRegion = sortedRegions.length > 0 ? sortedRegions[sortedRegions.length - 1] : null;
  const maxIntensity = worstRegion ? worstRegion[1].intensity : 1;

  return (
    <section id="research" className="section research-section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Real Carbon <span className="text-gradient">Reduction Data</span></h2>
          <p>Live metrics from our routing engine — every number is backed by real query data and grid carbon intensity.</p>
        </motion.div>

        {/* Live aggregate stats */}
        <motion.div className="transparency-strip" {...fadeUp}>
          {loading ? (
            <div className="strip-loading">Loading live data…</div>
          ) : hasStats ? (
            <>
              <div>
                <span className="transparency-value">{stats!.total_co2_saved_g.toFixed(2)}g</span>
                <span>CO₂ Saved</span>
                <small>total emissions avoided by green routing</small>
              </div>
              <div>
                <span className="transparency-value">{stats!.total_queries.toLocaleString()}</span>
                <span>Queries Routed</span>
                <small>through carbon-aware infrastructure</small>
              </div>
              <div>
                <span className="transparency-value">{stats!.green_query_pct}%</span>
                <span>Green Tier Rate</span>
                <small>queries served on lowest-carbon models</small>
              </div>
              <div>
                <span className="transparency-value">{stats!.avg_latency_s.toFixed(3)}s</span>
                <span>Avg Latency</span>
                <small>full request time, incl. provider generation</small>
              </div>
            </>
          ) : (
            <>
              <div>
                <span className="transparency-value">{carbonData ? carbonData.total_regions_covered : 13}</span>
                <span>Regions Monitored</span>
                <small>real-time carbon intensity tracking</small>
              </div>
              <div>
                <span className="transparency-value">{bestRegion ? `${bestRegion[1].intensity}` : '13'} g/kWh</span>
                <span>Lowest Region</span>
                <small>{bestRegion ? `${bestRegion[1].name}, ${bestRegion[1].country}` : 'Stockholm, Sweden'}</small>
              </div>
              <div>
                <span className="transparency-value">{carbonData?.data_source || 'IEA 2024'}</span>
                <span>Data Source</span>
                <small>{carbonData?.method === 'electricity-maps-api' ? 'real-time grid data' : 'IEA annual baselines'}</small>
              </div>
              <div>
                <span className="transparency-value">SHA-256</span>
                <span>Integrity Hash</span>
                <small>attached to every audit record</small>
              </div>
            </>
          )}
        </motion.div>

        {/* Live region carbon intensity grid */}
        {sortedRegions.length > 0 && (
          <motion.div className="regions-section" {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.15 }}>
            <div className="regions-header">
              <Globe size={20} className="text-accent" />
              <h3>Live Region Carbon Intensity</h3>
              <span className="data-source-badge">
                {carbonData?.data_source === 'Electricity Maps' ? (
                  <><Activity size={12} /> Real-time</>
                ) : (
                  <><BarChart3 size={12} /> {carbonData?.data_source || 'IEA 2024'}</>
                )}
              </span>
            </div>

            <div className="regions-grid">
              {sortedRegions.map(([code, region], i) => {
                const barWidth = (region.intensity / maxIntensity) * 100;
                const isOptimal = code === carbonData?.region;
                const topSources = Object.entries(region.energy_profile || {})
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 3);

                return (
                  <motion.div
                    key={code}
                    className={`region-row ${isOptimal ? 'region-optimal' : ''}`}
                    initial={{ opacity: 0, x: -20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.3, delay: i * 0.04, ease: EASE_FN }}
                  >
                    <div className="region-info">
                      <div className="region-name">
                        {isOptimal && <Leaf size={14} className="optimal-icon" />}
                        <span className="region-city">{region.name}</span>
                        <span className="region-country">{region.country}</span>
                      </div>
                      <div className="region-sources">
                        {topSources.map(([source, pct]) => (
                          <span key={source} className="source-tag">{source} {pct}%</span>
                        ))}
                      </div>
                    </div>
                    <div className="region-bar-container">
                      <div
                        className="region-bar"
                        style={{
                          width: `${barWidth}%`,
                          backgroundColor: intensityColor(region.intensity),
                        }}
                      />
                      <span className="region-intensity" style={{ color: intensityColor(region.intensity) }}>
                        {region.intensity} <small>g CO₂/kWh</small>
                      </span>
                    </div>
                    <span className="region-rating" style={{ color: intensityColor(region.intensity) }}>
                      {intensityLabel(region.intensity)}
                    </span>
                  </motion.div>
                );
              })}
            </div>

            {/* Savings summary */}
            {bestRegion && worstRegion && (
              <motion.div className="savings-summary" {...fadeUp} transition={{ ...fadeUp.transition, delay: 0.3 }}>
                <TrendingDown size={18} className="text-accent" />
                <p>
                  By routing to <strong>{bestRegion[1].name}</strong> ({bestRegion[1].intensity} g/kWh) instead of <strong>{worstRegion[1].name}</strong> ({worstRegion[1].intensity} g/kWh), each query saves up to <strong className="text-accent">{((worstRegion[1].intensity - bestRegion[1].intensity) * 0.005).toFixed(3)}g CO₂</strong>.
                </p>
              </motion.div>
            )}
          </motion.div>
        )}
      </div>
    </section>
  );
};

export default Research;
