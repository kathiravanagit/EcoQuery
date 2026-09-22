import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Features from '../components/Features';
import ImpactStats from '../components/ImpactStats';
import Hero from '../components/Hero';

describe('Features', () => {
  it('renders section heading', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    expect(screen.getByRole('heading', { level: 2 }).textContent).toMatch(/Platform Features/);
  });

  it('renders all feature cards', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    expect(screen.getByText('Request classification')).toBeInTheDocument();
    expect(screen.getByText('Grid data')).toBeInTheDocument();
    expect(screen.getByText('Model routing')).toBeInTheDocument();
    expect(screen.getByText('Response checks')).toBeInTheDocument();
    expect(screen.getByText('Usage records')).toBeInTheDocument();
  });

  it('renders feature descriptions', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    expect(screen.getByText(/capability it needs/)).toBeInTheDocument();
    expect(screen.getByText(/regional carbon-intensity data/)).toBeInTheDocument();
    expect(screen.getByText(/suitable provider and model/)).toBeInTheDocument();
    expect(screen.getByText(/what was requested/)).toBeInTheDocument();
    expect(screen.getByText(/query, cost, latency/)).toBeInTheDocument();
  });
});

describe('ImpactStats', () => {
  it('renders section heading', () => {
    render(<MemoryRouter><ImpactStats /></MemoryRouter>);
    const h2 = screen.getByRole('heading', { level: 2 });
    expect(h2.textContent).toMatch(/metrics/);
  });

  it('renders a loading state before metrics arrive', () => {
    render(<MemoryRouter><ImpactStats /></MemoryRouter>);
    expect(screen.getByRole('status')).toHaveTextContent('Loading live impact data...');
  });
});

describe('Hero', () => {
  it('renders the main heading', () => {
    render(<MemoryRouter><Hero /></MemoryRouter>);
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.textContent).toMatch(/ask AI with less.*unnecessary computation/i);
  });

  it('renders call-to-action buttons', () => {
    render(<MemoryRouter><Hero /></MemoryRouter>);
    expect(screen.getByText('try demo')).toBeInTheDocument();
    expect(screen.getByText(/see the system/)).toBeInTheDocument();
  });

  it('renders version badge', () => {
    render(<MemoryRouter><Hero /></MemoryRouter>);
    expect(document.querySelector('.badge')).toBeInTheDocument();
  });
});
