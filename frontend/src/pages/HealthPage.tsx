import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  Server,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
  ArrowLeft,
  Code2,
  Sun,
  Moon,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { workspaceService, API_BASE_URL } from '@/services/api';
import { useUIStore } from '@/stores/useUIStore';

export const HealthPage: React.FC = () => {
  const { theme, toggleTheme } = useUIStore();
  const isDark = theme === 'dark';
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

  const endpoints = [
    {
      method: 'POST',
      path: '/api/documents/upload',
      desc: 'Upload and chunk document files',
      payload: 'multipart/form-data (workspace_id: string, file: binary)',
      response: '201 Created (Document metadata & chunk count)',
    },
    {
      method: 'GET',
      path: '/api/documents',
      desc: 'Retrieve indexed document records',
      payload: 'Query: ?workspace_id=string',
      response: '200 OK (Array of Document objects with status)',
    },
    {
      method: 'POST',
      path: '/api/chat',
      desc: 'Execute grounded chat query',
      payload: 'JSON: { workspace_id, query, conversation_id? }',
      response: '200 OK (Stream or JSON response with citation sources)',
    },
    {
      method: 'POST',
      path: '/api/batch',
      desc: 'Execute multi-question batch suite',
      payload: 'JSON: { workspace_id, questions: string[] }',
      response: '200 OK (Batch result array with latency and grounding)',
    },
    {
      method: 'GET',
      path: '/api/chat/{conversation_id}/history',
      desc: 'Fetch conversation message history',
      payload: 'Path: conversation_id: string',
      response: '200 OK (Array of Message records)',
    },
    {
      method: 'GET',
      path: '/api/health',
      desc: 'FastAPI service health check',
      payload: 'None',
      response: '200 OK { status: "ok", timestamp: ISO8601 }',
    },
  ];

  return (
    <div className="min-h-screen bg-background p-6 sm:p-10 text-enterprise-text selection:bg-primary/20">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Top Restricted Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-surface-border">
          <div className="flex items-center gap-3.5">
            <div className="h-11 w-11 rounded-2xl bg-primary/10 border border-primary/25 flex items-center justify-center text-primary shrink-0 shadow-sm">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold tracking-tight text-enterprise-text">
                  FastAPI Health & Telemetry
                </h1>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-surface-muted text-enterprise-muted border border-surface-border font-semibold">
                  /health
                </span>
              </div>
              <p className="text-xs text-enterprise-muted mt-0.5">
                Restricted diagnostic view. Explicit direct URL entry only.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={toggleTheme}
              className="h-9 w-9 rounded-xl border border-surface-border bg-surface-elevated flex items-center justify-center text-enterprise-text hover:text-primary transition-colors shadow-subtle"
              title={`Switch to ${isDark ? 'light' : 'dark'} mode`}
            >
              {isDark ? <Moon className="h-4 w-4 text-amber-400" /> : <Sun className="h-4 w-4 text-amber-500" />}
            </button>

            <Link to="/">
              <Button variant="outline" size="sm" className="gap-2 text-xs">
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Back to App</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Live Diagnostics & Connection Probe */}
        <div className="p-6 rounded-2xl border border-surface-border bg-surface-elevated shadow-subtle space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-surface-border">
            <div className="flex items-center gap-2.5">
              <Server className="h-5 w-5 text-primary" />
              <div>
                <h3 className="text-sm font-semibold text-enterprise-text">
                  FastAPI Live Health Probe
                </h3>
                <p className="text-xs text-enterprise-muted font-mono">
                  Target: <span className="text-primary font-semibold">{API_BASE_URL}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <a
                href={`${API_BASE_URL}/docs`}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-primary hover:underline flex items-center gap-1 font-mono font-semibold"
              >
                <span>Swagger Docs</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>

              <Button
                size="sm"
                variant="primary"
                onClick={handleTestConnection}
                isLoading={isTestingHealth}
                className="gap-2 text-xs h-8 px-3.5 font-semibold"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Test /api/health</span>
              </Button>
            </div>
          </div>

          {healthResult ? (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className={`p-4 rounded-xl border text-sm flex items-start gap-3 ${
                healthResult.status === 'connected'
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
                  : 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-300'
              }`}
            >
              {healthResult.status === 'connected' ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              )}
              <div>
                <span className="font-bold block text-sm">
                  {healthResult.status === 'connected'
                    ? `FastAPI Online (${healthResult.latencyMs}ms)`
                    : `Backend Standby (${healthResult.latencyMs}ms)`}
                </span>
                <p className="text-xs opacity-90 mt-1 leading-relaxed">{healthResult.message}</p>
              </div>
            </motion.div>
          ) : (
            <div className="p-3.5 rounded-xl border border-surface-border bg-surface-muted/50 text-xs text-enterprise-muted flex items-center gap-2 font-mono">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
              <span>Ready to probe backend endpoint. Click "Test /api/health" to measure latency.</span>
            </div>
          )}
        </div>

        {/* Required FastAPI Endpoints Ledger */}
        <div className="p-6 sm:p-7 rounded-2xl border border-surface-border bg-surface-elevated shadow-paper space-y-4">
          <div className="flex items-center justify-between pb-3.5 border-b border-surface-border">
            <div className="flex items-center gap-2.5">
              <Code2 className="h-5 w-5 text-primary" />
              <h2 className="text-base font-bold text-enterprise-text tracking-tight">
                Required FastAPI Endpoints Ledger
              </h2>
            </div>
            <span className="text-xs font-mono font-semibold text-enterprise-dim">
              6 Core Contracts
            </span>
          </div>

          <div className="divide-y divide-surface-border text-sm font-mono">
            {endpoints.map((ep) => (
              <div
                key={ep.path}
                className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-surface-muted/30 px-2 rounded-xl transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span
                      className={`px-2.5 py-0.5 rounded text-xs font-bold tracking-wide ${
                        ep.method === 'POST'
                          ? 'bg-primary text-white shadow-sm'
                          : 'bg-surface-muted text-enterprise-text border border-surface-border'
                      }`}
                    >
                      {ep.method}
                    </span>
                    <span className="text-enterprise-text font-bold text-sm tracking-tight">
                      {ep.path}
                    </span>
                  </div>
                  <p className="text-xs text-enterprise-muted font-sans pl-0.5">
                    {ep.desc}
                  </p>
                </div>

                <div className="flex flex-col md:items-end text-[11px] text-enterprise-dim space-y-0.5 font-mono">
                  <span>Req: {ep.payload}</span>
                  <span className="text-enterprise-muted">Res: {ep.response}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Security & Access Notice */}
        <div className="p-4 rounded-xl border border-surface-border bg-surface-muted/60 text-xs text-enterprise-muted flex items-start gap-3">
          <ShieldAlert className="h-4.5 w-4.5 text-primary shrink-0 mt-0.5" />
          <div className="space-y-1 leading-relaxed">
            <span className="font-semibold text-enterprise-text block">
              Architectural Note
            </span>
            <p>
              This endpoint ledger serves as the authoritative interface contract for backend engineering. It is intentionally decoupled from navigation menus, user sidebars, and public tabs. Access is granted solely via explicit direct URL routing (<code className="text-primary font-mono font-bold">/health</code>).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};