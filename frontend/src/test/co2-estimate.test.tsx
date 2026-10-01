import { render, screen } from '@testing-library/react';
import Co2Estimate from '../components/Co2Estimate';
import { METHODOLOGY_URL } from '../constants';
import { formatCo2, uncertaintyPercent, uncertaintySuffix } from '../co2';

describe('Co2Estimate', () => {
  it('renders the value with its relative uncertainty band', () => {
    render(<Co2Estimate value={12.4} band={{ relative: 0.18 }} />);
    expect(screen.getByText('12.4 g')).toBeInTheDocument();
    expect(screen.getByText(/± 18%/)).toBeInTheDocument();
  });

  it('exposes the band to assistive tech through the info button label', () => {
    render(<Co2Estimate value={12.4} band={{ relative: 0.18 }} />);
    expect(
      screen.getByRole('button', { name: /12\.4 g, plus or minus 18 percent/ }),
    ).toBeInTheDocument();
  });

  it('links the tooltip to the methodology document', () => {
    render(<Co2Estimate value={0.05} band={{ relative: 0.62 }} />);
    const link = screen.getByRole('link', { name: /how this is calculated/i });
    expect(link).toHaveAttribute('href', METHODOLOGY_URL);
    expect(screen.getByRole('tooltip')).toHaveTextContent(/model-based estimate/i);
  });

  it('omits the band entirely when no uncertainty is available', () => {
    // Knowledge/cache answers are a literal 0 g — there is nothing to bound.
    render(<Co2Estimate value={0} band={{ relative: 0, range: { min: 0, max: 0 } }} />);
    expect(screen.getByText('0 g')).toBeInTheDocument();
    expect(screen.queryByText(/±/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('honours a custom unit', () => {
    render(<Co2Estimate value={1} band={{ relative: 0.5 }} unit="g CO₂e" />);
    expect(screen.getByText('1.00 g CO₂e')).toBeInTheDocument();
  });

  it('shows a display floor instead of claiming zero emissions', () => {
    // Backend rounds to 4 dp, so a tiny-but-real estimate arrives as 0 while
    // still carrying a band. "0 g ±62%" would read as "no emissions".
    render(<Co2Estimate value={0} band={{ relative: 0.62, range: { min: 0, max: 0 } }} />);
    expect(screen.getByText('<0.001 g')).toBeInTheDocument();
    expect(screen.getByText(/± 62%/)).toBeInTheDocument();
    expect(screen.getByRole('tooltip')).toHaveTextContent(/display floor/i);
  });
});

describe('uncertaintyPercent', () => {
  it('prefers the explicit relative value', () => {
    expect(uncertaintyPercent({ relative: 0.62, range: { min: 0, max: 1 } })).toBeCloseTo(62);
  });

  it('derives the percentage from the absolute range when relative is absent', () => {
    // 10 * (1 ± 0.62) → min 3.8, max 16.2
    expect(uncertaintyPercent({ range: { min: 3.8, max: 16.2 } })).toBeCloseTo(62, 5);
  });

  it('returns null rather than a bogus 0% band', () => {
    expect(uncertaintyPercent({ relative: 0, range: { min: 0, max: 0 } })).toBeNull();
    expect(uncertaintyPercent({})).toBeNull();
    expect(uncertaintyPercent({ range: { min: 0, max: 0 } })).toBeNull();
  });
});

describe('uncertaintySuffix', () => {
  it('formats the percentage for non-interactive renderers', () => {
    expect(uncertaintySuffix(62.04)).toBe(' ±62%');
  });

  it('degrades to an empty string when there is no band', () => {
    expect(uncertaintySuffix(undefined)).toBe('');
    expect(uncertaintySuffix(0)).toBe('');
    expect(uncertaintySuffix(null)).toBe('');
  });
});

describe('formatCo2', () => {
  it('keeps significant digits on tiny per-query figures', () => {
    expect(formatCo2(0.0008)).toBe('0.0008');
    expect(formatCo2(0.124)).toBe('0.124');
  });

  it('does not sprout decimals on large aggregates', () => {
    expect(formatCo2(12.4)).toBe('12.4');
    expect(formatCo2(1234.6)).toBe('1,235');
  });

  it('renders zero and non-finite input safely', () => {
    expect(formatCo2(0)).toBe('0');
    expect(formatCo2(NaN)).toBe('0');
    expect(formatCo2(Infinity)).toBe('0');
  });
});
