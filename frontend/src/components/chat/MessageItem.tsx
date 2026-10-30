import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Copy,
  Check,
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  FileText,
} from 'lucide-react';
import { ChatMessage, Citation, AnswerCoverage } from '@/types';
import { formatDate } from '@/lib/utils';

interface MessageItemProps {
  message: ChatMessage;
  onSelectCitation: (citation: Citation) => void;
  activeCitationId?: string;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onSelectCitation,
  activeCitationId,
}) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getCoverageIndicator = (coverage?: AnswerCoverage) => {
    switch (coverage) {
      case 'full':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs font-mono text-emerald-600 font-semibold">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            Grounded
          </span>
        );
      case 'partial':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs font-mono text-amber-600 font-semibold">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            Partial Evidence
          </span>
        );
      case 'insufficient_evidence':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs font-mono text-rose-600 font-semibold">
            <span className="h-2 w-2 rounded-full bg-rose-500" />
            Insufficient Evidence
          </span>
        );
      default:
        return null;
    }
  };

  // Replace citation markers like [1], [2] in content with clean interactive pills
  const renderMessageContent = (text: string, citations?: Citation[]) => {
    if (!citations || citations.length === 0) {
      return <div className="whitespace-pre-wrap leading-relaxed text-base">{text}</div>;
    }

    const parts = text.split(/(\[\d+\])/g);
    return (
      <div className="whitespace-pre-wrap leading-relaxed text-base">
        {parts.map((part, index) => {
          const match = part.match(/\[(\d+)\]/);
          if (match) {
            const citIndex = parseInt(match[1], 10) - 1;
            const citation = citations[citIndex];
            if (citation) {
              const isActive = activeCitationId === citation.id;
              return (
                <button
                  key={index}
                  onClick={() => onSelectCitation(citation)}
                  title={`${citation.documentName} (Page ${citation.pageNumber})`}
                  className={`inline-flex items-center px-2 py-0.5 mx-1 rounded-md text-xs font-mono font-semibold transition-all ${
                    isActive
                      ? 'bg-primary text-white shadow-sm'
                      : 'bg-surface-elevated text-primary hover:bg-primary/10 border border-primary/30'
                  }`}
                >
                  [{citIndex + 1}]
                </button>
              );
            }
          }
          return <span key={index}>{part}</span>;
        })}
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-3xl mx-auto w-full`}
    >
      {/* Header Info: Role, Status, Timestamp */}
      <div className="flex items-center gap-2 mb-1.5 px-1 text-xs text-enterprise-muted font-mono">
        {isUser ? (
          <>
            <span>{formatDate(message.timestamp)}</span>
            <span className="text-enterprise-text font-semibold">You</span>
          </>
        ) : (
          <>
            <span className="font-semibold text-enterprise-text">Assistant</span>
            {message.coverage && (
              <>
                <span>•</span>
                {getCoverageIndicator(message.coverage)}
              </>
            )}
            {message.executionTimeMs && (
              <>
                <span>•</span>
                <span>{message.executionTimeMs}ms</span>
              </>
            )}
            <span>•</span>
            <span>{formatDate(message.timestamp)}</span>
          </>
        )}
      </div>

      {/* Message Bubble (Minimalist, Apple / Gemini inspired) */}
      <div
        className={`rounded-2xl p-5 text-base transition-all relative group ${
          isUser
            ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white max-w-xl rounded-tr-sm shadow-subtle'
            : 'bg-surface-elevated/80 border border-surface-border text-enterprise-text w-full shadow-subtle'
        }`}
      >
        {/* Insufficient Evidence Notice */}
        {!isUser && message.coverage === 'insufficient_evidence' && (
          <div className="mb-4 p-3.5 rounded-xl border border-rose-500/30 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200 text-sm leading-relaxed space-y-1">
            <div className="flex items-center gap-2 font-semibold text-rose-700 dark:text-rose-400">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>Insufficient Evidence in Uploaded Files</span>
            </div>
            <p className="text-xs text-rose-800 dark:text-rose-300">
              The uploaded documents do not contain facts to substantiate an answer. In accordance with strict enterprise grounding, external assumptions were not made.
            </p>
          </div>
        )}

        {/* Text Content */}
        {renderMessageContent(message.content, message.citations)}

        {/* Citations Footer Chips */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-4 pt-3.5 border-t border-surface-border/60">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-enterprise-dim font-mono mr-1">
                Sources:
              </span>
              {message.citations.map((cit, idx) => {
                const isActive = activeCitationId === cit.id;
                return (
                  <button
                    key={cit.id}
                    onClick={() => onSelectCitation(cit)}
                    className={`text-xs px-3 py-1.5 rounded-xl border transition-all flex items-center gap-2 ${
                      isActive
                        ? 'border-primary bg-primary/10 text-primary font-semibold shadow-sm'
                        : 'border-surface-border bg-surface text-enterprise-text hover:border-primary/50 hover:bg-primary/10'
                    }`}
                  >
                    <span className="font-mono text-primary font-bold">
                      [{idx + 1}]
                    </span>
                    <span className="truncate max-w-[170px] font-medium">
                      {cit.documentName}
                    </span>
                    <span className="text-enterprise-dim font-mono">
                      p.{cit.pageNumber}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Action Toolbar on Hover */}
        {!isUser && (
          <div className="mt-3 pt-2 flex items-center justify-end text-xs text-enterprise-dim">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-enterprise-muted hover:text-enterprise-text hover:bg-surface-muted transition-colors font-medium"
              title="Copy message"
            >
              {copied ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="text-xs text-emerald-600 font-semibold">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5" />
                  <span className="text-xs">Copy</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
};
