import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, ShieldAlert, Lock, Key, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '@/stores/useAuthStore';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

export const AdminAuthModal: React.FC = () => {
  const {
    isAdminModalOpen,
    closeAdminModal,
    loginAsAdmin,
    lockedUntil,
  } = useAuthStore();

  const [passkey, setPasskey] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!passkey.trim()) return;

    setErrorMsg(null);
    const result = loginAsAdmin(passkey);

    if (result.success) {
      setIsSuccess(true);
      setTimeout(() => {
        setIsSuccess(false);
        setPasskey('');
        closeAdminModal();
      }, 700);
    } else {
      setErrorMsg(result.error || 'Authentication failed.');
    }
  };

  const isLocked = lockedUntil ? Date.now() < lockedUntil : false;

  return (
    <Modal
      isOpen={isAdminModalOpen}
      onClose={() => {
        setErrorMsg(null);
        setPasskey('');
        closeAdminModal();
      }}
      title="Enter Maintenance / Administrative Mode"
      description="Administrative privileges grant full CRUD access (upload, edit, delete knowledge base documents and workspaces)."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Security Warning Notice */}
        <div className="p-3.5 rounded-xl border border-primary/25 bg-orange-50/40 text-xs text-enterprise-text leading-relaxed flex items-start gap-2.5">
          <ShieldAlert className="h-4.5 w-4.5 text-primary shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-enterprise-text block">
              Restricted Area • Strict Auditing Active
            </span>
            <p className="text-enterprise-muted mt-0.5">
              Regular employees operate in read-only query mode. Only authorized administrators with the security passkey may access document management tools.
            </p>
          </div>
        </div>

        {/* Passkey Input */}
        <div>
          <label className="block text-xs font-semibold text-enterprise-text mb-1.5 flex items-center justify-between">
            <span>Admin Security Passkey</span>
            <span className="text-enterprise-dim font-mono text-[11px] font-normal">
              Default: admin2024!
            </span>
          </label>
          <div className="relative">
            <Key className="absolute left-3 top-2.5 h-4 w-4 text-enterprise-dim" />
            <input
              type="password"
              value={passkey}
              onChange={(e) => {
                setPasskey(e.target.value);
                if (errorMsg) setErrorMsg(null);
              }}
              disabled={isLocked || isSuccess}
              placeholder="Enter administrator passkey..."
              className="w-full bg-surface-muted border border-surface-border rounded-xl pl-9 pr-3 py-2 text-sm text-enterprise-text focus:outline-none focus:border-primary font-mono"
              autoFocus
            />
          </div>
        </div>

        {/* Error Feedback */}
        {errorMsg && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3 rounded-xl border border-rose-300 bg-rose-50 text-rose-800 text-xs flex items-center gap-2"
          >
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
            <span className="font-medium">{errorMsg}</span>
          </motion.div>
        )}

        {/* Success Feedback */}
        {isSuccess && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-800 text-xs flex items-center gap-2"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span className="font-semibold">Authenticated. Entering Administrative Mode...</span>
          </motion.div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-surface-border">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setErrorMsg(null);
              setPasskey('');
              closeAdminModal();
            }}
          >
            Cancel
          </Button>

          <Button
            type="submit"
            size="sm"
            disabled={!passkey.trim() || isLocked || isSuccess}
            className="gap-2 font-semibold"
          >
            <Lock className="h-3.5 w-3.5" />
            <span>Authenticate Admin</span>
          </Button>
        </div>
      </form>
    </Modal>
  );
};
