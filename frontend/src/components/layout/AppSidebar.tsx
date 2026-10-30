import React, { useRef } from 'react';
import { NavLink, useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  Plus,
  FolderOpen,
  FileSpreadsheet,
  Settings,
  Search,
  PanelLeft,
  Layers,
  ShieldCheck,
  Lock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { useUIStore } from '@/stores/useUIStore';
import { useAuthStore } from '@/stores/useAuthStore';

export const AppSidebar: React.FC = () => {
  const navigate = useNavigate();
  const { isSidebarCollapsed, toggleSidebar, setSidebarCollapsed } = useUIStore();
  const [sidebarSearch, setSidebarSearch] = React.useState('');
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { workspaces, activeWorkspaceId, setActiveWorkspaceId } = useWorkspaceStore();
  const { isAdmin, logoutAdmin, openAdminModal, currentUser } = useAuthStore();
  const isAdministrator = isAdmin();

  const handleNewChat = () => {
    navigate('/chat');
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sidebarSearch.trim()) return;
    navigate(`/workspace?q=${encodeURIComponent(sidebarSearch.trim())}`);
  };

  const handleSearchIconClick = () => {
    if (isSidebarCollapsed) {
      setSidebarCollapsed(false);
      setTimeout(() => searchInputRef.current?.focus(), 150);
    }
  };

  return (
    <motion.aside
      animate={{ width: isSidebarCollapsed ? 64 : 260 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className="border-r border-surface-border bg-surface flex flex-col justify-between shrink-0 h-screen select-none z-30 overflow-hidden"
    >
      <div className="p-3 space-y-3">
        {/* 1. Collapse/Expand Button (At the very top) */}
        <div className="flex items-center justify-between">
          {!isSidebarCollapsed ? (
            <div className="flex items-center justify-between w-full h-10 px-1">
              <span className="text-xs font-semibold text-enterprise-dim uppercase tracking-wider font-mono">
                Navigation
              </span>
              <motion.button
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                onClick={toggleSidebar}
                className="h-10 w-10 rounded-xl text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted transition-colors flex items-center justify-center shrink-0"
                title="Collapse sidebar"
              >
                <PanelLeft className="h-5 w-5" />
              </motion.button>
            </div>
          ) : (
            <motion.button
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
              onClick={toggleSidebar}
              className="h-10 w-10 rounded-xl text-enterprise-text hover:text-primary hover:bg-surface-muted transition-colors flex items-center justify-center mx-auto shrink-0 shadow-subtle border border-surface-border"
              title="Expand sidebar"
            >
              <PanelLeft className="h-5 w-5" />
            </motion.button>
          )}
        </div>

        {/* 2. Enterprise Query Button */}
        {!isSidebarCollapsed ? (
          <Link
            to="/"
            className="flex items-center gap-3 h-10 px-3 rounded-xl border border-surface-border bg-surface-elevated hover:border-primary/40 transition-colors shadow-subtle group"
          >
            <div className="h-7 w-7 rounded-lg bg-neutral-900 text-white dark:bg-primary dark:text-white flex items-center justify-center group-hover:bg-primary transition-colors shrink-0 shadow-sm">
              <Layers className="h-4 w-4" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-enterprise-text truncate">
              Enterprise Query
            </span>
          </Link>
        ) : (
          <Link
            to="/"
            className="h-10 w-10 rounded-xl border border-surface-border bg-surface-elevated text-enterprise-text hover:border-primary/50 hover:text-primary flex items-center justify-center transition-colors mx-auto shadow-subtle shrink-0 group"
            title="Enterprise Query Home"
          >
            <div className="h-7 w-7 rounded-lg bg-neutral-900 text-white dark:bg-primary dark:text-white flex items-center justify-center group-hover:bg-primary transition-colors shrink-0">
              <Layers className="h-4 w-4" />
            </div>
          </Link>
        )}

        {/* 3. New Query Button */}
        {!isSidebarCollapsed ? (
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleNewChat}
            className="w-full flex items-center gap-2.5 h-10 px-3.5 rounded-xl bg-neutral-900 text-white dark:bg-primary dark:text-white hover:bg-primary dark:hover:bg-primary-hover transition-colors text-sm font-medium shadow-subtle"
          >
            <Plus className="h-4.5 w-4.5 text-primary-200 dark:text-white shrink-0" />
            <span className="truncate">New Query</span>
          </motion.button>
        ) : (
          <motion.button
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.92 }}
            onClick={handleNewChat}
            className="h-10 w-10 rounded-xl bg-neutral-900 text-white dark:bg-primary dark:text-white hover:bg-primary dark:hover:bg-primary-hover flex items-center justify-center transition-colors mx-auto shadow-subtle shrink-0"
            title="New Query"
          >
            <Plus className="h-5 w-5" />
          </motion.button>
        )}

        {/* 4. Global Search Bar */}
        {!isSidebarCollapsed ? (
          <form onSubmit={handleSearchSubmit} className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-enterprise-dim" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search..."
              value={sidebarSearch}
              onChange={(e) => setSidebarSearch(e.target.value)}
              className="w-full h-10 bg-surface-muted/70 border border-surface-border rounded-xl pl-9 pr-3 text-sm text-enterprise-text placeholder-enterprise-dim focus:outline-none focus:border-primary/50 focus:bg-surface-elevated transition-colors"
            />
          </form>
        ) : (
          <motion.button
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.92 }}
            onClick={handleSearchIconClick}
            className="h-10 w-10 rounded-xl border border-surface-border bg-surface-elevated text-enterprise-muted hover:text-enterprise-text hover:border-primary/40 flex items-center justify-center transition-colors mx-auto shadow-subtle shrink-0"
            title="Search documents & queries"
          >
            <Search className="h-4.5 w-4.5" />
          </motion.button>
        )}

        {/* 5. Navigation Links */}
        <nav className="space-y-1.5">
          {[
            { name: 'Conversations', path: '/chat', icon: MessageSquare },
            { name: 'Documents', path: '/workspace', icon: FolderOpen },
            { name: 'Batch Suite', path: '/batch', icon: FileSpreadsheet },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  cn(
                    'h-10 rounded-xl text-sm font-medium transition-all group relative flex items-center',
                    isSidebarCollapsed ? 'w-10 mx-auto justify-center' : 'px-3 gap-3',
                    isActive
                      ? 'bg-primary/10 text-primary border border-primary/30 font-semibold shadow-sm'
                      : 'text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted/70 border border-transparent'
                  )
                }
                title={isSidebarCollapsed ? item.name : undefined}
              >
                <Icon className="h-4.5 w-4.5 shrink-0 transition-transform group-hover:scale-110" />
                {!isSidebarCollapsed && <span className="truncate">{item.name}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* 6. Workspaces List */}
        {!isSidebarCollapsed && workspaces.length > 0 && (
          <div className="pt-3 border-t border-surface-border">
            <div className="px-2 mb-2 text-xs font-semibold text-enterprise-dim uppercase tracking-wider font-mono">
              Workspaces
            </div>
            <div className="space-y-1.5 max-h-52 overflow-y-auto pr-0.5">
              {workspaces.map((ws) => {
                const isSelected = activeWorkspaceId === ws.id;
                return (
                  <motion.button
                    key={ws.id}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                    onClick={() => setActiveWorkspaceId(ws.id)}
                    className={cn(
                      'w-full text-left px-3 py-2 rounded-xl text-sm truncate transition-all flex items-center justify-between border',
                      isSelected
                        ? 'bg-primary/10 text-primary font-semibold border-primary/30 shadow-sm'
                        : 'text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted/60 border-transparent'
                    )}
                  >
                    <span className="truncate">{ws.name}</span>
                    <span className="text-xs font-mono opacity-70 ml-1.5 bg-surface-muted/60 px-1.5 py-0.5 rounded">
                      {ws.documentCount}d
                    </span>
                  </motion.button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Bottom User Gateway & Settings */}
      <div className="p-3 border-t border-surface-border space-y-2">
        {/* Corporate User Account Link */}
        {!isSidebarCollapsed ? (
          <Link
            to="/login"
            className="flex items-center gap-2.5 p-2 rounded-xl border border-surface-border bg-surface-muted/50 hover:bg-surface-muted transition-colors group"
            title="Switch corporate account or sign in"
          >
            <div className="h-7 w-7 rounded-lg bg-neutral-900 text-white dark:bg-primary dark:text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-sm">
              {currentUser?.avatarInitials || 'EM'}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-enterprise-text truncate leading-tight group-hover:text-primary transition-colors">
                {currentUser?.name || 'Corporate Account'}
              </div>
              <div className="text-[10px] text-enterprise-dim font-mono truncate">
                {currentUser?.email || 'Sign in'}
              </div>
            </div>
          </Link>
        ) : (
          <Link
            to="/login"
            className="h-10 w-10 mx-auto rounded-xl border border-surface-border bg-surface-muted/70 hover:border-primary/40 text-enterprise-text flex items-center justify-center transition-colors shadow-subtle shrink-0 font-bold text-xs"
            title={`${currentUser?.name || 'Corporate User'} (${currentUser?.email || 'Sign in'}) - Click to switch`}
          >
            {currentUser?.avatarInitials || 'EM'}
          </Link>
        )}

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            cn(
              'h-10 rounded-xl text-sm font-medium transition-colors flex items-center',
              isSidebarCollapsed ? 'w-10 mx-auto justify-center' : 'px-3 gap-3',
              isActive
                ? 'bg-primary/10 text-primary font-semibold border border-primary/30'
                : 'text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted border border-transparent'
            )
          }
          title={isSidebarCollapsed ? 'Settings' : undefined}
        >
          <Settings className="h-4.5 w-4.5 shrink-0" />
          {!isSidebarCollapsed && <span>Settings</span>}
        </NavLink>

        {/* Security / Admin Mode Switcher */}
        {!isSidebarCollapsed ? (
          <div className="pt-1">
            {isAdministrator ? (
              <div className="p-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-900 text-xs flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-amber-600 shrink-0" />
                  <span className="font-semibold text-xs">Admin Mode</span>
                </div>
                <button
                  onClick={logoutAdmin}
                  className="text-[11px] underline text-amber-800 hover:text-black font-mono font-medium"
                >
                  Exit
                </button>
              </div>
            ) : (
              <button
                onClick={openAdminModal}
                className="w-full h-10 px-3 rounded-xl border border-dashed border-surface-border hover:border-primary/40 text-enterprise-muted hover:text-primary hover:bg-orange-50/40 text-xs font-semibold flex items-center gap-2.5 transition-colors"
              >
                <Lock className="h-4 w-4 text-enterprise-dim" />
                <span>Admin Login</span>
              </button>
            )}
          </div>
        ) : (
          <div className="pt-1">
            {isAdministrator ? (
              <button
                onClick={logoutAdmin}
                className="h-10 w-10 mx-auto rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-700 hover:text-amber-900 flex items-center justify-center transition-colors"
                title="Admin Mode Active (Click to Exit)"
              >
                <ShieldCheck className="h-4.5 w-4.5 text-amber-600" />
              </button>
            ) : (
              <button
                onClick={openAdminModal}
                className="h-10 w-10 mx-auto rounded-xl border border-dashed border-surface-border hover:border-primary/40 text-enterprise-muted hover:text-primary hover:bg-orange-50/40 flex items-center justify-center transition-colors"
                title="Enter Admin Maintenance Mode"
              >
                <Lock className="h-4.5 w-4.5 text-enterprise-dim" />
              </button>
            )}
          </div>
        )}
      </div>
    </motion.aside>
  );
};
