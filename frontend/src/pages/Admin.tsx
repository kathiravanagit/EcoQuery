import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Shield, Users, BarChart3, Leaf, Search, Building2, ChevronLeft, ChevronRight } from 'lucide-react';
import { API_URL as API } from '../config';
import './Pages.css';
const PAGE_SIZE = 10;

const Admin = () => {
  const { user, token } = useAuth();
  const { toast } = useToast();
  const [users, setUsers] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [tab, setTab] = useState<'users' | 'stats'>('stats');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);

  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/admin/stats`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
      fetch(`${API}/api/admin/users?limit=200`, { headers }).then(r => { if (!r.ok) throw new Error(); return r.json(); }),
    ]).then(([s, u]) => { setStats(s); setUsers(u.users || []); }).catch(() => { toast.error('Failed to load admin data'); }).finally(() => setLoading(false));
  }, [token]);

  const toggleRole = async (email: string, current: string) => {
    const newRole = current === 'admin' ? 'user' : 'admin';
    const r = await fetch(`${API}/api/admin/users/${email}`, { method: 'PATCH', headers, body: JSON.stringify({ role: newRole }) });
    if (r.ok) setUsers(users.map(u => u.email === email ? { ...u, role: newRole } : u));
  };

  const toggleActive = async (email: string, current: boolean) => {
    const r = await fetch(`${API}/api/admin/users/${email}`, { method: 'PATCH', headers, body: JSON.stringify({ is_active: !current }) });
    if (r.ok) setUsers(users.map(u => u.email === email ? { ...u, is_active: !current } : u));
  };

  const filtered = users.filter(u => u.email.toLowerCase().includes(search.toLowerCase()) || u.display_name?.toLowerCase().includes(search.toLowerCase()));
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  useEffect(() => { setPage(0); }, [search]);

  if (loading) return <div className="page"><section className="section"><div className="container" style={{ textAlign: 'center', padding: '4rem 0' }}>Loading...</div></section></div>;

  return (
    <div className="page">
      <section className="section">
        <div className="container" style={{ maxWidth: 900 }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="section-title"><Shield size={24} /> Admin Panel</h1>

            {tab === 'stats' && (
              <>
                <div className="dashboard-cards" style={{ marginBottom: '2rem' }}>
                  <div className="dashboard-card">
                    <Users size={24} style={{ color: 'var(--accent)' }} />
                    <div className="dashboard-card-value">{stats?.total_users || 0}</div>
                    <div className="dashboard-card-label">Total Users</div>
                  </div>
                  <div className="dashboard-card">
                    <BarChart3 size={24} style={{ color: 'var(--accent)' }} />
                    <div className="dashboard-card-value">{stats?.total_queries || 0}</div>
                    <div className="dashboard-card-label">Total Queries</div>
                  </div>
                  <div className="dashboard-card">
                    <Leaf size={24} style={{ color: 'var(--accent)' }} />
                    <div className="dashboard-card-value">{stats?.total_co2_saved_g || 0}g</div>
                    <div className="dashboard-card-label">CO₂ Saved</div>
                  </div>
                  <div className="dashboard-card">
                    <Building2 size={24} style={{ color: 'var(--accent)' }} />
                    <div className="dashboard-card-value">{stats?.org_count || 0}</div>
                    <div className="dashboard-card-label">Organizations</div>
                  </div>
                </div>
                <button className="btn btn-primary" onClick={() => setTab('users')}><Users size={16} /> Manage Users</button>
              </>
            )}

            {tab === 'users' && (
              <>
                <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
                  <div className="input-group" style={{ flex: 1 }}>
                    <Search size={18} />
                    <input placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} />
                  </div>
                  <button className="btn btn-secondary" onClick={() => setTab('stats')}><BarChart3 size={16} /> Stats</button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {paged.map(u => (
                    <div key={u.email} className="card" style={{ padding: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>{u.display_name || u.email}</strong>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                          {u.email} · {u.auth_provider} · Role: <span style={{ color: u.role === 'admin' ? 'var(--accent)' : undefined }}>{u.role}</span>
                          {u.email_verified ? ' · ✅ Verified' : ''}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-secondary" style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }} onClick={() => toggleRole(u.email, u.role)}>
                          {u.role === 'admin' ? 'Revoke Admin' : 'Make Admin'}
                        </button>
                        <button className="btn btn-danger" style={{ padding: '0.3rem 0.75rem', fontSize: '0.8rem' }} onClick={() => toggleActive(u.email, u.is_active)}>
                          {u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </div>
                  ))}
                  {filtered.length === 0 && <p>No users found.</p>}
                </div>
                {totalPages > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.75rem', marginTop: '1.5rem' }}>
                    <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem' }} disabled={page === 0} onClick={() => setPage(p => p - 1)}>
                      <ChevronLeft size={16} />
                    </button>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      Page {page + 1} of {totalPages}
                    </span>
                    <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem' }} disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>
                      <ChevronRight size={16} />
                    </button>
                  </div>
                )}
              </>
            )}
          </motion.div>
        </div>
      </section>
    </div>
  );
};

export default Admin;
