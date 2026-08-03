import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Building2, Users, Key, Plus, Copy, Check, AlertCircle, LogOut, UserPlus } from 'lucide-react';
import { API_URL as API } from '../config';
import './Pages.css';

const Teams = () => {
  const { user, token } = useAuth();
  const { toast } = useToast();
  const [orgs, setOrgs] = useState<any[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [orgKeys, setOrgKeys] = useState<string[]>([]);
  const [copied, setCopied] = useState('');
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loading, setLoading] = useState(true);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchOrgs = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/orgs`, { headers });
      const d = await r.json();
      setOrgs(d.orgs || []);
    } catch (e) { toast("error", 'Failed to fetch organizations'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchOrgs(); }, []);

  const createOrg = async () => {
    if (!newOrgName.trim()) return;
    try {
      const r = await fetch(`${API}/api/orgs/create`, { method: 'POST', headers, body: JSON.stringify({ name: newOrgName }) });
      const d = await r.json();
      if (r.ok) { setNewOrgName(''); setShowCreate(false); await fetchOrgs(); setMessage({ type: 'success', text: `"${d.org.name}" created!` }); }
      else setMessage({ type: 'error', text: d.detail || 'Failed' });
    } catch (e) { setMessage({ type: 'error', text: 'Failed to connect to server' }); }
  };

  const selectOrg = async (org: any) => {
    setSelectedOrg(org);
    setInviteEmail('');
    setOrgKeys([]);
    try {
      const r = await fetch(`${API}/api/orgs/${org.id}`, { headers });
      const d = await r.json();
      if (d.org) setSelectedOrg(d.org);
    } catch (e) { toast("error", 'Failed to load organization details'); }
    setMessage({ type: '', text: '' });
  };

  const inviteMember = async () => {
    if (!inviteEmail.trim()) return;
    try {
      const r = await fetch(`${API}/api/orgs/${selectedOrg.id}/invite`, { method: 'POST', headers, body: JSON.stringify({ email: inviteEmail }) });
      const d = await r.json();
      if (r.ok) { setInviteEmail(''); setMessage({ type: 'success', text: d.message }); }
      else setMessage({ type: 'error', text: d.detail || 'Failed' });
    } catch (e) { setMessage({ type: 'error', text: 'Failed to connect to server' }); }
  };

  const removeMember = async (email: string) => {
    try {
      const r = await fetch(`${API}/api/orgs/${selectedOrg.id}/members/${email}`, { method: 'DELETE', headers });
      if (r.ok) { setSelectedOrg({ ...selectedOrg, members: selectedOrg.members.filter((m: string) => m !== email) }); }
    } catch (e) { toast("error", 'Failed to remove member'); }
  };

  const genOrgKey = async () => {
    try {
      const r = await fetch(`${API}/api/orgs/${selectedOrg.id}/api-key`, { method: 'POST', headers });
      const d = await r.json();
      if (r.ok) { setOrgKeys([...orgKeys, d.api_key]); setCopied(d.api_key); setTimeout(() => setCopied(''), 2000); }
    } catch (e) { toast("error", 'Failed to generate API key'); }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
      setTimeout(() => setCopied(''), 2000);
    } catch { toast("error", 'Failed to copy to clipboard'); }
  };

  if (loading) return <div className="page"><section className="section"><div className="container" style={{ textAlign: 'center', padding: '4rem 0' }}>Loading...</div></section></div>;

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: 800 }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="section-title">Teams & Organizations</h1>
            <p className="section-subtitle" style={{ textAlign: 'center', marginBottom: '2rem' }}>Collaborate with your team on carbon-aware routing.</p>

            {message.text && <div className={`auth-error`} style={{ borderColor: message.type === 'success' ? 'var(--accent)' : undefined, marginBottom: '1rem' }}><AlertCircle size={16} /> {message.text}</div>}

            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
              {!showCreate && <button className="btn btn-primary" onClick={() => setShowCreate(true)}><Plus size={16} /> Create Organization</button>}
            </div>

            {showCreate && (
              <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
                <h3>New Organization</h3>
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                  <label htmlFor="org-name" style={{ display: 'none' }}>Organization name</label>
                  <input id="org-name" value={newOrgName} onChange={e => setNewOrgName(e.target.value)} placeholder="Organization name" style={{ flex: 1 }} />
                  <button className="btn btn-primary" onClick={createOrg}>Create</button>
                  <button className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: selectedOrg ? '1fr 1fr' : '1fr' }}>
              <div>
                <h2 style={{ marginBottom: '1rem' }}><Building2 size={20} /> Your Organizations</h2>
                {orgs.length === 0 ? <p style={{ color: 'var(--text-secondary)' }}>No organizations yet. Create one to get started.</p> : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {orgs.map(o => (
                      <div key={o.id} className={`card ${selectedOrg?.id === o.id ? 'pricing-featured' : ''}`} style={{ padding: '1rem', cursor: 'pointer' }} onClick={() => selectOrg(o)}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <strong>{o.name}</strong>
                          <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}><Users size={14} /> {o.members?.length || 1}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {selectedOrg && (
                <div>
                  <h2 style={{ marginBottom: '1rem' }}><Users size={20} /> {selectedOrg.name}</h2>
                  <div className="card" style={{ padding: '1.5rem', marginBottom: '1rem' }}>
                    <h3 style={{ marginBottom: '0.75rem' }}>Members</h3>
                    {selectedOrg.members?.map((m: string) => (
                      <div key={m} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border-color)' }}>
                        <span>{m} {m === selectedOrg.owner && <span style={{ color: 'var(--accent)', fontSize: '0.8rem' }}>(Owner)</span>}</span>
                        {m !== selectedOrg.owner && user?.email === selectedOrg.owner && (
                          <button className="btn btn-danger" style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }} onClick={() => removeMember(m)}><LogOut size={14} /></button>
                        )}
                      </div>
                    ))}
                    {user?.email === selectedOrg.owner && (
                      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                        <label htmlFor="invite-email" style={{ display: 'none' }}>Email to invite</label>
                        <input id="invite-email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="Email to invite" style={{ flex: 1 }} />
                        <button className="btn btn-primary" onClick={inviteMember}><UserPlus size={16} /> Invite</button>
                      </div>
                    )}
                  </div>

                  <div className="card" style={{ padding: '1.5rem' }}>
                    <h3 style={{ marginBottom: '0.75rem' }}><Key size={16} /> Shared API Keys</h3>
                    {selectedOrg.api_keys?.length === 0 && orgKeys.length === 0 && <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No keys yet.</p>}
                    {[...(selectedOrg.api_keys || []), ...orgKeys.map(k => ({ key: k }))].map((k: any, i: number) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        <code style={{ flex: 1, padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: '4px', fontSize: '0.8rem' }}>{k.key || k}</code>
                        <button className="btn-icon" onClick={() => copyToClipboard(k.key || k)} aria-label="Copy key">
                          {copied === (k.key || k) ? <Check size={16} /> : <Copy size={16} />}
                        </button>
                      </div>
                    ))}
                    {user?.email === selectedOrg.owner && <button className="btn btn-secondary" style={{ marginTop: '0.5rem' }} onClick={genOrgKey}><Key size={16} /> Generate Key</button>}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default Teams;
