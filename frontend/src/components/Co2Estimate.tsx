/**
 * Renders a CO₂ figure as `12.4 g ± 62%` with an info affordance that explains
 * what the percentage means and links to docs/METHODOLOGY.md — the
 * authoritative description of how the figure and its error terms are derived.
 *
 * See `src/co2.ts` for the band helpers; they live there so this file exports
 * only a component (React Fast Refresh requirement).
 */

import { useId, type ReactNode } from 'react';
import { Info } from 'lucide-react';
import { METHODOLOGY_URL } from '../constants';
import { formatCo2, uncertaintyPercent, type Co2Band } from '../co2';

interface Co2EstimateProps {
  /** Value in grams. */
  value: number;
  band?: Co2Band;
  /** Rendered after the value, e.g. 'g' or 'g CO₂e'. Defaults to 'g'. */
  unit?: string;
  className?: string;
}

export default function Co2Estimate({
  value,
  band = {},
  unit = 'g',
  className,
}: Co2EstimateProps): ReactNode {
  const tipId = useId();
  const pct = uncertaintyPercent(band);
  // Backend values are rounded to 4 dp, so a genuinely tiny per-query figure
  // (a short prompt on a clean grid) can arrive as exactly 0 while still
  // carrying a real relative band. Printing a bare "0 g ±62%" would imply the
  // emissions were zero, so the figure is shown below the display floor.
  const belowFloor = value === 0 && pct !== null;
  const label = belowFloor ? `<0.001 ${unit}` : `${formatCo2(value)} ${unit}`;
  const rangeMin = band.range?.min ?? value * (1 - (pct ?? 0) / 100);
  const rangeMax = band.range?.max ?? value * (1 + (pct ?? 0) / 100);

  return (
    <span className={className ? `co2-estimate ${className}` : 'co2-estimate'}>
      <span className="co2-estimate-value">{label}</span>
      {pct !== null && (
        <span className="co2-uncertainty">
          <span className="co2-estimate-band" aria-hidden="true">
            {' '}± {Math.round(pct)}%
          </span>
          <button
            type="button"
            className="co2-info-btn"
            aria-label={`${label}, plus or minus ${Math.round(pct)} percent. What does this mean?`}
            aria-describedby={tipId}
          >
            <Info size={12} aria-hidden="true" focusable="false" />
          </button>
          <span className="co2-tooltip" role="tooltip" id={tipId}>
            {belowFloor ? (
              <>Below the {formatCo2(0.001)} {unit} display floor, with a ±{Math.round(pct)}%
              calibrated uncertainty band.</>
            ) : (
              <>Estimated at {label} with a ±{Math.round(pct)}% calibrated uncertainty
              band ({formatCo2(rangeMin)}–{formatCo2(rangeMax)} {unit}).</>
            )}{' '}
            This is a model-based estimate, not a direct measurement.{' '}
            <a href={METHODOLOGY_URL} target="_blank" rel="noreferrer">
              How this is calculated
            </a>
          </span>
        </span>
      )}
    </span>
  );
}
