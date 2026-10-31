import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowUp, FolderOpen } from 'lucide-react';
import { useNavigate, Link } from 'react-router-dom';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { useChatStore } from '@/stores/useChatStore';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { workspaces, activeWorkspaceId } = useWorkspaceStore();
  const { setMessages } = useChatStore();

  const activeWorkspace =
    workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];

  const [inputQuery, setInputQuery] = useState('');

  const handleQuerySubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputQuery.trim()) return;

    const query = inputQuery.trim();
    setInputQuery('');

    const userMsg = {
      id: `msg-${Date.now()}`,
      workspaceId: activeWorkspace?.id || 'default',
      role: 'user' as const,
      content: query,
      timestamp: new Date().toISOString(),
    };

    setMessages(activeWorkspace?.id || 'default', [userMsg]);
    navigate('/chat');
  };

  const promptStarters = [
    'Summarize the core topics in the uploaded documents',
    'What are the key requirements and action items?',
    'Explain the specifications and findings in detail',
    'Extract the primary metrics, dates, and conclusions',
  ];

  return (
    <div className="relative min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-center px-4 py-12 selection:bg-primary/20">
      {/* Subtle Warm Wrapped Paper Ambient Glow */}
      <div className="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden opacity-40">
        <div className="h-[480px] w-[560px] rounded-full bg-gradient-to-tr from-primary/10 via-amber-500/5 to-transparent blur-3xl" />
      </div>

      {/* Main Centered ChatGPT / Gemini Conversational Hero */}
      <div className="w-full max-w-2xl mx-auto space-y-8 text-center">
        {/* Editorial Minimal Greeting */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: 'easeOut' }}
          className="space-y-3"
        >
          <h1 className="text-3xl sm:text-4xl md:text-5xl font-semibold tracking-tight text-enterprise-text">
            Where knowledge begins.
          </h1>
          <p className="text-sm sm:text-base text-enterprise-muted max-w-lg mx-auto leading-relaxed">
            Ask anything grounded strictly in your enterprise documents.
          </p>
        </motion.div>

        {/* Central Composer Box */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08, ease: 'easeOut' }}
          className="relative w-full"
        >
          <form
            onSubmit={handleQuerySubmit}
            className="rounded-3xl border border-surface-border bg-surface-elevated/95 shadow-paper p-5 transition-all focus-within:border-primary/60 focus-within:shadow-warm text-left"
          >
            <textarea
              rows={3}
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleQuerySubmit();
                }
              }}
              placeholder={`Ask a question across ${activeWorkspace?.name || 'documents'}...`}
              className="w-full bg-transparent text-base sm:text-lg text-enterprise-text placeholder-enterprise-dim focus:outline-none resize-none leading-relaxed"
            />

            {/* Bottom Action Toolbar inside Composer */}
            <div className="pt-3.5 flex items-center justify-between border-t border-surface-border/50">
              <div className="flex items-center gap-3">
                {/* Workspace indicator */}
                <Link
                  to="/workspace"
                  className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted transition-colors font-mono"
                  title="View indexed documents in this workspace"
                >
                  <FolderOpen className="h-4 w-4 text-primary" />
                  <span className="truncate max-w-[200px] font-semibold">{activeWorkspace?.name}</span>
                </Link>
              </div>

              {/* Submit Query Button (Black Element with Orange Accent) */}
              <motion.button
                whileHover={{ scale: 1.08 }}
                whileTap={{ scale: 0.92 }}
                type="submit"
                disabled={!inputQuery.trim()}
                className={`h-9 w-9 sm:h-10 sm:w-10 rounded-xl flex items-center justify-center transition-all ${
                  inputQuery.trim()
                    ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white hover:bg-primary shadow-sm'
                    : 'bg-surface-muted text-enterprise-dim cursor-not-allowed opacity-50'
                }`}
              >
                <ArrowUp className="h-4.5 w-4.5 stroke-[2.5]" />
              </motion.button>
            </div>
          </form>

          {/* Prompt Starters (Paper Pills with Tactile Spring Micro-interactions) */}
          <div className="flex flex-wrap items-center justify-center gap-2.5 mt-6">
            {promptStarters.map((starter, idx) => (
              <motion.button
                key={idx}
                whileHover={{ scale: 1.04, y: -1 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => setInputQuery(starter)}
                className="px-4 py-2 rounded-full border border-surface-border bg-surface text-sm text-enterprise-text hover:text-primary hover:border-primary/50 hover:bg-primary/10 transition-colors shadow-subtle font-medium"
              >
                {starter}
              </motion.button>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
};
