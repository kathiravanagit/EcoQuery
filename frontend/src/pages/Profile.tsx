import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { User, Key, Trash2, LogOut, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ConfirmModal } from '../components/ConfirmModal';
import { API_URL as API } from '../config';
import './Pages.css';

interface ProfileUser { email?: string; display_name?: string; auth_provider?: string; }
interface ApiCallFn { (method: string, path: string, body: object): Promise<any> }
interface ToastFn { (type: 'success' | 'error' | 'info', message: string): void }

const Profile = () => {
  const { user, token, logout } = useAuth();
  const { toast } = useToast();
  const [openSection, setOpenSection] = useState<string | null>('name');

  const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

  const apiCall = async (method: string, path: string, body: object) => {
    const res = await fetch(`${API}${path}`, {
      method,
      headers,
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Something went wrong');
    return data;
  };

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: 600 }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="section-title">Profile Settings</h1>
            <p className="section-subtitle" style={{ textAlign: 'center', marginBottom: '2rem' }}>
              Manage your EcoQuery account
            </p>

            <AccordionSection
              title="Update Name"
              icon={<User size={18} />}
              isOpen={openSection === 'name'}
              onToggle={() => setOpenSection(openSection === 'name' ? null : 'name')}
            >
              <UpdateNameForm user={user} apiCall={apiCall} toast={toast} />
            </AccordionSection>

            <AccordionSection
              title="Update Password"
              icon={<Key size={18} />}
              isOpen={openSection === 'password'}
              onToggle={() => setOpenSection(openSection === 'password' ? null : 'password')}
            >
              <UpdatePasswordForm apiCall={apiCall} toast={toast} />
            </AccordionSection>

            <AccordionSection
              title="Delete Account"
              icon={<Trash2 size={18} />}
              isOpen={openSection === 'delete'}
              onToggle={() => setOpenSection(openSection === 'delete' ? null : 'delete')}
              danger
            >
              <DeleteAccountForm user={user} apiCall={apiCall} onDeleted={logout} toast={toast} />
            </AccordionSection>

            <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'center' }}>
              <button className="btn btn-secondary" onClick={logout} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <LogOut size={16} /> Logout
              </button>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

const AccordionSection = ({
  title, icon, isOpen, onToggle, children, danger
}: {
  title: string; icon: React.ReactNode; isOpen: boolean; onToggle: () => void; children: React.ReactNode; danger?: boolean
}) => (
  <div className={`profile-accordion ${danger ? 'profile-accordion-danger' : ''}`}>
    <button className="profile-accordion-header" onClick={onToggle} aria-expanded={isOpen}>
      <span className="profile-accordion-title">
        {icon} {title}
      </span>
      {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
    </button>
    {isOpen && <div className="profile-accordion-body">{children}</div>}
  </div>
);

function FormField({ label, error, children, htmlFor }: { label: string; error?: string; children: React.ReactNode; htmlFor?: string }) {
  return (
    <div className="profile-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {error && <span style={{ color: '#ef4444', fontSize: 12, marginTop: 4, display: 'block' }}>{error}</span>}
    </div>
  );
}

const UpdateNameForm = ({ user, apiCall, toast }: { user: ProfileUser | null; apiCall: ApiCallFn; toast: ToastFn }) => {
  const [name, setName] = useState(user?.display_name || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('Name is required'); return; }
    setError('');
    setLoading(true);
    try {
      await apiCall('PATCH', '/api/auth/profile', { display_name: name });
      toast('success', 'Name updated!');
    } catch (ex: unknown) {
      toast('error', ex instanceof Error ? ex.message : 'Failed');
    } finally { setLoading(false); }
  };

  return (
    <form onSubmit={submit}>
      <FormField label="Display Name" error={error} htmlFor="profile-name">
        <input id="profile-name" value={name} onChange={e => { setName(e.target.value); setError(''); }} placeholder="Your name" required />
      </FormField>
      <button type="submit" className="btn btn-primary" disabled={loading}>
        {loading ? 'Saving...' : 'Save Name'}
      </button>
    </form>
  );
};

const UpdatePasswordForm = ({ apiCall, toast }: { apiCall: ApiCallFn; toast: ToastFn }) => {
  const [current, setCurrent] = useState('');
  const [newPass, setNewPass] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({ current: '', newPass: '' });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = { current: '', newPass: '' };
    if (!current) errs.current = 'Current password is required';
    if (newPass.length < 6) errs.newPass = 'Password must be at least 6 characters';
    if (errs.current || errs.newPass) { setErrors(errs); return; }
    setErrors({ current: '', newPass: '' });
    setLoading(true);
    try {
      await apiCall('PATCH', '/api/auth/password', { current_password: current, new_password: newPass });
      setCurrent(''); setNewPass('');
      toast('success', 'Password updated!');
    } catch (ex: unknown) {
      toast('error', ex instanceof Error ? ex.message : 'Failed');
    } finally { setLoading(false); }
  };

  return (
    <form onSubmit={submit}>
      <FormField label="Current Password" error={errors.current} htmlFor="profile-current-pw">
        <input id="profile-current-pw" type="password" value={current} onChange={e => { setCurrent(e.target.value); setErrors(prev => ({ ...prev, current: '' })); }} placeholder="Current password" required />
      </FormField>
      <FormField label="New Password" error={errors.newPass} htmlFor="profile-new-pw">
        <input id="profile-new-pw" type="password" value={newPass} onChange={e => { setNewPass(e.target.value); setErrors(prev => ({ ...prev, newPass: '' })); }} placeholder="New password (min 6 chars)" required minLength={6} />
      </FormField>
      <button type="submit" className="btn btn-primary" disabled={loading}>
        {loading ? 'Saving...' : 'Update Password'}
      </button>
    </form>
  );
};

const DeleteAccountForm = ({ user, apiCall, onDeleted, toast }: { user: ProfileUser | null; apiCall: ApiCallFn; onDeleted: () => void; toast: ToastFn }) => {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState('');

  const handleDelete = async () => {
    setLoading(true);
    try {
      await apiCall('DELETE', '/api/auth/account', user?.auth_provider === 'google' ? {} : { password });
      toast('success', 'Account deleted');
      onDeleted();
    } catch (ex: unknown) {
      toast('error', ex instanceof Error ? ex.message : 'Failed');
    } finally { setLoading(false); setShowModal(false); }
  };

  return (
    <>
      <p className="profile-warning">This action is permanent. All your data and audit history will be removed.</p>
      {user?.auth_provider !== 'google' && (
        <FormField label="Your Password" error={error} htmlFor="profile-delete-pw">
          <input id="profile-delete-pw" type="password" value={password} onChange={e => { setPassword(e.target.value); setError(''); }} placeholder="Enter your password" required />
        </FormField>
      )}
      <button type="button" className="btn btn-danger" onClick={() => setShowModal(true)} disabled={loading}>
        {loading ? 'Deleting...' : 'Delete My Account'}
      </button>
      <ConfirmModal
        open={showModal}
        title="Delete Account?"
        message="This will permanently remove your account and all associated data. This cannot be undone."
        confirmLabel="Delete Forever"
        confirmDanger
        onConfirm={handleDelete}
        onCancel={() => setShowModal(false)}
      />
    </>
  );
};

export default Profile;
