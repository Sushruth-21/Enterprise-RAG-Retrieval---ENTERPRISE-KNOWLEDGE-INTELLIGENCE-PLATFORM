import { create } from 'zustand';
import { generateSecureToken } from '@/lib/security';

export type UserRole = 'employee' | 'admin';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  department: string;
  role: UserRole;
  avatarInitials: string;
}

// Disallowed generic/consumer domains
export const BLOCKED_DOMAINS = [
  'gmail.com',
  'yahoo.com',
  'hotmail.com',
  'outlook.com',
  'icloud.com',
  'aol.com',
  'mail.com',
  'proton.me',
  'protonmail.com',
  'zoho.com',
  'yandex.com',
];

export const DEMO_USERS: Record<string, { user: AuthUser; pass: string }> = {
  'alex.morgan@company.com': {
    pass: 'Enterprise@2026!',
    user: {
      id: 'emp-101',
      name: 'Alex Morgan',
      email: 'alex.morgan@company.com',
      department: 'Quantitative Analytics',
      role: 'employee',
      avatarInitials: 'AM',
    },
  },
  'admin@enterprise.internal': {
    pass: 'Admin@2026!',
    user: {
      id: 'adm-001',
      name: 'System Administrator',
      email: 'admin@enterprise.internal',
      department: 'Security & Infrastructure',
      role: 'admin',
      avatarInitials: 'SA',
    },
  },
};

interface AuthState {
  currentUser: AuthUser | null;
  role: UserRole;
  adminToken: string | null;
  adminSessionExpiresAt: number | null;
  failedAttempts: number;
  lockedUntil: number | null;
  isAdminModalOpen: boolean;

  // Password reset state
  resetEmail: string | null;
  resetCodeVerified: boolean;

  // Company Email Auth Actions
  loginWithEmail: (email: string, pass: string) => { success: boolean; error?: string };
  logout: () => void;
  requestPasswordResetCode: (email: string) => { success: boolean; error?: string; code?: string };
  verifyResetCode: (code: string) => { success: boolean; error?: string };
  completePasswordReset: (newPassword: string) => { success: boolean; error?: string };

  // Admin Maintenance Key Actions (preserved)
  loginAsAdmin: (passkey: string) => { success: boolean; error?: string };
  logoutAdmin: () => void;
  openAdminModal: () => void;
  closeAdminModal: () => void;
  isAdmin: () => boolean;
  checkSessionValidity: () => boolean;
}

// Default administrative maintenance key (can be overridden via env)
const ADMIN_SECRET = import.meta.env.VITE_ADMIN_PASSKEY || 'admin2024!';
const MAX_ATTEMPTS = 5;
const LOCKOUT_DURATION_MS = 2 * 60 * 1000; // 2 minutes lockout
const SESSION_DURATION_MS = 45 * 60 * 1000; // 45 minutes admin session

// Initial state restored from sessionStorage (never localStorage to prevent persistent disk tampering)
const getInitialSession = (): {
  token: string | null;
  expiresAt: number | null;
  user: AuthUser | null;
} => {
  try {
    const storedUser = sessionStorage.getItem('eq_user');
    const storedToken = sessionStorage.getItem('eq_admin_token');
    const storedExpiry = sessionStorage.getItem('eq_admin_expires');
    const user = storedUser ? JSON.parse(storedUser) : DEMO_USERS['alex.morgan@company.com'].user;

    if (storedToken && storedExpiry) {
      const exp = parseInt(storedExpiry, 10);
      if (exp > Date.now()) {
        return { token: storedToken, expiresAt: exp, user };
      }
    }
    return { token: null, expiresAt: null, user };
  } catch {
    // SessionStorage restricted or unavailable
  }
  return { token: null, expiresAt: null, user: DEMO_USERS['alex.morgan@company.com'].user };
};

const initialSession = getInitialSession();

