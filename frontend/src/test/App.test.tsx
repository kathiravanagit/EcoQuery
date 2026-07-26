import { render, screen } from '@testing-library/react';
import { AuthProvider } from '../context/AuthContext';
import App from '../App';

describe('App', () => {
  it('renders EcoQuery branding', () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );
    expect(screen.getAllByText('EcoQuery').length).toBeGreaterThan(0);
  });

  it('renders footer', () => {
    render(
      <AuthProvider>
        <App />
      </AuthProvider>
    );
    expect(screen.getByText(/EcoQuery Inc/i)).toBeInTheDocument();
  });
});
