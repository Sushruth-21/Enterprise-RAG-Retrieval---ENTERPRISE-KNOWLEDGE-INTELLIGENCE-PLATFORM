import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText,
  FileCode,
  FileSpreadsheet,
  Check,
  Trash2,
  ExternalLink,
  ChevronDown,
  Lock,
  Users,
} from 'lucide-react';
import { workspaceService } from '@/services/api';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { DocumentItem, DocumentFormat } from '@/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatBytes, formatDate } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { useAuthStore } from '@/stores/useAuthStore';

interface DocumentCardProps {
  document: DocumentItem;
  isSelected: boolean;
  onToggleSelect: (e: React.MouseEvent) => void;
  onRemove: (id: string) => void;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  isSelected,
  onToggleSelect,
  onRemove,
}) => {
  const { isAdmin } = useAuthStore();
  const isAdministrator = isAdmin();
  const [isExpanded, setIsExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <motion.div
      layout
      whileHover={{ y: -2, transition: { duration: 0.15 } }}
      className={`rounded-2xl border bg-surface-elevated transition-all p-4 flex flex-col justify-between ${
        isSelected
          ? 'border-primary ring-1 ring-primary/40 shadow-subtle'
          : 'border-surface-border hover:border-surface-border-hover'
      }`}
    >
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5 min-w-0">
            {/* Interactive Toggle Checkbox with Spring Micro-interaction & Shift-Select Support */}
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={(e) => onToggleSelect(e)}
              className={`mt-0.5 h-6 w-6 rounded-lg border flex items-center justify-center transition-colors shrink-0 ${
                isSelected
                  ? 'bg-primary border-primary text-white shadow-sm'
                  : 'bg-surface-muted border-surface-border hover:border-primary/50'
              }`}
              title={isSelected ? 'Shift+Click to range select • Click to exclude' : 'Shift+Click to range select • Click to include'}
            >
              <AnimatePresence>
                {isSelected && (
                  <motion.div
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0, opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  >
                    <Check className="h-4 w-4 stroke-[3]" />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.button>

            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`font-semibold text-sm sm:text-base truncate tracking-tight ${
                  isSelected ? 'text-enterprise-text font-bold' : 'text-enterprise-text'
                }`}>
                  {document.name}
                </span>
                <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-surface-muted text-enterprise-text font-medium">
                  {document.format}
                </span>
                {document.accessScope === 'confidential' ? (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 font-bold border border-amber-500/30 flex items-center gap-1">
                    <Lock className="h-2.5 w-2.5" /> Admin Only
                  </span>
                ) : (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
                    <Users className="h-2.5 w-2.5" /> Employee Accessible
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-xs text-enterprise-muted mt-1 font-mono">
                <span>{formatBytes(document.sizeBytes)}</span>
                <span>•</span>
                {document.pageCount && <span>{document.pageCount} pages</span>}
              </div>
            </div>
          </div>

          <Badge variant={isSelected ? 'default' : 'outline'} size="sm" className="font-mono text-xs shrink-0 font-medium">
            {document.status === 'ready' ? 'Indexed' : 'Processing'}
          </Badge>
        </div>

        {document.summary && (
          <div className="mt-3 text-sm text-enterprise-text/85 bg-surface-muted/60 rounded-xl p-3 leading-relaxed border border-surface-border/40">
            <p className={isExpanded ? '' : 'line-clamp-2'}>{document.summary}</p>
            {document.summary.length > 100 && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-primary text-xs font-semibold hover:underline mt-1.5 flex items-center gap-1"
              >
                <span>{isExpanded ? 'Less' : 'More'}</span>
                <ChevronDown className={`h-3 w-3 ${isExpanded ? 'rotate-180' : ''}`} />
              </button>
            )}
          </div>
        )}
      </div>

      <div className="mt-3 pt-2.5 border-t border-surface-border flex items-center justify-between text-xs text-enterprise-muted">
        <span className="text-[11px] font-mono">{formatDate(document.uploadedAt)}</span>

        <div className="flex items-center gap-2.5">
          {isAdministrator && (
            <label
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1.5 cursor-pointer text-xs select-none hover:opacity-90 px-2 py-0.5 rounded-lg bg-surface-muted/90 border border-surface-border transition-colors"
              title={document.accessScope === 'confidential' ? 'Admin Only: Unchecked. Click to allow employee queries.' : 'Employee Accessible: Checked. Click to restrict to Admin Only.'}
            >
              <input
                type="checkbox"
                checked={document.accessScope !== 'confidential'}
                onChange={async (e) => {
                  const newScope = e.target.checked ? 'public' : 'confidential';
                  try {
                    await workspaceService.updateDocumentScope(document.id, newScope);
                    useWorkspaceStore.getState().updateDocumentScope(document.id, newScope);
                  } catch (err) {
                    console.error('Failed to update scope:', err);
                  }
                }}
                className="h-3.5 w-3.5 rounded border-surface-border text-primary focus:ring-primary accent-primary cursor-pointer"
              />
              <span className="text-[11px] font-medium text-enterprise-text flex items-center gap-1">
                {document.accessScope === 'confidential' ? (
                  <span className="text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
                    <Lock className="h-2.5 w-2.5" /> Admin Only
                  </span>
                ) : (
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                    <Users className="h-2.5 w-2.5" /> Accessible to Employees
                  </span>
                )}
              </span>
            </label>
          )}

          <Link to={`/document/${document.id}`}>
            <Button size="sm" variant="ghost" className="h-6 text-xs gap-1 text-primary hover:text-primary-hover font-semibold">
              <span>Canvas</span>
              <ExternalLink className="h-3 w-3" />
            </Button>
          </Link>

          {isAdministrator && (
            confirmDelete ? (
              <div className="flex items-center gap-1.5 text-xs bg-rose-500/10 px-2 py-0.5 rounded-lg border border-rose-500/20">
                <span className="text-rose-600 dark:text-rose-400 font-medium">Delete?</span>
                <button onClick={() => onRemove(document.id)} className="text-rose-700 dark:text-rose-300 font-bold hover:underline px-1">
                  Yes
                </button>
                <button onClick={() => setConfirmDelete(false)} className="text-enterprise-muted hover:text-enterprise-text px-1">
                  No
                </button>
              </div>
            ) : (
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={() => setConfirmDelete(true)}
                className="p-1 rounded text-enterprise-muted hover:text-red-600 transition-colors"
                title="Delete document (Admin)"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </motion.button>
            )
          )}
        </div>
      </div>
    </motion.div>
  );
};
