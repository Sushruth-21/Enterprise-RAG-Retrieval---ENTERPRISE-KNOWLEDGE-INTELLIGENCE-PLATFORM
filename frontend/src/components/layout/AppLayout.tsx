import React, { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Sun, Moon } from 'lucide-react';
import { AppHeader } from './AppHeader';
import { AppSidebar } from './AppSidebar';
import { AdminAuthModal } from '@/components/auth/AdminAuthModal';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { useUIStore } from '@/stores/useUIStore';
import { INITIAL_WORKSPACES } from '@/mocks/initialData';
import { workspaceService } from '@/services/api';

export const AppLayout: React.FC = () => {
  const { workspaces, setWorkspaces, activeWorkspaceId, setActiveWorkspaceId, setDocuments } =
    useWorkspaceStore();
  const { theme, toggleTheme } = useUIStore();
  const isDark = theme === 'dark';

  useEffect(() => {
    // 1. Initialize clean workspace if none exists
    if (workspaces.length === 0) {
      setWorkspaces(INITIAL_WORKSPACES);
      if (!activeWorkspaceId && INITIAL_WORKSPACES.length > 0) {
        setActiveWorkspaceId(INITIAL_WORKSPACES[0].id);
      }
    }

    // 2. Fetch real production documents from Knowledge Vault
    workspaceService.getDocuments().then((docs) => {
      if (Array.isArray(docs)) {
        setDocuments(docs);
      }
    }).catch((err) => {
      console.warn('Initial document load from backend:', err);
    });
  }, [workspaces.length, setWorkspaces, setDocuments, activeWorkspaceId, setActiveWorkspaceId]);

  return (
    <div className="min-h-screen bg-background flex font-sans selection:bg-primary/20 selection:text-primary overflow-hidden">
      {/* Full-Height Left Sidebar (ChatGPT-style) */}
      <AppSidebar />

      {/* Main Right Viewport */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden relative">
        <AppHeader />

        {/* Floating Dark Mode Icon at Marked Location (Directly Below Menu Button) */}
        <motion.button
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          onClick={toggleTheme}
          className="fixed top-[74px] right-6 z-30 flex items-center justify-center h-10 w-10 rounded-xl border border-surface-border bg-surface-elevated/95 backdrop-blur-md text-enterprise-text hover:border-primary/50 hover:text-primary transition-all shadow-subtle group select-none"
          title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
        >
          <div className="relative overflow-hidden flex items-center justify-center">
            <AnimatePresence mode="wait" initial={false}>
              {isDark ? (
                <motion.div
                  key="moon"
                  initial={{ rotate: -90, scale: 0.5, opacity: 0 }}
                  animate={{ rotate: 0, scale: 1, opacity: 1 }}
                  exit={{ rotate: 90, scale: 0.5, opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                >
                  <Moon className="h-4.5 w-4.5 text-amber-400 group-hover:scale-110 transition-transform" />
                </motion.div>
              ) : (
                <motion.div
                  key="sun"
                  initial={{ rotate: 90, scale: 0.5, opacity: 0 }}
                  animate={{ rotate: 0, scale: 1, opacity: 1 }}
                  exit={{ rotate: 90, scale: 0.5, opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 350, damping: 25 }}
                >
                  <Sun className="h-4.5 w-4.5 text-amber-500 group-hover:scale-110 transition-transform" />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.button>

        <main className="flex-1 overflow-y-auto relative bg-background">
          <Outlet />
        </main>
      </div>

      {/* Global Administrative Mode Authentication Modal */}
      <AdminAuthModal />
    </div>
  );
};
