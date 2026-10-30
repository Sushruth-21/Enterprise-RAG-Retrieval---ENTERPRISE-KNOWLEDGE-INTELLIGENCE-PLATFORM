export type DocumentFormat = 'pdf' | 'docx' | 'txt' | 'md';

export type DocumentProcessingStatus = 'ready' | 'processing' | 'indexing' | 'failed';

export interface DocumentItem {
  id: string;
  workspaceId: string;
  name: string;
  format: DocumentFormat;
  sizeBytes: number;
  uploadedAt: string;
  status: DocumentProcessingStatus;
  pageCount?: number;
  chunksCount?: number;
  summary?: string;
  version: string;
}

export interface Workspace {
  id: string;
  name: string;
  description: string;
  createdAt: string;
  updatedAt: string;
  documentCount: number;
  queryCount: number;
  selectedDocumentIds: string[];
}

export interface Citation {
  id: string;
  documentId: string;
  documentName: string;
  pageNumber: number;
  chunkId?: string;
  snippet: string;
  relevanceScore: number; // 0.0 - 1.0
  highlightArea?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export type AnswerCoverage = 'full' | 'partial' | 'insufficient_evidence';

export interface ChatMessage {
  id: string;
  workspaceId: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: Citation[];
  coverage?: AnswerCoverage;
  isStreaming?: boolean;
  groundedDocCount?: number;
  executionTimeMs?: number;
}

export interface BatchQueryItem {
  id: string;
  question: string;
  status: 'idle' | 'processing' | 'completed' | 'failed';
  answer?: string;
  coverage?: AnswerCoverage;
  citations?: Citation[];
  error?: string;
}

export interface UserSettings {
  theme: 'dark';
  streamingSpeed: 'fast' | 'normal' | 'instant';
  groundingStrictness: 'strict' | 'balanced';
  apiBaseUrl: string;
  useMockApi: boolean;
  reducedMotion: boolean;
}

export type EmployeeRole = 'employee' | 'analyst' | 'manager' | 'compliance_officer';
export type EmployeeStatus = 'active' | 'suspended';

export interface Employee {
  id: string;
  name: string;
  email: string;
  department: string;
  role: EmployeeRole;
  status: EmployeeStatus;
  assignedWorkspaces: string[];
  createdAt: string;
}

export type PolicyCategory =
  | 'Information Security'
  | 'Data Privacy & GDPR'
  | 'Financial & SEC'
  | 'HR & Code of Conduct'
  | 'Engineering & Operations';

export interface PolicyDocument {
  id: string;
  title: string;
  category: PolicyCategory;
  version: string;
  department: string;
  summary: string;
  content: string;
  effectiveDate: string;
  status: 'published' | 'draft' | 'under_review';
  updatedAt: string;
}
