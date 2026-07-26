import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import About from '../pages/About';
import Pricing from '../pages/Pricing';
import Contact from '../pages/Contact';
import Privacy from '../pages/Privacy';

describe('About page', () => {
  it('renders the heading', () => {
    render(<MemoryRouter><About /></MemoryRouter>);
    expect(screen.getByText(/Our Mission/)).toBeInTheDocument();
  });
});

describe('Pricing page', () => {
  it('renders all pricing plans', () => {
    render(<MemoryRouter><Pricing /></MemoryRouter>);
    expect(screen.getByText('Starter')).toBeInTheDocument();
    expect(screen.getByText('Pro')).toBeInTheDocument();
    expect(screen.getByText('Enterprise')).toBeInTheDocument();
  });
});

describe('Contact page', () => {
  it('renders the contact form', () => {
    render(<MemoryRouter><Contact /></MemoryRouter>);
    expect(screen.getByPlaceholderText('Your Name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Your Email')).toBeInTheDocument();
  });
});

describe('Privacy page', () => {
  it('renders the heading', () => {
    render(<MemoryRouter><Privacy /></MemoryRouter>);
    expect(screen.getByText(/Data Collection/)).toBeInTheDocument();
  });
});
