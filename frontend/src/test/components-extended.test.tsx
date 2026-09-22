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
    expect(screen.getByText('Compute Sufficiency Engine')).toBeInTheDocument();
    expect(screen.getByText('Live Grid Intelligence')).toBeInTheDocument();
    expect(screen.getByText('Green Route Control')).toBeInTheDocument();
    expect(screen.getByText('Model Integrity Proof')).toBeInTheDocument();
    expect(screen.getByText('Impact Ledger')).toBeInTheDocument();
  });

  it('renders feature descriptions', () => {
    render(<MemoryRouter><Features /></MemoryRouter>);
    expect(screen.getByText(/smallest capability/)).toBeInTheDocument();
    expect(screen.getByText(/regional carbon intensity/)).toBeInTheDocument();
    expect(screen.getByText(/cleanest capable provider/)).toBeInTheDocument();
    expect(screen.getByText(/what was requested/)).toBeInTheDocument();
    expect(screen.getByText(/routing decisions/)).toBeInTheDocument();
  });
});

describe('ImpactStats', () => {
  it('renders section heading', () => {
    render(<MemoryRouter><ImpactStats /></MemoryRouter>);
    const h2 = screen.getByRole('heading', { level: 2 });
    expect(h2.textContent).toMatch(/Impact/);
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
    expect(h1.textContent).toMatch(/control plane.*sustainable AI/i);
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
