import { apiClient } from './api';
import { ApiBatchQueryResponse, ApiBatchQueryItemResult } from '@/types/apiContracts';
import { DocumentItem } from '@/types';

export const batchService = {
  async executeBatchQueries(
    workspaceId: string,
    questions: string[],
    activeDocs: DocumentItem[],
    onProgress?: (completed: number, total: number, currentItem?: ApiBatchQueryItemResult) => void
  ): Promise<ApiBatchQueryResponse> {
    try {
      // POST /api/batch
      const res = await apiClient.post<ApiBatchQueryResponse>('/api/batch', {
        workspace_id: workspaceId || 'default',
        questions,
        document_ids: activeDocs.map((d) => d.id),
      });
      return res.data;
    } catch {
      // Process queries sequentially through /api/chat
      const results: ApiBatchQueryItemResult[] = [];

      for (let i = 0; i < questions.length; i++) {
        const q = questions[i].trim();
        if (!q) continue;

        try {
          const chatRes = await apiClient.post('/api/chat', {
            question: q,
            message: q,
            query: q,
            workspace_id: workspaceId || 'default',
            document_ids: activeDocs.map((d) => d.id),
          });

          const itemResult: ApiBatchQueryItemResult = {
            id: `batch-item-${Date.now()}-${i}`,
            question: q,
            status: chatRes.data.status === 'not_covered' ? 'insufficient_evidence' : 'completed',
            coverage: chatRes.data.coverage || (chatRes.data.citations?.length > 0 ? 'full' : 'insufficient_evidence'),
            answer: chatRes.data.answer || chatRes.data.response || 'No response generated.',
            citations: chatRes.data.citations || [],
            latency_ms: chatRes.data.latency_ms || 250,
          };

          results.push(itemResult);
          if (onProgress) {
            onProgress(i + 1, questions.length, itemResult);
          }
        } catch (err: any) {
          const errorResult: ApiBatchQueryItemResult = {
            id: `batch-item-${Date.now()}-${i}`,
            question: q,
            status: 'failed',
            coverage: 'insufficient_evidence',
            answer: `Failed to evaluate query against backend: ${err.message || 'connection error'}`,
            citations: [],
            latency_ms: 100,
          };
          results.push(errorResult);
          if (onProgress) {
            onProgress(i + 1, questions.length, errorResult);
          }
        }
      }

      const fullCount = results.filter((r) => r.coverage === 'full').length;
      const partialCount = results.filter((r) => r.coverage === 'partial').length;
      const insufficientCount = results.filter((r) => r.coverage === 'insufficient_evidence').length;
      const avgLatency = Math.round(
        results.reduce((acc, r) => acc + r.latency_ms, 0) / (results.length || 1)
      );

      return {
        batch_id: `batch-exec-${Date.now()}`,
        workspace_id: workspaceId || 'default',
        total_questions: questions.length,
        completed_count: results.length,
        results,
        summary: {
          full_coverage_count: fullCount,
          partial_coverage_count: partialCount,
          insufficient_evidence_count: insufficientCount,
          avg_latency_ms: avgLatency,
        },
      };
    }
  },

  exportBatchResultsAsJSON(response: ApiBatchQueryResponse) {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(response, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `Batch_Query_Evaluation_${response.batch_id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  },
};
