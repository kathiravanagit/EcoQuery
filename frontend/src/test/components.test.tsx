import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import Navbar from '../components/Navbar';

const renderNavbar = () => render(
  <BrowserRouter>
    <AuthProvider>
      <Navbar theme="dark" toggleTheme={() => {}} />
    </AuthProvider>
  </BrowserRouter>
);

describe('Navbar', () => {
  it('renders the logo', () => {
    renderNavbar();
    expect(screen.getByText('EcoQuery')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    renderNavbar();
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Pricing')).toBeInTheDocument();
    expect(screen.getByText('About')).toBeInTheDocument();
    expect(screen.getByText('Contact')).toBeInTheDocument();
  });
});
