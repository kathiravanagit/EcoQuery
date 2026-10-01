import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CookieBanner from '../components/CookieBanner';
import { CONSENT_STORAGE_KEY, readCookieConsent } from '../cookieConsent';

const REGION = { name: 'Cookie consent' } as const;

const renderBanner = () =>
  render(
    <MemoryRouter>
      <CookieBanner />
    </MemoryRouter>,
  );

beforeEach(() => {
  localStorage.clear();
});

describe('CookieBanner', () => {
  it('shows itself to a first-time visitor', () => {
    renderBanner();

    expect(screen.getByRole('region', REGION)).toBeInTheDocument();
    expect(screen.getByText(/advertising or analytics trackers/)).toBeInTheDocument();
  });

  it('stays hidden once a choice is already stored', () => {
    localStorage.setItem(CONSENT_STORAGE_KEY, 'accepted');
    renderBanner();

    expect(screen.queryByRole('region', REGION)).not.toBeInTheDocument();
  });

  it('records acceptance and dismisses the bar', async () => {
    renderBanner();
    fireEvent.click(screen.getByRole('button', { name: 'Accept' }));

    expect(localStorage.getItem(CONSENT_STORAGE_KEY)).toBe('accepted');
    expect(readCookieConsent()).toBe('accepted');
    await waitFor(() => expect(screen.queryByRole('region', REGION)).not.toBeInTheDocument());
  });

  it('records a decline the same way, so declining is not a dead control', async () => {
    renderBanner();
    fireEvent.click(screen.getByRole('button', { name: 'Decline' }));

    expect(localStorage.getItem(CONSENT_STORAGE_KEY)).toBe('declined');
    expect(readCookieConsent()).toBe('declined');
    await waitFor(() => expect(screen.queryByRole('region', REGION)).not.toBeInTheDocument());
  });

  it('offers a route to the policy it cites', () => {
    renderBanner();

    expect(screen.getByRole('link', { name: /cookie policy/i })).toHaveAttribute(
      'href',
      '/cookies',
    );
  });

  it('asks again when the stored answer is not one we recognise', () => {
    localStorage.setItem(CONSENT_STORAGE_KEY, 'maybe');

    expect(readCookieConsent()).toBeNull();
    renderBanner();
    expect(screen.getByRole('region', REGION)).toBeInTheDocument();
  });

  it('still renders when reading storage throws', () => {
    const original = localStorage.getItem;
    localStorage.getItem = () => {
      throw new Error('storage blocked');
    };

    try {
      expect(readCookieConsent()).toBeNull();
      renderBanner();
      expect(screen.getByRole('region', REGION)).toBeInTheDocument();
    } finally {
      localStorage.getItem = original;
    }
  });

  it('survives storage being unavailable when the choice is made', async () => {
    renderBanner();
    const original = localStorage.setItem;
    localStorage.setItem = () => {
      throw new Error('storage blocked');
    };

    try {
      // The bar must still close for this visit rather than trapping the user.
      fireEvent.click(screen.getByRole('button', { name: 'Accept' }));
      await waitFor(() => expect(screen.queryByRole('region', REGION)).not.toBeInTheDocument());
    } finally {
      localStorage.setItem = original;
    }
  });
});
