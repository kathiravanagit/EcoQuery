import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { API_URL as API } from '../config'
import './CarbonMap.css'

interface Region {
  intensity: number
  name: string
  country: string
  source: string
  energy_profile: Record<string, number>
}

interface CarbonRegionsResponse {
  all_regions: Record<string, Region>
}

const ENERGY_COLORS: Record<string, string> = {
  'Natural Gas': '#94a3b8',
  'Coal': '#64748b',
  'Solar': '#f59e0b',
  'Wind': '#3b82f6',
  'Nuclear': '#8b5cf6',
  'Hydro': '#06b6d4',
  'Biomass': '#84cc16',
  'Geothermal': '#d946ef',
  'Oil': '#78716c',
  'Gas': '#94a3b8',
}

function getIntensityColor(i: number): string {
  if (i < 100) return '#00d46a'
  if (i < 400) return '#f59e0b'
  return '#ef4444'
}

function getIntensityLabel(i: number): string {
  if (i < 100) return 'Low Carbon'
  if (i < 400) return 'Moderate'
  return 'High Carbon'
}

const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] as const },
}

const CarbonMap = () => {
  const [regions, setRegions] = useState<Record<string, Region>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/api/carbon/regions`)
      .then(r => r.json())
      .then((data: CarbonRegionsResponse) => {
        setRegions(data.all_regions || {})
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load carbon data')
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <section className="carbon-map-section section">
        <div className="container">
          <div className="carbon-map-legend">
            <span className="legend-item"><span className="skeleton-box" style={{ width: 16, height: 16, borderRadius: '50%' }} /> Loading...</span>
          </div>
          <div className="carbon-map-grid">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="carbon-map-card carbon-map-card--skeleton">
                <div className="skeleton-box" style={{ height: 18, width: '65%', marginBottom: 4 }} />
                <div className="skeleton-box" style={{ height: 14, width: '40%', marginBottom: 16 }} />
                <div className="skeleton-box" style={{ height: 36, width: '50%', marginBottom: 4 }} />
                <div className="skeleton-box" style={{ height: 12, width: '35%', marginBottom: 16 }} />
                <div className="skeleton-box" style={{ height: 8, width: '100%' }} />
              </div>
            ))}
          </div>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="carbon-map-section section">
        <div className="container">
          <div className="carbon-map-error">{error}</div>
        </div>
      </section>
    )
  }

  const entries = Object.entries(regions)

  return (
    <section className="carbon-map-section section">
      <div className="container">
        <motion.div className="section-header" {...fadeUp}>
          <h2>Global Carbon <span className="text-gradient">Map</span></h2>
          <p>Real-time carbon intensity across AWS regions</p>
        </motion.div>

        <div className="carbon-map-legend">
          <span className="legend-item">
            <span className="legend-dot" style={{ background: '#00d46a' }} />
            &lt; 100 g/kWh — Low Carbon
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: '#f59e0b' }} />
            100–400 g/kWh — Moderate
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: '#ef4444' }} />
            &gt; 400 g/kWh — High Carbon
          </span>
        </div>

        {entries.length === 0 ? (
          <div className="carbon-map-empty">No region data available.</div>
        ) : (
          <div className="carbon-map-grid">
            {entries.map(([key, region], idx) => {
              const color = getIntensityColor(region.intensity)
              const profile = region.energy_profile || {}
              const profileEntries = Object.entries(profile).filter(([, v]) => v > 0)

              return (
                <motion.div
                  key={key}
                  className="carbon-map-card"
                  style={{ borderLeft: `4px solid ${color}` }}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: idx * 0.04, ease: [0.25, 0.46, 0.45, 0.94] as const }}
                  onMouseEnter={() => setHoveredId(key)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <div className="carbon-map-card-header">
                    <div className="carbon-map-name">{region.name || key}</div>
                    <div className="carbon-map-country">{region.country || '\u00a0'}</div>
                  </div>

                  <div className="carbon-map-metric">
                    <div className="carbon-map-intensity" style={{ color }}>
                      {region.intensity}
                      <span className="carbon-map-unit"> g/kWh</span>
                    </div>
                    <div className="carbon-map-source">{region.source}</div>
                  </div>

                  {profileEntries.length > 0 && (
                    <div className="carbon-map-energy-bar">
                      {profileEntries.map(([src, pct]) => (
                        <div
                          key={src}
                          className="carbon-map-energy-segment"
                          style={{
                            width: `${pct * 100}%`,
                            background: ENERGY_COLORS[src] || '#a1a1aa',
                          }}
                        />
                      ))}
                    </div>
                  )}

                  {hoveredId === key && profileEntries.length > 0 && (
                    <div className="carbon-map-tooltip">
                      {profileEntries.map(([src, pct]) => (
                        <div key={src} className="tooltip-row">
                          <span className="tooltip-dot" style={{ background: ENERGY_COLORS[src] || '#a1a1aa' }} />
                          <span className="tooltip-label">{src}</span>
                          <span className="tooltip-value">{(pct * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}

export default CarbonMap
