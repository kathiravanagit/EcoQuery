import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Footer from '../components/Footer';

describe('Footer', () => {
  it('renders brand description', () => {
    render(<MemoryRouter><Footer /></MemoryRouter>);
    expect(screen.getByText(/sustainable intelligence layer/)).toBeInTheDocument();
  });

  it('renders all section headings', () => {
    render(<MemoryRouter><Footer /></MemoryRouter>);
    expect(screen.getByText('Product')).toBeInTheDocument();
    expect(screen.getByText('Company')).toBeInTheDocument();
    expect(screen.getByText('Legal')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    render(<MemoryRouter><Footer /></MemoryRouter>);
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Pricing')).toBeInTheDocument();
    expect(screen.getByText('About Us')).toBeInTheDocument();
    expect(screen.getByText('Contact')).toBeInTheDocument();
    expect(screen.getByText('Privacy Policy')).toBeInTheDocument();
  });

  it('renders copyright', () => {
    render(<MemoryRouter><Footer /></MemoryRouter>);
    const year = new Date().getFullYear().toString();
    expect(screen.getByText(new RegExp(year))).toBeInTheDocument();
  });
});
