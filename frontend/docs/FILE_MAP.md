# Enterprise Query — Complete File Map

This document records the architectural structure of the project, detailing file locations and their core responsibilities.

```
EnterpriseQuery/
├── docs/
│   ├── REFERENCE_ANALYSIS.md     # Reference repos analysis & motion design strategy
│   ├── PROJECT_STATUS.md         # Real-time progress, stages, dependencies, and audit status
│   ├── FILE_MAP.md               # File structure and responsibility ledger
│   └── DECISIONS.md              # Architectural and design decision records (ADRs)
├── public/
│   └── assets/
│       └── logo.svg              # Enterprise Query platform vector logo
├── src/
│   ├── app/
│   │   └── App.tsx               # Code-split routing, Suspense fallback, MotionConfig
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.tsx     # Enterprise header with grounding badge & switcher
│   │   │   ├── AppSidebar.tsx    # Collapsible animated sidebar navigation
│   │   │   └── AppLayout.tsx     # Main container shell
│   │   ├── dashboard/
│   │   │   ├── WorkspaceStats.tsx# Animated KPI counters (workspaces, files, chunks, grounding)
│   │   │   └── RecentActivityFeed.tsx # Real-time knowledge audit trail
│   │   ├── documents/
│   │   │   ├── DocumentUploadDropzone.tsx # Drag-and-drop upload with multi-step progress bar
│   │   │   └── DocumentCard.tsx  # Document cards with format badges, selection & deletion
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx # 3-panel grounded workspace query shell
│   │   │   ├── MessageItem.tsx   # Answer renderer with citation pills & coverage badges
│   │   │   ├── MessageComposer.tsx# Input composer with suggested queries carousel
│   │   │   └── TypingIndicator.tsx# Subtle wave typing indicator
│   │   ├── citations/
│   │   │   └── EvidenceInspector.tsx # Collapsible panel displaying verified excerpt & score
│   │   ├── batch/
│   │   │   ├── BatchExecutionSummary.tsx # Coverage telemetry and distribution breakdown
│   │   │   └── BatchQuestionRow.tsx # Expandable question row with citations & latency
│   │   └── ui/
│   │       ├── Button.tsx        # Spring physics button with loading state
│   │       ├── Badge.tsx         # Enterprise status and evidence compliance badges
│   │       └── Modal.tsx         # Animated modal with keyboard accessibility
│   ├── pages/
│   │   ├── DashboardPage.tsx     # Workspace overview, metrics, search & creation
│   │   ├── WorkspacePage.tsx     # Ingestion, document selection & query readiness
│   │   ├── ChatPage.tsx          # 3-panel grounded enterprise chat
│   │   ├── BatchPage.tsx         # Multi-question batch processing suite
│   │   ├── DocumentViewerPage.tsx# Document inspection and PDF canvas with deep linking
│   │   ├── SettingsPage.tsx      # Grounding strictness, health check & backend settings
│   │   └── NotFoundPage.tsx      # 404 handler
│   ├── services/
│   │   ├── api.ts                # Axios client with fallback mock simulation layer
│   │   └── batchService.ts       # Batch query execution & JSON audit exporter
│   ├── stores/
│   │   ├── useWorkspaceStore.ts  # Workspace and document selection state
│   │   ├── useChatStore.ts       # Chat messages, citations, evidence panel state
│   │   └── useSettingsStore.ts   # System settings and grounding configuration
│   ├── types/
│   │   ├── index.ts              # Domain interfaces (Workspace, DocumentItem, ChatMessage, Citation)
│   │   └── apiContracts.ts       # Formal FastAPI request & response schemas
│   ├── mocks/
│   │   └── initialData.ts        # Realistic seed datasets for offline development
│   ├── lib/
│   │   └── utils.ts              # cn helper, formatBytes, formatDate
│   └── styles/
│       └── index.css             # Tailwind layers, dark scrollbar, reduced motion query
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```
