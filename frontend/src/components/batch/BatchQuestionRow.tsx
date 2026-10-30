import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDown,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  FileText,
  ExternalLink,
} from 'lucide-react';
import { ApiBatchQueryItemResult, ApiCoverageClassification } from '@/types/apiContracts';
import { Badge } from '@/components/ui/Badge';
import { Link } from 'react-router-dom';

interface BatchQuestionRowProps {
  item: ApiBatchQueryItemResult;
  index: number;
}

export const BatchQuestionRow: React.FC<BatchQuestionRowProps> = ({ item, index }) => {
  const [isExpanded, setIsExpanded] = useState(index === 0);

  const getCoverageBadge = (coverage: ApiCoverageClassification) => {
    switch (coverage) {
      case 'full':
        return (
          <span className="text-xs font-mono text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full flex items-center gap-1.5 font-semibold">
            <ShieldCheck className="h-3.5 w-3.5" /> Full
          </span>
        );
      case 'partial':
        return (
          <span className="text-xs font-mono text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1 rounded-full flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="h-3.5 w-3.5" /> Partial
          </span>
        );
      case 'insufficient_evidence':
        return (
          <span className="text-xs font-mono text-rose-700 bg-rose-50 border border-rose-200 px-2.5 py-1 rounded-full flex items-center gap-1.5 font-semibold">
            <HelpCircle className="h-3.5 w-3.5" /> Insufficient
          </span>
        );
    }
  };

  return (
    <div className="rounded-2xl border border-surface-border bg-surface-elevated transition-colors shadow-subtle overflow-hidden">
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="p-4 flex items-start justify-between gap-3.5 cursor-pointer select-none"
      >
        <div className="flex items-start gap-3 min-w-0">
          <span className="h-6 px-2 rounded-lg bg-surface-muted text-primary text-xs font-mono font-bold flex items-center justify-center shrink-0">
            Q{index + 1}
          </span>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-enterprise-text tracking-tight leading-snug">
              {item.question}
            </h4>
            {!isExpanded && (
              <p className="text-xs text-enterprise-muted mt-1 truncate max-w-xl">
                {item.answer}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {getCoverageBadge(item.coverage)}
          <span className="text-xs font-mono text-enterprise-dim hidden sm:inline-block">
            {item.latency_ms}ms
          </span>
          <ChevronDown
            className={`h-4 w-4 text-enterprise-muted transition-transform ${
              isExpanded ? 'rotate-180 text-primary' : ''
            }`}
          />
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="px-4 pb-4 border-t border-surface-border pt-3 space-y-3"
          >
            <div className="p-3.5 rounded-xl bg-surface-muted/50 border border-surface-border text-sm leading-relaxed text-enterprise-text">
              <p className="whitespace-pre-wrap">{item.answer}</p>
            </div>

            {item.citations && item.citations.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-mono uppercase text-enterprise-dim block">
                  Citations:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {item.citations.map((cit) => (
                    <div
                      key={cit.id}
                      className="p-2 rounded-xl border border-surface-border bg-surface text-xs flex items-start justify-between gap-2"
                    >
                      <div className="min-w-0 flex-1">
                        <span className="font-medium text-[11px] truncate block text-enterprise-text">
                          {cit.document_name} <span className="text-primary font-mono font-normal">p.{cit.page_number}</span>
                        </span>
                        <p className="text-[10px] text-enterprise-muted italic truncate">"{cit.snippet}"</p>
                      </div>
                      <Link
                        to={`/document/${cit.document_id}?page=${cit.page_number}`}
                        className="text-primary hover:text-enterprise-text p-1 shrink-0"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
