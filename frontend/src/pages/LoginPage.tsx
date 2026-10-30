import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Layers,
  Lock,
  Mail,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  ShieldCheck,
  RefreshCw,
  KeyRound,
  ArrowLeft,
  Building,
  UserCheck,
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { useAuthStore, BLOCKED_DOMAINS } from '@/stores/useAuthStore';
import { useUIStore } from '@/stores/useUIStore';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggleTheme } = useUIStore();
  const isDark = theme === 'dark';

  const {
    loginWithEmail,
    requestPasswordResetCode,
    verifyResetCode,
    completePasswordReset,
  } = useAuthStore();

  // Mode: 'login' | 'reset-email' | 'reset-otp' | 'reset-newpass' | 'reset-success'
  const [view, setView] = useState<
    'login' | 'reset-email' | 'reset-otp' | 'reset-newpass' | 'reset-success'
  >('login');

  // Login form state
  const [email, setEmail] = useState('alex.morgan@company.com');
  const [password, setPassword] = useState('Enterprise@2026!');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Reset password state
  const [resetEmailInput, setResetEmailInput] = useState('');
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resendCountdown, setResendCountdown] = useState(45);

  const otpInputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Resend timer effect
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (view === 'reset-otp' && resendCountdown > 0) {
      timer = setTimeout(() => setResendCountdown((c) => c - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [view, resendCountdown]);

  // Handle Login submission
  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsLoading(true);

    setTimeout(() => {
      const res = loginWithEmail(email, password);
      setIsLoading(false);

      if (res.success) {
        navigate('/');
      } else {
        setLoginError(res.error || 'Authentication failed.');
      }
    }, 400);
  };

  // Quick fill helper for demo testing
  const handleQuickFill = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setLoginError(null);
  };

  // Handle Request Reset Code (Step 1)
  const handleRequestResetCode = (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    setIsLoading(true);

    setTimeout(() => {
      setIsLoading(false);
      const res = requestPasswordResetCode(resetEmailInput);
      if (res.success) {
        setResendCountdown(45);
        setOtpDigits(['', '', '', '', '', '']);
        setView('reset-otp');
      } else {
        setResetError(res.error || 'Failed to send code.');
      }
    }, 450);
  };

  // Handle OTP digit changes
  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;

    const newDigits = [...otpDigits];
    newDigits[index] = value.slice(-1);
    setOtpDigits(newDigits);
    setResetError(null);

    // Auto-advance to next input
    if (value && index < 5) {
      otpInputRefs.current[index + 1]?.focus();
    }
  };

  // Handle OTP Backspace navigation
  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus();
    }
  };

  // Handle OTP Paste
  const handleOtpPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;

    const newDigits = [...otpDigits];
    for (let i = 0; i < pasted.length; i++) {
      newDigits[i] = pasted[i];
    }
    setOtpDigits(newDigits);
    const nextFocusIndex = Math.min(pasted.length, 5);
    otpInputRefs.current[nextFocusIndex]?.focus();
  };

  // Handle Verify OTP (Step 2)
  const handleVerifyOtp = (e: React.FormEvent) => {
    e.preventDefault();
    const code = otpDigits.join('');
    if (code.length < 6) {
      setResetError('Please enter all 6 digits of the verification code.');
      return;
    }

    setIsLoading(true);
    setResetError(null);

    setTimeout(() => {
      setIsLoading(false);
      const res = verifyResetCode(code);
      if (res.success) {
        setView('reset-newpass');
      } else {
        setResetError(res.error || 'Invalid code.');
      }
    }, 400);
  };

  // Handle Set New Password (Step 3)
  const handleSetNewPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setResetError('Password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setResetError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    setResetError(null);

    setTimeout(() => {
      setIsLoading(false);
      const res = completePasswordReset(newPassword);
      if (res.success) {
        setView('reset-success');
      } else {
        setResetError(res.error || 'Failed to update password.');
      }
    }, 400);
  };

  return (
    <div className="min-h-screen bg-background text-enterprise-text flex flex-col justify-between p-4 sm:p-8 relative overflow-hidden select-none">
      {/* Precision Background Glow & Ambient Grid */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 right-1/4 w-[500px] h-[500px] bg-primary/8 blur-[140px] rounded-full" />
        <div className="absolute bottom-0 left-1/4 w-[450px] h-[450px] bg-black/10 dark:bg-black/40 blur-[120px] rounded-full" />
      </div>

      {/* Top Header Bar */}
      <div className="relative z-10 max-w-6xl w-full mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-neutral-900 text-white dark:bg-primary dark:text-white flex items-center justify-center font-bold shadow-subtle">
            <Layers className="h-5 w-5" />
          </div>
          <div>
            <span className="font-bold text-base tracking-tight text-enterprise-text">
              EnterpriseQuery
            </span>
            <span className="hidden sm:inline-block ml-2 text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-surface-muted text-enterprise-muted border border-surface-border font-semibold">
              Corporate Gateway
            </span>
          </div>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="h-9 px-3 rounded-xl border border-surface-border bg-surface-elevated text-xs font-semibold text-enterprise-text hover:text-primary transition-colors shadow-subtle flex items-center gap-2"
        >
          <span className="font-mono">{isDark ? 'Dark Mode' : 'Light Mode'}</span>
        </button>
      </div>

      {/* Main Center Card Viewport */}
      <div className="relative z-10 w-full max-w-md mx-auto my-auto py-8">
        <AnimatePresence mode="wait">
          {/* VIEW 1: SIGN IN FORM */}
          {view === 'login' && (
            <motion.div
              key="login"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
              className="rounded-3xl border border-surface-border bg-surface-elevated p-7 sm:p-9 shadow-paper space-y-6"
            >
              <div className="space-y-1.5 text-center">
                <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-primary/10 border border-primary/20 text-primary mb-2 shadow-sm">
                  <Lock className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-enterprise-text">
                  Sign in to Enterprise
                </h2>
                <p className="text-xs text-enterprise-muted max-w-xs mx-auto leading-relaxed">
                  Authentication restricted exclusively to authorized company email addresses.
                </p>
              </div>

              {/* Login Error Notification */}
              {loginError && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 leading-relaxed"
                >
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{loginError}</span>
                </motion.div>
              )}

              {/* Form */}
              <form onSubmit={handleLoginSubmit} className="space-y-4">
                {/* Company Email Field */}
                <div>
                  <label className="block text-xs font-semibold text-enterprise-text mb-1.5">
                    Corporate Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-3 h-4 w-4 text-enterprise-dim" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (loginError) setLoginError(null);
                      }}
                      placeholder="name@company.com"
                      className="w-full bg-surface-muted border border-surface-border rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-enterprise-text font-mono placeholder-enterprise-dim focus:outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                    />
                  </div>
                  <p className="text-[11px] text-enterprise-dim mt-1 font-mono">
                    Must be corporate domain (e.g. @company.com)
                  </p>
                </div>

                {/* Password Field */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-semibold text-enterprise-text">
                      Password
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setResetEmailInput(email);
                        setResetError(null);
                        setView('reset-email');
                      }}
                      className="text-xs text-primary hover:underline font-semibold"
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-3 h-4 w-4 text-enterprise-dim" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      required
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (loginError) setLoginError(null);
                      }}
                      placeholder="••••••••••••"
                      className="w-full bg-surface-muted border border-surface-border rounded-xl pl-10 pr-10 py-2.5 text-sm text-enterprise-text font-mono placeholder-enterprise-dim focus:outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/20"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-3 text-enterprise-dim hover:text-enterprise-text"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {/* Remember Me */}
                <div className="flex items-center justify-between pt-1">
                  <label className="flex items-center gap-2 text-xs text-enterprise-muted cursor-pointer">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="rounded border-surface-border text-primary focus:ring-primary h-3.5 w-3.5"
                    />
                    <span>Remember this device</span>
                  </label>
                  <span className="text-[11px] font-mono text-enterprise-dim">
                    TLS 1.3 Partition Isolated
                  </span>
                </div>

                {/* Submit Button */}
                <Button
                  type="submit"
                  size="lg"
                  isLoading={isLoading}
                  className="w-full font-semibold gap-2 shadow-warm mt-2"
                >
                  <span>Sign In to Vault</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </form>

              {/* Quick Fill Demo Access Helper */}
              <div className="pt-4 border-t border-surface-border space-y-2.5">
                <div className="flex items-center justify-between text-[11px] font-mono text-enterprise-dim">
                  <span>PROTOTYPE TEST ACCOUNTS</span>
                  <span>1-CLICK AUTOFILL</span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs font-semibold">
                  <button
                    type="button"
                    onClick={() => handleQuickFill('alex.morgan@company.com', 'Enterprise@2026!')}
                    className="p-2.5 rounded-xl border border-surface-border bg-surface-muted/60 hover:bg-surface-muted hover:border-primary/50 text-left transition-colors flex flex-col gap-0.5"
                  >
                    <span className="text-enterprise-text font-bold flex items-center gap-1.5">
                      <UserCheck className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                      <span>Employee</span>
                    </span>
                    <span className="text-[10px] text-enterprise-dim font-mono truncate">
                      alex.morgan@company.com
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleQuickFill('admin@enterprise.internal', 'Admin@2026!')}
                    className="p-2.5 rounded-xl border border-surface-border bg-surface-muted/60 hover:bg-surface-muted hover:border-primary/50 text-left transition-colors flex flex-col gap-0.5"
                  >
                    <span className="text-enterprise-text font-bold flex items-center gap-1.5">
                      <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                      <span>Admin</span>
                    </span>
                    <span className="text-[10px] text-enterprise-dim font-mono truncate">
                      admin@enterprise.internal
                    </span>
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* VIEW 2: PASSWORD RESET - STEP 1 (ENTER EMAIL) */}
          {view === 'reset-email' && (
            <motion.div
              key="reset-email"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
              className="rounded-3xl border border-surface-border bg-surface-elevated p-7 sm:p-9 shadow-paper space-y-6"
            >
              <div className="space-y-1.5 text-center">
                <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-primary/10 border border-primary/20 text-primary mb-2 shadow-sm">
                  <KeyRound className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-enterprise-text">
                  Reset Password
                </h2>
                <p className="text-xs text-enterprise-muted max-w-xs mx-auto leading-relaxed">
                  Enter your company email. We will send a 6-digit verification code to confirm your identity.
                </p>
              </div>

              {resetError && (
                <div className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 leading-relaxed">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{resetError}</span>
                </div>
              )}

              <form onSubmit={handleRequestResetCode} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-enterprise-text mb-1.5">
                    Corporate Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-3 h-4 w-4 text-enterprise-dim" />
                    <input
                      type="email"
                      required
                      autoFocus
                      value={resetEmailInput}
                      onChange={(e) => {
                        setResetEmailInput(e.target.value);
                        if (resetError) setResetError(null);
                      }}
                      placeholder="name@company.com"
                      className="w-full bg-surface-muted border border-surface-border rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-enterprise-text font-mono placeholder-enterprise-dim focus:outline-none focus:border-primary/60"
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  size="lg"
                  isLoading={isLoading}
                  className="w-full font-semibold gap-2 shadow-warm"
                >
                  <span>Send Verification Code</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>

                <button
                  type="button"
                  onClick={() => {
                    setResetError(null);
                    setView('login');
                  }}
                  className="w-full py-2 text-xs font-semibold text-enterprise-muted hover:text-enterprise-text transition-colors flex items-center justify-center gap-1.5"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span>Return to Sign In</span>
                </button>
              </form>
            </motion.div>
          )}

          {/* VIEW 3: PASSWORD RESET - STEP 2 (ENTER 6-DIGIT OTP CODE) */}
          {view === 'reset-otp' && (
            <motion.div
              key="reset-otp"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
              className="rounded-3xl border border-surface-border bg-surface-elevated p-7 sm:p-9 shadow-paper space-y-6"
            >
              <div className="space-y-1.5 text-center">
                <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-primary/10 border border-primary/20 text-primary mb-2 shadow-sm">
                  <Mail className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-enterprise-text">
                  Enter Verification Code
                </h2>
                <p className="text-xs text-enterprise-muted max-w-xs mx-auto leading-relaxed">
                  We've sent a 6-digit code to <span className="font-semibold text-enterprise-text font-mono">{resetEmailInput}</span>.
                </p>
              </div>

              {/* Demo Helper Banner */}
              <div
                onClick={() => setOtpDigits(['8', '4', '2', '1', '0', '9'])}
                className="p-3 rounded-xl border border-primary/30 bg-primary/10 text-xs text-primary font-mono text-center cursor-pointer hover:bg-primary/15 transition-colors font-semibold"
                title="Click to autofill demo code"
              >
                <span>Demo Code: 842109 (Click to autofill)</span>
              </div>

              {resetError && (
                <div className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 leading-relaxed">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{resetError}</span>
                </div>
              )}

              <form onSubmit={handleVerifyOtp} className="space-y-5">
                {/* 6 Digit Segmented Input Boxes */}
                <div className="flex items-center justify-between gap-2 on-paste" onPaste={handleOtpPaste}>
                  {otpDigits.map((digit, index) => (
                    <input
                      key={index}
                      ref={(el) => (otpInputRefs.current[index] = el)}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      value={digit}
                      onChange={(e) => handleOtpChange(index, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(index, e)}
                      className="h-12 w-11 sm:h-14 sm:w-12 text-center text-xl font-bold font-mono rounded-xl border border-surface-border bg-surface-muted text-enterprise-text focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/25 transition-all shadow-subtle"
                    />
                  ))}
                </div>

                <div className="flex items-center justify-between text-xs text-enterprise-muted font-mono">
                  <span>Didn't receive code?</span>
                  {resendCountdown > 0 ? (
                    <span className="text-enterprise-dim">Resend in {resendCountdown}s</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setResendCountdown(45)}
                      className="text-primary hover:underline font-semibold"
                    >
                      Resend Code
                    </button>
                  )}
                </div>

                <Button
                  type="submit"
                  size="lg"
                  isLoading={isLoading}
                  disabled={otpDigits.join('').length < 6}
                  className="w-full font-semibold gap-2 shadow-warm"
                >
                  <span>Verify Code</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>

                <button
                  type="button"
                  onClick={() => setView('reset-email')}
                  className="w-full py-2 text-xs font-semibold text-enterprise-muted hover:text-enterprise-text transition-colors flex items-center justify-center gap-1.5"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span>Change Email</span>
                </button>
              </form>
            </motion.div>
          )}

          {/* VIEW 4: PASSWORD RESET - STEP 3 (NEW PASSWORD) */}
          {view === 'reset-newpass' && (
            <motion.div
              key="reset-newpass"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
              className="rounded-3xl border border-surface-border bg-surface-elevated p-7 sm:p-9 shadow-paper space-y-6"
            >
              <div className="space-y-1.5 text-center">
                <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-primary/10 border border-primary/20 text-primary mb-2 shadow-sm">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-bold tracking-tight text-enterprise-text">
                  Set New Password
                </h2>
                <p className="text-xs text-enterprise-muted max-w-xs mx-auto leading-relaxed">
                  Create a new secure password for <span className="font-semibold text-enterprise-text">{resetEmailInput}</span>.
                </p>
              </div>

              {resetError && (
                <div className="p-3.5 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2.5 leading-relaxed">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{resetError}</span>
                </div>
              )}

              <form onSubmit={handleSetNewPassword} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-enterprise-text mb-1.5">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-3 h-4 w-4 text-enterprise-dim" />
                    <input
                      type={showNewPassword ? 'text' : 'password'}
                      required
                      value={newPassword}
                      onChange={(e) => {
                        setNewPassword(e.target.value);
                        if (resetError) setResetError(null);
                      }}
                      placeholder="Minimum 8 characters"
                      className="w-full bg-surface-muted border border-surface-border rounded-xl pl-10 pr-10 py-2.5 text-sm text-enterprise-text font-mono placeholder-enterprise-dim focus:outline-none focus:border-primary/60"
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      className="absolute right-3 top-3 text-enterprise-dim hover:text-enterprise-text"
                    >
                      {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-enterprise-text mb-1.5">
                    Confirm New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-3 h-4 w-4 text-enterprise-dim" />
                    <input
                      type={showNewPassword ? 'text' : 'password'}
                      required
                      value={confirmPassword}
                      onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (resetError) setResetError(null);
                      }}
                      placeholder="Re-enter new password"
                      className="w-full bg-surface-muted border border-surface-border rounded-xl pl-10 pr-10 py-2.5 text-sm text-enterprise-text font-mono placeholder-enterprise-dim focus:outline-none focus:border-primary/60"
                    />
                  </div>
                </div>

                {/* Password Criteria Checklist */}
                <div className="p-3 rounded-xl border border-surface-border bg-surface-muted/50 space-y-1.5 text-[11px] font-mono">
                  <div className="flex items-center gap-2">
                    <CheckCircle2
                      className={`h-3.5 w-3.5 ${
                        newPassword.length >= 8 ? 'text-emerald-500' : 'text-enterprise-dim'
                      }`}
                    />
                    <span className={newPassword.length >= 8 ? 'text-enterprise-text' : 'text-enterprise-dim'}>
                      At least 8 characters
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2
                      className={`h-3.5 w-3.5 ${
                        /[A-Z]/.test(newPassword) ? 'text-emerald-500' : 'text-enterprise-dim'
                      }`}
                    />
                    <span className={/[A-Z]/.test(newPassword) ? 'text-enterprise-text' : 'text-enterprise-dim'}>
                      Contains an uppercase letter
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2
                      className={`h-3.5 w-3.5 ${
                        /[0-9!@#$%^&*]/.test(newPassword) ? 'text-emerald-500' : 'text-enterprise-dim'
                      }`}
                    />
                    <span className={/[0-9!@#$%^&*]/.test(newPassword) ? 'text-enterprise-text' : 'text-enterprise-dim'}>
                      Contains a number or symbol
                    </span>
                  </div>
                </div>

                <Button
                  type="submit"
                  size="lg"
                  isLoading={isLoading}
                  className="w-full font-semibold gap-2 shadow-warm"
                >
                  <span>Update Password</span>
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </form>
            </motion.div>
          )}

          {/* VIEW 5: PASSWORD RESET SUCCESS */}
          {view === 'reset-success' && (
            <motion.div
              key="reset-success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="rounded-3xl border border-surface-border bg-surface-elevated p-8 sm:p-10 shadow-paper text-center space-y-5"
            >
              <div className="inline-flex items-center justify-center h-16 w-16 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-8 w-8" />
              </div>

              <div className="space-y-1.5">
                <h3 className="text-2xl font-bold tracking-tight text-enterprise-text">
                  Password Updated
                </h3>
                <p className="text-xs text-enterprise-muted max-w-xs mx-auto leading-relaxed">
                  Your corporate credentials have been verified and updated. You can now log into your workspace with your new password.
                </p>
              </div>

              <Button
                onClick={() => {
                  setPassword(newPassword);
                  setEmail(resetEmailInput);
                  setView('login');
                }}
                size="lg"
                className="w-full font-semibold gap-2 shadow-warm"
              >
                <span>Proceed to Sign In</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer Info */}
      <div className="relative z-10 max-w-6xl w-full mx-auto flex flex-col sm:flex-row items-center justify-between text-xs text-enterprise-dim gap-2 border-t border-surface-border/50 pt-4">
        <span>© 2026 EnterpriseQuery Systems Inc. All rights reserved.</span>
        <div className="flex items-center gap-4 font-mono text-[11px]">
          <span>Grounded Retrieval</span>
          <span>•</span>
          <span>Role Partitioning</span>
          <span>•</span>
          <span>Audit Sealed</span>
        </div>
      </div>
    </div>
  );
};