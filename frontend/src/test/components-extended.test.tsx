import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Features from '../components/Features';
import ImpactStats from '../components/ImpactStats';
import Hero from '../components/Hero';

describe('Features', () => {
  it('renders section heading', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    const h2 = screen.getByRole('heading', { level: 2 });
    expect(h2.textContent).toMatch(/Platform Features/);
  });

  it('renders all feature cards', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    expect(screen.getByText('Smart Classifier')).toBeInTheDocument();
    expect(screen.getByText('Carbon Estimator')).toBeInTheDocument();
    expect(screen.getByText('Intelligent Router')).toBeInTheDocument();
    expect(screen.getByText('Verification Engine')).toBeInTheDocument();
    expect(screen.getByText('Live Dashboard')).toBeInTheDocument();
  });

  it('renders feature descriptions', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    expect(screen.getByText(/query complexity/)).toBeInTheDocument();
    expect(screen.getByText(/real-time grid/)).toBeInTheDocument();
    expect(screen.getByText(/renewable energy/)).toBeInTheDocument();
    expect(screen.getByText(/immutable audit/)).toBeInTheDocument();
    expect(screen.getByText(/deep visibility/)).toBeInTheDocument();
  });
});

describe('ImpactStats', () => {
  it('renders section heading', () => {
    render(<MemoryRouter><ImpactStats /></MemoryRouter>);
    const h2 = screen.getByRole('heading', { level: 2 });
    expect(h2.textContent).toMatch(/Real Impact/);
  });

  it('renders all stat labels', () => {
    render(<MemoryRouter><ImpactStats /></MemoryRouter>);
    expect(screen.getByText(/CO₂ Emissions/)).toBeInTheDocument();
    expect(screen.getByText(/Response Quality/)).toBeInTheDocument();
    expect(screen.getByText(/Average Latency/)).toBeInTheDocument();
  });
});

describe('Hero', () => {
  it('renders the main heading', () => {
    render(<MemoryRouter><Hero /></MemoryRouter>);
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.textContent).toMatch(/Make Every LLM Call Greener/);
  });

  it('renders call-to-action buttons', () => {
    render(<MemoryRouter><Hero /></MemoryRouter>);
    expect(screen.getByText('Try Demo')).toBeInTheDocument();
    expect(screen.getByText(/Learn How It Works/)).toBeInTheDocument();
  });

  it('renders version badge', () => {
    render(<MemoryRouter><Hero /></MemoryRouter>);
    expect(screen.getByText(/EcoQuery v2.0/)).toBeInTheDocument();
  });
});
