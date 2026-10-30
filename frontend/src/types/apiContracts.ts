/**
 * FastApi Schema Definition Contracts
 * These interfaces define the expected shape of the FastAPI endpoints
 * developed by the independent backend team.
 */

export type ApiCoverageClassification = 'full' | 'partial' | 'insufficient_evidence';

export interface ApiHealthResponse {
  status: 'ok' | 'degraded';
  version: string;
  vectorDbStatus: 'connected' | 'indexing' | 'offline';
  modelGroundingStrictness: 'enforced';
}

export interface ApiWorkspaceSummary {
  id: string;
  name: string;
  description: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface ApiWorkspaceCreateRequest {
  name: string;
  description?: string;
}

export interface ApiDocumentUploadResponse {
  id: string;
  workspace_id: string;
  filename: string;
  format: 'pdf' | 'docx' | 'txt' | 'md';
  size_bytes: number;
  status: 'ready' | 'processing' | 'failed';
  page_count: number;
  chunk_count: number;
  sha256_hash: string;
}

export interface ApiCitation {
  id: string;
  document_id: string;
  document_name: string;
  page_number: number;
  chunk_id: string;
  snippet: string;
  relevance_score: number;
  vector_distance: number;
}

export interface ApiQueryRequest {
  workspace_id: string;
  question: string;
  selected_document_ids?: string[];
  strict_grounding?: boolean;
}

export interface ApiQueryResponse {
  query_id: string;
  answer: string;
  coverage: ApiCoverageClassification;
  citations: ApiCitation[];
  grounded_document_count: number;
  execution_latency_ms: number;
  reasoning_summary?: string;
}

export interface ApiBatchQueryRequest {
  workspace_id: string;
  questions: string[];
  selected_document_ids?: string[];
}

export interface ApiBatchQueryItemResult {
  id: string;
  question: string;
  status: 'completed' | 'insufficient_evidence' | 'failed';
  answer: string;
  coverage: ApiCoverageClassification;
  citations: ApiCitation[];
  latency_ms: number;
}

export interface ApiBatchQueryResponse {
  batch_id: string;
  workspace_id: string;
  total_questions: number;
  completed_count: number;
  results: ApiBatchQueryItemResult[];
  summary: {
    full_coverage_count: number;
    partial_coverage_count: number;
    insufficient_evidence_count: number;
    avg_latency_ms: number;
  };
}
