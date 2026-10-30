import React from 'react';
import { motion } from 'framer-motion';
import { Database, Files, ShieldCheck, Cpu, HardDrive } from 'lucide-react';
import { Workspace, DocumentItem } from '@/types';
import { formatBytes } from '@/lib/utils';

interface WorkspaceStatsProps {
  workspaces: Workspace[];
  documents: DocumentItem[];
}

export const WorkspaceStats: React.FC<WorkspaceStatsProps> = ({ workspaces, documents }) => {
  const totalSizeBytes = documents.reduce((acc, doc) => acc + doc.sizeBytes, 0);
  const totalChunks = documents.reduce((acc, doc) => acc + (doc.chunksCount || 0), 0);
  const totalPages = documents.reduce((acc, doc) => acc + (doc.pageCount || 0), 0);

  const formatCounts = documents.reduce(
    (acc, doc) => {
      acc[doc.format] = (acc[doc.format] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Workspaces */}
      <motion.div
        whileHover={{ y: -2 }}
        className="p-5 rounded-xl border border-surface-border bg-surface/70 backdrop-blur shadow-sm hover:border-primary/40 transition-all"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-enterprise-muted uppercase tracking-wider">
            Workspaces
          </span>
          <div className="h-8 w-8 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
            <Database className="h-4 w-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-white tracking-tight">{workspaces.length}</div>
        <p className="text-[11px] text-enterprise-dim mt-1.5 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Isolated knowledge containers
        </p>
      </motion.div>

      {/* Indexed Documents */}
      <motion.div
        whileHover={{ y: -2 }}
        className="p-5 rounded-xl border border-surface-border bg-surface/70 backdrop-blur shadow-sm hover:border-primary/40 transition-all"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-enterprise-muted uppercase tracking-wider">
            Indexed Files
          </span>
          <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Files className="h-4 w-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-white tracking-tight">{documents.length}</div>
        <div className="text-[11px] text-enterprise-dim mt-1.5 flex items-center gap-2 font-mono">
          <span>{formatBytes(totalSizeBytes)}</span>
          <span>•</span>
          <span>{totalPages} pages</span>
        </div>
      </motion.div>

      {/* Semantic Chunks */}
      <motion.div
        whileHover={{ y: -2 }}
        className="p-5 rounded-xl border border-surface-border bg-surface/70 backdrop-blur shadow-sm hover:border-primary/40 transition-all"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-enterprise-muted uppercase tracking-wider">
            Indexed Chunks
          </span>
          <div className="h-8 w-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Cpu className="h-4 w-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-white tracking-tight">{totalChunks}</div>
        <p className="text-[11px] text-enterprise-dim mt-1.5">
          Searchable lexical & vector passages
        </p>
      </motion.div>

      {/* Grounding Compliance */}
      <motion.div
        whileHover={{ y: -2 }}
        className="p-5 rounded-xl border border-surface-border bg-surface/70 backdrop-blur shadow-sm hover:border-primary/40 transition-all"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-enterprise-muted uppercase tracking-wider">
            Grounding Isolation
          </span>
          <div className="h-8 w-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <ShieldCheck className="h-4 w-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-emerald-400 tracking-tight">100% Strict</div>
        <p className="text-[11px] text-enterprise-dim mt-1.5">
          Zero external web retrieval
        </p>
      </motion.div>
    </div>
  );
};
