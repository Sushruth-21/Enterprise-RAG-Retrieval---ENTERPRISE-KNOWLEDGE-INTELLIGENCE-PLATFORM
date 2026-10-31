import { Workspace, DocumentItem, ChatMessage, Citation } from '@/types';

export const INITIAL_WORKSPACES: Workspace[] = [
  {
    id: 'default',
    name: 'Enterprise Knowledge Base',
    description: 'Production workspace for enterprise documents, reports, and knowledge retrieval.',
    createdAt: '2026-10-31T00:00:00Z',
    updatedAt: '2026-10-31T00:00:00Z',
    documentCount: 0,
    queryCount: 0,
    selectedDocumentIds: [],
  },
];

export const INITIAL_DOCUMENTS: DocumentItem[] = [];

export const INITIAL_CITATIONS: Citation[] = [];

export const INITIAL_MESSAGES: Record<string, ChatMessage[]> = {};
