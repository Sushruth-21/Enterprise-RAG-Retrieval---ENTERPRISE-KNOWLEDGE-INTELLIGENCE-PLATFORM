import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, X, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { formatBytes } from '@/lib/utils';
import { DocumentFormat } from '@/types';

interface DocumentUploadDropzoneProps {
  onUpload: (file: File) => Promise<void>;
  isUploading?: boolean;
  uploadProgress?: number;
  currentProcessingStep?: string;
}

const ALLOWED_EXTENSIONS: DocumentFormat[] = ['pdf', 'docx', 'txt', 'md'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export const DocumentUploadDropzone: React.FC<DocumentUploadDropzoneProps> = ({
  onUpload,
  isUploading = false,
  uploadProgress = 0,
  currentProcessingStep = 'Indexing document chunks...',
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndStageFile = (file: File) => {
    setError(null);
    const ext = file.name.split('.').pop()?.toLowerCase() as DocumentFormat;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported format ".${ext}". Supported: PDF, DOCX, TXT, Markdown.`);
      return false;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(`File exceeds 50MB limit (${formatBytes(file.size)}).`);
      return false;
    }
    return true;
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validateAndStageFile(file)) {
        await onUpload(file);
      }
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateAndStageFile(file)) {
        await onUpload(file);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`relative rounded-2xl border-2 border-dashed p-6 text-center transition-all cursor-pointer shadow-subtle group ${
          isDragOver || isUploading
            ? 'border-primary bg-primary/10'
            : 'border-surface-border bg-surface-elevated hover:border-primary/60 hover:bg-surface-muted/40'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="hidden"
          onChange={handleFileChange}
          disabled={isUploading}
        />

        {isUploading ? (
          <div className="max-w-md mx-auto py-2 space-y-3">
            <div className="flex items-center justify-between text-xs font-medium text-enterprise-text">
              <span className="flex items-center gap-2 text-primary">
                <Sparkles className="h-4 w-4 animate-spin" />
                {currentProcessingStep}
              </span>
              <span className="font-mono text-primary font-bold">{uploadProgress}%</span>
            </div>

            <div className="w-full h-1.5 rounded-full bg-surface-muted overflow-hidden">
              <motion.div
                className="h-full bg-primary rounded-full"
                animate={{ width: `${uploadProgress}%` }}
                transition={{ ease: 'easeOut', duration: 0.2 }}
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center space-y-2.5">
            <div className="h-10 w-10 rounded-xl bg-surface-muted text-primary flex items-center justify-center group-hover:bg-primary group-hover:text-white transition-colors">
              <UploadCloud className="h-5 w-5" />
            </div>

            <div>
              <p className="text-xs sm:text-sm font-semibold text-enterprise-text tracking-tight">
                Drop your documents here, or{' '}
                <span className="text-primary hover:underline">browse files</span>
              </p>
              <p className="text-[11px] text-enterprise-muted mt-0.5">
                PDF, DOCX, TXT, and Markdown up to 50MB
              </p>
            </div>
          </div>
        )}
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center justify-between p-2.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-700 dark:text-rose-300 text-xs"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-800">
              <X className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
