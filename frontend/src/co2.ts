/**
 * Pure helpers for rendering CO₂ figures with their uncertainty band.
 *
 * Kept out of `Co2Estimate.tsx` so that file exports only a component — mixing
 * component and non-component exports breaks React Fast Refresh, and these are
 * also used by renderers that cannot host the interactive tooltip (the canvas
 * certificate PNG).
 *
 * Every CO₂ figure this UI prints is an estimate, not a measurement, so it is
 * always shown with the calibrated band the backend already computes
 * (`uncertainty_range_g` / `uncertainty_relative` from
 * `router.compute_savings`). A bare number would imply a precision the
 * calibration cannot support.
 */

export interface Co2Band {
  /** Relative uncertainty as a fraction: 0.62 → "±62%". */
  relative?: number | null;
  /** Absolute range in grams, used to derive `relative` when it is absent. */
  range?: { min: number; max: number } | null;
}

/**
 * Relative uncertainty as a percentage, or `null` when neither source is
 * available. Derived from the absolute range as (max-min) / (max+min), which
 * is exact for the symmetric band `value * (1 ± r)` the backend produces.
 */
export function uncertaintyPercent(band: Co2Band): number | null {
  if (typeof band.relative === 'number' && band.relative > 0) {
    return band.relative * 100;
  }
  const range = band.range;
  if (range && range.max > 0 && range.max + range.min > 0) {
    return ((range.max - range.min) / (range.max + range.min)) * 100;
  }
  return null;
}

/**
 * ` ±62%` for renderers that cannot host an interactive tooltip — the canvas
 * certificate PNG, for instance. Returns an empty string when no band is
 * available, so the figure degrades to a bare value rather than a bogus `±0%`.
 */
export function uncertaintySuffix(pct?: number | null): string {
  return typeof pct === 'number' && pct > 0 ? ` ±${Math.round(pct)}%` : '';
}

/** Adaptive precision: tiny per-query figures keep significant digits, large
 *  aggregates do not sprout decimals. */
export function formatCo2(value: number): string {
  if (!Number.isFinite(value)) return '0';
  if (value === 0) return '0';
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (abs >= 100) return value.toFixed(0);
  if (abs >= 10) return value.toFixed(1);
  if (abs >= 1) return value.toFixed(2);
  return String(Number(value.toPrecision(3)));
}
