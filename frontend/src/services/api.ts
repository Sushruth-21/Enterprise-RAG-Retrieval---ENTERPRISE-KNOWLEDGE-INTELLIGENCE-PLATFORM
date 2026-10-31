import axios from 'axios';
import { Workspace, DocumentItem, ChatMessage, Citation } from '@/types';
import { INITIAL_WORKSPACES } from '@/mocks/initialData';
import { useAuthStore } from '@/stores/useAuthStore';
import { sanitizeFilename, validateQueryInput } from '@/lib/security';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Security Interceptor: Injects Admin Authorization Token when Admin session is active
apiClient.interceptors.request.use((config) => {
  const authState = useAuthStore.getState();
  if (authState.isAdmin()) {
    config.headers['Authorization'] = `Bearer ${authState.adminToken}`;
    config.headers['X-System-Mode'] = 'maintenance-admin';
  } else {
    config.headers['X-System-Mode'] = 'read-only-employee';
  }
  return config;
});

export const workspaceService = {
  // GET /api/health
  async checkHealth(): Promise<{ status: string; latencyMs: number }> {
    const start = performance.now();
    try {
      const res = await apiClient.get('/api/health');
      const latencyMs = Math.round(performance.now() - start);
      return { status: res.data?.status || 'ok', latencyMs };
    } catch {
      const latencyMs = Math.round(performance.now() - start);
      return { status: 'standby', latencyMs };
    }
  },

  // GET /api/documents
  async getDocuments(workspaceId?: string): Promise<DocumentItem[]> {
    try {
      const res = await apiClient.get<DocumentItem[]>('/api/documents', {
        params: workspaceId ? { workspace_id: workspaceId, as_list: true } : { as_list: true },
        headers: { 'x-frontend': 'true' },
      });
      if (Array.isArray(res.data)) {
        return res.data;
      }
      if (res.data && Array.isArray((res.data as any).documents)) {
        return (res.data as any).documents;
      }
      return [];
    } catch (err) {
      console.warn('Failed to fetch documents from backend:', err);
      return [];
    }
  },

  // POST /api/documents/upload - STRICT ADMIN ONLY
  async uploadDocument(
    workspaceId: string,
    file: File,
    isEmployeeAccessible: boolean = true,
    onProgress?: (percent: number) => void
  ): Promise<DocumentItem> {
    // Strict RBAC Guard: Block non-admins from uploading documents
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      throw new Error('Access Denied: Document upload is restricted to Administrative Maintenance Mode.');
    }

    const safeName = sanitizeFilename(file.name);
    const formData = new FormData();
    formData.append('file', file, safeName);
    formData.append('workspace_id', workspaceId || 'default');
    formData.append('document_name', safeName);
    formData.append('is_employee_accessible', String(isEmployeeAccessible));
    formData.append('access_scope', isEmployeeAccessible ? 'public' : 'confidential');

    try {
      const res = await apiClient.post<DocumentItem>('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(percent);
          }
        },
      });
      return res.data;
    } catch (err: any) {
      console.error('Document upload failed on backend:', err);
      const detail = err.response?.data?.detail || err.message || 'Document upload failed';
      throw new Error(detail);
    }
  },

  // POST /api/documents/{documentId}/scope - Admin scope update
  async updateDocumentScope(
    docId: string,
    accessScope: 'public' | 'confidential'
  ): Promise<{ status: string; document_id: string; access_scope: string }> {
    const isEmployeeAccessible = accessScope === 'public';
    const res = await apiClient.post(`/api/documents/${docId}/scope`, {
      access_scope: accessScope,
      is_employee_accessible: isEmployeeAccessible,
    });
    return res.data;
  },

  // POST /api/chat
  async sendChatMessage(payload: {
    message: string;
    workspace_id: string;
    document_ids?: string[];
    conversation_id?: string;
    access_scope?: string;
  }): Promise<{
    answer: string;
    citations?: Citation[];
    coverage?: 'full' | 'partial' | 'insufficient_evidence';
    latency_ms?: number;
    confidence_score?: number;
    status?: string;
  }> {
    // Validate input against injection before dispatch
    const validation = validateQueryInput(payload.message);
    const isAdm = useAuthStore.getState().isAdmin();
    const effectiveScope = payload.access_scope || (isAdm ? 'confidential' : 'public');

    const cleanPayload = {
      ...payload,
      access_scope: effectiveScope,
      question: validation.isValid ? validation.sanitized : payload.message,
      query: validation.isValid ? validation.sanitized : payload.message,
      message: validation.isValid ? validation.sanitized : payload.message,
    };

    const res = await apiClient.post('/api/chat', cleanPayload);
    return res.data;
  },

  // GET /api/chat/{conversation_id}/history
  async getChatHistory(conversationId: string): Promise<ChatMessage[]> {
    try {
      const res = await apiClient.get<ChatMessage[]>(`/api/chat/${conversationId}/history`);
      return res.data;
    } catch {
      return [];
    }
  },

  // POST /api/batch
  async sendBatchQuery(payload: {
    questions: string[];
    workspace_id: string;
    document_ids?: string[];
  }): Promise<any> {
    const res = await apiClient.post('/api/batch', payload);
    return res.data;
  },

  async getWorkspaces(): Promise<Workspace[]> {
    return INITIAL_WORKSPACES;
  },
};
