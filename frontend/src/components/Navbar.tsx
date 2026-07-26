import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Moon, Sun, Menu, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import ProfileMenu from './ProfileMenu';
import './Navbar.css';

interface NavbarProps {
  theme: 'dark' | 'light'
  toggleTheme: () => void
}

const Navbar = ({ theme, toggleTheme }: NavbarProps) => {
  const { user } = useAuth();
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const isHome = location.pathname === '/';

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location]);

  const closeMobile = useCallback(() => setMobileMenuOpen(false), []);

  const pageLinks = [
    { name: 'Home', to: isHome ? '#home' : '/' },
    { name: 'Pricing', to: '/pricing' },
    { name: 'About', to: '/about' },
    { name: 'Contact', to: '/contact' },
    ...(user ? [{ name: 'Dashboard', to: '/dashboard' }] : []),
    ...(user && user.role === 'admin' ? [{ name: 'Admin', to: '/admin' }] : []),
  ];

  return (
    <header className={`navbar ${isScrolled ? 'glass scanned' : ''}`}>
      <div className="container navbar-container">
        <span className="navbar-brand">EcoQuery</span>

        <nav className={`nav-links ${mobileMenuOpen ? 'mobile-open' : ''}`}>
          {pageLinks.map((link) =>
            link.to.startsWith('#') ? (
              <a key={link.name} href={link.to} className="nav-link" onClick={closeMobile}>{link.name}</a>
            ) : (
              <Link key={link.name} to={link.to} className={`nav-link ${location.pathname === link.to ? 'nav-link-active' : ''}`} onClick={closeMobile}>
                {link.name}
              </Link>
            )
          )}
          <div className="nav-mobile-auth">
            {!user && (
              <>
                <Link to="/login" className="nav-link nav-auth-link" onClick={closeMobile}>Sign In</Link>
                <Link to="/signup" className="nav-link nav-auth-link nav-signup-link" onClick={closeMobile}>Sign Up</Link>
              </>
            )}
          </div>
        </nav>

        <div className="nav-actions">
          {user && <ProfileMenu />}
          {!user && (
            <div className="nav-actions-auth">
              <Link to="/login" className="nav-link nav-auth-link">Sign In</Link>
              <Link to="/signup" className="nav-link nav-auth-link nav-signup-link">Sign Up</Link>
            </div>
          )}
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <button className="mobile-menu-btn" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label="Toggle menu">
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