export const useAuthStore = create<AuthState>((set, get) => ({
  currentUser: initialSession.user,
  role: initialSession.token ? 'admin' : (initialSession.user?.role || 'employee'),
  adminToken: initialSession.token,
  adminSessionExpiresAt: initialSession.expiresAt,
  failedAttempts: 0,
  lockedUntil: null,
  isAdminModalOpen: false,

  resetEmail: null,
  resetCodeVerified: false,

  openAdminModal: () => set({ isAdminModalOpen: true }),
  closeAdminModal: () => set({ isAdminModalOpen: false }),

  // Company Email Authentication
  loginWithEmail: (email: string, pass: string) => {
    const cleanEmail = email.trim().toLowerCase();
    const cleanPass = pass.trim();

    // 1. Basic format verification
    if (!cleanEmail || !cleanEmail.includes('@') || !cleanEmail.includes('.')) {
      return { success: false, error: 'Please enter a valid corporate email address.' };
    }

    // 2. Strict company domain validation (reject public consumer mail)
    const domain = cleanEmail.split('@')[1];
    if (BLOCKED_DOMAINS.includes(domain)) {
      return {
        success: false,
        error: `Personal email providers (@${domain}) are prohibited. Please sign in with your corporate enterprise email.`,
      };
    }

    // 3. Match against demo/placeholder credentials
    const target = DEMO_USERS[cleanEmail];
    if (target) {
      if (target.pass !== cleanPass) {
        return { success: false, error: 'Invalid password. Try the demo password: ' + target.pass };
      }

      // Successful login
      try {
        sessionStorage.setItem('eq_user', JSON.stringify(target.user));
        if (target.user.role === 'admin') {
          const token = generateSecureToken(32);
          const expiresAt = Date.now() + SESSION_DURATION_MS;
          sessionStorage.setItem('eq_admin_token', token);
          sessionStorage.setItem('eq_admin_expires', expiresAt.toString());
          set({
            adminToken: token,
            adminSessionExpiresAt: expiresAt,
          });
        }
      } catch {
        /* noop */
      }

      set({
        currentUser: target.user,
        role: target.user.role,
      });

      return { success: true };
    }

    // Fallback: If it's another valid corporate domain, allow login with default company pass for seamless prototyping
    if (cleanPass === 'Enterprise@2026!' || cleanPass === 'Admin@2026!') {
      const isAdm = cleanPass === 'Admin@2026!' || cleanEmail.includes('admin');
      const newUser: AuthUser = {
        id: `usr-${Date.now().toString(36)}`,
        name: cleanEmail.split('@')[0].replace('.', ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        email: cleanEmail,
        department: isAdm ? 'Enterprise Administration' : 'Global Operations',
        role: isAdm ? 'admin' : 'employee',
        avatarInitials: cleanEmail.substring(0, 2).toUpperCase(),
      };

      try {
        sessionStorage.setItem('eq_user', JSON.stringify(newUser));
        if (isAdm) {
          const token = generateSecureToken(32);
          const expiresAt = Date.now() + SESSION_DURATION_MS;
          sessionStorage.setItem('eq_admin_token', token);
          sessionStorage.setItem('eq_admin_expires', expiresAt.toString());
          set({
            adminToken: token,
            adminSessionExpiresAt: expiresAt,
          });
        }
      } catch {
        /* noop */
      }

      set({
        currentUser: newUser,
        role: newUser.role,
      });

      return { success: true };
    }

    return {
      success: false,
      error: 'Unrecognized enterprise credentials. Use demo: alex.morgan@company.com (Enterprise@2026!)',
    };
  },

  logout: () => {
    try {
      sessionStorage.removeItem('eq_user');
      sessionStorage.removeItem('eq_admin_token');
      sessionStorage.removeItem('eq_admin_expires');
    } catch {
      /* noop */
    }
    set({
      currentUser: null,
      role: 'employee',
      adminToken: null,
      adminSessionExpiresAt: null,
    });
  },

  // Password Reset Flow
  requestPasswordResetCode: (email: string) => {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      return { success: false, error: 'Enter your valid corporate email.' };
    }
    const domain = cleanEmail.split('@')[1];
    if (BLOCKED_DOMAINS.includes(domain)) {
      return {
        success: false,
        error: `Personal email providers (@${domain}) cannot receive enterprise verification codes.`,
      };
    }

    set({ resetEmail: cleanEmail, resetCodeVerified: false });
    return { success: true, code: '842109' };
  },

  verifyResetCode: (code: string) => {
    if (code.trim() === '842109') {
      set({ resetCodeVerified: true });
      return { success: true };
    }
    return { success: false, error: 'Invalid verification code. Please check the code or use demo code: 842109.' };
  },

  completePasswordReset: (newPassword: string) => {
    const state = get();
    if (!state.resetEmail || !state.resetCodeVerified) {
      return { success: false, error: 'Session expired or email unverified.' };
    }
    if (newPassword.length < 8) {
      return { success: false, error: 'Password must be at least 8 characters with numbers and symbols.' };
    }

    // Update demo user password if applicable
    if (DEMO_USERS[state.resetEmail]) {
      DEMO_USERS[state.resetEmail].pass = newPassword;
    }

    set({ resetEmail: null, resetCodeVerified: false });
    return { success: true };
  },

  // Admin Maintenance Mode (Preserved for Administrative Maintenance Mode)
  isAdmin: () => {
    return get().checkSessionValidity();
  },

  checkSessionValidity: () => {
    const { role, adminToken, adminSessionExpiresAt } = get();
    if (role !== 'admin' || !adminToken || !adminSessionExpiresAt) {
      return false;
    }
    if (Date.now() > adminSessionExpiresAt) {
      try {
        sessionStorage.removeItem('eq_admin_token');
        sessionStorage.removeItem('eq_admin_expires');
      } catch {
        /* noop */
      }
      set({
        role: 'employee',
        adminToken: null,
        adminSessionExpiresAt: null,
      });
      return false;
    }
    return true;
  },

  loginAsAdmin: (passkey: string) => {
    const state = get();
    const now = Date.now();

    if (state.lockedUntil && now < state.lockedUntil) {
      const remainingSec = Math.ceil((state.lockedUntil - now) / 1000);
      return {
        success: false,
        error: `Too many failed attempts. Locked for ${remainingSec} seconds.`,
      };
    }

    const isMatch = passkey.trim() === ADMIN_SECRET;

    if (!isMatch) {
      const newAttempts = state.failedAttempts + 1;
      const isNowLocked = newAttempts >= MAX_ATTEMPTS;
      set({
        failedAttempts: newAttempts,
        lockedUntil: isNowLocked ? now + LOCKOUT_DURATION_MS : null,
      });

      if (isNowLocked) {
        return {
          success: false,
          error: `Maximum attempts exceeded. Administrative access locked for 2 minutes.`,
        };
      }

      return {
        success: false,
        error: `Invalid administrative passkey. (${MAX_ATTEMPTS - newAttempts} attempts remaining)`,
      };
    }

    const token = generateSecureToken(32);
    const expiresAt = now + SESSION_DURATION_MS;

    try {
      sessionStorage.setItem('eq_admin_token', token);
      sessionStorage.setItem('eq_admin_expires', expiresAt.toString());
    } catch {
      /* noop */
    }

    set({
      role: 'admin',
      adminToken: token,
      adminSessionExpiresAt: expiresAt,
      failedAttempts: 0,
      lockedUntil: null,
      isAdminModalOpen: false,
    });

    return { success: true };
  },

  logoutAdmin: () => {
    try {
      sessionStorage.removeItem('eq_admin_token');
      sessionStorage.removeItem('eq_admin_expires');
    } catch {
      /* noop */
    }

    set({
      role: 'employee',
      adminToken: null,
      adminSessionExpiresAt: null,
    });
  },
}));
