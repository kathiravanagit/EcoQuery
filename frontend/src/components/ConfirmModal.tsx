import { motion, AnimatePresence } from 'framer-motion';

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  confirmDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({ open, title, message, confirmLabel = 'Confirm', confirmDanger, onConfirm, onCancel }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="dialog"
          aria-modal="true"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 9998, display: 'flex',
            alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
          }}
          onClick={onCancel}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
            onClick={e => e.stopPropagation()}
            style={{
              background: 'var(--bg-secondary)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16,
              padding: '2rem', maxWidth: 420, width: '90%', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem' }}>{title}</h3>
            <p style={{ color: 'var(--text-secondary)', margin: '0 0 1.5rem', fontSize: 14, lineHeight: 1.5 }}>{message}</p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={onCancel}>Cancel</button>
              <button
                className={`btn ${confirmDanger ? 'btn-danger' : 'btn-primary'}`}
                onClick={onConfirm}
                style={{ fontWeight: 600 }}
              >{confirmLabel}</button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
