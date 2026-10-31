import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  ChevronRight,
  ChevronLeft,
  Trash2,
  Check,
  CheckSquare,
  BookOpen,
  Sun,
  Moon,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { useChatStore } from '@/stores/useChatStore';
import { useUIStore } from '@/stores/useUIStore';
import { MessageItem } from './MessageItem';
import { MessageComposer } from './MessageComposer';
import { TypingIndicator } from './TypingIndicator';
import { EvidenceInspector } from '@/components/citations/EvidenceInspector';
import { ChatMessage, Citation } from '@/types';
import { INITIAL_MESSAGES } from '@/mocks/initialData';
import { workspaceService } from '@/services/api';

export const ChatContainer: React.FC = () => {
  const {
    workspaces,
    activeWorkspaceId,
    documents,
    toggleDocumentSelection,
    selectAllDocuments,
    deselectAllDocuments,
  } = useWorkspaceStore();

  const { theme, toggleTheme } = useUIStore();
  const isDark = theme === 'dark';

  const {
    messages,
    setMessages,
    activeCitation,
    setActiveCitation,
    isEvidencePanelOpen,
    toggleEvidencePanel,
    setEvidencePanelOpen,
    isStreaming,
    setIsStreaming,
  } = useChatStore();

  const [isLeftPanelOpen, setIsLeftPanelOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const activeWorkspace =
    workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];

  const currentWorkspaceId = activeWorkspace?.id || 'default';
  const currentMessages =
    messages[currentWorkspaceId] || INITIAL_MESSAGES[currentWorkspaceId] || [];

  const workspaceDocs = documents.filter((d) => !d.workspaceId || d.workspaceId === currentWorkspaceId || currentWorkspaceId === 'default');
  const validSelectedIds = (activeWorkspace?.selectedDocumentIds || []).filter((id) =>
    workspaceDocs.some((d) => d.id === id)
  );
  const activeDocs =
    validSelectedIds.length > 0
      ? workspaceDocs.filter((d) => validSelectedIds.includes(d.id))
      : workspaceDocs;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentMessages, isStreaming]);

  const messageForActiveCitation = currentMessages.find((m) =>
    m.citations?.some((c) => c.id === activeCitation?.id)
  );
  const latestAssistantMsg = [...currentMessages].reverse().find((m) => m.role === 'assistant');
  const activeSources: Citation[] =
    messageForActiveCitation?.citations || latestAssistantMsg?.citations || [];

  const handleSendMessage = async (userPrompt: string) => {
    setActiveCitation(null);
    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      workspaceId: currentWorkspaceId,
      role: 'user',
      content: userPrompt,
      timestamp: new Date().toISOString(),
    };

    const nextList = [...currentMessages, userMsg];
    setMessages(currentWorkspaceId, nextList);
    setIsStreaming(true);

    // 1. Send query to backend intelligence service (Ollama Qwen + Knowledge Vault)
    try {
      // If user selected a specific subset in the checklist, restrict to those; otherwise query active partition docs
      const activeDocIds = validSelectedIds.length > 0 ? activeDocs.map((d) => d.id) : undefined;
      const res = await workspaceService.sendChatMessage({
        message: userPrompt,
        workspace_id: currentWorkspaceId,
        document_ids: activeDocIds,
        conversation_id: currentWorkspaceId,
      });

      if (res && res.answer) {
        const rawConf = (res as any).confidence_score ?? (res as any).confidenceScore;
        const confidenceScore = typeof rawConf === 'number'
          ? rawConf
          : (res.coverage === 'full' ? 0.92 : res.coverage === 'partial' ? 0.65 : 0.0);

        const mappedCitations: Citation[] = (res.citations || []).map((c: any, idx: number) => ({
          id: c.id || c.chunk_id || ('cit-' + Date.now() + '-' + idx),
          documentId: c.documentId || c.document_id || activeDocs[0]?.id || '',
          documentName: c.documentName || c.document_name || activeDocs[0]?.name || 'Uploaded Document',
          pageNumber: c.pageNumber ?? c.page_number ?? c.page ?? 1,
          chunkId: c.chunkId || c.chunk_id,
          snippet: c.snippet || c.section || '',
          relevanceScore: c.relevanceScore ?? c.relevance_score ?? 0.85,
        }));

        const assistantMsg: ChatMessage = {
          id: `msg-resp-${Date.now()}`,
          workspaceId: currentWorkspaceId,
          role: 'assistant',
          content: res.answer,
          timestamp: new Date().toISOString(),
          coverage: res.coverage || (mappedCitations.length > 0 ? 'full' : 'insufficient_evidence'),
          groundedDocCount: mappedCitations.length || activeDocs.length,
          executionTimeMs: res.latency_ms || (res as any).execution_time_ms || 320,
          confidenceScore: confidenceScore,
          citations: mappedCitations,
        };

        setMessages(currentWorkspaceId, [...nextList, assistantMsg]);
        setIsStreaming(false);

        if (assistantMsg.citations && assistantMsg.citations.length > 0) {
          setActiveCitation(assistantMsg.citations[0]);
          setEvidencePanelOpen(true);
        } else {
          setActiveCitation(null);
        }
        return;
      }
    } catch (err: any) {
      console.warn('Real backend chat request failed:', err);
      const assistantMsg: ChatMessage = {
        id: `msg-resp-${Date.now()}`,
        workspaceId: currentWorkspaceId,
        role: 'assistant',
        content: `Unable to connect to knowledge backend: ${err.message || 'connection error'}. Please verify the backend service is running on port 8000.`,
        timestamp: new Date().toISOString(),
        coverage: 'insufficient_evidence',
        groundedDocCount: 0,
        executionTimeMs: 120,
        confidenceScore: 0.0,
      };
      setMessages(currentWorkspaceId, [...nextList, assistantMsg]);
      setIsStreaming(false);
      return;
    }
  };


    const handleStopStreaming = () => {
    if (streamTimeoutRef.current) {
      clearTimeout(streamTimeoutRef.current);
      streamTimeoutRef.current = null;
    }
    setIsStreaming(false);
  };

  const handleClearHistory = () => {
    setMessages(currentWorkspaceId, []);
    setActiveCitation(null);
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex overflow-hidden bg-background">
      {/* =========================================================================
          LEFT PANEL: Documents Scope Checklist with High Contrast & Micro-interactions
         ========================================================================= */}
      <motion.div
        animate={{ width: isLeftPanelOpen ? 280 : 0 }}
        transition={{ type: 'spring', damping: 30, stiffness: 350 }}
        className="border-r border-surface-border bg-surface shrink-0 flex flex-col justify-between overflow-hidden z-20"
      >
        <div className="p-4 space-y-4 flex-1 overflow-y-auto">
          <div className="flex items-center justify-between pb-2 border-b border-surface-border">
            <span className="text-sm font-semibold text-enterprise-text tracking-tight">
              Active Documents ({activeDocs.length})
            </span>
            <button
              onClick={() => setIsLeftPanelOpen(false)}
              className="text-enterprise-muted hover:text-enterprise-text p-1.5 rounded-lg transition-colors"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>

          {/* Quick Select All Button for Drawer */}
          <div className="flex items-center justify-between py-1">
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => {
                if (activeDocs.length === workspaceDocs.length && workspaceDocs.length > 0) {
                  deselectAllDocuments();
                } else {
                  selectAllDocuments(workspaceDocs.map((d) => d.id));
                }
              }}
              className="text-xs font-semibold text-primary hover:text-primary-hover flex items-center gap-1.5 transition-colors"
            >
              <CheckSquare className="h-3.5 w-3.5" />
              <span>
                {activeDocs.length === workspaceDocs.length && workspaceDocs.length > 0
                  ? 'Deselect All'
                  : 'Select All'}
              </span>
            </motion.button>
            <span className="text-[11px] font-mono text-enterprise-dim">
              {activeDocs.length}/{workspaceDocs.length}
            </span>
          </div>

          <div className="space-y-1.5">
            {workspaceDocs.map((doc) => {
              const isChecked = activeWorkspace?.selectedDocumentIds.includes(doc.id);
              return (
                <motion.div
                  key={doc.id}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => toggleDocumentSelection(doc.id)}
                  className={`p-3 rounded-xl text-sm cursor-pointer transition-all flex items-start gap-3 border ${
                    isChecked
                      ? 'bg-primary/10 text-enterprise-text border-primary/40 font-medium shadow-sm'
                      : 'border-transparent text-enterprise-text/75 hover:text-enterprise-text hover:bg-surface-muted/60'
                  }`}
                >
                  <div
                    className={`h-4.5 w-4.5 mt-0.5 rounded-lg border flex items-center justify-center shrink-0 transition-colors ${
                      isChecked
                        ? 'border-primary bg-primary text-white shadow-sm'
                        : 'border-surface-border bg-surface-elevated'
                    }`}
                  >
                    {isChecked && <Check className="h-3 w-3 stroke-[3]" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-sm text-enterprise-text">{doc.name}</p>
                    <p className="text-xs text-enterprise-muted font-mono mt-0.5">
                      {doc.format.toUpperCase()}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="p-3.5 border-t border-surface-border">
          <button
            onClick={handleClearHistory}
            className="w-full text-left px-3 py-2 rounded-xl text-sm text-enterprise-muted hover:text-red-600 flex items-center gap-2.5 transition-colors font-medium"
          >
            <Trash2 className="h-4 w-4" />
            <span>Clear conversation</span>
          </button>
        </div>
      </motion.div>

      {/* =========================================================================
          CENTER PANEL: Minimal Conversational Stream
         ========================================================================= */}
      <div className="flex-1 flex flex-col justify-between overflow-hidden bg-background relative">
        {/* Subtle Chat Header */}
        <div className="h-14 border-b border-surface-border px-6 flex items-center justify-between shrink-0 bg-surface/60 backdrop-blur z-10">
          <div className="flex items-center gap-3">
            {!isLeftPanelOpen && (
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => setIsLeftPanelOpen(true)}
                className="p-1.5 rounded-lg text-enterprise-muted hover:text-enterprise-text transition-colors"
                title="Toggle documents scope"
              >
                <ChevronRight className="h-4 w-4" />
              </motion.button>
            )}
            <span className="text-sm sm:text-base font-semibold text-enterprise-text">
              {activeWorkspace?.name}
            </span>
            <span className="text-xs text-enterprise-muted font-mono bg-surface-muted/60 px-2 py-0.5 rounded-md border border-surface-border/50">
              {activeDocs.length} files active
            </span>
          </div>

          {/* Right Action: Evidence Drawer Toggle (Offset for Top-Right Floating Dark Mode Button) */}
          <div className="flex items-center gap-2.5 mr-24">
            <motion.button
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.96 }}
              onClick={toggleEvidencePanel}
              className={`text-sm h-9 px-3.5 rounded-xl border flex items-center gap-2 transition-all shadow-subtle ${
                isEvidencePanelOpen
                  ? 'border-primary/50 bg-primary/10 text-primary font-semibold'
                  : 'border-surface-border bg-surface-elevated text-enterprise-text hover:border-surface-border-hover'
              }`}
            >
              <BookOpen className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">Sources</span>
              {activeSources.length > 0 && (
                <span className="h-4.5 px-2 rounded-full bg-primary text-white text-xs font-mono font-bold flex items-center justify-center">
                  {activeSources.length}
                </span>
              )}
            </motion.button>
          </div>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {currentMessages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 text-enterprise-muted space-y-2">
              <p className="text-sm font-semibold text-enterprise-text">Start a conversation</p>
              <p className="text-xs max-w-sm text-enterprise-muted">
                Ask questions about your uploaded documents. Answers will cite specific pages.
              </p>
            </div>
          ) : (
            currentMessages.map((msg) => (
              <MessageItem
                key={msg.id}
                message={msg}
                onSelectCitation={(cit) => {
                  setActiveCitation(cit);
                  setEvidencePanelOpen(true);
                }}
                activeCitationId={activeCitation?.id}
              />
            ))
          )}

          {isStreaming && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Query Input Composer */}
        <MessageComposer
          onSendMessage={handleSendMessage}
          isStreaming={isStreaming}
          onStopStreaming={handleStopStreaming}
          activeDocCount={activeDocs.length}
        />
      </div>

      {/* =========================================================================
          RIGHT PANEL: Sources and Evidence Inspector
         ========================================================================= */}
      <AnimatePresence>
        {isEvidencePanelOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 380, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', damping: 30, stiffness: 350 }}
            className="shrink-0 h-full overflow-hidden z-20"
          >
            <EvidenceInspector
              citation={activeCitation}
              allCitations={activeSources}
              onSelectCitation={(cit) => setActiveCitation(cit)}
              onClose={() => setEvidencePanelOpen(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
