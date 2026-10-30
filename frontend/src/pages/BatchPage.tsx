import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileSpreadsheet,
  Play,
  Sparkles,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { batchService } from '@/services/batchService';
import { ApiBatchQueryResponse, ApiCoverageClassification } from '@/types/apiContracts';
import { Button } from '@/components/ui/Button';
import { BatchExecutionSummary } from '@/components/batch/BatchExecutionSummary';
import { BatchQuestionRow } from '@/components/batch/BatchQuestionRow';

const TEMPLATES = [
  {
    name: 'Q3 Financial & SEC Audit',
    questions: [
      'What was the consolidated net revenue in Q3 2024?',
      'How does our cash runway compare to current operational burn?',
      'What was the gross profit margin improvement?',
      'What was the total company travel expense in Singapore?',
    ],
  },
  {
    name: 'K8s Cloud Architecture Evaluation',
    questions: [
      'What is the automated DNS failover threshold for cluster loss?',
      'How does the state replication quorum handle dirty writes?',
      'What is our disaster recovery RTO and RPO target?',
      'What brand of server racks are deployed in Iceland?',
    ],
  },
  {
    name: 'GDPR Compliance & Data Retention',
    questions: [
      'What processing activities are documented under GDPR Article 30?',
      'What is the review schedule for sub-processor data agreements?',
      'What is our policy on quantum cryptographic export licenses?',
    ],
  },
];

