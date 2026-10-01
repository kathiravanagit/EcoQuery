import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { EASE_FN } from '../constants';
import { readCookieConsent, storeCookieConsent, type CookieChoice } from '../cookieConsent';
import './CookieBanner.css';

export default function CookieBanner() {
  const reduceMotion = useReducedMotion();
  const [choice, setChoice] = useState<CookieChoice | null>(() => readCookieConsent());

  // Positioned under ConfirmModal (9998) and toasts (9999) in CookieBanner.css,
  // so this never covers a dialog or a toast.
  const enter = reduceMotion ? { opacity: 0 } : { opacity: 0, y: 24 };

  const decide = (next: CookieChoice) => {
    storeCookieConsent(next);
    setChoice(next);
  };

  return (
    <AnimatePresence>
      {choice === null && (
        <motion.div
          role="region"
          aria-label="Cookie consent"
          className="cookie-banner"
          initial={enter}
          animate={{ opacity: 1, y: 0 }}
          exit={enter}
          transition={{ duration: reduceMotion ? 0 : 0.35, ease: EASE_FN }}
        >
          <div className="cookie-banner__body">
            <p className="cookie-banner__title">Cookies on EcoQuery</p>
            <p className="cookie-banner__text">
              This device stores a small amount of information to keep you signed in and to remember
              your settings. We do not run advertising or analytics trackers.{' '}
              <Link to="/cookies" className="cookie-banner__link">
                Read the cookie policy
              </Link>
            </p>
          </div>
          <div className="cookie-banner__actions">
            <button type="button" className="btn btn-secondary" onClick={() => decide('declined')}>
              Decline
            </button>
            <button type="button" className="btn btn-primary" onClick={() => decide('accepted')}>
              Accept
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
