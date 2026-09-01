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
  CheckCircle2,
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
    <div className="relative min-h-screen w-full flex items-center justify-center bg-[#07090e] text-slate-100 overflow-hidden font-sans select-none">
      {/* Dynamic Luxury Editorial Background Gradients */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.15),rgba(255,255,255,0))]" />
      <div className="absolute top-1/4 -left-48 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-48 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b0a_1px,transparent_1px),linear-gradient(to_bottom,#1e293b0a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

      {/* Main Glass Card */}
      <div className="relative z-10 w-full max-w-md mx-4 p-8 sm:p-10 rounded-3xl bg-slate-900/80 backdrop-blur-2xl border border-slate-800/80 shadow-2xl shadow-black/80 flex flex-col gap-6 animate-fade-in">
        
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center gap-2">
          <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-gradient-to-tr from-cyan-500/20 via-slate-800 to-purple-500/20 border border-cyan-500/30 text-cyan-400 shadow-lg shadow-cyan-500/10">
            <Sparkles size={26} className="animate-pulse" />
          </div>
          <span className="text-[10px] tracking-[0.3em] uppercase font-mono font-semibold text-cyan-400/90">
            Haute Couture AI Platform
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Fashion Art Director
          </h1>
          <p className="text-xs text-slate-400 max-w-xs leading-relaxed">
            Autonomous multi-modal fashion intelligence, prompt architecture & high-resolution studio generation.
          </p>
        </div>

        {/* RESTRICTED / INVITE REQUIRED SCREEN */}
        {isRestricted ? (
          <div className="flex flex-col gap-5 pt-2 border-t border-slate-800/80 animate-fade-in">
            <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-800/50 flex flex-col gap-2.5 text-amber-200 text-xs">
              <div className="flex items-center gap-2 font-semibold text-amber-300">
                <ShieldAlert size={18} className="shrink-0 text-amber-400" />
                <span>Studio Access Restricted (Invite-Only)</span>
              </div>
              <p className="text-slate-300 leading-relaxed">
                Signed in as <strong className="text-white font-mono">{currentUser.email || currentUser.uid}</strong>.
              </p>
              <p className="text-slate-400 leading-relaxed text-[11px]">
                This studio operates on an exclusive invite-only whitelist. Your account is currently{' '}
                <span className="font-semibold text-amber-400 uppercase tracking-wider font-mono">
                  {userProfile?.status || 'unauthorized'}
                </span>
                . Please contact your studio administrator to approve access.
              </p>
            </div>

            <div className="flex flex-col gap-2.5">
              <button
                type="button"
                onClick={handleRefreshStatus}
                disabled={isCheckingStatus}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-white flex items-center justify-center gap-2 transition disabled:opacity-50"
              >
                <RefreshCw size={14} className={isCheckingStatus ? 'animate-spin' : ''} />
                <span>{isCheckingStatus ? 'Checking Whitelist...' : 'Check Approval Status'}</span>
              </button>

              <button
                type="button"
                onClick={signOutUser}
                className="w-full py-2.5 px-4 rounded-xl bg-red-950/40 hover:bg-red-900/50 border border-red-800/60 text-xs font-semibold text-red-300 flex items-center justify-center gap-2 transition"
              >
                <LogOut size={14} />
                <span>Sign Out / Switch Account</span>
              </button>
            </div>
          </div>
        ) : (
          /* AUTHENTICATION FORM SCREEN */
          <div className="flex flex-col gap-5 pt-2 border-t border-slate-800/80">
            {error && (
              <div className="flex items-center gap-2.5 p-3 rounded-xl bg-red-950/40 border border-red-800/60 text-red-300 text-xs animate-shake">
                <AlertCircle size={16} className="shrink-0 text-red-400" />
                <span>{error}</span>
              </div>
            )}

            {/* Google OAuth Button */}
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={loading}
              className="w-full py-3 px-4 rounded-xl bg-slate-800/90 hover:bg-slate-700 border border-slate-700/80 text-xs font-semibold text-white flex items-center justify-center gap-3 transition shadow-md hover:border-slate-600 disabled:opacity-50 active:scale-[0.99]"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
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

            <div className="flex items-center gap-3 text-slate-600 text-xs">
              <div className="flex-1 h-px bg-slate-800" />
              <span className="uppercase text-[10px] tracking-wider text-slate-500 font-mono">or email login</span>
              <div className="flex-1 h-px bg-slate-800" />
            </div>

            {/* Email Form */}
            <form onSubmit={handleEmailAuth} className="flex flex-col gap-3.5">
              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
                  Email Address
                </label>
                <div className="relative">
                  <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="director@fashionstudio.com"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 text-xs text-white placeholder-slate-600 outline-none transition"
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
                  Password
                </label>
                <div className="relative">
                  <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 text-xs text-white placeholder-slate-600 outline-none transition"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="mt-1.5 w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 transition disabled:opacity-50 active:scale-[0.99]"
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
            <div className="text-center pt-2 text-xs text-slate-400">
              {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
              <button
                type="button"
                onClick={() => {
                  setIsSignUp(!isSignUp);
                  setError('');
                }}
                className="text-cyan-400 hover:text-cyan-300 font-semibold underline underline-offset-2 ml-1"
              >
                {isSignUp ? 'Sign In' : 'Register'}
              </button>
            </div>

            {/* Quick Developer Access */}
            <div className="pt-3 border-t border-slate-800/60 flex flex-col items-center">
              <button
                type="button"
                onClick={quickDevLogin}
                className="inline-flex items-center gap-1.5 py-1.5 px-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 text-[11px] text-slate-400 hover:text-cyan-300 font-mono transition"
                title="Bypass auth for rapid offline local development"
              >
                <Terminal size={13} className="text-cyan-400" />
                <span>Developer Quick Access (Local Admin)</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer Branding */}
      <div className="absolute bottom-4 text-center text-[11px] font-mono text-slate-600">
        Fashion Art Director Studio &bull; Powered by Gemini 3.5 & Imagen 3
      </div>
    </div>
  );
}
