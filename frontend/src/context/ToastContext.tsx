import React, { createContext, useContext, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

interface Toast {
  id: number;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

interface ToastContextType {
  toast: (type: Toast['type'], message: string) => void;
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} });

export const useToast = () => useContext(ToastContext);

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((type: Toast['type'], message: string) => {
    const id = nextId++;
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }, []);

  const remove = (id: number) => setToasts(prev => prev.filter(t => t.id !== id));

  const icons = {
    success: <CheckCircle size={16} />,
    error: <XCircle size={16} />,
    warning: <AlertTriangle size={16} />,
    info: <Info size={16} />,
  };

  const borderColors = {
    success: 'var(--accent)',
    error: 'var(--color-error)',
    warning: '#f1fa8c',
    info: 'var(--color-info)',
  };

  const iconColors = {
    success: 'var(--accent)',
    error: 'var(--color-error)',
    warning: '#f1fa8c',
    info: 'var(--color-info)',
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div role="status" aria-live="polite" style={{
        position: 'fixed', bottom: '2rem', right: '2rem', zIndex: 9999,
        display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: '400px',
      }}>
        <AnimatePresence>
          {toasts.map(t => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 50, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 100, scale: 0.9 }}
              transition={{ duration: 0.2 }}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                padding: '0.875rem 1rem', background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderLeft: `3px solid ${borderColors[t.type]}`,
                fontFamily: 'var(--font-mono)', fontSize: '0.8rem',
                color: 'var(--text-primary)',
                boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)',
                cursor: 'pointer',
              }}
              onClick={() => remove(t.id)}
            >
              <span style={{ flexShrink: 0, display: 'flex', color: iconColors[t.type] }}>
                {icons[t.type]}
              </span>
              <span style={{ flex: 1 }}>{t.message}</span>
              <button style={{
                flexShrink: 0, display: 'flex', color: 'var(--text-secondary)',
                cursor: 'pointer', background: 'none', border: 'none', padding: '2px',
              }}>
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
