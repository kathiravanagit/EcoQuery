import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { API_URL as API } from '../config';
import './WorldMap.css';

interface Region {
  intensity: number;
  name: string;
  country: string;
  source: string;
  energy_profile: Record<string, number>;
}

interface CarbonRegionsResponse {
  all_regions: Record<string, Region>;
}

const REGIONS_ON_MAP: { code: string; x: number; y: number; name: string }[] = [
  { code: 'eu-west-1', x: 48, y: 35, name: 'Ireland' },
  { code: 'eu-west-2', x: 50, y: 33, name: 'London' },
  { code: 'eu-west-3', x: 50, y: 36, name: 'Paris' },
  { code: 'eu-central-1', x: 53, y: 34, name: 'Frankfurt' },
  { code: 'eu-north-1', x: 54, y: 28, name: 'Stockholm' },
  { code: 'us-east-1', x: 25, y: 38, name: 'N. Virginia' },
  { code: 'us-west-1', x: 15, y: 38, name: 'N. California' },
  { code: 'us-west-2', x: 18, y: 32, name: 'Oregon' },
];

function getColor(intensity: number): string {
  if (intensity < 150) return '#00d46a';
  if (intensity < 300) return '#22c55e';
  if (intensity < 450) return '#eab308';
  if (intensity < 600) return '#f97316';
  return '#ef4444';
}

function getLabel(intensity: number): string {
  if (intensity < 150) return 'Very Low';
  if (intensity < 300) return 'Low';
  if (intensity < 450) return 'Medium';
  if (intensity < 600) return 'High';
  return 'Very High';
}

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const WorldMap = () => {
  const [regions, setRegions] = useState<Record<string, Region>>({});
  const [hovered, setHovered] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/api/carbon/regions`)
      .then(r => r.json())
      .then((d: CarbonRegionsResponse) => setRegions(d.all_regions || {}))
      .catch(() => {});
  }, []);

  return (
    <section className="worldmap-section section">
      <div className="container">
        <motion.div
          className="section-header"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: easeFn }}
        >
          <h2>Carbon-Free <span className="text-gradient">Regions</span></h2>
          <p>Low-carbon data centers powered by renewable energy</p>
        </motion.div>

        <motion.div
          className="worldmap-container"
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: easeFn }}
        >
          <svg viewBox="0 0 100 70" className="worldmap-svg">
            <defs>
              <radialGradient id="dotGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.8" />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Simplified world map paths */}
            <g className="worldmap-land" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.1)" strokeWidth="0.15">
              {/* North America */}
              <path d="M10,25 L28,22 L32,28 L30,38 L25,42 L18,45 L12,40 L8,32 Z" />
              {/* South America */}
              <path d="M22,48 L28,46 L30,52 L28,62 L24,65 L20,60 L19,52 Z" />
              {/* Europe */}
              <path d="M46,28 L55,26 L58,30 L56,38 L50,40 L46,36 Z" />
              {/* Africa */}
              <path d="M48,42 L56,40 L60,45 L58,58 L52,62 L46,55 L45,46 Z" />
              {/* Asia */}
              <path d="M58,22 L75,20 L82,25 L85,35 L80,42 L70,45 L62,40 L58,32 Z" />
              {/* Australia */}
              <path d="M76,52 L86,50 L88,56 L84,60 L78,58 Z" />
            </g>

            {/* Grid lines */}
            <g className="worldmap-grid" stroke="rgba(255,255,255,0.03)" strokeWidth="0.1">
              {[10, 20, 30, 40, 50, 60].map(y => (
                <line key={`h${y}`} x1="0" y1={y} x2="100" y2={y} />
              ))}
              {[20, 40, 60, 80].map(x => (
                <line key={`v${x}`} x1={x} y1="0" x2={x} y2="70" />
              ))}
            </g>

            {/* Region dots */}
            {REGIONS_ON_MAP.map((r) => {
              const data = regions[r.code];
              const intensity = data?.intensity ?? 0;
              const color = getColor(intensity);
              const isHovered = hovered === r.code;

              return (
                <g
                  key={r.code}
                  className="worldmap-region"
                  onMouseEnter={() => setHovered(r.code)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <circle cx={r.x} cy={r.y} r={isHovered ? 2.5 : 1.8} fill={color} opacity={0.3}>
                    <animate attributeName="r" values={isHovered ? "2.5;3.5;2.5" : "1.8;2.2;1.8"} dur="3s" repeatCount="indefinite" />
                  </circle>
                  <circle cx={r.x} cy={r.y} r={isHovered ? 1.2 : 0.8} fill={color} />
                  {data && (
                    <text x={r.x} y={r.y - 3} textAnchor="middle" className="worldmap-label" fontSize="1.6" fill="var(--text-primary)" opacity={isHovered ? 1 : 0}>
                      {r.name}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Tooltip */}
          {hovered && regions[hovered] && (
            <div className="worldmap-tooltip">
              <div className="worldmap-tooltip-header">
                <span className="worldmap-tooltip-dot" style={{ background: getColor(regions[hovered].intensity) }}></span>
                <strong>{regions[hovered].name}</strong>
              </div>
              <div className="worldmap-tooltip-row">
                <span>{regions[hovered].intensity} g/kWh</span>
                <span className="worldmap-tooltip-label">{getLabel(regions[hovered].intensity)}</span>
              </div>
              <div className="worldmap-tooltip-row">
                <span>{regions[hovered].source}</span>
              </div>
            </div>
          )}
        </motion.div>

        {/* Legend */}
        <div className="worldmap-legend">
          <span className="worldmap-legend-item"><span className="worldmap-legend-dot" style={{ background: '#00d46a' }} /> Very Low</span>
          <span className="worldmap-legend-item"><span className="worldmap-legend-dot" style={{ background: '#22c55e' }} /> Low</span>
          <span className="worldmap-legend-item"><span className="worldmap-legend-dot" style={{ background: '#eab308' }} /> Medium</span>
          <span className="worldmap-legend-item"><span className="worldmap-legend-dot" style={{ background: '#f97316' }} /> High</span>
          <span className="worldmap-legend-item"><span className="worldmap-legend-dot" style={{ background: '#ef4444' }} /> Very High</span>
        </div>
      </div>
    </section>
  );
};

export default WorldMap;
