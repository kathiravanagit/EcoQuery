import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, ArrowLeft, Check, Leaf, Zap, Shield, Terminal } from 'lucide-react';

interface Props {
  onComplete: () => void;
}

const steps = [
  {
    icon: <Terminal size={32} />,
    title: 'Welcome to EcoQuery',
    description: 'Carbon-aware LLM routing that reduces your AI emissions without sacrificing quality.',
    code: '$ ecoquery --init',
  },
  {
    icon: <Leaf size={32} />,
    title: 'Green Routing',
    description: 'Every query is automatically routed to the greenest data center based on real-time carbon intensity data.',
    code: '$ ecoquery --route --greenest',
  },
  {
    icon: <Zap size={32} />,
    title: 'Real-Time Tracking',
    description: 'Monitor your carbon savings, API costs, and query analytics in a live dashboard.',
    code: '$ ecoquery --stats --live',
  },
  {
    icon: <Shield size={32} />,
    title: 'Verified Impact',
    description: 'Independent verification ensures your carbon savings are real, not just estimates.',
    code: '$ ecoquery --verify --all',
  },
];

const OnboardingWizard = ({ onComplete }: Props) => {
  const [step, setStep] = useState(0);

  const next = () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      onComplete();
    }
  };

  const prev = () => {
    if (step > 0) setStep(step - 1);
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 10000,
      background: 'var(--bg-color)', display: 'flex',
      alignItems: 'center', justifyContent: 'center',
      backgroundImage:
        'linear-gradient(var(--border-color) 1px, transparent 1px), linear-gradient(90deg, var(--border-color) 1px, transparent 1px)',
      backgroundSize: '40px 40px',
    }}>
      <div style={{
        maxWidth: 500, width: '100%', padding: '3rem 2rem',
        background: 'var(--bg-secondary)', border: '1px solid var(--border-color)',
        position: 'relative',
      }}>
        {/* Progress bar */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: 'var(--border-color)',
        }}>
          <motion.div
            animate={{ width: `${((step + 1) / steps.length) * 100}%` }}
            style={{ height: '100%', background: 'var(--accent)' }}
          />
        </div>

        {/* Step indicator */}
        <div style={{
          fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
          color: 'var(--text-secondary)', marginBottom: '2rem',
        }}>
          step {step + 1}/{steps.length}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
          >
            <div style={{ color: 'var(--accent)', marginBottom: '1.5rem' }}>
              {steps[step].icon}
            </div>

            <h2 style={{
              fontFamily: 'var(--font-sans)', fontSize: '1.5rem',
              marginBottom: '0.75rem', color: 'var(--text-primary)',
            }}>
              {steps[step].title}
            </h2>

            <p style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.85rem',
              color: 'var(--text-secondary)', lineHeight: 1.7,
              marginBottom: '2rem',
            }}>
              {steps[step].description}
            </p>

            <div style={{
              fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
              color: 'var(--accent)', padding: '1rem',
              background: 'var(--bg-color)', border: '1px solid var(--border-color)',
              marginBottom: '2rem',
            }}>
              {steps[step].code}
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Navigation */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <button
            onClick={prev}
            disabled={step === 0}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
              color: step === 0 ? 'transparent' : 'var(--text-secondary)',
              background: 'none', border: 'none', cursor: step === 0 ? 'default' : 'pointer',
              padding: '0.5rem 0',
            }}
          >
            <ArrowLeft size={14} /> back
          </button>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {steps.map((_, i) => (
              <div
                key={i}
                style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: i <= step ? 'var(--accent)' : 'var(--border-color)',
                  transition: 'background 0.2s',
                }}
              />
            ))}
          </div>

          <button
            onClick={next}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
              color: 'var(--bg-color)', background: 'var(--accent)',
              border: 'none', padding: '0.5rem 1rem', cursor: 'pointer',
              textTransform: 'uppercase',
            }}
          >
            {step === steps.length - 1 ? (
              <>get started <Check size={14} /></>
            ) : (
              <>next <ArrowRight size={14} /></>
            )}
          </button>
        </div>

        {/* Skip link */}
        <button
          onClick={onComplete}
          style={{
            position: 'absolute', top: '1rem', right: '1rem',
            fontFamily: 'var(--font-mono)', fontSize: '0.7rem',
            color: 'var(--text-secondary)', background: 'none',
            border: 'none', cursor: 'pointer', textTransform: 'lowercase',
          }}
        >
          skip →
        </button>
      </div>
    </div>
  );
};

export default OnboardingWizard;
