import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Server,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Lock,
  Users,
  FileText,
  Sliders,
  ShieldAlert,
  UploadCloud,
  Layers,
} from 'lucide-react';
import { workspaceService, API_BASE_URL } from '@/services/api';
import { EmployeeManagementSection } from '@/components/admin/EmployeeManagementSection';
import { PolicyManagementSection } from '@/components/admin/PolicyManagementSection';
import { DocumentIngestionSection } from '@/components/admin/DocumentIngestionSection';

export const SettingsPage: React.FC = () => {
  const { settings, updateSettings, resetSettings } = useSettingsStore();
  const { isAdmin, openAdminModal, logoutAdmin } = useAuthStore();
  const isAdministrator = isAdmin();

  const [activeTab, setActiveTab] = useState<'endpoints' | 'ingestion' | 'employees' | 'policies'>('endpoints');
  const [isTestingHealth, setIsTestingHealth] = useState(false);
  const [healthResult, setHealthResult] = useState<{
    status: 'connected' | 'offline';
    latencyMs?: number;
    message: string;
  } | null>(null);

  const handleTestConnection = async () => {
    setIsTestingHealth(true);
    setHealthResult(null);

    const res = await workspaceService.checkHealth();
    if (res.status === 'ok') {
      setHealthResult({
        status: 'connected',
        latencyMs: res.latencyMs,
        message: 'Successfully reached FastAPI backend at /api/health.',
      });
    } else {
      setHealthResult({
        status: 'offline',
        latencyMs: res.latencyMs,
        message: 'FastAPI backend offline at http://localhost:8000. Standalone mock engine is active.',
      });
    }
    setIsTestingHealth(false);
  };

  const handleTabClick = (tab: 'endpoints' | 'ingestion' | 'employees' | 'policies') => {
    if (tab !== 'endpoints' && !isAdministrator) {
      openAdminModal();
      return;
    }
    setActiveTab(tab);
  };

  return (
    <div className="p-6 sm:p-8 max-w-5xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-border">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-enterprise-text tracking-tight">
            Administrative Settings & Controls
          </h1>
          <p className="text-sm text-enterprise-muted mt-1">
            System configuration, document ingestion vault, employee directory, and policy repository.
          </p>
        </div>

        {isAdministrator ? (
          <div className="flex items-center gap-2 p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-900 text-xs font-semibold shadow-subtle">
            <ShieldCheck className="h-4 w-4 text-amber-600 shrink-0" />
            <span>Maintenance Mode Active (Full CRUD)</span>
            <button
              onClick={logoutAdmin}
              className="ml-2 px-2.5 py-1 rounded-lg bg-surface border border-surface-border text-enterprise-text hover:bg-surface-muted transition-colors font-mono font-medium"
            >
              Exit
            </button>
          </div>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            onClick={openAdminModal}
            className="gap-2 text-xs font-semibold"
          >
            <Lock className="h-3.5 w-3.5 text-primary" />
            <span>Admin Authentication</span>
          </Button>
        )}
      </div>

      {/* Settings Navigation Tabs with Vibrant High-Contrast Highlighting */}
      <div className="flex items-center gap-2.5 border-b border-surface-border pb-3 overflow-x-auto no-scrollbar">
        {/* Tab 1: Endpoints */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => handleTabClick('endpoints')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all relative ${
            activeTab === 'endpoints'
              ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white shadow-subtle border border-transparent'
              : 'text-enterprise-text/75 hover:text-enterprise-text hover:bg-surface-muted/60 border border-transparent'
          }`}
        >
          <Server className="h-4 w-4" />
          <span>Platform & Backend</span>
        </motion.button>

        {/* Tab 2: Document Ingestion (Admin Only) */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => handleTabClick('ingestion')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all relative ${
            activeTab === 'ingestion'
              ? 'bg-primary text-white shadow-warm border border-primary font-bold'
              : 'text-enterprise-text hover:text-primary hover:bg-primary/10 border border-transparent'
          }`}
        >
          <UploadCloud className="h-4.5 w-4.5 shrink-0" />
          <span>Document Ingestion</span>
          {!isAdministrator ? (
            <span className="text-[10px] font-mono uppercase bg-surface-muted px-1.5 py-0.5 rounded border border-surface-border flex items-center gap-1 text-enterprise-dim font-bold">
              <Lock className="h-2.5 w-2.5" /> Admin
            </span>
          ) : (
            <span
              className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-md font-bold ${
                activeTab === 'ingestion'
                  ? 'bg-white/20 text-white'
                  : 'bg-primary/15 text-primary border border-primary/30'
              }`}
            >
              Add Files
            </span>
          )}
        </motion.button>

        {/* Tab 3: Employee Management (Admin Only) */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => handleTabClick('employees')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all relative ${
            activeTab === 'employees'
              ? 'bg-primary text-white shadow-warm border border-primary font-bold'
              : 'text-enterprise-text hover:text-primary hover:bg-primary/10 border border-transparent'
          }`}
        >
          <Users className="h-4.5 w-4.5 shrink-0" />
          <span>Employee Management</span>
          {!isAdministrator ? (
            <span className="text-[10px] font-mono uppercase bg-surface-muted px-1.5 py-0.5 rounded border border-surface-border flex items-center gap-1 text-enterprise-dim font-bold">
              <Lock className="h-2.5 w-2.5" /> Admin
            </span>
          ) : (
            <span
              className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-md font-bold ${
                activeTab === 'employees'
                  ? 'bg-white/20 text-white'
                  : 'bg-primary/15 text-primary border border-primary/30'
              }`}
            >
              CRUD
            </span>
          )}
        </motion.button>

        {/* Tab 4: Policy Documents (Admin Only) */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => handleTabClick('policies')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all relative ${
            activeTab === 'policies'
              ? 'bg-primary text-white shadow-warm border border-primary font-bold'
              : 'text-enterprise-text hover:text-primary hover:bg-primary/10 border border-transparent'
          }`}
        >
          <FileText className="h-4.5 w-4.5 shrink-0" />
          <span>Policy Documents</span>
          {!isAdministrator ? (
            <span className="text-[10px] font-mono uppercase bg-surface-muted px-1.5 py-0.5 rounded border border-surface-border flex items-center gap-1 text-enterprise-dim font-bold">
              <Lock className="h-2.5 w-2.5" /> Admin
            </span>
          ) : (
            <span
              className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-md font-bold ${
                activeTab === 'policies'
                  ? 'bg-white/20 text-white'
                  : 'bg-primary/15 text-primary border border-primary/30'
              }`}
            >
              CRUD
            </span>
          )}
        </motion.button>
      </div>

      {/* Tab 1: Platform & Endpoints */}
      {activeTab === 'endpoints' && (
        <div className="space-y-6">
          {/* FastAPI Backend Box */}
          <div className="p-6 rounded-2xl border border-surface-border bg-surface-elevated space-y-4 shadow-subtle">
            <div className="flex items-center justify-between pb-3.5 border-b border-surface-border">
              <div className="flex items-center gap-3">
                <Server className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="text-base font-semibold text-enterprise-text">FastAPI Backend</h3>
                  <p className="text-xs text-enterprise-muted">
                    Default target: <code className="text-primary font-mono font-medium">http://localhost:8000</code>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <a
                  href="http://localhost:8000/docs"
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1 font-mono font-semibold"
                >
                  <span>Swagger Docs</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>

                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleTestConnection}
                  isLoading={isTestingHealth}
                  className="gap-2 text-xs h-8 px-3 font-semibold"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  <span>Test /api/health</span>
                </Button>
              </div>
            </div>

            <div className="space-y-3.5">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-semibold text-enterprise-text">
                    API Base URL
                  </label>
                  {!isAdministrator && (
                    <span className="text-xs text-enterprise-dim flex items-center gap-1 font-mono">
                      <Lock className="h-3 w-3" />
                      Read-Only (Admin required to edit)
                    </span>
                  )}
                </div>
                <input
                  type="text"
                  disabled={!isAdministrator}
                  value={settings.apiBaseUrl}
                  onChange={(e) => {
                    if (isAdministrator) {
                      updateSettings({ apiBaseUrl: e.target.value });
                    }
                  }}
                  className={`w-full border rounded-xl px-3.5 py-2 text-sm font-mono text-enterprise-text focus:outline-none ${
                    isAdministrator
                      ? 'bg-surface-muted border-surface-border focus:border-primary'
                      : 'bg-surface-muted/40 border-surface-border/50 opacity-70 cursor-not-allowed'
                  }`}
                />
                {!isAdministrator && (
                  <div className="mt-2 flex items-center justify-between text-xs text-enterprise-muted bg-surface-muted/50 p-2.5 rounded-xl border border-surface-border/60">
                    <span>Modifying network targets is locked in Employee mode.</span>
                    <button
                      onClick={openAdminModal}
                      className="text-primary font-semibold hover:underline flex items-center gap-1"
                    >
                      <Lock className="h-3 w-3" />
                      <span>Admin Mode</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Health Result */}
              {healthResult && (
                <div
                  className={`p-3.5 rounded-xl border text-sm flex items-start gap-2.5 ${
                    healthResult.status === 'connected'
                      ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                      : 'border-amber-300 bg-amber-50 text-amber-800'
                  }`}
                >
                  {healthResult.status === 'connected' ? (
                    <CheckCircle2 className="h-4.5 w-4.5 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="h-4.5 w-4.5 text-amber-600 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <span className="font-semibold block text-sm">
                      {healthResult.status === 'connected'
                        ? `FastAPI Online (${healthResult.latencyMs}ms)`
                        : `Backend Standby (${healthResult.latencyMs}ms)`}
                    </span>
                    <p className="text-xs opacity-90 mt-0.5">{healthResult.message}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Document Ingestion (Admin Only) */}
      {activeTab === 'ingestion' && isAdministrator && (
        <DocumentIngestionSection />
      )}

      {/* Tab 3: Employee Management (Admin Only) */}
      {activeTab === 'employees' && isAdministrator && (
        <EmployeeManagementSection />
      )}

      {/* Tab 4: Policy Documents (Admin Only) */}
      {activeTab === 'policies' && isAdministrator && (
        <PolicyManagementSection />
      )}
    </div>
  );
};