export const BatchPage: React.FC = () => {
  const { workspaces, activeWorkspaceId, documents } = useWorkspaceStore();
  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];
  const workspaceDocs = documents.filter((d) => d.workspaceId === activeWorkspace?.id);
  const activeDocs = workspaceDocs.filter((d) =>
    activeWorkspace?.selectedDocumentIds.includes(d.id)
  );

  const [questionsText, setQuestionsText] = useState(
    TEMPLATES[0].questions.join('\n')
  );
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [batchResponse, setBatchResponse] = useState<ApiBatchQueryResponse | null>(null);
  const [filterCoverage, setFilterCoverage] = useState<'all' | ApiCoverageClassification>('all');

  const questionList = questionsText
    .split('\n')
    .map((q) => q.trim())
    .filter((q) => q.length > 0);

  const handleExecuteBatch = async () => {
    if (questionList.length === 0 || isRunning) return;

    setIsRunning(true);
    setProgress({ current: 0, total: questionList.length });
    setBatchResponse(null);

    try {
      const response = await batchService.executeBatchQueries(
        activeWorkspace?.id || 'ws-fin-2024',
        questionList,
        activeDocs,
        (current, total) => {
          setProgress({ current, total });
        }
      );
      setBatchResponse(response);
    } finally {
      setIsRunning(false);
    }
  };

  const handleApplyTemplate = (questions: string[]) => {
    setQuestionsText(questions.join('\n'));
    setBatchResponse(null);
  };

  const filteredResults = batchResponse?.results.filter((item) => {
    if (filterCoverage === 'all') return true;
    return item.coverage === filterCoverage;
  });

  return (
    <div className="p-6 sm:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-border">
        <div>
          <h1 className="text-2xl sm:text-3xl font-semibold text-enterprise-text tracking-tight">
            Batch Question Suite
          </h1>
          <p className="text-sm text-enterprise-muted mt-1 max-w-xl leading-relaxed">
            Evaluate multiple queries simultaneously against active documents in {activeWorkspace?.name}.
          </p>
        </div>

        <Button
          onClick={handleExecuteBatch}
          disabled={questionList.length === 0 || isRunning || activeDocs.length === 0}
          isLoading={isRunning}
          size="md"
          className="gap-2.5 text-sm font-semibold"
        >
          <Play className="h-4 w-4 fill-current" />
          <span>Execute Suite ({questionList.length}q)</span>
        </Button>
      </div>

      {/* Editor & Scope Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3.5">
          <div className="flex items-center justify-between text-sm font-semibold text-enterprise-text">
            <span>Questions (one per line)</span>
            <span className="text-enterprise-dim font-mono text-xs">{questionList.length} queued</span>
          </div>

          <div className="rounded-2xl border border-surface-border bg-surface-elevated overflow-hidden shadow-subtle focus-within:border-primary/50">
            <textarea
              rows={7}
              value={questionsText}
              onChange={(e) => setQuestionsText(e.target.value)}
              disabled={isRunning}
              placeholder="Enter enterprise questions..."
              className="w-full bg-transparent p-4 text-sm font-mono text-enterprise-text placeholder-enterprise-dim focus:outline-none resize-none leading-relaxed"
            />
          </div>

          {/* Presets with Spring Micro-interaction */}
          <div className="flex flex-wrap items-center gap-2.5 pt-1">
            <span className="text-xs font-semibold text-enterprise-dim mr-1">Templates:</span>
            {TEMPLATES.map((tmpl) => (
              <motion.button
                key={tmpl.name}
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => handleApplyTemplate(tmpl.questions)}
                disabled={isRunning}
                className="px-3.5 py-1.5 rounded-xl border border-surface-border bg-surface text-sm font-medium text-enterprise-text hover:border-primary/50 hover:bg-primary/10 transition-colors shadow-subtle"
              >
                {tmpl.name}
              </motion.button>
            ))}
          </div>
        </div>

        {/* Scope */}
        <div className="space-y-3.5">
          <span className="text-sm font-semibold text-enterprise-text block">
            Target Documents ({activeDocs.length})
          </span>

          <div className="p-4 rounded-2xl border border-surface-border bg-surface space-y-3 shadow-subtle">
            <div className="text-sm font-semibold text-enterprise-text border-b border-surface-border pb-2.5">
              {activeWorkspace?.name}
            </div>

            <div className="space-y-2 max-h-48 overflow-y-auto pr-1 text-sm">
              {activeDocs.map((doc) => (
                <div key={doc.id} className="p-2.5 rounded-xl bg-surface-muted/70 text-enterprise-text text-xs font-medium truncate flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-primary shrink-0" />
                  <span className="truncate">{doc.name}</span>
                </div>
              ))}
              {activeDocs.length === 0 && (
                <div className="text-enterprise-dim text-xs py-2 text-center">
                  No active documents selected.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Progress */}
      {isRunning && (
        <div className="p-4 rounded-2xl border border-primary/30 bg-primary/5 space-y-2">
          <div className="flex items-center justify-between text-xs text-primary font-semibold">
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 animate-spin" />
              Evaluating question {progress.current} of {progress.total}...
            </span>
            <span className="font-mono">{Math.round((progress.current / progress.total) * 100)}%</span>
          </div>
          <div className="w-full h-1.5 rounded-full bg-surface-muted overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Results */}
      {batchResponse && (
        <div className="space-y-5 pt-2">
          <BatchExecutionSummary summaryData={batchResponse} />

          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-enterprise-text">Results ({filteredResults?.length})</span>

              {/* High-Contrast Interactive Filter Tabs */}
              <div className="flex items-center gap-1 bg-surface-muted p-1 rounded-xl border border-surface-border">
                {(['all', 'full', 'partial', 'insufficient_evidence'] as const).map((c) => {
                  const isActive = filterCoverage === c;
                  return (
                    <motion.button
                      key={c}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setFilterCoverage(c)}
                      className={`px-3 py-1 rounded-lg text-xs capitalize transition-all ${
                        isActive
                          ? 'bg-neutral-900 text-white dark:bg-primary dark:text-white font-bold shadow-sm'
                          : 'text-enterprise-text/70 hover:text-enterprise-text hover:bg-surface-elevated font-medium'
                      }`}
                    >
                      {c.replace('_', ' ')}
                    </motion.button>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              {filteredResults?.map((item, index) => (
                <BatchQuestionRow key={item.id} item={item} index={index} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
