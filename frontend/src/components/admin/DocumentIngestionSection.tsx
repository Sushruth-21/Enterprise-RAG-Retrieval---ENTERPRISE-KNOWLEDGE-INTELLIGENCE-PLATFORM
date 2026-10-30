import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  UploadCloud,
  FolderOpen,
  FileText,
  CheckCircle2,
  Clock,
  Layers,
  ShieldCheck,
  FileSpreadsheet,
} from 'lucide-react';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';
import { workspaceService } from '@/services/api';
import { DocumentUploadDropzone } from '@/components/documents/DocumentUploadDropzone';
import { formatBytes } from '@/lib/utils';

export const DocumentIngestionSection: React.FC = () => {
  const { workspaces, activeWorkspaceId, setActiveWorkspaceId, documents, addDocument } =
    useWorkspaceStore();

  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStep, setProcessingStep] = useState('');
  const [recentUploads, setRecentUploads] = useState<string[]>([]);

  const activeWorkspace =
    workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];

  const handleFileUpload = async (file: File) => {
    if (!activeWorkspace) return;

    setIsUploading(true);
    setUploadProgress(15);
    setProcessingStep('Validating file layout & text...');

    try {
      setTimeout(() => {
        setUploadProgress(45);
        setProcessingStep('Extracting semantic text chunks...');
      }, 350);

      setTimeout(() => {
        setUploadProgress(80);
        setProcessingStep('Generating vector embeddings...');
      }, 700);

      const newDoc = await workspaceService.uploadDocument(
        activeWorkspace.id,
        file,
        (percent) => {
          setUploadProgress(Math.max(percent, 85));
        }
      );

      setTimeout(() => {
        setUploadProgress(100);
        setProcessingStep('Indexed & partition-isolated.');
        addDocument(newDoc);
        setRecentUploads((prev) => [newDoc.id, ...prev]);
        setIsUploading(false);
        setUploadProgress(0);
      }, 1000);
    } catch (err) {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const workspaceDocs = documents.filter((d) => d.workspaceId === activeWorkspace?.id);

  return (
    <div className="p-6 rounded-2xl border border-surface-border bg-surface-elevated space-y-6 shadow-subtle">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3.5 pb-4 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
            <UploadCloud className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-enterprise-text">Document Ingestion & Vault Indexing</h3>
            <p className="text-xs text-enterprise-muted mt-0.5">
              Administrative gateway to upload, chunk, and index official documents into enterprise knowledge partitions.
            </p>
          </div>
        </div>

        {/* Target Workspace Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-enterprise-muted">Target Partition:</span>
          <select
            value={activeWorkspace?.id || ''}
            onChange={(e) => setActiveWorkspaceId(e.target.value)}
            className="bg-surface-muted border border-surface-border rounded-xl px-3 py-1.5 text-xs font-semibold text-enterprise-text focus:outline-none focus:border-primary"
          >
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id} className="bg-surface-elevated text-enterprise-text">
                {ws.name} ({ws.documentCount} docs)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Upload Dropzone */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs font-semibold text-enterprise-text">
          <span>Ingest Files into: <span className="text-primary font-bold">{activeWorkspace?.name}</span></span>
          <span className="text-enterprise-dim font-mono text-[11px]">PDF, DOCX, TXT, MD up to 50MB</span>
        </div>

        <DocumentUploadDropzone
          onUpload={handleFileUpload}
          isUploading={isUploading}
          uploadProgress={uploadProgress}
          currentProcessingStep={processingStep}
        />
      </div>

      {/* Partition Current Documents Preview */}
      <div className="space-y-3 pt-2 border-t border-surface-border">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-enterprise-text uppercase tracking-wider font-mono">
            Currently Indexed in this Partition ({workspaceDocs.length})
          </span>
          <span className="text-xs text-enterprise-dim font-mono">
            Partition ID: {activeWorkspace?.id}
          </span>
        </div>

        <div className="divide-y divide-surface-border/60 border border-surface-border rounded-xl overflow-hidden bg-surface max-h-60 overflow-y-auto">
          {workspaceDocs.map((doc) => {
            const isJustAdded = recentUploads.includes(doc.id);
            return (
              <div
                key={doc.id}
                className={`p-3 flex items-center justify-between gap-3 text-xs transition-colors ${
                  isJustAdded ? 'bg-primary/15' : 'hover:bg-surface-muted/60'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <FileText className="h-4 w-4 text-primary shrink-0" />
                  <span className="font-semibold text-enterprise-text truncate">
                    {doc.name}
                  </span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-surface-muted text-enterprise-text font-bold border border-surface-border/50">
                    {doc.format}
                  </span>
                  {isJustAdded && (
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                      Just Ingested
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3 text-enterprise-muted font-mono shrink-0 text-[11px]">
                  <span>{formatBytes(doc.sizeBytes)}</span>
                  <span>•</span>
                  <span>{doc.pageCount || 1}p</span>
                </div>
              </div>
            );
          })}

          {workspaceDocs.length === 0 && (
            <div className="p-8 text-center text-xs text-enterprise-muted">
              No documents currently indexed in this partition. Use the dropzone above to ingest files.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
