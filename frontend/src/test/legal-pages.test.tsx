import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Terms from '../pages/Terms';
import CookiePolicy from '../pages/CookiePolicy';
import NotFound from '../pages/NotFound';

describe('Terms page', () => {
  it('renders the h1 heading', () => {
    render(<MemoryRouter><Terms /></MemoryRouter>);
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.textContent).toMatch(/Terms of Service/);
  });

  it('renders all section headings', () => {
    render(<MemoryRouter><Terms /></MemoryRouter>);
    expect(screen.getByText('1. Acceptance of Terms')).toBeInTheDocument();
    expect(screen.getByText('2. Description of Service')).toBeInTheDocument();
    expect(screen.getByText('3. User Responsibilities')).toBeInTheDocument();
    expect(screen.getByText('4. API Usage')).toBeInTheDocument();
    expect(screen.getByText('5. Limitation of Liability')).toBeInTheDocument();
    expect(screen.getByText('6. Changes')).toBeInTheDocument();
  });

  it('renders contact email', () => {
    render(<MemoryRouter><Terms /></MemoryRouter>);
    expect(screen.getByText(/kathiravanawork@gmail.com/)).toBeInTheDocument();
  });
});

describe('CookiePolicy page', () => {
  it('renders the h1 heading', () => {
    render(<MemoryRouter><CookiePolicy /></MemoryRouter>);
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.textContent).toMatch(/Cookie Policy/);
  });

  it('renders all section headings', () => {
    render(<MemoryRouter><CookiePolicy /></MemoryRouter>);
    expect(screen.getByText('1. What Are Cookies')).toBeInTheDocument();
    expect(screen.getByText('2. How We Use Cookies')).toBeInTheDocument();
    expect(screen.getByText('3. Third-Party Cookies')).toBeInTheDocument();
    expect(screen.getByText('4. Managing Cookies')).toBeInTheDocument();
    expect(screen.getByText('5. Changes')).toBeInTheDocument();
  });
});

describe('NotFound page', () => {
  it('renders 404 and home link', () => {
    render(<MemoryRouter><NotFound /></MemoryRouter>);
    expect(screen.getByText('404')).toBeInTheDocument();
    expect(screen.getByText('Page not found')).toBeInTheDocument();
    expect(screen.getByText('Back to Home')).toBeInTheDocument();
  });
});
