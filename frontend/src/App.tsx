import React, { useState, useEffect, Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import HowItWorks from './components/HowItWorks';
import Features from './components/Features';
import ImpactStats from './components/ImpactStats';
import LiveDemo from './components/LiveDemo';
import Research from './components/Research';
import Footer from './components/Footer';
import ErrorBoundary from './components/ErrorBoundary';
import OnboardingWizard from './components/OnboardingWizard';
import { PageSkeleton } from './components/Skeleton';
import './App.css';

const About = lazy(() => import('./pages/About'));
const Pricing = lazy(() => import('./pages/Pricing'));
const Contact = lazy(() => import('./pages/Contact'));
const Privacy = lazy(() => import('./pages/Privacy'));
const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const AuthCallback = lazy(() => import('./pages/AuthCallback'));
const NotFound = lazy(() => import('./pages/NotFound'));
const Terms = lazy(() => import('./pages/Terms'));
const CookiePolicy = lazy(() => import('./pages/CookiePolicy'));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail'));
const Profile = lazy(() => import('./pages/Profile'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Admin = lazy(() => import('./pages/Admin'));
const Blog = lazy(() => import('./pages/Blog'));
const BlogPost = lazy(() => import('./pages/BlogPost'));
const FAQ = lazy(() => import('./pages/FAQ'));

const easeFn = [0.25, 0.46, 0.45, 0.94] as const;

const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.5, ease: easeFn } },
  exit: { opacity: 0, y: -12, transition: { duration: 0.3, ease: easeFn } },
};

function AnimatedPage({ children }: { children: React.ReactNode }) {
  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" exit="exit">
      <ErrorBoundary>
        <Suspense fallback={<PageSkeleton />}>
          {children}
        </Suspense>
      </ErrorBoundary>
    </motion.div>
  );
}

function HomePage() {
  return (
    <main>
      <Hero />
      <HowItWorks />
      <Features />
      <ImpactStats />
      <LiveDemo />
      <Research />
    </main>
  );
}

function AppContent() {
  const location = useLocation();
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [showOnboarding, setShowOnboarding] = useState(() => {
    return !localStorage.getItem('ecoquery_onboarded');
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleOnboardingComplete = () => {
    localStorage.setItem('ecoquery_onboarded', 'true');
    setShowOnboarding(false);
  };

  return (
    <div className="app-wrapper">
      {showOnboarding && <OnboardingWizard onComplete={handleOnboardingComplete} />}
      <Navbar theme={theme} toggleTheme={toggleTheme} />
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<AnimatedPage><HomePage /></AnimatedPage>} />
          <Route path="/about" element={<AnimatedPage><About /></AnimatedPage>} />
          <Route path="/pricing" element={<AnimatedPage><Pricing /></AnimatedPage>} />
          <Route path="/contact" element={<AnimatedPage><Contact /></AnimatedPage>} />
          <Route path="/profile" element={<ProtectedRoute><AnimatedPage><Profile /></AnimatedPage></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><AnimatedPage><Dashboard /></AnimatedPage></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><AnimatedPage><Admin /></AnimatedPage></ProtectedRoute>} />
          <Route path="/privacy" element={<AnimatedPage><Privacy /></AnimatedPage>} />
          <Route path="/login" element={<AnimatedPage><Login /></AnimatedPage>} />
          <Route path="/signup" element={<AnimatedPage><Signup /></AnimatedPage>} />
          <Route path="/forgot-password" element={<AnimatedPage><ForgotPassword /></AnimatedPage>} />
          <Route path="/reset-password" element={<AnimatedPage><ResetPassword /></AnimatedPage>} />
          <Route path="/verify-email" element={<AnimatedPage><VerifyEmail /></AnimatedPage>} />
          <Route path="/terms" element={<AnimatedPage><Terms /></AnimatedPage>} />
          <Route path="/cookies" element={<AnimatedPage><CookiePolicy /></AnimatedPage>} />
          <Route path="/blog" element={<AnimatedPage><Blog /></AnimatedPage>} />
          <Route path="/blog/:id" element={<AnimatedPage><BlogPost /></AnimatedPage>} />
          <Route path="/faq" element={<AnimatedPage><FAQ /></AnimatedPage>} />
          <Route path="/auth/callback" element={<AnimatedPage><AuthCallback /></AnimatedPage>} />
          <Route path="*" element={<AnimatedPage><NotFound /></AnimatedPage>} />
        </Routes>
      </AnimatePresence>
      <Footer />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
