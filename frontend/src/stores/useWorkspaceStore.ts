import { create } from 'zustand';
import { Workspace, DocumentItem } from '@/types';
import { useAuthStore } from './useAuthStore';
import { sanitizeText } from '@/lib/security';
import { INITIAL_WORKSPACES } from '@/mocks/initialData';

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  documents: DocumentItem[];
  searchQuery: string;
  isLoading: boolean;
  
  // Actions
  setWorkspaces: (workspaces: Workspace[]) => void;
  setActiveWorkspaceId: (id: string | null) => void;
  setDocuments: (docs: DocumentItem[]) => void;
  setSearchQuery: (query: string) => void;
  createWorkspace: (name: string, description: string) => Workspace | null;
  deleteWorkspace: (id: string) => boolean;
  toggleDocumentSelection: (docId: string) => void;
  selectDocumentRange: (docIds: string[]) => void;
  selectAllDocuments: (docIds: string[]) => void;
  deselectAllDocuments: () => void;
  addDocument: (doc: DocumentItem) => boolean;
  removeDocument: (docId: string) => boolean;
  updateDocumentScope: (docId: string, scope: 'public' | 'confidential') => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: INITIAL_WORKSPACES,
  activeWorkspaceId: 'default',
  documents: [],
  searchQuery: '',
  isLoading: false,

  setWorkspaces: (workspaces) => set({ workspaces }),
  setActiveWorkspaceId: (id) => set({ activeWorkspaceId: id }),
  setDocuments: (documents) => {
    set((state) => {
      const allDocIds = documents.map((d) => d.id);
      const targetWsId = state.activeWorkspaceId || state.workspaces[0]?.id || 'default';
      const updatedWorkspaces = state.workspaces.map((w) => {
        if (!w.selectedDocumentIds || w.selectedDocumentIds.length === 0) {
          return {
            ...w,
            documentCount: documents.length,
            selectedDocumentIds: allDocIds,
          };
        }
        return {
          ...w,
          documentCount: documents.length,
        };
      });

      return {
        documents,
        workspaces: updatedWorkspaces.length > 0 ? updatedWorkspaces : [
          {
            ...INITIAL_WORKSPACES[0],
            documentCount: documents.length,
            selectedDocumentIds: allDocIds,
          },
        ],
        activeWorkspaceId: targetWsId,
      };
    });
  },
  setSearchQuery: (searchQuery) => set({ searchQuery: sanitizeText(searchQuery) }),

  createWorkspace: (name, description) => {
    // Strict RBAC Guard: Only administrator can create workspaces
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return null;
    }

    const cleanName = sanitizeText(name);
    const cleanDesc = sanitizeText(description);

    const newWs: Workspace = {
      id: `ws-${Date.now()}`,
      name: cleanName,
      description: cleanDesc,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      documentCount: 0,
      queryCount: 0,
      selectedDocumentIds: [],
    };
    set((state) => ({
      workspaces: [newWs, ...state.workspaces],
      activeWorkspaceId: newWs.id,
    }));
    return newWs;
  },

  deleteWorkspace: (id) => {
    // Strict RBAC Guard: Only administrator can delete workspaces
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      workspaces: state.workspaces.filter((w) => w.id !== id),
      activeWorkspaceId:
        state.activeWorkspaceId === id
          ? state.workspaces.find((w) => w.id !== id)?.id || null
          : state.activeWorkspaceId,
    }));
    return true;
  },

  toggleDocumentSelection: (docId) => {
    const { activeWorkspaceId, workspaces } = get();
    const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

    set({
      workspaces: workspaces.map((w) => {
        if (w.id !== targetWsId) return w;
        const currentSelected = w.selectedDocumentIds || [];
        const exists = currentSelected.includes(docId);
        return {
          ...w,
          selectedDocumentIds: exists
            ? currentSelected.filter((id) => id !== docId)
            : [...currentSelected, docId],
        };
      }),
    });
  },

  selectDocumentRange: (docIds) => {
    const { activeWorkspaceId, workspaces } = get();
    const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

    set({
      workspaces: workspaces.map((w) => {
        if (w.id !== targetWsId) return w;
        const currentSelected = w.selectedDocumentIds || [];
        const combined = Array.from(new Set([...currentSelected, ...docIds]));
        return {
          ...w,
          selectedDocumentIds: combined,
        };
      }),
    });
  },

  selectAllDocuments: (docIds) => {
    const { activeWorkspaceId, workspaces } = get();
    const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

    set({
      workspaces: workspaces.map((w) =>
        w.id === targetWsId ? { ...w, selectedDocumentIds: docIds } : w
      ),
    });
  },

  deselectAllDocuments: () => {
    const { activeWorkspaceId, workspaces } = get();
    const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

    set({
      workspaces: workspaces.map((w) =>
        w.id === targetWsId ? { ...w, selectedDocumentIds: [] } : w
      ),
    });
  },

  addDocument: (doc) => {
    // Strict RBAC Guard: Only administrator can add / upload documents
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => {
      const targetWsId = doc.workspaceId || state.activeWorkspaceId || 'default';
      return {
        documents: [doc, ...state.documents],
        workspaces: state.workspaces.map((w) =>
          w.id === targetWsId || (!w.id && targetWsId === 'default')
            ? {
                ...w,
                documentCount: w.documentCount + 1,
                selectedDocumentIds: Array.from(
                  new Set([...(w.selectedDocumentIds || []), doc.id])
                ),
              }
            : w
        ),
      };
    });
    return true;
  },

  removeDocument: (docId) => {
    // Strict RBAC Guard: Only administrator can delete documents
    if (!useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      documents: state.documents.filter((d) => d.id !== docId),
      workspaces: state.workspaces.map((w) => ({
        ...w,
        documentCount: Math.max(0, w.documentCount - 1),
        selectedDocumentIds: w.selectedDocumentIds.filter((id) => id !== docId),
      })),
    }));
    return true;
  },

  updateDocumentScope: (docId, scope) => {
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === docId
          ? {
              ...d,
              accessScope: scope,
              isEmployeeAccessible: scope === 'public',
            }
          : d
      ),
    }));
  },
}));
