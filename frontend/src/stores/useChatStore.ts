import { create } from 'zustand';
import { ChatMessage, Citation } from '@/types';

interface ChatState {
  messages: Record<string, ChatMessage[]>; // workspaceId -> messages
  activeCitation: Citation | null;
  isEvidencePanelOpen: boolean;
  isStreaming: boolean;
  currentQuery: string;

  // Actions
  setMessages: (workspaceId: string, messages: ChatMessage[]) => void;
  addMessage: (workspaceId: string, message: ChatMessage) => void;
  updateLastMessage: (workspaceId: string, patch: Partial<ChatMessage>) => void;
  clearMessages: (workspaceId: string) => void;
  setActiveCitation: (citation: Citation | null) => void;
  toggleEvidencePanel: () => void;
  setEvidencePanelOpen: (open: boolean) => void;
  setIsStreaming: (streaming: boolean) => void;
  setCurrentQuery: (query: string) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: {},
  activeCitation: null,
  isEvidencePanelOpen: true,
  isStreaming: false,
  currentQuery: '',

  setMessages: (workspaceId, messages) =>
    set((state) => ({
      messages: { ...state.messages, [workspaceId]: messages },
    })),

  addMessage: (workspaceId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [workspaceId]: [...(state.messages[workspaceId] || []), message],
      },
    })),

  updateLastMessage: (workspaceId, patch) =>
    set((state) => {
      const currentList = state.messages[workspaceId] || [];
      if (currentList.length === 0) return state;
      const updated = [...currentList];
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        ...patch,
      };
      return {
        messages: {
          ...state.messages,
          [workspaceId]: updated,
        },
      };
    }),

  clearMessages: (workspaceId) =>
    set((state) => ({
      messages: { ...state.messages, [workspaceId]: [] },
    })),

  setActiveCitation: (citation) =>
    set({
      activeCitation: citation,
      isEvidencePanelOpen: citation ? true : false,
    }),

  toggleEvidencePanel: () =>
    set((state) => ({ isEvidencePanelOpen: !state.isEvidencePanelOpen })),

  setEvidencePanelOpen: (open) => set({ isEvidencePanelOpen: open }),
  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setCurrentQuery: (currentQuery) => set({ currentQuery }),
}));
