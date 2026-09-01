import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Users,
  UserPlus,
  Shield,
  ShieldCheck,
  ShieldAlert,
  Trash2,
  CheckCircle2,
  Clock,
  Ban,
  Search,
  DollarSign,
  Loader2,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import {
  fetchAdminUsersList,
  inviteUser,
  updateUserStatus,
  deleteUser,
} from '../services/apiClient';

export default function AdminPortalModal({ isOpen, onClose }) {
  const [users, setUsers] = useState([]);
  const [summary, setSummary] = useState({
    total_users: 0,
    approved_count: 0,
    pending_count: 0,
    disabled_count: 0,
    total_spend_usd: 0.0,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col text-slate-200">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-800/80 flex items-center justify-between bg-slate-950/40">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Users size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span>Studio Whitelist & Team Management</span>
              </h2>
              <p className="text-xs text-slate-400">
                Pre-authorize team members, manage permissions, and monitor compute spend.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 overflow-y-auto flex flex-col gap-6">
          
          {/* Summary Stats Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] font-mono uppercase text-slate-400 tracking-wider">Total Members</span>
              <span className="text-2xl font-bold text-white">{summary.total_users}</span>
            </div>
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] font-mono uppercase text-emerald-400 tracking-wider">Approved</span>
              <span className="text-2xl font-bold text-emerald-400">{summary.approved_count}</span>
            </div>
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] font-mono uppercase text-amber-400 tracking-wider">Pending Invites</span>
              <span className="text-2xl font-bold text-amber-400">{summary.pending_count}</span>
            </div>
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 flex flex-col gap-1">
              <span className="text-[11px] font-mono uppercase text-cyan-400 tracking-wider">Studio Spend</span>
              <span className="text-2xl font-bold text-cyan-400">${summary.total_spend_usd.toFixed(2)}</span>
            </div>
          </div>

          {/* Feedback alerts */}
          {error && (
            <div className="flex items-center gap-2 p-3.5 rounded-xl bg-red-950/50 border border-red-800 text-red-300 text-xs animate-fade-in">
              <AlertCircle size={16} className="shrink-0 text-red-400" />
              <span>{error}</span>
            </div>
          )}

          {actionSuccess && (
            <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs animate-fade-in">
              <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
              <span>{actionSuccess}</span>
            </div>
          )}

          {/* Invite Form */}
          <div className="p-5 rounded-2xl bg-slate-950/40 border border-slate-800/80 flex flex-col gap-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono flex items-center gap-2">
              <UserPlus size={15} className="text-cyan-400" />
              <span>Pre-authorize New Member</span>
            </h3>

            <form onSubmit={handleInvite} className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="designer@fashionstudio.com"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-700 focus:border-cyan-500 text-xs text-white placeholder-slate-500 outline-none transition"
                />
              </div>

              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="px-3 py-2.5 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white outline-none focus:border-cyan-500"
              >
                <option value="user">Studio Member (User)</option>
                <option value="admin">Fashion Director (Admin)</option>
              </select>

              <button
                type="submit"
                disabled={isInviting}
                className="py-2.5 px-5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-cyan-600/20 transition disabled:opacity-50"
              >
                {isInviting ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />}
                <span>Add to Whitelist</span>
              </button>
            </form>
          </div>

          {/* Users Table Controls */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-2 flex-1 max-w-sm relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search member email or name..."
                className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-600 outline-none focus:border-cyan-500 transition"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 outline-none focus:border-cyan-500"
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
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Refresh user list"
              >
                <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* Whitelist Table */}
          <div className="rounded-2xl border border-slate-800 overflow-hidden bg-slate-950/30">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-950/60 text-slate-400 font-mono uppercase text-[10px] tracking-wider">
                    <th className="py-3 px-4">Member</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Spend</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {loading && users.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500">
                        <Loader2 size={20} className="animate-spin mx-auto mb-2 text-cyan-400" />
                        Loading studio whitelist...
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500">
                        No members match the current filter.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((u) => (
                      <tr key={u.id || u.email} className="hover:bg-slate-800/30 transition">
                        {/* Member */}
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2.5">
                            {u.photo_url ? (
                              <img src={u.photo_url} alt="" className="w-7 h-7 rounded-full object-cover border border-slate-700" />
                            ) : (
                              <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-cyan-400 font-mono text-[11px] font-bold">
                                {(u.email || 'U')[0].toUpperCase()}
                              </div>
                            )}
                            <div className="flex flex-col">
                              <span className="font-semibold text-white">{u.display_name || u.email}</span>
                              <span className="text-[11px] text-slate-400 font-mono">{u.email}</span>
                            </div>
                          </div>
                        </td>

                        {/* Role */}
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider font-semibold ${
                              u.role === 'admin'
                                ? 'bg-purple-950/60 text-purple-300 border border-purple-800/50'
                                : 'bg-slate-800 text-slate-300 border border-slate-700'
                            }`}
                          >
                            {u.role === 'admin' ? <Shield size={10} /> : null}
                            {u.role}
                          </span>
                        </td>

                        {/* Status */}
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider font-semibold ${
                              u.status === 'approved'
                                ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/50'
                                : u.status === 'pending_invite'
                                ? 'bg-amber-950/60 text-amber-300 border border-amber-800/50'
                                : 'bg-red-950/60 text-red-300 border border-red-800/50'
                            }`}
                          >
                            {u.status === 'approved' && <CheckCircle2 size={10} />}
                            {u.status === 'pending_invite' && <Clock size={10} />}
                            {u.status === 'disabled' && <Ban size={10} />}
                            {u.status}
                          </span>
                        </td>

                        {/* Spend */}
                        <td className="py-3 px-4 font-mono text-slate-300">
                          ${(u.total_spend_usd || 0).toFixed(2)}
                        </td>

                        {/* Actions */}
                        <td className="py-3 px-4 text-right">
                          <div className="inline-flex items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleToggleStatus(u)}
                              className={`p-1.5 rounded-lg border text-[11px] transition ${
                                u.status === 'approved'
                                  ? 'bg-amber-950/30 border-amber-800/50 text-amber-300 hover:bg-amber-900/40'
                                  : 'bg-emerald-950/30 border-emerald-800/50 text-emerald-300 hover:bg-emerald-900/40'
                              }`}
                              title={u.status === 'approved' ? 'Disable Account' : 'Approve Account'}
                            >
                              {u.status === 'approved' ? 'Disable' : 'Approve'}
                            </button>

                            <button
                              type="button"
                              onClick={() => handleDelete(u)}
                              className="p-1.5 rounded-lg bg-red-950/30 border border-red-800/50 text-red-400 hover:bg-red-900/40 transition"
                              title="Delete / Revoke Member"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800/80 flex items-center justify-between bg-slate-950/40 text-xs text-slate-500 font-mono">
          <span>Whitelist synchronization is instant</span>
          <button
            onClick={onClose}
            className="py-1.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-sans transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
