import React from 'react';
import {
  VenetianMask,
  Shield,
  LogOut,
  Users,
  DollarSign,
  AlertTriangle,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { formatSpendSGD } from '../utils/formatters';

export default function ProxyBanner({ onOpenAdminModal }) {
  const { userProfile, stopProxy } = useAuth();

  if (!userProfile?.is_proxy) return null;

  const targetName = userProfile.display_name || userProfile.email || 'Studio Member';
  const targetEmail = userProfile.email;
  const adminEmail =
    userProfile.proxied_by?.email ||
    userProfile.real_user?.email ||
    'Administrator';

  return (
    <div className="proxy-banner" role="status" aria-label="Proxy Account Session Banner">
      <div className="proxy-banner-inner">
        {/* Left: Icon & Target Identity */}
        <div className="proxy-banner-identity">
          <div className="proxy-banner-icon-box">
            <VenetianMask size={16} />
          </div>

          <div className="proxy-banner-text">
            <div className="proxy-banner-headline">
              <span className="proxy-banner-title">PROXY SESSION ACTIVE</span>
              <span className="proxy-banner-divider">•</span>
              <span className="proxy-banner-target">
                Acting as <strong>{targetName}</strong> {targetEmail && `(${targetEmail})`}
              </span>
            </div>

            <div className="proxy-banner-meta">
              <span className="proxy-meta-tag">
                <Shield size={10} />
                <span>Role: {userProfile.role || 'user'}</span>
              </span>

              <span className="proxy-meta-tag">
                <DollarSign size={10} />
                <span>Spend: {formatSpendSGD(userProfile.total_spend_sgd, userProfile.total_spend_usd)}</span>
              </span>

              <span className="proxy-meta-tag proxy-meta-admin">
                <span>Authenticated Admin: {adminEmail}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="proxy-banner-actions">
          {onOpenAdminModal && (
            <button
              type="button"
              onClick={onOpenAdminModal}
              className="proxy-btn-switch"
              title="Open Whitelist & Switch Proxy User"
            >
              <Users size={13} />
              <span>Switch User</span>
            </button>
          )}

          <button
            type="button"
            onClick={stopProxy}
            className="proxy-btn-exit"
            title="Exit proxy mode and return to your administrator account"
          >
            <LogOut size={13} />
            <span>Exit Proxy</span>
          </button>
        </div>
      </div>
    </div>
  );
}
