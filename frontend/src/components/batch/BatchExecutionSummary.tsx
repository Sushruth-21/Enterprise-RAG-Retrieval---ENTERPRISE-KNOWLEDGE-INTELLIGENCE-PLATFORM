import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, AlertTriangle, HelpCircle, Clock, Download } from 'lucide-react';
import { ApiBatchQueryResponse } from '@/types/apiContracts';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { batchService } from '@/services/batchService';

interface BatchExecutionSummaryProps {
  summaryData: ApiBatchQueryResponse;
}

export const BatchExecutionSummary: React.FC<BatchExecutionSummaryProps> = ({ summaryData }) => {
  const { summary, total_questions } = summaryData;

  const fullPercent = Math.round((summary.full_coverage_count / total_questions) * 100) || 0;
  const partialPercent = Math.round((summary.partial_coverage_count / total_questions) * 100) || 0;
  const insufficientPercent = Math.round((summary.insufficient_evidence_count / total_questions) * 100) || 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-5 rounded-2xl border border-surface-border bg-surface shadow-subtle space-y-4"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-surface-border">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-primary font-semibold">
            Suite Completed
          </span>
          <h2 className="text-base font-semibold text-enterprise-text tracking-tight">Coverage Telemetry</h2>
        </div>

        <Button
          size="sm"
          variant="secondary"
          onClick={() => batchService.exportBatchResultsAsJSON(summaryData)}
          className="gap-1.5 text-xs"
        >
          <Download className="h-3 w-3 text-primary" />
          <span>Export JSON</span>
        </Button>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/50">
          <div className="flex items-center justify-between text-xs text-emerald-800 mb-1 font-medium">
            <span>Full Evidence</span>
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-emerald-950">
            {summary.full_coverage_count}{' '}
            <span className="text-xs font-normal text-emerald-700 font-mono">({fullPercent}%)</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/50">
          <div className="flex items-center justify-between text-xs text-amber-800 mb-1 font-medium">
            <span>Partial Evidence</span>
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
          </div>
          <div className="text-xl font-bold text-amber-950">
            {summary.partial_coverage_count}{' '}
            <span className="text-xs font-normal text-amber-700 font-mono">({partialPercent}%)</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50/50">
          <div className="flex items-center justify-between text-xs text-rose-800 mb-1 font-medium">
            <span>Insufficient</span>
            <HelpCircle className="h-3.5 w-3.5 text-rose-600" />
          </div>
          <div className="text-xl font-bold text-rose-950">
            {summary.insufficient_evidence_count}{' '}
            <span className="text-xs font-normal text-rose-700 font-mono">({insufficientPercent}%)</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl border border-surface-border bg-surface-elevated">
          <div className="flex items-center justify-between text-xs text-enterprise-muted mb-1 font-medium">
            <span>Avg Speed</span>
            <Clock className="h-3.5 w-3.5 text-primary" />
          </div>
          <div className="text-xl font-bold text-enterprise-text font-mono">{summary.avg_latency_ms}ms</div>
        </div>
      </div>
    </motion.div>
  );
};
