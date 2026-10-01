/**
 * Where EcoQuery records a visitor's answer to the cookie banner, and how.
 *
 * This lives outside the component so the storage contract has exactly one
 * home: the banner only decides what to render, and nothing else has to know
 * the key or the accepted/declined vocabulary.
 */

export const CONSENT_STORAGE_KEY = 'cookie_consent';

export type CookieChoice = 'accepted' | 'declined';

/**
 * Returns the stored answer, or null when there is none.
 *
 * A missing or corrupt value both mean "we have not asked yet", so the banner
 * comes back rather than silently treating an unreadable flag as consent.
 * Reading storage can itself throw — private browsing, blocked third-party
 * storage — and when it does there is nothing to remember, so we ask again.
 */
export function readCookieConsent(): CookieChoice | null {
  try {
    const stored = localStorage.getItem(CONSENT_STORAGE_KEY);
    return stored === 'accepted' || stored === 'declined' ? stored : null;
  } catch {
    return null;
  }
}

/**
 * Records the answer and reports whether it actually stuck.
 *
 * False means storage was unavailable; the caller should still dismiss the
 * banner for this visit rather than trapping the visitor behind it, and the
 * question will simply be asked again next time.
 */
export function storeCookieConsent(choice: CookieChoice): boolean {
  try {
    localStorage.setItem(CONSENT_STORAGE_KEY, choice);
    return true;
  } catch {
    return false;
  }
}
