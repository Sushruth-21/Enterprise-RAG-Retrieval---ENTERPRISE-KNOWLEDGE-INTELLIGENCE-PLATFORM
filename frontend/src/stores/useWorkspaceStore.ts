import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { Workspace, DocumentItem } from '@/types';
import { useAuthStore } from './useAuthStore';
import { sanitizeText } from '@/lib/security';
import { INITIAL_WORKSPACES } from '@/mocks/initialData';

interface WorkspaceState {
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  documents: DocumentItem[];
  hasInitializedSelection: Record<string, boolean>;
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

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      workspaces: INITIAL_WORKSPACES,
      activeWorkspaceId: 'default',
      documents: [],
      hasInitializedSelection: {},
      searchQuery: '',
      isLoading: false,

      setWorkspaces: (workspaces) => set({ workspaces }),
      setActiveWorkspaceId: (id) => set({ activeWorkspaceId: id }),

      setDocuments: (documents) => {
        set((state) => {
          const allDocIds = documents.map((d) => d.id);
          const validDocIdSet = new Set(allDocIds);
          const targetWsId = state.activeWorkspaceId || state.workspaces[0]?.id || 'default';
          const nextInitMap = { ...(state.hasInitializedSelection || {}) };

          const updatedWorkspaces = state.workspaces.map((w) => {
            const isInit = nextInitMap[w.id];

            // 1. If this workspace selection was never initialized, select all documents by default
            if (!isInit) {
              nextInitMap[w.id] = true;
              return {
                ...w,
                documentCount: documents.length,
                selectedDocumentIds: allDocIds,
              };
            }

            // 2. Already initialized: preserve user's explicit selections/deselections, prune any deleted docs
            const currentSelected = w.selectedDocumentIds || [];
            const preserved = currentSelected.filter((id) => validDocIdSet.has(id));

            return {
              ...w,
              documentCount: documents.length,
              selectedDocumentIds: preserved,
            };
          });

          return {
            documents,
            hasInitializedSelection: nextInitMap,
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
          hasInitializedSelection: {
            ...state.hasInitializedSelection,
            [newWs.id]: true,
          },
        }));
        return newWs;
      },

      deleteWorkspace: (id) => {
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

        set((state) => {
          const currentWs = state.workspaces.find((w) => w.id === targetWsId) || state.workspaces[0];
          const currentSelected = currentWs?.selectedDocumentIds || [];
          const exists = currentSelected.includes(docId);
          const nextSelected = exists
            ? currentSelected.filter((id) => id !== docId)
            : [...currentSelected, docId];

          return {
            hasInitializedSelection: {
              ...(state.hasInitializedSelection || {}),
              [targetWsId]: true,
            },
            workspaces: state.workspaces.map((w) =>
              w.id === targetWsId ? { ...w, selectedDocumentIds: nextSelected } : w
            ),
          };
        });
      },

      selectDocumentRange: (docIds) => {
        const { activeWorkspaceId, workspaces } = get();
        const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

        set((state) => {
          const currentWs = state.workspaces.find((w) => w.id === targetWsId) || state.workspaces[0];
          const currentSelected = currentWs?.selectedDocumentIds || [];
          const combined = Array.from(new Set([...currentSelected, ...docIds]));

          return {
            hasInitializedSelection: {
              ...(state.hasInitializedSelection || {}),
              [targetWsId]: true,
            },
            workspaces: state.workspaces.map((w) =>
              w.id === targetWsId ? { ...w, selectedDocumentIds: combined } : w
            ),
          };
        });
      },

      selectAllDocuments: (docIds) => {
        const { activeWorkspaceId, workspaces } = get();
        const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

        set((state) => ({
          hasInitializedSelection: {
            ...(state.hasInitializedSelection || {}),
            [targetWsId]: true,
          },
          workspaces: state.workspaces.map((w) =>
            w.id === targetWsId ? { ...w, selectedDocumentIds: docIds } : w
          ),
        }));
      },

      deselectAllDocuments: () => {
        const { activeWorkspaceId, workspaces } = get();
        const targetWsId = activeWorkspaceId || workspaces[0]?.id || 'default';

        set((state) => ({
          hasInitializedSelection: {
            ...(state.hasInitializedSelection || {}),
            [targetWsId]: true,
          },
          workspaces: state.workspaces.map((w) =>
            w.id === targetWsId ? { ...w, selectedDocumentIds: [] } : w
          ),
        }));
      },

      addDocument: (doc) => {
        if (!useAuthStore.getState().isAdmin()) {
          useAuthStore.getState().openAdminModal();
          return false;
        }

        set((state) => {
          const targetWsId = doc.workspaceId || state.activeWorkspaceId || 'default';
          const existingDocIndex = state.documents.findIndex((d) => d.id === doc.id);
          const nextDocs = existingDocIndex >= 0
            ? state.documents.map((d, idx) => (idx === existingDocIndex ? doc : d))
            : [doc, ...state.documents];

          return {
            documents: nextDocs,
            hasInitializedSelection: {
              ...(state.hasInitializedSelection || {}),
              [targetWsId]: true,
            },
            workspaces: state.workspaces.map((w) =>
              w.id === targetWsId || (!w.id && targetWsId === 'default')
                ? {
                    ...w,
                    documentCount: nextDocs.length,
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
        if (!useAuthStore.getState().isAdmin()) {
          useAuthStore.getState().openAdminModal();
          return false;
        }

        set((state) => {
          const nextDocs = state.documents.filter((d) => d.id !== docId);
          return {
            documents: nextDocs,
            workspaces: state.workspaces.map((w) => ({
              ...w,
              documentCount: Math.max(0, w.documentCount - 1),
              selectedDocumentIds: (w.selectedDocumentIds || []).filter((id) => id !== docId),
            })),
          };
        });
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
    }),
    {
      name: 'eq_workspace_storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        workspaces: state.workspaces,
        activeWorkspaceId: state.activeWorkspaceId,
        documents: state.documents,
        hasInitializedSelection: state.hasInitializedSelection,
      }),
    }
  )
);
