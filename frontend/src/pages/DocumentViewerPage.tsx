import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  FileText,
  ShieldCheck,
  Info,
  BookOpen,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { formatBytes, formatDate } from '@/lib/utils';
import { INITIAL_CITATIONS, INITIAL_DOCUMENTS } from '@/mocks/initialData';
import { apiClient } from '@/services/api';

export const DocumentViewerPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();

  const { documents } = useWorkspaceStore();

  const doc =
    documents.find((d) => d.id === id) ||
    INITIAL_DOCUMENTS.find((d) => d.id === id) ||
    INITIAL_DOCUMENTS[0];

  const totalPages = doc?.pageCount || 14;
  const initialPage = parseInt(searchParams.get('page') || '1', 10);

  const [currentPage, setCurrentPage] = useState(
    Math.min(Math.max(1, initialPage), totalPages)
  );
  const [zoomScale, setZoomScale] = useState<number>(100);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [hasCopiedHash, setHasCopiedHash] = useState(false);
  const [loadedChunks, setLoadedChunks] = useState<any[]>([]);

  useEffect(() => {
    if (!id) return;
    apiClient.get(`/api/documents/${id}`)
      .then((res) => {
        const chunks = res.data?.chunks;
        if (Array.isArray(chunks) && chunks.length > 0) {
          setLoadedChunks(chunks);
        }
      })
      .catch(() => {});
  }, [id]);

  const pageContainerRef = useRef<HTMLDivElement>(null);

  const docCitations = INITIAL_CITATIONS.filter(
    (c) => c.documentId === doc.id || c.documentName === doc.name
  );

  useEffect(() => {
    const pageParam = searchParams.get('page');
    if (pageParam) {
      const p = parseInt(pageParam, 10);
      if (!isNaN(p) && p >= 1 && p <= totalPages) {
        setCurrentPage(p);
      }
    }
  }, [searchParams, totalPages]);

  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage((p) => p - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage((p) => p + 1);
  };

  const handleZoomIn = () => {
    setZoomScale((z) => Math.min(z + 25, 200));
  };

  const handleZoomOut = () => {
    setZoomScale((z) => Math.max(z - 25, 50));
  };

  const handleResetZoom = () => {
    setZoomScale(100);
  };

  const handleJumpToPage = (pageNum: number) => {
    setCurrentPage(pageNum);
    pageContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCopyFingerprint = () => {
    navigator.clipboard.writeText(`sha256-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`);
    setHasCopiedHash(true);
    setTimeout(() => setHasCopiedHash(false), 2000);
  };

  const renderSimulatedPageContent = (page: number) => {
    const pageChunks = loadedChunks.filter(
      (c) => c.page_number === page || c.page === page || c.chunk_index + 1 === page
    );

    const isFinDoc = doc.name.toLowerCase().includes('10q') || doc.name.toLowerCase().includes('financial') || doc.name.toLowerCase().includes('treasury');
    const isTechDoc = doc.name.toLowerCase().includes('k8s') || doc.name.toLowerCase().includes('failover') || doc.name.toLowerCase().includes('sharding');
    const hasEvidence = docCitations.some((c) => c.pageNumber === page);
    const evidenceItem = docCitations.find((c) => c.pageNumber === page);

    if (pageChunks.length > 0) {
      return (
        <div className="space-y-6 text-enterprise-text leading-relaxed font-sans select-text">
          <div className="pb-3 border-b border-surface-border flex items-center justify-between text-xs text-enterprise-dim font-mono">
            <span>{doc.name}</span>
            <span>PAGE {page} OF {totalPages}</span>
          </div>

          {hasEvidence && evidenceItem && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-2xl border-2 border-primary/40 bg-primary/5 text-enterprise-text text-xs shadow-subtle space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-primary flex items-center gap-1.5 font-mono text-[11px]">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  Cited Evidence in Active Query
                </span>
                <span className="font-mono text-[11px] text-primary font-bold">
                  {(evidenceItem.relevanceScore * 100).toFixed(0)}% Match
                </span>
              </div>
              <p className="font-medium italic bg-white dark:bg-surface-elevated p-3 rounded-xl border border-primary/20 shadow-sm">
                "{evidenceItem.snippet}"
              </p>
            </motion.div>
          )}

          <div className="space-y-4">
            {pageChunks.map((chunk, i) => (
              <div key={chunk.chunk_id || i} className="p-4 rounded-xl bg-surface-muted/30 border border-surface-border/60 space-y-2">
                {chunk.section_context && (
                  <h3 className="text-sm font-semibold text-primary font-mono tracking-tight">
                    {chunk.section_context}
                  </h3>
                )}
                <p className="text-sm text-enterprise-text leading-relaxed whitespace-pre-wrap font-sans">
                  {chunk.content || chunk.content_preview}
                </p>
              </div>
            ))}
          </div>

          <div className="pt-6 border-t border-surface-border text-center text-xs text-enterprise-dim font-mono">
            CONFIDENTIAL — ENTERPRISE VERIFIED DOCUMENT
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-6 text-enterprise-text leading-relaxed font-sans select-text">
        <div className="pb-3 border-b border-surface-border flex items-center justify-between text-xs text-enterprise-dim font-mono">
          <span>{doc.name}</span>
          <span>PAGE {page} OF {totalPages}</span>
        </div>

        {hasEvidence && evidenceItem && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            className="p-4 rounded-2xl border-2 border-primary/40 bg-primary/5 text-enterprise-text text-xs shadow-subtle space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-primary flex items-center gap-1.5 font-mono text-[11px]">
                <ShieldCheck className="h-3.5 w-3.5" />
                Cited Evidence in Active Query
              </span>
              <span className="font-mono text-[11px] text-primary font-bold">
                {(evidenceItem.relevanceScore * 100).toFixed(0)}% Match
              </span>
            </div>
            <p className="font-medium italic bg-white dark:bg-surface-elevated p-3 rounded-xl border border-primary/20 shadow-sm">
              "{evidenceItem.snippet}"
            </p>
          </motion.div>
        )}

        <h2 className="text-xl font-bold text-enterprise-text tracking-tight">
          {doc.name} — Page {page}
        </h2>

        <div className="p-4 rounded-xl bg-surface-muted/30 border border-surface-border text-sm text-enterprise-text leading-relaxed whitespace-pre-wrap">
          {doc.summary || `Extracted and indexed page ${page} of ${doc.name}. Content verified for grounded retrieval.`}
        </div>

        <div className="pt-6 border-t border-surface-border text-center text-xs text-enterprise-dim font-mono">
          CONFIDENTIAL — ENTERPRISE VERIFIED DOCUMENT
        </div>
      </div>
    );
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col bg-background overflow-hidden">
      {/* Top Toolbar */}
      <div className="h-12 border-b border-surface-border px-4 flex items-center justify-between bg-surface/90 backdrop-blur shrink-0 z-30">
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/workspace">
            <Button size="sm" variant="ghost" className="h-8 gap-1.5 text-xs text-enterprise-muted hover:text-enterprise-text font-medium">
              <ArrowLeft className="h-4 w-4" />
              <span>Back</span>
            </Button>
          </Link>

          <div className="h-4 w-[1px] bg-surface-border hidden sm:block" />

          <div className="flex items-center gap-2.5 truncate">
            <FileText className="h-4 w-4 text-primary shrink-0" />
            <span className="text-sm font-semibold text-enterprise-text truncate max-w-xs sm:max-w-md">
              {doc.name}
            </span>
          </div>
        </div>

        {/* Page navigation */}
        <div className="flex items-center gap-2 bg-surface-muted/60 border border-surface-border rounded-xl px-2.5 py-1">
          <button
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            className="p-1 rounded text-enterprise-muted hover:text-enterprise-text disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-xs font-mono font-semibold">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
            className="p-1 rounded text-enterprise-muted hover:text-enterprise-text disabled:opacity-30"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {/* Zoom & Sidebar */}
        <div className="flex items-center gap-2.5">
          <div className="hidden sm:flex items-center gap-1.5 bg-surface-muted/60 border border-surface-border rounded-xl px-2 py-1 text-xs font-mono">
            <button onClick={handleZoomOut} disabled={zoomScale <= 50} className="p-0.5 text-enterprise-muted hover:text-enterprise-text">
              <ZoomOut className="h-3.5 w-3.5" />
            </button>
            <button onClick={handleResetZoom} className="px-1 text-xs font-semibold">
              {zoomScale}%
            </button>
            <button onClick={handleZoomIn} disabled={zoomScale >= 200} className="p-0.5 text-enterprise-muted hover:text-enterprise-text">
              <ZoomIn className="h-3.5 w-3.5" />
            </button>
          </div>

          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={`p-2 rounded-xl border text-xs transition-colors ${
              isSidebarOpen
                ? 'border-primary/40 bg-primary/10 text-primary'
                : 'border-surface-border bg-surface text-enterprise-muted hover:text-enterprise-text'
            }`}
          >
            <Info className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Canvas Area */}
      <div className="flex-1 flex overflow-hidden">
        <div
          ref={pageContainerRef}
          className="flex-1 overflow-y-auto p-6 sm:p-10 flex flex-col items-center justify-start bg-background/50 relative"
        >
          {/* Paper Canvas Sheet */}
          <motion.div
            animate={{ scale: zoomScale / 100 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="w-full max-w-3xl bg-white dark:bg-surface-elevated border border-surface-border rounded-2xl shadow-paper p-8 sm:p-12 my-2"
            style={{ transformOrigin: 'top center' }}
          >
            {renderSimulatedPageContent(currentPage)}
          </motion.div>
        </div>

        {/* Sidebar */}
        <AnimatePresence>
          {isSidebarOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 320, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ type: 'spring', damping: 28, stiffness: 350 }}
              className="border-l border-surface-border bg-surface shrink-0 flex flex-col justify-between overflow-hidden z-20"
            >
              <div className="p-4 space-y-4 flex-1 overflow-y-auto">
                <div className="flex items-center justify-between pb-2 border-b border-surface-border">
                  <span className="text-xs font-semibold text-enterprise-text tracking-tight flex items-center gap-1.5">
                    <BookOpen className="h-3.5 w-3.5 text-primary" />
                    Document Evidence
                  </span>
                  <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                    v{doc.version || '1.0'}
                  </Badge>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] font-semibold text-enterprise-dim uppercase tracking-wider font-mono">
                    Summary
                  </span>
                  <p className="text-xs text-enterprise-muted bg-surface-muted/60 p-3 rounded-xl border border-surface-border leading-relaxed">
                    {doc.summary || 'Indexed for grounded queries.'}
                  </p>
                </div>

                {/* Citations on this doc */}
                <div className="space-y-2">
                  <span className="text-[10px] font-semibold text-enterprise-dim uppercase tracking-wider font-mono block">
                    Citations ({docCitations.length})
                  </span>
                  <div className="space-y-1.5">
                    {docCitations.map((cit) => (
                      <div
                        key={cit.id}
                        onClick={() => handleJumpToPage(cit.pageNumber)}
                        className={`p-2.5 rounded-xl border text-xs cursor-pointer transition-colors ${
                          cit.pageNumber === currentPage
                            ? 'border-primary/50 bg-primary/5 text-primary'
                            : 'border-surface-border bg-surface-elevated text-enterprise-muted hover:border-surface-border-hover'
                        }`}
                      >
                        <div className="flex items-center justify-between font-medium text-[11px] mb-1">
                          <span>Page {cit.pageNumber}</span>
                          <span className="font-mono">{(cit.relevanceScore * 100).toFixed(0)}% Match</span>
                        </div>
                        <p className="text-[11px] italic line-clamp-2 text-enterprise-text">"{cit.snippet}"</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Tech spec */}
                <div className="space-y-1 pt-2 border-t border-surface-border text-xs text-enterprise-dim font-mono">
                  <div className="flex justify-between">
                    <span>Format</span>
                    <span className="uppercase text-enterprise-text">{doc.format}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Size</span>
                    <span className="text-enterprise-text">{formatBytes(doc.sizeBytes)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Uploaded</span>
                    <span className="text-enterprise-text">{formatDate(doc.uploadedAt)}</span>
                  </div>
                </div>
              </div>

              <div className="p-3 border-t border-surface-border">
                <button
                  onClick={handleCopyFingerprint}
                  className="w-full p-2 rounded-xl bg-surface-muted border border-surface-border text-[10px] font-mono text-enterprise-dim hover:text-primary transition-colors flex items-center justify-between"
                >
                  <span className="truncate mr-1">sha256:e3b0c442...991b</span>
                  <span className="text-primary font-bold">{hasCopiedHash ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};
