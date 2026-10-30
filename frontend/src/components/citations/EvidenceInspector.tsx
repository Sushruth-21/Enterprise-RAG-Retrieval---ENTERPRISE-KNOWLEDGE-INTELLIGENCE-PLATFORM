import React from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  ExternalLink,
  ShieldCheck,
  X,
  BookOpen,
} from 'lucide-react';
import { Citation } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Link } from 'react-router-dom';

interface EvidenceInspectorProps {
  citation: Citation | null;
  allCitations?: Citation[];
  onSelectCitation: (cit: Citation) => void;
  onClose: () => void;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({
  citation,
  allCitations = [],
  onSelectCitation,
  onClose,
}) => {
  return (
    <div className="h-full flex flex-col justify-between bg-surface text-enterprise-text border-l border-surface-border">
      {/* Header */}
      <div className="h-14 border-b border-surface-border px-4 flex items-center justify-between shrink-0 bg-surface-muted/40">
        <div className="flex items-center gap-2.5">
          <BookOpen className="h-4.5 w-4.5 text-primary" />
          <span className="text-sm font-semibold text-enterprise-text tracking-tight">Source Evidence</span>
          {citation && (
            <Badge variant="default" size="sm" className="font-mono text-xs">
              Active
            </Badge>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted transition-colors"
          title="Close evidence drawer"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {citation ? (
          <motion.div
            key={citation.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-3.5"
          >
            {/* Document Card Header */}
            <div className="p-4 rounded-2xl border border-surface-border bg-surface-elevated space-y-2.5 shadow-subtle">
              <div className="flex items-start justify-between gap-2.5">
                <span className="text-sm font-semibold text-enterprise-text break-all leading-snug">
                  {citation.documentName}
                </span>
                <Badge variant="outline" size="sm" className="shrink-0 font-mono text-xs font-semibold">
                  p.{citation.pageNumber}
                </Badge>
              </div>

              {/* Relevance Bar */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-enterprise-dim">Relevance Match</span>
                  <span className="text-primary font-bold text-sm">
                    {(citation.relevanceScore * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-surface-muted overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all"
                    style={{ width: `${citation.relevanceScore * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Exact Excerpt */}
            <div className="space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-enterprise-dim flex items-center gap-1.5 font-mono">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                Verified Text Excerpt
              </span>
              <div className="p-3.5 rounded-2xl border border-primary/25 bg-orange-50/40 text-sm text-enterprise-text leading-relaxed">
                <p className="italic font-normal">"{citation.snippet}"</p>
              </div>
            </div>

            {/* Jump to Document Viewer */}
            <Link to={`/document/${citation.documentId}?page=${citation.pageNumber}`} className="block">
              <Button variant="secondary" size="md" className="w-full gap-2 text-sm font-medium">
                <span>Inspect in Document Canvas</span>
                <ExternalLink className="h-4 w-4 text-primary" />
              </Button>
            </Link>
          </motion.div>
        ) : (
          <div className="py-12 text-center space-y-2">
            <div className="h-10 w-10 rounded-xl bg-surface-muted border border-surface-border flex items-center justify-center text-primary mx-auto">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-enterprise-text">No Citation Selected</p>
              <p className="text-xs text-enterprise-muted mt-0.5">
                Click any citation tag like [1] to inspect source text.
              </p>
            </div>
          </div>
        )}

        {/* All Citations in current conversation */}
        {allCitations.length > 0 && (
          <div className="pt-3.5 border-t border-surface-border space-y-2.5">
            <span className="text-xs font-semibold text-enterprise-dim uppercase tracking-wider font-mono block">
              Grounded Citations ({allCitations.length})
            </span>
            <div className="space-y-2">
              {allCitations.map((cit, idx) => (
                <button
                  key={cit.id}
                  onClick={() => onSelectCitation(cit)}
                  className={`w-full text-left p-2.5 rounded-xl border text-sm transition-colors flex items-start gap-2.5 ${
                    citation?.id === cit.id
                      ? 'border-primary/50 bg-primary/10 text-primary font-medium'
                      : 'border-surface-border bg-surface-elevated text-enterprise-muted hover:text-enterprise-text hover:border-surface-border-hover'
                  }`}
                >
                  <span className="h-5 w-5 rounded-md bg-primary/15 text-primary text-xs font-mono flex items-center justify-center shrink-0 font-bold">
                    {idx + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-enterprise-text">{cit.documentName}</p>
                    <p className="text-xs text-enterprise-dim font-mono">p.{cit.pageNumber}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
