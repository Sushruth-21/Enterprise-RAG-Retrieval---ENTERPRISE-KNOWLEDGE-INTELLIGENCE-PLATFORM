import React, { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  FolderOpen,
  FileSpreadsheet,
  FileText,
  Settings,
  Plus,
  Check,
  MessageSquare,
  Layers,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Lock,
  Sun,
  Moon,
  UserCheck,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { useUIStore } from '@/stores/useUIStore';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

export const AppHeader: React.FC = () => {
  const navigate = useNavigate();
  const { workspaces, activeWorkspaceId, setActiveWorkspaceId, createWorkspace } =
    useWorkspaceStore();
  const { isAdmin, logoutAdmin, openAdminModal, currentUser } = useAuthStore();
  const { theme, toggleTheme } = useUIStore();
  const isDark = theme === 'dark';
  const isAdministrator = isAdmin();

  const [isWorkspaceMenuOpen, setIsWorkspaceMenuOpen] = useState(false);
  const [isToolsMenuOpen, setIsToolsMenuOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newWsName, setNewWsName] = useState('');
  const [newWsDesc, setNewWsDesc] = useState('');

  const workspaceMenuRef = useRef<HTMLDivElement>(null);
  const toolsMenuRef = useRef<HTMLDivElement>(null);

  const activeWorkspace =
    workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        workspaceMenuRef.current &&
        !workspaceMenuRef.current.contains(e.target as Node)
      ) {
        setIsWorkspaceMenuOpen(false);
      }
      if (
        toolsMenuRef.current &&
        !toolsMenuRef.current.contains(e.target as Node)
      ) {
        setIsToolsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCreateWorkspace = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;

    if (!isAdministrator) {
      openAdminModal();
      return;
    }

    const ws = createWorkspace(newWsName.trim(), newWsDesc.trim());
    if (ws) {
      setNewWsName('');
      setNewWsDesc('');
      setIsCreateOpen(false);
      setIsWorkspaceMenuOpen(false);
      navigate('/workspace');
    }
  };

  return (
    <>
      <header className="h-16 border-b border-surface-border/70 bg-surface/70 dark:bg-surface/50 backdrop-blur-xl backdrop-saturate-150 sticky top-0 z-40 px-4 sm:px-6 flex items-center justify-end gap-3 transition-all duration-300">
        {/* Center/Right: Security Mode Indicator & Dropdowns */}
        <div className="flex items-center gap-3 shrink-0">
          {/* RBAC Mode Badge */}
          {isAdministrator ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 text-xs font-semibold shadow-subtle">
              <ShieldCheck className="h-4 w-4 text-amber-600" />
              <span className="hidden sm:inline">Admin Mode (Full CRUD)</span>
              <span className="sm:hidden">Admin</span>
              <button
                onClick={logoutAdmin}
                className="ml-1 text-[11px] underline text-amber-800 dark:text-amber-300 hover:text-black dark:hover:text-white font-mono font-medium"
                title="Exit Admin Maintenance Mode"
              >
                Exit
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-surface-border bg-surface-muted/60 text-enterprise-muted text-xs">
              <Lock className="h-3.5 w-3.5 text-enterprise-dim" />
              <span className="hidden sm:inline">Employee (Read-Only)</span>
              <button
                onClick={openAdminModal}
                className="ml-1 text-[11px] font-semibold text-primary hover:underline font-mono"
                title="Authenticate as Admin"
              >
                Admin Mode
              </button>
            </div>
          )}

          {/* Workspace Switcher Dropdown */}
          <div className="relative" ref={workspaceMenuRef}>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsWorkspaceMenuOpen(!isWorkspaceMenuOpen)}
              className="flex items-center gap-2 h-10 px-3.5 rounded-xl border border-surface-border bg-surface-elevated text-sm font-medium text-enterprise-text hover:border-surface-border-hover transition-colors shadow-subtle"
            >
              <FolderOpen className="h-4 w-4 text-primary" />
              <span className="truncate max-w-[140px] sm:max-w-[190px]">
                {activeWorkspace?.name || 'Workspace'}
              </span>
              <motion.div
                animate={{ rotate: isWorkspaceMenuOpen ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-3.5 w-3.5 text-enterprise-muted shrink-0" />
              </motion.div>
            </motion.button>

            {/* Animated Workspace Dropdown */}
            <AnimatePresence>
              {isWorkspaceMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: -6 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: -6 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 350 }}
                  className="absolute right-0 top-full mt-2 w-72 rounded-2xl border border-surface-border bg-surface-elevated shadow-paper p-2 z-50 text-sm space-y-1.5 origin-top-right"
                >
                  <div className="px-3 py-1.5 text-xs font-semibold text-enterprise-dim uppercase tracking-wider font-mono">
                    Select Workspace
                  </div>

                  <div className="max-h-60 overflow-y-auto space-y-1">
                    {workspaces.map((ws) => (
                      <motion.button
                        key={ws.id}
                        whileHover={{ x: 2 }}
                        onClick={() => {
                          setActiveWorkspaceId(ws.id);
                          setIsWorkspaceMenuOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2.5 rounded-xl flex items-center justify-between transition-colors ${
                          activeWorkspace?.id === ws.id
                            ? 'bg-primary/10 text-primary font-semibold'
                            : 'text-enterprise-text/85 hover:text-enterprise-text hover:bg-surface-muted'
                        }`}
                      >
                        <span className="truncate mr-2 font-medium">{ws.name}</span>
                        {activeWorkspace?.id === ws.id && (
                          <Check className="h-4 w-4 shrink-0 text-primary" />
                        )}
                      </motion.button>
                    ))}
                  </div>

                  <div className="pt-2 border-t border-surface-border">
                    <button
                      onClick={() => {
                        if (!isAdministrator) {
                          openAdminModal();
                          setIsWorkspaceMenuOpen(false);
                          return;
                        }
                        setIsCreateOpen(true);
                        setIsWorkspaceMenuOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 rounded-xl text-primary hover:bg-primary/10 flex items-center justify-between transition-colors font-semibold"
                    >
                      <div className="flex items-center gap-2">
                        <Plus className="h-4 w-4" />
                        <span>Create Workspace</span>
                      </div>
                      {!isAdministrator && (
                        <span className="text-[10px] uppercase font-mono text-enterprise-dim border border-surface-border px-1.5 py-0.5 rounded">
                          Admin Only
                        </span>
                      )}
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Navigation Menu Dropdown (Animated with Framer Motion & Perfect Dark Mode Shifting) */}
          <div className="relative" ref={toolsMenuRef}>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsToolsMenuOpen(!isToolsMenuOpen)}
              className="flex items-center gap-2 h-10 px-4 rounded-xl bg-neutral-900 text-white dark:bg-surface-elevated dark:text-enterprise-text dark:border dark:border-surface-border hover:bg-primary dark:hover:border-primary/50 dark:hover:text-primary transition-colors text-sm font-semibold shadow-subtle group"
            >
              <span>Menu</span>
              <motion.div
                animate={{ rotate: isToolsMenuOpen ? 180 : 0 }}
                transition={{ duration: 0.2 }}
              >
                <ChevronDown className="h-3.5 w-3.5 text-white/80 dark:text-enterprise-muted group-hover:text-white dark:group-hover:text-primary transition-colors" />
              </motion.div>
            </motion.button>

            {/* Animated Menu Dropdown Container */}
            <AnimatePresence>
              {isToolsMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: -6 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95, y: -6 }}
                  transition={{ type: 'spring', damping: 25, stiffness: 350 }}
                  className="absolute right-0 top-full mt-2 w-64 rounded-2xl border border-surface-border bg-surface-elevated shadow-paper p-2 z-50 text-sm space-y-1 origin-top-right"
                >
                  <Link
                    to="/"
                    onClick={() => setIsToolsMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                  >
                    <Layers className="h-4.5 w-4.5 text-enterprise-muted group-hover:text-primary transition-colors" />
                    <span>Landing / Home</span>
                  </Link>

                  <Link
                    to="/chat"
                    onClick={() => setIsToolsMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                  >
                    <MessageSquare className="h-4.5 w-4.5 text-primary" />
                    <span>Grounded Chat</span>
                  </Link>

                  <Link
                    to="/workspace"
                    onClick={() => setIsToolsMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                  >
                    <FolderOpen className="h-4.5 w-4.5 text-enterprise-muted group-hover:text-primary transition-colors" />
                    <span>Documents & Ingestion</span>
                  </Link>

                  <Link
                    to="/batch"
                    onClick={() => setIsToolsMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                  >
                    <FileSpreadsheet className="h-4.5 w-4.5 text-enterprise-muted group-hover:text-primary transition-colors" />
                    <span>Batch Question Suite</span>
                  </Link>

                  {activeWorkspace && activeWorkspace.selectedDocumentIds[0] && (
                    <Link
                      to={`/document/${activeWorkspace.selectedDocumentIds[0]}`}
                      onClick={() => setIsToolsMenuOpen(false)}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                    >
                      <FileText className="h-4.5 w-4.5 text-enterprise-muted group-hover:text-primary transition-colors" />
                      <span>Document Canvas</span>
                    </Link>
                  )}

                  <Link
                    to="/settings"
                    onClick={() => setIsToolsMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                  >
                    <Settings className="h-4.5 w-4.5 text-enterprise-muted group-hover:text-primary transition-colors" />
                    <div className="flex items-center justify-between flex-1">
                      <span>Platform Settings</span>
                      {!isAdministrator && (
                        <span className="text-[10px] font-mono text-enterprise-dim uppercase">
                          Admin
                        </span>
                      )}
                    </div>
                  </Link>

                  <Link
                    to="/login"
                    onClick={() => setIsToolsMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-all hover:translate-x-0.5 group font-medium"
                  >
                    <UserCheck className="h-4.5 w-4.5 text-enterprise-muted group-hover:text-primary transition-colors" />
                    <div className="flex items-center justify-between flex-1">
                      <span>Corporate Account</span>
                      <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-bold truncate max-w-[100px]">
                        {currentUser?.name || 'Sign In'}
                      </span>
                    </div>
                  </Link>

                  {/* Dark Mode Option Exactly Below the Menu Options */}
                  <div className="h-[1px] bg-surface-border my-1.5" />

                  <motion.button
                    whileHover={{ x: 2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => {
                      toggleTheme();
                    }}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-enterprise-text hover:bg-surface-muted transition-colors font-medium text-sm group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="h-5 w-5 rounded-lg bg-surface-muted border border-surface-border flex items-center justify-center shrink-0">
                        <AnimatePresence mode="wait" initial={false}>
                          {isDark ? (
                            <motion.div
                              key="moon"
                              initial={{ rotate: -90, scale: 0.5, opacity: 0 }}
                              animate={{ rotate: 0, scale: 1, opacity: 1 }}
                              exit={{ rotate: 90, scale: 0.5, opacity: 0 }}
                              transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                            >
                              <Moon className="h-3.5 w-3.5 text-amber-400" />
                            </motion.div>
                          ) : (
                            <motion.div
                              key="sun"
                              initial={{ rotate: 90, scale: 0.5, opacity: 0 }}
                              animate={{ rotate: 0, scale: 1, opacity: 1 }}
                              exit={{ rotate: -90, scale: 0.5, opacity: 0 }}
                              transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                            >
                              <Sun className="h-3.5 w-3.5 text-amber-500" />
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                      <span className="text-sm font-medium text-enterprise-text">
                        {isDark ? 'Dark Mode' : 'Light Mode'}
                      </span>
                    </div>

                    {/* Smooth Animated Toggle Switch */}
                    <div
                      className={`w-9 h-5 rounded-full p-0.5 transition-colors duration-300 flex items-center ${
                        isDark ? 'bg-primary' : 'bg-surface-border'
                      }`}
                    >
                      <motion.div
                        layout
                        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                        className={`h-4 w-4 rounded-full bg-white shadow-sm ${
                          isDark ? 'ml-auto' : 'mr-auto'
                        }`}
                      />
                    </div>
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </header>

      {/* Create Workspace Modal */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create New Workspace"
        description="Documents uploaded here are partition-isolated and queried only within this space."
      >
        <form onSubmit={handleCreateWorkspace} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-enterprise-text mb-1">
              Workspace Name
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Q4 Financial Disclosures"
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text placeholder-enterprise-dim focus:outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-enterprise-text mb-1">
              Description (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Scope, regulatory domain, or document types..."
              value={newWsDesc}
              onChange={(e) => setNewWsDesc(e.target.value)}
              className="w-full bg-surface-muted border border-surface-border rounded-xl px-3 py-2 text-sm text-enterprise-text placeholder-enterprise-dim focus:outline-none focus:border-primary resize-none"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit">Create Workspace</Button>
          </div>
        </form>
      </Modal>
    </>
  );
};
