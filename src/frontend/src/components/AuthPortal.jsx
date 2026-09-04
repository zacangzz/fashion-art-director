import React, { useState } from 'react';
import {
  Sparkles,
  Lock,
  Mail,
  LogIn,
  UserPlus,
  AlertCircle,
  Loader2,
  ShieldAlert,
  LogOut,
  RefreshCw,
  Terminal,
  VenetianMask,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function AuthPortal() {
  const {
    currentUser,
    userProfile,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    signOutUser,
    quickDevLogin,
    refreshUserProfile,
    stopProxy,
  } = useAuth();

  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(false);

  // If user is authenticated but not approved or disabled, show Access Restricted screen
  const isRestricted = currentUser && userProfile && userProfile.status !== 'approved';

  const handleGoogleSignIn = async () => {
    setError('');
    setLoading(true);
    try {
      await signInWithGoogle();
    } catch (err) {
      console.error('Google Sign In error:', err);
      setError(err.message || 'Failed to sign in with Google.');
    } finally {
      setLoading(false);
    }
  };

  const handleEmailAuth = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isSignUp) {
        await signUpWithEmail(email, password);
      } else {
        await signInWithEmail(email, password);
      }
    } catch (err) {
      console.error('Auth error:', err);
      let msg = err.message || 'Failed to authenticate';
      if (msg.includes('auth/invalid-credential') || msg.includes('auth/wrong-password')) {
        msg = 'Invalid email or password.';
      } else if (msg.includes('auth/email-already-in-use')) {
        msg = 'This email is already registered. Please sign in.';
      } else if (msg.includes('auth/weak-password')) {
        msg = 'Password should be at least 6 characters.';
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshStatus = async () => {
    setIsCheckingStatus(true);
    try {
      await refreshUserProfile();
    } finally {
      setIsCheckingStatus(false);
    }
  };

  return (
    <div className="auth-portal-container">
      {/* Background Ambient Glows */}
      <div className="auth-portal-glow-1" />
      <div className="auth-portal-glow-2" />

      {/* Main Glass Portal Card */}
      <div className="auth-portal-card">
        {/* Brand Header */}
        <div className="auth-brand-header">
          <div className="auth-brand-badge">
            <Sparkles size={13} />
            <span>mise en scène &bull; Vision Studio</span>
          </div>
          <h1 className="auth-brand-title">mise en scène</h1>
          <p className="auth-brand-subtitle">
            Autonomous multi-modal fashion intelligence, prompt architecture &amp; high-resolution exhibition generation.
          </p>
        </div>

        {/* RESTRICTED / INVITE REQUIRED SCREEN */}
        {isRestricted ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div className="auth-restricted-card">
              <div className="auth-restricted-title">
                <ShieldAlert size={18} />
                <span>Studio Access Restricted (Invite-Only)</span>
              </div>
              <p className="auth-restricted-text">
                Signed in as <span className="auth-restricted-user">{currentUser.email || currentUser.uid}</span>.
              </p>
              <p className="auth-restricted-text">
                This studio operates on an exclusive invite-only whitelist. Your account status is currently{' '}
                <span className="auth-restricted-status">{userProfile?.status || 'unauthorized'}</span>.
                Please contact your administrator to request access.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {userProfile?.is_proxy && (
                <button
                  type="button"
                  onClick={stopProxy}
                  className="auth-btn-primary"
                  style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)', color: '#000000', fontWeight: 600 }}
                  title="Exit proxy mode and return to your authentic administrator account"
                >
                  <VenetianMask size={14} />
                  <span>Exit Proxy Mode (Return to Admin)</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleRefreshStatus}
                disabled={isCheckingStatus}
                className="auth-btn-secondary"
              >
                <RefreshCw size={14} className={isCheckingStatus ? 'animate-spin' : ''} />
                <span>{isCheckingStatus ? 'Checking Whitelist...' : 'Check Approval Status'}</span>
              </button>

              <button
                type="button"
                onClick={signOutUser}
                className="auth-btn-danger"
              >
                <LogOut size={14} />
                <span>Sign Out / Switch Account</span>
              </button>
            </div>
          </div>
        ) : (
          /* AUTHENTICATION FORM SCREEN */
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {error && (
              <div className="auth-alert-error">
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            {/* Google OAuth Button */}
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={loading}
              className="auth-google-btn"
            >
              <svg className="auth-google-icon" viewBox="0 0 24 24">
                <path
                  fill="#EA4335"
                  d="M12 5c1.6 0 3 .6 4.1 1.7l3.1-3.1C17.3 1.8 14.8 1 12 1 7.5 1 3.7 3.6 1.9 7.3l3.7 2.9C6.5 7.4 9 5 12 5z"
                />
                <path
                  fill="#4285F4"
                  d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.6 14.8c-.2-.7-.4-1.5-.4-2.8s.2-2.1.4-2.8L1.9 6.3C.7 8.7 0 10.8 0 12s.7 3.3 1.9 5.7l3.7-2.9z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3 0-5.5-2.4-6.4-5.2L1.9 16C3.7 19.7 7.5 23 12 23z"
                />
              </svg>
              <span>Continue with Google</span>
            </button>

            {/* Divider */}
            <div className="auth-divider">
              <div className="auth-divider-line" />
              <span>or email login</span>
              <div className="auth-divider-line" />
            </div>

            {/* Email Form */}
            <form onSubmit={handleEmailAuth} className="auth-form">
              <div className="auth-input-group">
                <label className="auth-label">Email Address</label>
                <div className="auth-input-wrapper">
                  <Mail size={15} className="auth-input-icon" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="director@fashionstudio.com"
                    className="auth-input"
                  />
                </div>
              </div>

              <div className="auth-input-group">
                <label className="auth-label">Password</label>
                <div className="auth-input-wrapper">
                  <Lock size={15} className="auth-input-icon" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="auth-submit-btn"
              >
                {loading ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : isSignUp ? (
                  <>
                    <UserPlus size={15} />
                    <span>Create Studio Account</span>
                  </>
                ) : (
                  <>
                    <LogIn size={15} />
                    <span>Sign In to Studio</span>
                  </>
                )}
              </button>
            </form>

            {/* Toggle Mode */}
            <div className="auth-toggle-container">
              {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp);
                  setError('');
                }}
                className="auth-toggle-btn"
              >
                {isSignUp ? 'Sign In' : 'Register'}
              </button>
            </div>

            {/* Quick Developer Access */}
            <div className="auth-dev-container">
              <button
                type="button"
                onClick={quickDevLogin}
                className="auth-dev-btn"
                title="Bypass auth for rapid offline local development"
              >
                <Terminal size={13} />
                <span>Developer Quick Access (Local Admin)</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer Branding */}
      <div className="auth-portal-footer">
        mise en scène Studio &bull; Powered by Gemini 3.5 &amp; Imagen 3
      </div>
    </div>
  );
}
