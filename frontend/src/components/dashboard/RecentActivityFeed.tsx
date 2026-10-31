import React from 'react';
import { UploadCloud, Clock } from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { useWorkspaceStore } from '@/stores/useWorkspaceStore';

export const RecentActivityFeed: React.FC = () => {
  const { documents, workspaces } = useWorkspaceStore();

  const activities = documents.slice(0, 5).map((doc) => {
    const ws = workspaces.find((w) => w.id === doc.workspaceId) || workspaces[0];
    return {
      id: `act-${doc.id}`,
      type: 'upload' as const,
      title: 'Document Indexed & Grounded',
      description: `${doc.name} (${doc.pageCount || 1} pages, ${doc.chunksCount || 0} chunks)`,
      timestamp: doc.uploadedAt,
      workspaceName: ws ? ws.name : 'Enterprise Knowledge Base',
      workspaceId: doc.workspaceId || 'default',
    };
  });

  return (
    <div className="rounded-xl border border-surface-border bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-surface-border">
        <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          Recent Knowledge Audit Trail
        </h3>
        <span className="text-[11px] text-enterprise-dim font-mono">Live Audit Log</span>
      </div>

      <div className="space-y-3">
        {activities.length === 0 ? (
          <div className="py-6 text-center text-xs text-enterprise-muted">
            No recent document activity recorded yet. Upload a document to start indexing.
          </div>
        ) : (
          activities.map((act) => (
            <div
              key={act.id}
              className="flex items-start gap-3 p-3 rounded-lg bg-surface-elevated/40 border border-surface-border/60 hover:border-surface-border-hover transition-colors"
            >
              <div className="mt-0.5 h-6 w-6 rounded-md bg-surface-muted border border-surface-border flex items-center justify-center shrink-0">
                <UploadCloud className="h-3.5 w-3.5 text-primary" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-white truncate">{act.title}</span>
                  <span className="text-[10px] text-enterprise-dim whitespace-nowrap">
                    {formatDate(act.timestamp)}
                  </span>
                </div>
                <p className="text-xs text-enterprise-muted mt-0.5 line-clamp-1">{act.description}</p>
                <div className="mt-1 flex items-center gap-1.5 text-[11px] text-enterprise-dim font-mono">
                  <span>Workspace:</span>
                  <Link
                    to="/documents"
                    className="text-primary hover:underline truncate"
                  >
                    {act.workspaceName}
                  </Link>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
