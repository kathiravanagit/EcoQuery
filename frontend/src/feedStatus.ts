/**
 * Shared interpretation of the carbon feed's freshness metadata.
 *
 * `/api/carbon/regions` returns `is_live`, `stale`, `method` and `last_updated`.
 * The UI must never present a cached or static number as real-time, so every
 * surface renders its provenance badge through this helper rather than
 * re-deriving it (which previously led to "real-time" being shown whenever an
 * API key merely existed).
 */

export interface CarbonFeedMeta {
  is_live?: boolean;
  stale?: boolean;
  method?: string;
  data_source?: string;
  last_updated?: string | null;
}

export interface FeedStatus {
  /** Short badge text, e.g. "Live", "Cached · 12 min ago". */
  label: string;
  /** Long sentence for the descriptive caption under a chart. */
  description: string;
  isLive: boolean;
  isCached: boolean;
}

/** Human age from an ISO timestamp: "just now", "12 min ago", "3 h ago", "4 d ago". */
export function relativeAge(iso?: string | null): string | null {
  if (!iso) return null;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return null;

  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.floor(hours / 24)} d ago`;
}

export function feedStatus(meta?: CarbonFeedMeta | null): FeedStatus {
  if (!meta) {
    return {
      label: 'Unavailable',
      description: 'Live feed unavailable — showing no carbon data.',
      isLive: false,
      isCached: false,
    };
  }

  const age = relativeAge(meta.last_updated);

  if (meta.is_live === true) {
    return {
      label: 'Live',
      description: 'Live grid carbon intensity (g CO₂/kWh) across regions. Lower is greener.',
      isLive: true,
      isCached: false,
    };
  }

  if (meta.stale === true || meta.method === 'stale-cache') {
    if (age) {
      return {
        label: `Cached · ${age}`,
        description: `Live feed unavailable — showing last known values from ${age}.`,
        isLive: false,
        isCached: true,
      };
    }
    return {
      label: 'Cached',
      description: 'Live feed unavailable — showing last known values.',
      isLive: false,
      isCached: true,
    };
  }

  // Static annual baseline: a legitimate source, but not real-time.
  const source = meta.data_source || 'IEA 2024';
  return {
    label: `${source} baselines`,
    description: 'Live feed unavailable — showing annual average grid carbon intensity.',
    isLive: false,
    isCached: false,
  };
}
