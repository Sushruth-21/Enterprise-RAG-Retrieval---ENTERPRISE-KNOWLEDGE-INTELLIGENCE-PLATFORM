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
      const res = await apiClient.get<any>('/api/documents', {
        params: workspaceId ? { workspace_id: workspaceId, as_list: true } : { as_list: true },
        headers: { 'x-frontend': 'true' },
      });
      const rawList = Array.isArray(res.data) ? res.data : (res.data?.documents || []);
      return rawList.map((d: any) => {
        const id = d.id || d.document_id || '';
        const name = d.name || d.document_name || 'Document';
        const rawDate = d.uploadedAt || d.uploaded_at;
        let validDate = new Date().toISOString();
        if (rawDate) {
          try {
            const parsed = new Date(rawDate);
            if (!isNaN(parsed.getTime())) {
              validDate = parsed.toISOString();
            }
          } catch {}
        }
        const scope = d.accessScope || d.access_scope || 'public';
        return {
          id,
          workspaceId: d.workspaceId || d.workspace_id || 'default',
          name,
          format: (d.format || d.doc_type || 'pdf').toLowerCase() as any,
          sizeBytes: Number(d.sizeBytes || d.size_bytes || 0),
          uploadedAt: validDate,
          status: 'ready' as any,
          pageCount: Number(d.pageCount || d.page_count || 1),
          chunksCount: Number(d.chunksCount || d.chunkCount || d.section_count || 0),
          summary: d.summary || d.description || '',
          version: String(d.version || '1.0'),
          accessScope: scope as any,
          isEmployeeAccessible: d.isEmployeeAccessible ?? (scope === 'public'),
        };
      });
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
      const res = await apiClient.post<any>('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(percent);
          }
        },
      });

      const raw = res.data || {};
      const uploadedDoc: DocumentItem = {
        id: raw.id || raw.document_id || `doc_${Date.now()}`,
        workspaceId: raw.workspaceId || raw.workspace_id || workspaceId || 'default',
        name: raw.name || raw.document_name || safeName,
        format: (raw.format || 'pdf').toLowerCase() as any,
        sizeBytes: Number(raw.sizeBytes || file.size || 0),
        uploadedAt: raw.uploadedAt || new Date().toISOString(),
        status: 'ready',
        pageCount: Number(raw.pageCount || 1),
        chunksCount: Number(raw.chunkCount || raw.chunksCount || 0),
        summary: raw.summary || raw.description || '',
        version: String(raw.version || raw.version_id || '1.0'),
        accessScope: isEmployeeAccessible ? 'public' : 'confidential',
        isEmployeeAccessible: isEmployeeAccessible,
      };
      return uploadedDoc;
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

  // DELETE /api/chat/{conversation_id} - Clear backend conversation history
  async clearChatHistory(conversationId: string): Promise<void> {
    try {
      await apiClient.delete(`/api/chat/${conversationId}`);
    } catch (err) {
      console.warn('Failed to clear conversation history:', err);
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
