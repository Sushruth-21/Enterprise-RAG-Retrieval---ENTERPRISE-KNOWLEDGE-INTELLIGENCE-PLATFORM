import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FolderOpen,
  MessageSquare,
  ArrowRight,
  Search,
  Check,
  CheckSquare,
  ShieldAlert,
  ShieldCheck,
  Lock,
  UploadCloud,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { Button } from '@/components/ui/Button';
import { DocumentCard } from '@/components/documents/DocumentCard';
import { DocumentFormat } from '@/types';
import { Link } from 'react-router-dom';

const FORMAT_FILTERS = ['all', 'pdf', 'docx', 'md', 'txt'] as const;

export const WorkspacePage: React.FC = () => {
  const {
    workspaces,
    activeWorkspaceId,
    documents,
    toggleDocumentSelection,
    selectDocumentRange,
    selectAllDocuments,
    deselectAllDocuments,
    removeDocument,
  } = useWorkspaceStore();

  const { isAdmin, openAdminModal } = useAuthStore();
  const isAdministrator = isAdmin();

  const [searchDoc, setSearchDoc] = useState('');
  const [formatFilter, setFormatFilter] = useState<'all' | DocumentFormat>('all');
  const [lastSelectedDocId, setLastSelectedDocId] = useState<string | null>(null);

  const filterRefs = React.useRef<(HTMLButtonElement | null)[]>([]);
  const [indicatorProps, setIndicatorProps] = useState<{ left: number; width: number; ready: boolean }>({
    left: 0,
    width: 0,
    ready: false,
  });

  React.useEffect(() => {
    const updateIndicator = () => {
      const activeIdx = FORMAT_FILTERS.indexOf(formatFilter);
      const activeEl = filterRefs.current[activeIdx];
      if (activeEl) {
        setIndicatorProps({
          left: activeEl.offsetLeft,
          width: activeEl.offsetWidth,
          ready: true,
        });
      }
    };

    updateIndicator();
    window.addEventListener('resize', updateIndicator);
    return () => window.removeEventListener('resize', updateIndicator);
  }, [formatFilter]);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];
  const currentWorkspaceId = activeWorkspace?.id || 'default';
  const workspaceDocs = documents.filter(
    (d) => !d.workspaceId || d.workspaceId === currentWorkspaceId || currentWorkspaceId === 'default'
  );

  if (!activeWorkspace) {
    return (
      <div className="p-12 text-center max-w-md mx-auto space-y-3">
        <p className="text-sm text-enterprise-muted">No active workspace selected.</p>
        <Link to="/">
          <Button size="sm">Go to Home</Button>
        </Link>
      </div>
    );
  }

  const filteredDocs = workspaceDocs.filter((doc) => {
    const matchesSearch = doc.name.toLowerCase().includes(searchDoc.toLowerCase());
    const matchesFormat = formatFilter === 'all' || doc.format === formatFilter;
    return matchesSearch && matchesFormat;
  });

  const selectedCount = (activeWorkspace.selectedDocumentIds || []).filter((id) =>
    workspaceDocs.some((d) => d.id === id)
  ).length;

  const handleDocumentSelect = (docId: string, event: React.MouseEvent) => {
    if (event.shiftKey && lastSelectedDocId) {
      const lastIndex = filteredDocs.findIndex((d) => d.id === lastSelectedDocId);
      const currentIndex = filteredDocs.findIndex((d) => d.id === docId);

      if (lastIndex !== -1 && currentIndex !== -1) {
        const start = Math.min(lastIndex, currentIndex);
        const end = Math.max(lastIndex, currentIndex);
        const rangeIds = filteredDocs.slice(start, end + 1).map((d) => d.id);
        selectDocumentRange(rangeIds);
        setLastSelectedDocId(docId);
        return;
      }
    }

    toggleDocumentSelection(docId);
    setLastSelectedDocId(docId);
  };

  return (
    <div className="p-6 sm:p-8 max-w-6xl mx-auto space-y-6">
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-surface-border">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-enterprise-text tracking-tight">
            {activeWorkspace.name}
          </h1>
          <p className="text-sm text-enterprise-muted mt-1 max-w-xl leading-relaxed">
            {activeWorkspace.description || 'Partition-isolated documents for grounded queries.'}
          </p>
        </div>

        <Link to="/chat">
          <Button size="md" className="gap-2.5 text-sm font-semibold">
            <MessageSquare className="h-4 w-4" />
            <span>Chat ({selectedCount} active docs)</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>

      {/* Centralized Document Ingestion Notice (Settings Only) */}
      {isAdministrator ? (
        <div className="p-4 sm:p-5 rounded-2xl border border-primary/30 bg-primary/5 shadow-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="h-10 w-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0 shadow-sm">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-enterprise-text flex items-center gap-2">
                <span>Admin Document Ingestion Vault</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-primary text-white font-bold">
                  Settings Only
                </span>
              </h3>
              <p className="text-xs text-enterprise-muted mt-1 max-w-xl leading-relaxed">
                In accordance with enterprise security policy, all document ingestion and vector indexing is centralized exclusively in Admin Settings.
              </p>
            </div>
          </div>

          <Link to="/settings">
            <Button size="sm" className="gap-2 shrink-0 text-xs font-semibold shadow-warm">
              <span>Go to Settings → Document Ingestion</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
      ) : (
        <div className="p-4 sm:p-5 rounded-2xl border border-surface-border bg-surface-elevated shadow-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="h-10 w-10 rounded-xl bg-surface-muted border border-surface-border flex items-center justify-center text-enterprise-dim shrink-0 shadow-sm">
              <ShieldAlert className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-enterprise-text flex items-center gap-2">
                <span>Knowledge Base Ingestion Restricted (Employee Mode)</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-surface-muted text-enterprise-dim font-bold">
                  Read-Only
                </span>
              </h3>
              <p className="text-xs text-enterprise-muted mt-1 max-w-xl leading-relaxed">
                Employees can execute queries and audit grounded citations across indexed documents. Document addition is restricted exclusively to Admin Settings.
              </p>
            </div>
          </div>

          <Button
            size="sm"
            variant="secondary"
            onClick={openAdminModal}
            className="gap-2 shrink-0 text-xs font-semibold"
          >
            <Lock className="h-3.5 w-3.5 text-primary" />
            <span>Admin Login</span>
          </Button>
        </div>
      )}

      {/* Documents List & Controls */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 bg-surface p-4 rounded-2xl border border-surface-border shadow-subtle">
          {/* Left: Prominent Select All Button & Selection Status */}
          <div className="flex items-center gap-3">
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => {
                if (selectedCount === workspaceDocs.length && workspaceDocs.length > 0) {
                  deselectAllDocuments();
                } else {
                  selectAllDocuments(workspaceDocs.map((d) => d.id));
                }
              }}
              className={`h-9 px-3.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all shadow-subtle ${
                selectedCount === workspaceDocs.length && workspaceDocs.length > 0
                  ? 'bg-primary text-white border border-primary shadow-warm'
                  : 'bg-surface-elevated text-enterprise-text border border-surface-border hover:border-primary/50 hover:text-primary'
              }`}
              title={selectedCount === workspaceDocs.length ? 'Deselect all documents' : 'Select all documents'}
            >
              <CheckSquare
                className={`h-4 w-4 ${
                  selectedCount === workspaceDocs.length && workspaceDocs.length > 0
                    ? 'text-white'
                    : 'text-primary'
                }`}
              />
              <span>
                {selectedCount === workspaceDocs.length && workspaceDocs.length > 0
                  ? 'All Selected'
                  : 'Select All'}
              </span>
              <span className="font-mono text-[11px] opacity-85 px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-bold">
                {selectedCount}/{workspaceDocs.length}
              </span>
            </motion.button>

            {selectedCount > 0 && selectedCount < workspaceDocs.length && (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={deselectAllDocuments}
                className="h-9 px-3 rounded-xl text-xs font-medium text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted border border-surface-border/50 transition-colors"
              >
                Deselect All
              </motion.button>
            )}
          </div>

          {/* Right: Search & Unified Sliding Indicator Segmented Control */}
          <div className="flex items-center gap-3">
            <div className="relative flex items-center gap-1 bg-surface-muted/90 p-1 rounded-xl border border-surface-border text-xs">
              {/* Single Continuous Sliding Indicator - Zero Overlapping Divs */}
              {indicatorProps.ready && (
                <motion.div
                  className="absolute top-1 bottom-1 left-0 bg-neutral-900 dark:bg-primary rounded-lg shadow-sm pointer-events-none"
                  initial={false}
                  animate={{
                    x: indicatorProps.left,
                    width: indicatorProps.width,
                  }}
                  transition={{
                    type: 'spring',
                    stiffness: 450,
                    damping: 35,
                    mass: 0.8,
                  }}
                />
              )}

              {FORMAT_FILTERS.map((fmt, idx) => {
                const isActive = formatFilter === fmt;
                return (
                  <motion.button
                    key={fmt}
                    ref={(el) => (filterRefs.current[idx] = el)}
                    whileTap={{ scale: 0.94 }}
                    onClick={() => setFormatFilter(fmt)}
                    className={`relative z-10 px-3 py-1.5 rounded-lg text-xs font-mono uppercase font-bold select-none transition-colors duration-200 ${
                      isActive
                        ? 'text-white'
                        : 'text-enterprise-text/75 hover:text-enterprise-text'
                    }`}
                  >
                    {fmt}
                  </motion.button>
                );
              })}
            </div>

            <div className="relative w-52">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-enterprise-dim" />
              <input
                type="text"
                placeholder="Search documents..."
                value={searchDoc}
                onChange={(e) => setSearchDoc(e.target.value)}
                className="w-full bg-surface-elevated border border-surface-border rounded-xl pl-9 pr-3 py-1.5 text-sm text-enterprise-text placeholder-enterprise-dim focus:outline-none focus:border-primary/50"
              />
            </div>
          </div>
        </div>

        {/* Cards Grid with Layout Animations & Shift-Select Support */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AnimatePresence mode="popLayout">
            {filteredDocs.map((doc) => {
              const isSelected = (activeWorkspace.selectedDocumentIds || []).includes(doc.id);
              return (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  isSelected={isSelected}
                  onToggleSelect={(e) => handleDocumentSelect(doc.id, e)}
                  onRemove={(id) => removeDocument(id)}
                />
              );
            })}
          </AnimatePresence>

          {filteredDocs.length === 0 && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="col-span-full py-12 text-center border border-dashed border-surface-border rounded-2xl bg-surface/50"
            >
              <FolderOpen className="h-8 w-8 text-enterprise-dim mx-auto mb-2 opacity-50" />
              <p className="text-xs text-enterprise-muted">No documents found matching filter.</p>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
};
