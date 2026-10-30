import React from 'react';
import { UploadCloud, MessageSquare, PlusCircle, CheckCircle, Clock } from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { Link } from 'react-router-dom';

export interface ActivityItem {
  id: string;
  type: 'upload' | 'query' | 'create_workspace';
  title: string;
  description: string;
  timestamp: string;
  workspaceName: string;
  workspaceId: string;
}

const SAMPLE_ACTIVITIES: ActivityItem[] = [
  {
    id: 'act-1',
    type: 'query',
    title: 'Grounded Query Answered',
    description: '"What was our total net revenue in Q3 2024?" — 2 citations linked',
    timestamp: '2026-10-30T10:15:00Z',
    workspaceName: 'Q3 Financial & SEC Filings',
    workspaceId: 'ws-fin-2024',
  },
  {
    id: 'act-2',
    type: 'upload',
    title: 'New Document Indexed',
    description: 'Q3_2024_Form_10Q_Consolidated.pdf (68 pages, 142 chunks)',
    timestamp: '2026-10-29T15:40:00Z',
    workspaceName: 'Q3 Financial & SEC Filings',
    workspaceId: 'ws-fin-2024',
  },
  {
    id: 'act-3',
    type: 'upload',
    title: 'New Document Indexed',
    description: 'K8s_Multi_Region_Failover_Spec.pdf (35 pages, 84 chunks)',
    timestamp: '2026-10-29T12:20:00Z',
    workspaceName: 'Distributed Cloud Architecture',
    workspaceId: 'ws-eng-arch',
  },
  {
    id: 'act-4',
    type: 'create_workspace',
    title: 'Workspace Initialized',
    description: 'Global Compliance & GDPR Audit created with strict privacy enforcement',
    timestamp: '2026-10-28T09:00:00Z',
    workspaceName: 'Global Compliance & GDPR Audit',
    workspaceId: 'ws-legal-compliance',
  },
];

export const RecentActivityFeed: React.FC = () => {
  const getIcon = (type: ActivityItem['type']) => {
    switch (type) {
      case 'upload':
        return <UploadCloud className="h-3.5 w-3.5 text-primary" />;
      case 'query':
        return <MessageSquare className="h-3.5 w-3.5 text-accent-emerald" />;
      case 'create_workspace':
        return <PlusCircle className="h-3.5 w-3.5 text-accent-purple" />;
    }
  };

  return (
    <div className="rounded-xl border border-surface-border bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-surface-border">
        <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          Recent Knowledge Audit Trail
        </h3>
        <span className="text-[11px] text-enterprise-dim font-mono">Live Session Log</span>
      </div>

      <div className="space-y-3">
        {SAMPLE_ACTIVITIES.map((act) => (
          <div
            key={act.id}
            className="flex items-start gap-3 p-3 rounded-lg bg-surface-elevated/40 border border-surface-border/60 hover:border-surface-border-hover transition-colors"
          >
            <div className="mt-0.5 h-6 w-6 rounded-md bg-surface-muted border border-surface-border flex items-center justify-center shrink-0">
              {getIcon(act.type)}
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
                  to="/workspace"
                  className="text-primary hover:underline truncate"
                >
                  {act.workspaceName}
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
