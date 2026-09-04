import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Users,
  UserPlus,
  Shield,
  Trash2,
  CheckCircle2,
  Clock,
  Ban,
  Search,
  Loader2,
  RefreshCw,
  AlertCircle,
  VenetianMask,
  LogOut,
} from 'lucide-react';
import {
  fetchAdminUsersList,
  inviteUser,
  updateUserStatus,
  deleteUser,
} from '../services/apiClient';
import { useAuth } from '../contexts/AuthContext';
import { formatSpendSGD } from '../utils/formatters';

export default function AdminPortalModal({ isOpen, onClose }) {
  const { userProfile, startProxy, stopProxy } = useAuth();
  const [users, setUsers] = useState([]);
  const [summary, setSummary] = useState({
    total_users: 0,
    approved_count: 0,
    pending_count: 0,
    disabled_count: 0,
    total_spend_usd: 0.0,
    total_spend_sgd: 0.0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  // Form state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('user');
  const [isInviting, setIsInviting] = useState(false);

  // Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchAdminUsersList();
      if (data) {
        setUsers(data.users || []);
        if (data.summary) {
          setSummary(data.summary);
        }
      }
    } catch (err) {
      console.error('Failed to load admin users:', err);
      setError(err.message || 'Failed to load authorized users list.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadUsers();
      setActionSuccess('');
      setError('');
    }
  }, [isOpen, loadUsers]);

  if (!isOpen) return null;

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteEmail || !inviteEmail.includes('@')) {
      setError('Please enter a valid email address.');
      return;
    }

    setIsInviting(true);
    setError('');
    setActionSuccess('');

    try {
      const res = await inviteUser(inviteEmail, inviteRole);
      setActionSuccess(res.message || `Successfully pre-authorized ${inviteEmail}.`);
      setInviteEmail('');
      await loadUsers();
    } catch (err) {
      console.error('Failed to invite user:', err);
      setError(err.message || 'Failed to pre-authorize email.');
    } finally {
      setIsInviting(false);
    }
  };

  const handleToggleStatus = async (user) => {
    const newStatus = user.status === 'approved' ? 'disabled' : 'approved';
    try {
      await updateUserStatus(user.id, { status: newStatus });
      setActionSuccess(`Updated ${user.email} status to ${newStatus}.`);
      await loadUsers();
    } catch (err) {
      console.error('Status update failed:', err);
      setError(err.message || 'Failed to update user status.');
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`Are you sure you want to remove ${user.email} from the studio whitelist?`)) {
      return;
    }
    try {
      await deleteUser(user.id);
      setActionSuccess(`Removed ${user.email} from whitelist.`);
      await loadUsers();
    } catch (err) {
      console.error('Delete user failed:', err);
      setError(err.message || 'Failed to remove user.');
    }
  };

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      !searchQuery ||
      u.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.display_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || u.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="admin-modal-backdrop">
      <div className="admin-modal-container animate-fade-in">
        
        {/* Header */}
        <div className="admin-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div className="admin-header-icon">
              <Users size={20} />
            </div>
            <div>
              <h2 className="admin-modal-title">Studio Whitelist & Team Management</h2>
              <p className="admin-modal-subtitle">
                Pre-authorize team members, manage permissions, and monitor compute spend.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="modal-close-btn"
            title="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="admin-modal-body">
          
          {/* Summary Stats Grid */}
          <div className="admin-stats-grid">
            <div className="admin-stat-card">
              <span className="admin-stat-label">Total Members</span>
              <span className="admin-stat-value">{summary.total_users}</span>
            </div>
            <div className="admin-stat-card">
              <span className="admin-stat-label stat-approved">Approved</span>
              <span className="admin-stat-value stat-approved">{summary.approved_count}</span>
            </div>
            <div className="admin-stat-card">
              <span className="admin-stat-label stat-pending">Pending Invites</span>
              <span className="admin-stat-value stat-pending">{summary.pending_count}</span>
            </div>
            <div className="admin-stat-card">
              <span className="admin-stat-label stat-spend">Studio Spend</span>
              <span className="admin-stat-value stat-spend">{formatSpendSGD(summary.total_spend_sgd, summary.total_spend_usd)}</span>
            </div>
          </div>

          {/* Feedback alerts */}
          {error && (
            <div className="auth-alert-error">
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {actionSuccess && (
            <div className="auth-alert-success">
              <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
              <span>{actionSuccess}</span>
            </div>
          )}

          {/* Invite Form */}
          <div className="admin-invite-form">
            <h3 style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <UserPlus size={14} style={{ color: 'var(--accent-primary, #2563eb)' }} />
              <span>Pre-authorize New Member</span>
            </h3>

            <form onSubmit={handleInvite} className="admin-form-row">
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="designer@fashionstudio.com"
                className="admin-input-email"
              />

              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="admin-select-role"
              >
                <option value="user">Studio Member (User)</option>
                <option value="admin">Fashion Director (Admin)</option>
              </select>

              <button
                type="submit"
                disabled={isInviting}
                className="admin-btn-primary"
              >
                {isInviting ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />}
                <span>Add to Whitelist</span>
              </button>
            </form>
          </div>

          {/* Users Table Controls */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', position: 'relative', flex: 1, minWidth: '220px', maxWidth: '360px' }}>
              <Search size={14} style={{ position: 'absolute', left: '0.75rem', color: 'var(--text-muted)', pointerEvents: 'none' }} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search member email or name..."
                className="admin-input-email"
                style={{ paddingLeft: '2.2rem', width: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="admin-select-role"
              >
                <option value="all">All Statuses ({users.length})</option>
                <option value="approved">Approved</option>
                <option value="pending_invite">Pending Invites</option>
                <option value="disabled">Disabled</option>
              </select>

              <button
                type="button"
                onClick={loadUsers}
                disabled={loading}
                className="admin-action-btn"
                style={{ background: 'var(--bg-inset, #f4f4f6)', borderColor: 'var(--border-static, #eeeef2)', color: 'var(--text-primary)' }}
                title="Refresh user list"
              >
                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* Whitelist Table */}
          <div className="admin-table-container">
            <div style={{ overflowX: 'auto' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Spend</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && users.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        <Loader2 size={20} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: 'var(--accent-primary, #2563eb)' }} />
                        Loading studio whitelist...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                        No members match the current filter.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => {
                      const isCurrentProxy = Boolean(userProfile?.is_proxy && (userProfile.id === u.id || userProfile.uid === u.id || userProfile.email === u.email));
                      const realAdminId = userProfile?.real_user?.id || userProfile?.real_user?.uid || (!userProfile?.is_proxy ? (userProfile?.id || userProfile?.uid) : null);
                      const realAdminEmail = userProfile?.real_user?.email || (!userProfile?.is_proxy ? userProfile?.email : null);
                      const isOwnAdminAccount = Boolean((realAdminId && (realAdminId === u.id || realAdminId === u.uid)) || (realAdminEmail && realAdminEmail === u.email));

                      return (
                        <tr key={u.id || u.email} className={isCurrentProxy ? "admin-row-active-proxy" : ""}>
                          {/* Member */}
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                              {u.photo_url ? (
                                <img src={u.photo_url} alt="" style={{ width: '28px', height: '28px', borderRadius: '50%', objectFit: 'cover' }} />
                              ) : (
                                <div className="admin-avatar-fallback">
                                  {(u.email || 'U')[0].toUpperCase()}
                                </div>
                              )}
                              <div style={{ display: 'flex', flexDirection: 'column' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                  <span style={{ fontWeight: 600, color: 'var(--text-primary, #18181b)' }}>{u.display_name || u.email}</span>
                                  {isCurrentProxy && (
                                    <span className="admin-badge admin-badge-active-proxy">
                                      <VenetianMask size={10} /> Active Proxy
                                    </span>
                                  )}
                                </div>
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #52525b)', fontFamily: 'var(--font-mono)' }}>{u.email}</span>
                              </div>
                            </div>
                          </td>

                          {/* Role */}
                          <td>
                            <span className={`admin-badge ${u.role === 'admin' ? 'admin-badge-role-admin' : 'admin-badge-role-user'}`}>
                              {u.role === 'admin' && <Shield size={10} />}
                              {u.role}
                            </span>
                          </td>

                          {/* Status */}
                          <td>
                            <span className={`admin-badge ${u.status === 'approved' ? 'admin-badge-approved' : u.status === 'pending_invite' ? 'admin-badge-pending' : 'admin-badge-disabled'}`}>
                              {u.status === 'approved' && <CheckCircle2 size={10} />}
                              {u.status === 'pending_invite' && <Clock size={10} />}
                              {u.status === 'disabled' && <Ban size={10} />}
                              {u.status}
                            </span>
                          </td>

                          {/* Spend */}
                          <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary, #52525b)' }}>
                            {formatSpendSGD(u.total_spend_sgd, u.total_spend_usd)}
                          </td>

                          {/* Actions */}
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                              {/* Act as User / Exit Proxy button */}
                              {isCurrentProxy ? (
                                <button
                                  type="button"
                                  onClick={async () => {
                                    await stopProxy();
                                    onClose();
                                  }}
                                  className="admin-action-btn admin-btn-active-proxy"
                                  title="Active proxy session — click to exit proxy"
                                >
                                  <LogOut size={12} />
                                  <span>Exit Proxy</span>
                                </button>
                              ) : isOwnAdminAccount ? (
                                <span className="admin-badge admin-badge-current-admin" title="Your authentic administrator account">
                                  <Shield size={10} />
                                  <span>You</span>
                                </span>
                              ) : (
                                <button
                                  type="button"
                                  onClick={async () => {
                                    await startProxy(u);
                                    onClose();
                                  }}
                                  className="admin-action-btn admin-btn-proxy"
                                  title={`Proxy into ${u.email} and act on their behalf`}
                                >
                                  <VenetianMask size={12} />
                                  <span>Act as User</span>
                                </button>
                              )}

                              <button
                                type="button"
                                onClick={() => handleToggleStatus(u)}
                                disabled={isOwnAdminAccount}
                                className={`admin-action-btn ${u.status === 'approved' ? 'admin-btn-disable' : 'admin-btn-approve'}`}
                                title={u.status === 'approved' ? 'Disable Account' : 'Approve Account'}
                              >
                                {u.status === 'approved' ? 'Disable' : 'Approve'}
                              </button>

                              <button
                                type="button"
                                onClick={() => handleDelete(u)}
                                disabled={isOwnAdminAccount}
                                className="admin-action-btn admin-btn-delete"
                                title="Delete / Revoke Member"
                              >
                                <Trash2 size={12} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="admin-modal-footer">
          <span>Whitelist synchronization is instant</span>
          <button
            onClick={onClose}
            className="auth-btn-secondary"
            style={{ width: 'auto', padding: '0.4rem 1rem' }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
